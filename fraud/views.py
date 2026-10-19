import logging

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FraudEvent, FraudProfile
from .serializers import (
    FraudEventSerializer,
    FraudProfileSerializer,
    FraudProfileSummarySerializer,
    ReviewSerializer,
)

logger = logging.getLogger('sanoa.fraud')


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


# ── Buyer self-service ───────────────────────────────────────────────────────

class MyFraudProfileView(generics.RetrieveAPIView):
    """GET /api/fraud/me/ — buyer's own risk level (transparency only)."""
    serializer_class   = FraudProfileSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = FraudProfile.objects.get_or_create(user=self.request.user)
        return profile


# ── Admin — profiles ─────────────────────────────────────────────────────────

class FraudProfileListView(generics.ListAPIView):
    """
    GET /api/fraud/profiles/

    Query params:
      risk_level  = low | medium | high | critical
      flagged     = true
      reviewed    = false
      subject     = user | vendor
    """
    serializer_class   = FraudProfileSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = FraudProfile.objects.select_related('user', 'vendor').prefetch_related('events')

        p = self.request.query_params
        if p.get('risk_level'):
            qs = qs.filter(risk_level=p['risk_level'])
        if p.get('flagged') == 'true':
            qs = qs.filter(is_flagged=True)
        if p.get('reviewed') == 'false':
            qs = qs.filter(is_reviewed=False, is_flagged=True)
        if p.get('subject') == 'user':
            qs = qs.filter(vendor__isnull=True)
        elif p.get('subject') == 'vendor':
            qs = qs.filter(user__isnull=True)

        return qs.order_by('-risk_score')


class FraudProfileDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/fraud/profiles/<pk>/ — retrieve or review a profile."""
    queryset           = FraudProfile.objects.select_related('user', 'vendor').prefetch_related('events')
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ReviewSerializer
        return FraudProfileSerializer

    def perform_update(self, serializer):
        serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())


# ── Admin — events ───────────────────────────────────────────────────────────

class FraudEventListView(generics.ListAPIView):
    """
    GET /api/fraud/events/

    Query params:
      event_type = rapid_orders | high_refund_rate | ml_anomaly | …
      severity   = low | medium | high | critical
      resolved   = true | false
    """
    serializer_class   = FraudEventSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = FraudEvent.objects.select_related('profile')
        p  = self.request.query_params
        if p.get('event_type'):
            qs = qs.filter(event_type=p['event_type'])
        if p.get('severity'):
            qs = qs.filter(severity=p['severity'])
        if p.get('resolved') == 'false':
            qs = qs.filter(is_resolved=False)
        elif p.get('resolved') == 'true':
            qs = qs.filter(is_resolved=True)
        return qs.order_by('-created_at')


class ResolveEventView(APIView):
    """POST /api/fraud/events/<pk>/action/ — resolve or mark as false positive."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            event = FraudEvent.objects.get(pk=pk)
        except FraudEvent.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action not in ('resolve', 'false_positive'):
            return Response(
                {'detail': 'action must be "resolve" or "false_positive".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event.is_resolved = True
        event.resolved_by = request.user
        event.resolved_at = timezone.now()
        if action == 'false_positive':
            event.is_false_positive = True
        event.save()

        return Response(FraudEventSerializer(event).data)


# ── Admin — on-demand rescoring ───────────────────────────────────────────────

class RescoreUserView(APIView):
    """POST /api/fraud/rescore/user/<user_id>/ — immediately rescore one user."""
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        from django.contrib.auth import get_user_model
        from .engine import score_user

        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        profile = score_user(user)
        return Response(FraudProfileSerializer(profile).data)


class RescoreVendorView(APIView):
    """POST /api/fraud/rescore/vendor/<vendor_id>/ — immediately rescore one vendor."""
    permission_classes = [IsAdminUser]

    def post(self, request, vendor_id):
        from django.apps import apps
        from .engine import score_vendor

        VendorProfile = apps.get_model('business', 'VendorProfile')
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return Response({'detail': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

        profile = score_vendor(vendor)
        return Response(FraudProfileSerializer(profile).data)


# ── Admin — model retraining ──────────────────────────────────────────────────

class TrainModelsView(APIView):
    """POST /api/fraud/train/ — retrain XGBoost models on demand."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from .ml_models import train_all_models
        try:
            train_all_models()
            return Response({'detail': 'Fraud models retrained successfully.'})
        except Exception as exc:
            logger.exception("Model retraining failed: %s", exc)
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

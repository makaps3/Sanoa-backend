"""
Views for the Business Tiers app.
Integrated with Paystack for payment processing.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import BusinessTier, VendorTierSubscription
from .serializers import (
    BusinessTierSerializer,
    VendorTierSubscriptionSerializer,
    VendorTierSubscribeSerializer,
    AdminBusinessTierSerializer,
    AdminVendorTierSubscriptionSerializer,
    AdminVendorTierAssignSerializer,
)
from core.permissions import IsPlatformAdmin

User = get_user_model()


class BusinessTierViewSet(viewsets.ReadOnlyModelViewSet):
    """List available business tiers."""
    queryset = BusinessTier.objects.filter(is_active=True)
    serializer_class = BusinessTierSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def list(self, request, *args, **kwargs):
        """Auto-sync any un-synced paid tiers to Paystack before listing."""
        unsynced = BusinessTier.objects.filter(
            is_active=True, paystack_plan_code__isnull=True
        ).exclude(price=0)
        if unsynced.exists():
            from .serializers import VendorTierSubscribeSerializer
            for tier in unsynced:
                VendorTierSubscribeSerializer._sync_tier_to_paystack(tier)
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='sync-paystack',
            permission_classes=[permissions.IsAuthenticated])
    def sync_paystack(self, request, slug=None):
        """Sync this tier to Paystack (admin only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tier = self.get_object()
        if tier.is_free:
            return Response(
                {'error': 'Free tiers do not need Paystack plans.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .serializers import VendorTierSubscribeSerializer
        tier = VendorTierSubscribeSerializer._sync_tier_to_paystack(tier)

        if tier.paystack_plan_code:
            return Response({
                'message': 'Tier synced to Paystack.',
                'paystack_plan_code': tier.paystack_plan_code,
            })
        return Response(
            {'error': 'Failed to sync tier to Paystack.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class VendorTierSubscriptionViewSet(viewsets.GenericViewSet):
    """Manage vendor tier subscriptions with Paystack payment."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = VendorTierSubscriptionSerializer

    @action(detail=False, methods=['get'], url_path='my-tier')
    def my_tier(self, request):
        """Get the current vendor's tier subscription."""
        try:
            subscription = VendorTierSubscription.objects.select_related('tier').get(
                vendor__user=request.user
            )
            if subscription.is_overdue:
                subscription.expire_and_downgrade()
            serializer = VendorTierSubscriptionSerializer(subscription)
            return Response(serializer.data)
        except VendorTierSubscription.DoesNotExist:
            tiers = BusinessTier.objects.filter(is_active=True)
            return Response({
                'detail': 'No active tier subscription.',
                'available_tiers': BusinessTierSerializer(tiers, many=True).data,
            })

    def retrieve(self, request, pk=None):
        """GET /api/tiers/subscriptions/<id>/ — detail of a single tier
        subscription. Scoped to the requesting vendor, so a vendor can only
        ever view their own subscription (never another vendor's by id)."""
        try:
            subscription = (
                VendorTierSubscription.objects
                .select_related('tier')
                .get(id=pk, vendor__user=request.user)
            )
        except VendorTierSubscription.DoesNotExist:
            return Response(
                {'detail': 'Subscription not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if subscription.is_overdue:
            subscription.expire_and_downgrade()
        return Response(VendorTierSubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """
        Subscribe to a business tier or change tier.
        For paid tiers, returns a Paystack authorization_url.
        Body: {"tier_id": "<uuid>", "callback_url": "<optional>"}
        """
        serializer = VendorTierSubscribeSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()

        response_data = VendorTierSubscriptionSerializer(subscription).data
        paystack_data = serializer.context.get('paystack_data', {})
        if paystack_data:
            response_data['paystack'] = paystack_data

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel the current tier subscription (also disables on Paystack)."""
        try:
            subscription = VendorTierSubscription.objects.get(vendor__user=request.user)
        except VendorTierSubscription.DoesNotExist:
            return Response(
                {'detail': 'No active tier subscription to cancel.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subscription.tier.is_free:
            return Response(
                {'detail': 'Cannot cancel a free tier. Subscribe to a different tier instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from subscriptions.billing import expire_subscription
        expire_subscription(subscription, reason='Subscriber cancelled', force=True, status='cancelled')
        return Response(VendorTierSubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['get'], url_path='manage-card')
    def manage_card(self, request):
        """Get a Paystack link to update the subscription card."""
        try:
            subscription = VendorTierSubscription.objects.get(vendor__user=request.user)
        except VendorTierSubscription.DoesNotExist:
            return Response(
                {'error': 'No active tier subscription found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.paystack_subscription_code:
            return Response(
                {'error': 'No Paystack subscription linked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from payments.paystack import paystack_api
        result = paystack_api.generate_subscription_link(
            subscription.paystack_subscription_code,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to generate link.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'link': result['data'].get('link', '')})


# ═══════════════════════════════════════════════════════════════
# Admin — Vendor Tiers
# ═══════════════════════════════════════════════════════════════

class AdminBusinessTierViewSet(viewsets.ModelViewSet):
    """
    Full CRUD on BusinessTier for platform admins.
    GET    /api/tiers/admin/plans/           — list all (incl. inactive)
    POST   /api/tiers/admin/plans/           — create tier
    GET    /api/tiers/admin/plans/<id>/      — retrieve
    PUT    /api/tiers/admin/plans/<id>/      — full update
    PATCH  /api/tiers/admin/plans/<id>/      — partial update
    DELETE /api/tiers/admin/plans/<id>/      — delete
    POST   /api/tiers/admin/plans/<id>/toggle-active/   — toggle is_active
    POST   /api/tiers/admin/plans/<id>/sync-paystack/   — sync to Paystack
    """
    serializer_class = AdminBusinessTierSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = BusinessTier.objects.all().order_by('sort_order', 'price')

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        tier = self.get_object()
        tier.is_active = not tier.is_active
        tier.save(update_fields=['is_active', 'updated_at'])
        return Response(AdminBusinessTierSerializer(tier).data)

    @action(detail=True, methods=['post'], url_path='sync-paystack')
    def sync_paystack(self, request, pk=None):
        tier = self.get_object()
        if tier.is_free:
            return Response(
                {'error': 'Free tiers do not need Paystack plans.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tier = VendorTierSubscribeSerializer._sync_tier_to_paystack(tier)
        if tier.paystack_plan_code:
            return Response({
                'message': 'Tier synced to Paystack.',
                'paystack_plan_code': tier.paystack_plan_code,
            })
        return Response(
            {'error': 'Failed to sync tier to Paystack.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdminVendorTierSubscriptionViewSet(viewsets.GenericViewSet,
                                         viewsets.mixins.ListModelMixin,
                                         viewsets.mixins.RetrieveModelMixin):
    """
    Admin view of all vendor tier subscriptions.
    GET  /api/tiers/admin/subscriptions/              — list all (filter: ?status=, ?tier=)
    GET  /api/tiers/admin/subscriptions/<id>/         — retrieve one
    POST /api/tiers/admin/subscriptions/<id>/cancel/  — force cancel
    POST /api/tiers/admin/subscriptions/assign/       — assign tier to vendor
    """
    serializer_class = AdminVendorTierSubscriptionSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = VendorTierSubscription.objects.select_related(
            'tier', 'vendor', 'vendor__user',
        ).order_by('-started_at')
        status_filter = self.request.query_params.get('status')
        tier_filter = self.request.query_params.get('tier')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if tier_filter:
            qs = qs.filter(tier_id=tier_filter)
        return qs

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        if sub.status == 'cancelled':
            return Response({'error': 'Already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        from subscriptions.billing import expire_subscription
        expire_subscription(sub, reason='Administrator cancelled', force=True, status='cancelled')
        return Response(AdminVendorTierSubscriptionSerializer(sub).data)

    @action(detail=False, methods=['post'])
    def assign(self, request):
        """Directly assign a tier to a vendor profile (bypass Paystack)."""
        from business.models import VendorProfile
        serializer = AdminVendorTierAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vendor_id = request.data.get('vendor_id')
        vendor = get_object_or_404(VendorProfile, id=vendor_id)
        tier = BusinessTier.objects.get(id=serializer.validated_data['tier_id'])
        sub_status = serializer.validated_data['status']
        now = timezone.now()

        from .serializers import compute_period_end
        period_end = compute_period_end(now, tier)

        from subscriptions.billing import queue_cancellation
        previous = VendorTierSubscription.objects.filter(vendor=vendor).first()
        if previous:
            queue_cancellation(previous.paystack_subscription_code, previous.paystack_email_token,
                               'Administrator replaced subscription')
        sub, _ = VendorTierSubscription.objects.update_or_create(
            vendor=vendor,
            defaults={
                'tier': tier,
                'status': sub_status,
                'current_period_start': now,
                'current_period_end': period_end,
                'cancelled_at': None,
                'pending_reference': '', 'last_payment_reference': '',
                'paystack_subscription_code': '', 'paystack_email_token': '',
            },
        )
        return Response(AdminVendorTierSubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)

"""
Views for accounts app
"""
from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema

from .models import CustomerProfile, APIToken
from .serializers import (
    UserSerializer, UserDetailSerializer, UserRegisterSerializer,
    CustomerProfileSerializer,
    APITokenSerializer, APITokenCreateSerializer, APITokenCreatedSerializer,
)
from core.permissions import IsOwnerOrAdmin, IsAdminUser

User = get_user_model()


class UserRegisterView(generics.CreateAPIView):
    unverified_actions = ('post',)
    """
    Register a new user.
    Returns user data + JWT tokens so the client can authenticate immediately.
    Also auto-creates a verification OTP and sends it to the user's email.
    """
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Auto-create and send verification OTP for all user types.
        otp_sent = self._send_verification_otp(user)

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'otp_sent': otp_sent,
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def _send_verification_otp(user):
        from datetime import timedelta
        from django.utils import timezone
        from otp.models import OTPCode

        code = OTPCode.generate_code()
        OTPCode.objects.create(
            user=user,
            code=code,
            purpose='verification',
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        try:
            from core.email import send_otp_email
            return bool(send_otp_email(user, code, purpose='verification', expires_minutes=10))
        except Exception:
            import logging
            logging.getLogger('sanoa.email').exception(
                'Verification OTP email failed for %s', user.email)
            return False


class UserProfileView(generics.RetrieveUpdateAPIView):
    unverified_actions = ('get', 'put', 'patch')
    """Get or update the current user's profile"""
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    """Admin-only viewset for managing users"""
    queryset = User.objects.all().select_related(
        'customer_profile', 'individual_vendor_profile', 'business_vendor_profile'
    ).order_by('pk')
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer


class CustomerProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for customer profiles"""
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CustomerProfile.objects.none()
        if self.request.user.is_staff:
            return CustomerProfile.objects.all().select_related('user')
        return CustomerProfile.objects.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# =============================================================================
# API Token Views
# =============================================================================

class APITokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing API tokens.
    Users can create, list, and revoke their own tokens.
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_serializer_class(self):
        if self.action == 'create':
            return APITokenCreateSerializer
        return APITokenSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return APIToken.objects.none()
        return APIToken.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @extend_schema(responses={201: APITokenCreatedSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save()
        return Response(
            APITokenCreatedSerializer(token).data,
            status=status.HTTP_201_CREATED,
            headers={'Cache-Control': 'no-store'},
        )

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke an API token"""
        token = self.get_object()
        token.is_active = False
        token.save(update_fields=['is_active'])
        return Response({'status': 'revoked'})

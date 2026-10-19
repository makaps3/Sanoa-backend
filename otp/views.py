import secrets
from django.db import transaction
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode
from .serializers import ResendOTPSerializer, SendOTPSerializer, VerifyOTPSerializer

logger = logging.getLogger(__name__)

User = None


def get_user_model():
    """Lazy import to avoid circular imports."""
    global User
    if User is None:
        from django.contrib.auth import get_user_model as django_get_user_model
        User = django_get_user_model()
    return User


class SendOTPView(APIView):
    unverified_actions = ('post',)
    """Generate and send a 6-digit OTP code via email."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = serializer.validated_data['purpose']

        UserModel = get_user_model()
        try:
            user = UserModel.objects.select_for_update().get(email__iexact=email)
        except UserModel.DoesNotExist:
            return Response(
                {'detail': 'No account found with this email address.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_active or user.is_suspended:
            return Response({'detail': 'This account is unavailable.'}, status=403)
        if OTPCode.objects.filter(user=user, purpose=purpose,
                created_at__gte=timezone.now() - timedelta(minutes=10)).count() >= 3:
            return Response({'detail': 'Too many OTP requests. Please try again later.'}, status=429)

        # Invalidate any existing unused OTPs for the same user and purpose
        OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).update(is_used=True)

        # Generate and save new OTP
        code = OTPCode.generate_code()
        otp = OTPCode.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Send email
        if not _send_otp_email(user, code, purpose):
            return Response({'detail': 'Email could not be sent. Please try again shortly.'}, status=503)

        logger.info("OTP sent to %s for purpose '%s'", email, purpose)
        return Response(
            {'detail': 'OTP has been sent to your email address.'},
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    unverified_actions = ('post',)
    """Verify a 6-digit OTP code."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        purpose = serializer.validated_data['purpose']

        UserModel = get_user_model()
        try:
            user = UserModel.objects.select_for_update().get(email__iexact=email)
        except UserModel.DoesNotExist:
            return Response(
                {'detail': 'No account found with this email address.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_active or user.is_suspended:
            return Response({'detail': 'This account is unavailable.'}, status=403)

        # Find the most recent unused OTP for this user and purpose
        otp = OTPCode.objects.select_for_update().filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).first()

        if otp is None:
            return Response(
                {'detail': 'No active OTP found. Please request a new one.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.is_valid:
            if otp.is_expired:
                return Response(
                    {'detail': 'OTP has expired. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if otp.attempts >= OTPCode.MAX_ATTEMPTS:
                return Response(
                    {'detail': 'Maximum verification attempts exceeded. Please request a new OTP.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check the code
        if not secrets.compare_digest(otp.code, code):
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = OTPCode.MAX_ATTEMPTS - otp.attempts
            return Response(
                {
                    'detail': 'Invalid OTP code.',
                    'remaining_attempts': remaining,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP is correct - mark as used
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        # If purpose is verification, mark user as verified + welcome them
        if purpose == 'verification':
            already_verified = user.is_verified
            user.is_verified = True
            user.save(update_fields=['is_verified'])
            if not already_verified:
                try:
                    from core.email import send_welcome_email
                    send_welcome_email(user)
                except Exception:
                    logger.exception('Welcome email failed for %s', email)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        tokens = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

        logger.info("OTP verified successfully for %s (purpose: %s)", email, purpose)
        return Response(
            {
                'detail': 'OTP verified successfully.',
                'tokens': tokens,
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):
    unverified_actions = ('post',)
    """Resend OTP with rate limiting (max 3 resends per 10 minutes)."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = serializer.validated_data['purpose']

        UserModel = get_user_model()
        try:
            user = UserModel.objects.select_for_update().get(email__iexact=email)
        except UserModel.DoesNotExist:
            return Response(
                {'detail': 'No account found with this email address.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Rate limiting: max 3 OTPs in the last 10 minutes
        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        recent_otp_count = OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            created_at__gte=ten_minutes_ago,
        ).count()

        if recent_otp_count >= 3:
            return Response(
                {'detail': 'Too many OTP requests. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not user.is_active or user.is_suspended:
            return Response({'detail': 'This account is unavailable.'}, status=403)
        # Invalidate any existing unused OTPs for the same user and purpose
        OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).update(is_used=True)

        # Generate and save new OTP
        code = OTPCode.generate_code()
        OTPCode.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Send email
        if not _send_otp_email(user, code, purpose):
            return Response({'detail': 'Email could not be sent. Please try again shortly.'}, status=503)

        logger.info("OTP resent to %s for purpose '%s'", email, purpose)
        return Response(
            {'detail': 'OTP has been resent to your email address.'},
            status=status.HTTP_200_OK,
        )


def _send_otp_email(user, code, purpose='verification'):
    """Send the OTP code via the branded HTML email."""
    from core.email import send_otp_email, send_password_reset_email
    if purpose == 'password_reset':
        return send_password_reset_email(user, code, expires_minutes=10)
    else:
        return send_otp_email(user, code, purpose=purpose, expires_minutes=10)

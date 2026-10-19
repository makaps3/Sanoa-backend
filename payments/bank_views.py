"""REST endpoints for bank-account verification + Paystack recipient setup.

Endpoints:

    GET  /api/payments/banks/                           — list supported banks
    GET  /api/payments/me/recipient/                    — current vendor/driver recipient
    POST /api/payments/me/recipient/                    — submit bank details (vendor)
    POST /api/payments/me/driver-recipient/             — submit bank details (driver)
    POST /api/payments/admin/recipients/<id>/approve/   — admin override for MANUAL_REVIEW
"""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view, permission_classes, authentication_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .paystack import paystack_api
from .bank_verification import (
    SUPPORTED_CURRENCIES, approve_manual_review, verify_and_register,
)
from .wallet_models import PaystackRecipient


def _resolve_currency(raw) -> str:
    """Coerce a client-supplied currency to one of the supported codes.

    Defaults to ZAR (the marketplace's home currency) when missing or
    unrecognised — the Paystack API would otherwise reject the
    Transfer Recipient creation with an unfriendly error.
    """
    if raw is None:
        return 'ZAR'
    code = str(raw).strip().upper()
    return code if code in SUPPORTED_CURRENCIES else 'ZAR'


# ─── Public ───────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def list_supported_banks(request):
    """List banks supported by Paystack for the requested country."""
    country = request.query_params.get('country', 'south africa')
    result = paystack_api.list_banks(country=country)
    if not result.get('status'):
        return Response(
            {'error': result.get('message', 'Could not list banks.')},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    banks = [
        {
            'name': b.get('name'),
            'code': b.get('code'),
            'slug': b.get('slug'),
            'country': b.get('country'),
            'currency': b.get('currency'),
        }
        for b in (result.get('data') or [])
    ]
    return Response({'banks': banks, 'count': len(banks)})


# ─── Vendor ───────────────────────────────────────────────────────────────────

class VendorRecipientView(APIView):
    unverified_actions = ('get', 'post')
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        vendor = getattr(request.user, 'vendor_profile', None)
        if vendor is None:
            return Response(
                {'error': 'No vendor profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        recipient = PaystackRecipient.objects.filter(
            owner_type=PaystackRecipient.OWNER_VENDOR,
            owner_id=str(vendor.id),
            archived_at__isnull=True,
        ).first()
        return Response(_serialise_recipient(recipient))

    def post(self, request):
        """Submit / update bank details for the calling vendor."""
        vendor = getattr(request.user, 'vendor_profile', None)
        if vendor is None:
            return Response(
                {'error': 'No vendor profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            bank_code = request.data['bank_code']
            account_number = str(request.data['account_number'])
        except KeyError as missing:
            return Response(
                {'error': f'Missing field: {missing.args[0]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        business_name = (
            request.data.get('business_name')
            or getattr(vendor, 'trading_name', None)
            or getattr(vendor, 'name', None)
            or ''
        )
        bank_name = request.data.get('bank_name', '')
        currency = _resolve_currency(request.data.get('currency'))

        result = verify_and_register(
            owner_type=PaystackRecipient.OWNER_VENDOR,
            owner_id=str(vendor.id),
            business_name=business_name,
            bank_code=bank_code,
            bank_name=bank_name,
            account_number=account_number,
            currency=currency,
        )
        return Response({
            'recipient': _serialise_recipient(result.recipient),
            'verified': result.verified,
            'resolved_account_name': result.resolved_name,
            'similarity': round(result.similarity, 2),
            'error': result.error,
        }, status=status.HTTP_201_CREATED)


# ─── Driver ───────────────────────────────────────────────────────────────────

class DriverRecipientView(APIView):
    unverified_actions = ('get', 'post')
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        driver = getattr(request.user, 'driver_profile', None)
        if driver is None:
            return Response(
                {'error': 'No driver profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        recipient = PaystackRecipient.objects.filter(
            owner_type=PaystackRecipient.OWNER_DRIVER,
            owner_id=str(driver.id),
            archived_at__isnull=True,
        ).first()
        return Response(_serialise_recipient(recipient))

    def post(self, request):
        driver = getattr(request.user, 'driver_profile', None)
        if driver is None:
            return Response(
                {'error': 'No driver profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            bank_code = request.data['bank_code']
            account_number = str(request.data['account_number'])
        except KeyError as missing:
            return Response(
                {'error': f'Missing field: {missing.args[0]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        full_name = (
            request.data.get('full_name')
            or f"{request.user.first_name} {request.user.last_name}".strip()
            or request.user.email
        )
        bank_name = request.data.get('bank_name', '')
        currency = _resolve_currency(request.data.get('currency'))

        result = verify_and_register(
            owner_type=PaystackRecipient.OWNER_DRIVER,
            owner_id=str(driver.id),
            business_name=full_name,
            bank_code=bank_code,
            bank_name=bank_name,
            account_number=account_number,
            currency=currency,
        )
        return Response({
            'recipient': _serialise_recipient(result.recipient),
            'verified': result.verified,
            'resolved_account_name': result.resolved_name,
            'similarity': round(result.similarity, 2),
            'error': result.error,
        }, status=status.HTTP_201_CREATED)


# ─── Admin override ───────────────────────────────────────────────────────────

class AdminApproveRecipientView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, recipient_id):
        profile = getattr(request.user, 'admin_profile', None)
        if profile is None or not (
            profile.is_super_admin or profile.has_permission('financial_access')
        ):
            return Response(
                {'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN,
            )
        try:
            recipient = PaystackRecipient.objects.get(id=recipient_id)
        except PaystackRecipient.DoesNotExist:
            return Response(
                {'error': 'Recipient not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = approve_manual_review(recipient)
        except (ValueError, RuntimeError) as exc:
            return Response(
                {'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'recipient': _serialise_recipient(result.recipient),
            'verified': True,
        })


# ─── Helper ───────────────────────────────────────────────────────────────────

def _serialise_recipient(r):
    if r is None:
        return None
    return {
        'id': str(r.id),
        'owner_type': r.owner_type,
        'owner_id': r.owner_id,
        'business_name': r.business_name,
        'bank_code': r.bank_code,
        'bank_name': r.bank_name,
        'account_number': r.account_number,
        'submitted_account_name': r.submitted_account_name,
        'resolved_account_name': r.resolved_account_name,
        'recipient_code': r.recipient_code,
        'verification_status': r.verification_status,
        'bank_verified': r.bank_verified,
        'payout_enabled': r.payout_enabled,
        'archived_at': r.archived_at.isoformat() if r.archived_at else None,
        'created_at': r.created_at.isoformat(),
        'updated_at': r.updated_at.isoformat(),
    }

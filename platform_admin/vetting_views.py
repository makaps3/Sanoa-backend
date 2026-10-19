"""Admin vetting + bank-verification endpoints.

Two distinct workflows live here:

  Vetting:
    Admins approve / reject the *identity* of a customer, vendor, or
    driver — i.e. they validate the documents the user uploaded
    during onboarding (ID, CIPC for businesses, driver's licence,
    etc.) and flip the profile's `verification_status` /
    `is_verified` flag.

  Bank verification:
    A separate workflow for vendors + drivers only. The owner
    submitted bank details on their profile; admins run them through
    Paystack's `/bank/resolve` endpoint, compare the resolved name
    against the submitted account-holder name, and approve or
    reject the bank account. On approval the matching
    `payments.PaystackRecipient` row is created so the marketplace
    payout engine can transfer to that account.

Permissions follow ``platform_admin.models.ROLE_PERMISSIONS``:

    * customers vetting → ``manage_customers``
    * vendors  vetting → ``manage_vendors``
    * drivers  vetting → ``manage_drivers``
    * bank verification → ``manage_payments``  OR  ``financial_access``
"""
from __future__ import annotations

from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import serializers
from core.document_validation import validate_document
from business.verification import (vendor_vetting_checklist, _vendor_missing_documents,
                                   _driver_missing_documents, _vendor_bank_ready)
from business.verification_workflow import record_decision, sync_review_state, invalidate_vendor
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from .vetting_serializers import (
    VENDOR_DOCUMENT_FIELDS, VendorSelfVettingSerializer,
    VendorDocumentUploadSerializer, VendorDocumentUploadedSerializer,
    DriverSelfVettingSerializer, DriverVettingSubmittedSerializer,
    VettingErrorSerializer,
)

from accounts.models import CustomerProfile, User
from business.models import VendorProfile
from delivery.models import DeliveryDriver


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _admin_profile(request):
    return getattr(request.user, 'admin_profile', None)


def _has(request, *keys: str) -> bool:
    """True when the caller has any of the listed permission keys."""
    profile = _admin_profile(request)
    if profile is None or profile.status != 'active':
        return False
    if profile.is_super_admin:
        return True
    return any(profile.has_permission(k) for k in keys)


def _forbidden():
    return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)


def _missing(label):
    return Response({'error': f'{label} not found.'},
                    status=status.HTTP_404_NOT_FOUND)


def _bad(message):
    return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)


def _serialise_user(u: User):
    return {
        'id': u.id,
        'email': u.email,
        'full_name': (f'{u.first_name} {u.last_name}').strip() or u.email,
        'phone_number': u.phone_number,
        'is_verified': u.is_verified,
        'is_suspended': u.is_suspended,
        'date_joined': u.date_joined.isoformat() if u.date_joined else None,
        'user_type': u.user_type,
    }


def _customer_completeness(c: CustomerProfile) -> int:
    """0-100 score showing how complete a customer's profile is.

    Drives the "ready to vet" sorting on the admin queue — customers
    with more filled-in fields surface first.
    """
    score = 0
    u = c.user
    if u.first_name and u.last_name: score += 25
    if u.phone_number:               score += 15
    if u.is_verified:                score += 20
    if c.avatar:                     score += 10
    if c.gender:                     score += 5
    if c.latitude and c.longitude:   score += 10
    if c.bio:                        score += 5
    if c.interest_categories.exists(): score += 10
    return min(score, 100)


def _serialise_customer(c: CustomerProfile):
    return {
        'id': c.id,
        'user': _serialise_user(c.user),
        'avatar': c.avatar.url if c.avatar else None,
        'gender': c.gender,
        'bio': c.bio,
        'preferred_language': c.preferred_language,
        'loyalty_points': c.loyalty_points,
        'has_location': bool(c.latitude and c.longitude),
        'completeness': _customer_completeness(c),
        'created_at': c.created_at.isoformat(),
        'missing_documents': _customer_missing_fields(c),
        'suspension_reason': c.user.suspension_reason,
    }


def _customer_missing_fields(c: CustomerProfile) -> list:
    missing = []
    u = c.user

    def need(value, label, code):
        if not value:
            missing.append({'label': label, 'code': code})

    need(u.first_name, 'First name', 'first_name')
    need(u.last_name, 'Last name', 'last_name')
    need(u.phone_number, 'Phone number', 'phone_number')
    return missing


def _serialise_vendor(v: VendorProfile, *, detailed: bool = False):
    payload = {
        'id': str(v.id),
        'user': _serialise_user(v.user),
        'profile_type': v.profile_type,
        'business_category': v.business_category,
        'name': v.name,
        'trading_name': v.trading_name,
        'description': v.description,
        'logo': v.logo.url if v.logo else None,
        'verification_status': v.verification_status,
        'owner_vetting_passed': v.owner_vetting_passed,
        'business_vetting_passed': v.business_vetting_passed,
        'rejection_reason': v.rejection_reason,
        'verified_at': v.verified_at.isoformat() if v.verified_at else None,
        'store_active': v.store_active,
        'created_at': v.created_at.isoformat(),
        # Banking summary — full numbers only on detail view.
        'has_bank_details': bool(v.bank_name and v.bank_account_number),
        'bank_name': v.bank_name,
        'bank_account_holder': v.bank_account_holder,
        'bank_account_last4':
            v.bank_account_number[-4:] if v.bank_account_number else '',
        'missing_documents': _vendor_missing_documents(v),
    }
    if detailed:
        payload.update({
            'vendor_type': v.vendor_type,
            'business_type': v.business_type,
            'id_number': v.id_number,
            'id_document': v.id_document.url if v.id_document else None,
            'proof_of_address':
                v.proof_of_address.url if v.proof_of_address else None,
            'selfie_with_id':
                v.selfie_with_id.url if v.selfie_with_id else None,
            'cipc_registration_number': v.cipc_registration_number,
            'cipc_document':
                v.cipc_document.url if v.cipc_document else None,
            'tax_number': v.tax_number,
            'tax_clearance_certificate':
                v.tax_clearance_certificate.url
                if v.tax_clearance_certificate else None,
            'vat_number': v.vat_number,
            'bee_certificate':
                v.bee_certificate.url if v.bee_certificate else None,
            'owner_full_name': v.owner_full_name,
            'owner_id_number': v.owner_id_number,
            'owner_id_document':
                v.owner_id_document.url if v.owner_id_document else None,
            'owner_proof_of_address':
                v.owner_proof_of_address.url
                if v.owner_proof_of_address else None,
            'street_address': v.street_address,
            'city': v.city,
            'province': v.province,
            'postal_code': v.postal_code,
            'country': v.country,
            'bank_account_number': v.bank_account_number,
            'bank_branch_code': v.bank_branch_code,
        })
    return payload


def _serialise_driver(d: DeliveryDriver, *, detailed: bool = False):
    payload = {
        'id': str(d.id),
        'user': _serialise_user(d.user),
        'vehicle_type': d.vehicle_type,
        'vehicle_brand': d.vehicle_brand,
        'vehicle_model': d.vehicle_model,
        'vehicle_registration': d.vehicle_registration,
        'license_number': d.license_number,
        'background_check_status': d.background_check_status,
        'identity_verification_status': d.identity_verification_status,
        'training_completed': d.training_completed,
        'terms_accepted': d.terms_accepted,
        'is_available': d.is_available,
        'total_deliveries': d.total_deliveries,
        'vetting_notes': d.vetting_notes,
        'created_at': d.created_at.isoformat(),
        'missing_documents': _driver_missing_documents(d),
    }
    if detailed:
        payload.update({
            'vehicle_color': d.vehicle_color,
            'vehicle_license_expiry':
                d.vehicle_license_expiry.isoformat()
                if d.vehicle_license_expiry else None,
            'vehicle_photo_front':
                d.vehicle_photo_front.url if d.vehicle_photo_front else None,
            'vehicle_photo_side':
                d.vehicle_photo_side.url if d.vehicle_photo_side else None,
            'vehicle_photo_rear':
                d.vehicle_photo_rear.url if d.vehicle_photo_rear else None,
            'insurance_document':
                d.insurance_document.url if d.insurance_document else None,
            'driver_license_document':
                d.driver_license_document.url
                if d.driver_license_document else None,
            'license_expiry_date':
                d.license_expiry_date.isoformat()
                if d.license_expiry_date else None,
        })
    return payload


# ═════════════════════════════════════════════════════════════════════════════
# Queue overview
# ═════════════════════════════════════════════════════════════════════════════

class VettingOverviewView(APIView):
    """Counts per vetting queue — drives the dashboard pills."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Caller must have at least one vetting permission to see the
        # overview. Each entry is gated by its own permission below.
        if not _has(request, 'manage_customers', 'manage_vendors',
                    'manage_drivers', 'manage_payments', 'financial_access'):
            return _forbidden()

        last_7d = timezone.now() - timedelta(days=7)

        out = {}

        if _has(request, 'manage_customers'):
            out['customers'] = {
                'unverified': User.objects.filter(
                    user_type='customer', is_verified=False,
                ).count(),
                'verified': User.objects.filter(
                    user_type='customer', is_verified=True,
                ).count(),
                'new_7d': User.objects.filter(
                    user_type='customer', date_joined__gte=last_7d,
                ).count(),
                'suspended': User.objects.filter(
                    user_type='customer', is_suspended=True,
                ).count(),
            }

        if _has(request, 'manage_vendors'):
            vendor_buckets = (
                VendorProfile.objects.values('verification_status')
                .annotate(c=Count('id'))
            )
            counts = {row['verification_status']: row['c']
                      for row in vendor_buckets}
            out['vendors'] = {
                'pending':        counts.get('pending', 0),
                'owner_verified': counts.get('owner_verified', 0),
                'under_review':   counts.get('under_review', 0),
                'verified':       counts.get('verified', 0),
                'rejected':       counts.get('rejected', 0),
                'suspended':      counts.get('suspended', 0),
            }

        if _has(request, 'manage_drivers'):
            driver_id_buckets = (
                DeliveryDriver.objects
                .values('identity_verification_status')
                .annotate(c=Count('id'))
            )
            id_counts = {row['identity_verification_status']: row['c']
                         for row in driver_id_buckets}
            bg_buckets = (
                DeliveryDriver.objects
                .values('background_check_status')
                .annotate(c=Count('id'))
            )
            bg_counts = {row['background_check_status']: row['c']
                         for row in bg_buckets}
            out['drivers'] = {
                'identity_pending':  id_counts.get('pending', 0),
                'identity_verified': id_counts.get('verified', 0),
                'identity_rejected': id_counts.get('rejected', 0),
                'background_pending':  bg_counts.get('pending', 0),
                'background_verified': bg_counts.get('verified', 0),
                'background_rejected': bg_counts.get('rejected', 0),
            }

        if _has(request, 'manage_payments', 'financial_access'):
            out['bank_verification'] = {
                'vendors_with_bank_details':
                    VendorProfile.objects.exclude(
                        Q(bank_account_number='') | Q(bank_name=''),
                    ).count(),
                'drivers_with_bank_details': 0,  # see DriverBankVerifyView
            }

        return Response(out)


# ═════════════════════════════════════════════════════════════════════════════
# Customer vetting
# ═════════════════════════════════════════════════════════════════════════════

class CustomerVettingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _has(request, 'manage_customers'):
            return _forbidden()
        # `status=` filter: pending (is_verified=False & not suspended),
        # verified, suspended, all.
        target = (request.query_params.get('status') or 'pending').lower()
        qs = CustomerProfile.objects.select_related('user').all()
        if target == 'pending':
            qs = qs.filter(user__is_verified=False, user__is_suspended=False)
        elif target == 'verified':
            qs = qs.filter(user__is_verified=True)
        elif target == 'suspended':
            qs = qs.filter(user__is_suspended=True)
        # default: all
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__phone_number__icontains=search),
            )
        qs = qs.order_by('-created_at')[:200]
        return Response({
            'results': [_serialise_customer(c) for c in qs],
        })


class CustomerVettingActionView(APIView):
    """POST approve/reject for a customer profile.

    Body:
        ``{ "action": "approve" | "reject" | "suspend" | "unsuspend",
            "reason": "<text, required for reject/suspend>" }``
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, customer_id):
        if not _has(request, 'manage_customers'):
            return _forbidden()
        try:
            customer = CustomerProfile.objects.select_related('user').get(
                id=customer_id,
            )
        except CustomerProfile.DoesNotExist:
            return _missing('Customer')

        action = str(request.data.get('action') or '').lower()
        reason = str(request.data.get('reason') or '').strip()
        user = customer.user

        if action == 'approve':
            user.is_verified = True
            user.save(update_fields=['is_verified', 'updated_at'])
        elif action == 'reject':
            if not reason:
                return _bad("Rejection 'reason' is required.")
            user.is_verified = False
            user.save(update_fields=['is_verified', 'updated_at'])
        elif action == 'suspend':
            if not reason:
                return _bad("Suspension 'reason' is required.")
            user.is_suspended = True
            user.suspended_at = timezone.now()
            user.suspension_reason = reason[:1000]
            user.save(update_fields=[
                'is_suspended', 'suspended_at', 'suspension_reason',
                'updated_at',
            ])
        elif action == 'unsuspend':
            user.is_suspended = False
            user.suspended_at = None
            user.suspension_reason = ''
            user.save(update_fields=[
                'is_suspended', 'suspended_at', 'suspension_reason',
                'updated_at',
            ])
        else:
            return _bad("'action' must be approve / reject / suspend / unsuspend.")

        return Response(_serialise_customer(customer))


class CustomerVettingDeleteView(APIView):
    """Hard-delete a customer profile + user. Use sparingly — usually
    suspension is the right call. The platform's audit trail keeps
    orders, payments, etc. via SET_NULL on those FKs."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, customer_id):
        if not _has(request, 'manage_customers'):
            return _forbidden()
        try:
            customer = CustomerProfile.objects.select_related('user').get(
                id=customer_id,
            )
        except CustomerProfile.DoesNotExist:
            return _missing('Customer')
        user = customer.user
        # Profile cascades when the User is deleted (OneToOneField with
        # on_delete=CASCADE).
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═════════════════════════════════════════════════════════════════════════════
# Vendor vetting
# ═════════════════════════════════════════════════════════════════════════════

class VendorVettingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _has(request, 'manage_vendors'):
            return _forbidden()
        target = (request.query_params.get('status') or 'pending').lower()
        qs = VendorProfile.objects.select_related('user').all()
        if target != 'all':
            qs = qs.filter(verification_status=target)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(trading_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(cipc_registration_number__icontains=search),
            )
        profile_type = request.query_params.get('profile_type')
        if profile_type in ('individual', 'business'):
            qs = qs.filter(profile_type=profile_type)
        qs = qs.order_by('-created_at')[:200]
        return Response({
            'results': [_serialise_vendor(v) for v in qs],
        })


class VendorVettingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, vendor_id):
        if not _has(request, 'manage_vendors'):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_related('user').get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')
        payload = _serialise_vendor(v, detailed=True)
        # Same sectioned checklist the vendor sees, with document URLs, so the
        # admin board can review each item (and open the uploaded file).
        payload['checklist'] = vendor_vetting_checklist(v, request)['sections']
        return Response(payload)


class VendorVettingActionView(APIView):
    """POST approve / reject / review / request_info / suspend.

    Body:
        ``{ "action": "approve" | "reject" | "review" | "request_info"
                      | "suspend" | "unsuspend",
            "reason": "<text>",
            "owner_vetting_passed":     true/false,   // optional
            "business_vetting_passed":  true/false }  // optional
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, vendor_id):
        if not _has(request, 'manage_vendors'):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_for_update().get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')

        action = str(request.data.get('action') or '').lower()
        reason = str(request.data.get('reason') or '').strip()

        previous = v.verification_status
        if action == 'approve':
            missing = _vendor_missing_documents(v)
            if missing:
                return Response({'detail': 'Complete all required items before approval.',
                                 'missing_documents': missing}, status=400)
            if v.verification_status != 'under_review':
                return _bad('Only a submitted application under review can be approved.')
            if v.user.is_suspended or not v.user.is_active or not v.user.is_verified:
                return _bad('The account must be active and its email verified before approval.')
            v.owner_vetting_passed = True
            v.business_vetting_passed = v.profile_type == 'business'
            v.verification_status = 'verified'
            v.verified_at = timezone.now()
            v.verified_by = request.user
            v.rejection_reason = ''
            v.store_active = True
        elif action == 'review':
            v.verification_status = 'under_review'
        elif action == 'request_info':
            # Admin requests more info / flags missing documents. The
            # vendor sees this note in their KYC screen and re-submits
            # the application once the missing docs are uploaded.
            if not reason:
                return _bad("'reason' is required when requesting info.")
            v.verification_status = 'pending'
            v.rejection_reason = reason[:2000]
        elif action == 'reject':
            if not reason:
                return _bad("Rejection 'reason' is required.")
            v.verification_status = 'rejected'
            v.rejection_reason = reason[:2000]
            v.store_active = False
        elif action == 'suspend':
            if not reason:
                return _bad("Suspension 'reason' is required.")
            v.verification_status = 'suspended'
            v.rejection_reason = reason[:2000]
            v.store_active = False
        elif action == 'unsuspend':
            v.verification_status = 'pending'
            v.rejection_reason = ''
        else:
            return _bad(
                "'action' must be approve / review / request_info / "
                "reject / suspend / unsuspend.",
            )

        if action != 'approve':
            v.store_active = False
            v.owner_vetting_passed = False
            v.business_vetting_passed = False
            v.verified_at = None
            v.verified_by = None
        v.save()
        sync_review_state(v)
        record_decision(v, request.user, action, previous, v.verification_status, reason)
        return Response(_serialise_vendor(v, detailed=True))


class VendorVettingDeleteView(APIView):
    """Hard-delete a vendor profile + user."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, vendor_id):
        if not _has(request, 'manage_vendors'):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_related('user').get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')
        v.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═════════════════════════════════════════════════════════════════════════════
# Driver vetting
# ═════════════════════════════════════════════════════════════════════════════

class DriverVettingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _has(request, 'manage_drivers'):
            return _forbidden()
        target = (request.query_params.get('status') or 'pending').lower()
        qs = DeliveryDriver.objects.select_related('user').all()
        # `status` filters identity verification — the most common
        # gate — but admins can pass `field=background_check` to flip
        # to background-check status filtering.
        field = (request.query_params.get('field') or 'identity').lower()
        if target != 'all':
            if field == 'background_check':
                qs = qs.filter(background_check_status=target)
            else:
                qs = qs.filter(identity_verification_status=target)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(license_number__icontains=search)
                | Q(vehicle_registration__icontains=search),
            )
        qs = qs.order_by('-created_at')[:200]
        return Response({
            'results': [_serialise_driver(d) for d in qs],
        })


class DriverVettingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, driver_id):
        if not _has(request, 'manage_drivers'):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_related('user').get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')
        return Response(_serialise_driver(d, detailed=True))


class DriverVettingActionView(APIView):
    """POST approve / reject / review / request_info on driver fields.

    Body:
        ``{ "field": "identity" | "background_check",
            "action": "approve" | "reject" | "review" | "request_info",
            "reason": "<text>" }``
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, driver_id):
        if not _has(request, 'manage_drivers'):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_for_update().get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')

        field = str(request.data.get('field') or 'identity').lower()
        action = str(request.data.get('action') or '').lower()
        reason = str(request.data.get('reason') or '').strip()

        # Driver enum uses 'approved' (not 'verified'). request_info
        # bounces the status back to pending and stores the admin's
        # missing-docs note on `vetting_notes`.
        new_status = {
            'approve':      'approved',
            'reject':       'rejected',
            'review':       'under_review',
            'request_info': 'pending',
        }.get(action)
        if new_status is None:
            return _bad(
                "'action' must be approve / reject / review / request_info.",
            )
        if action in ('reject', 'request_info') and not reason:
            return _bad(f"'reason' is required for {action}.")

        if action == 'approve':
            missing = _driver_missing_documents(d)
            if missing:
                return Response({'detail': 'Complete the required driver documents before approval.',
                                 'missing_documents': missing}, status=400)
            if not d.user.is_verified or d.user.is_suspended or not d.user.is_active:
                return _bad('The account must be active and its email verified before approval.')
        previous = d.identity_verification_status if field == 'identity' else d.background_check_status
        if field == 'identity':
            d.identity_verification_status = new_status
        elif field == 'background_check':
            d.background_check_status = new_status
        else:
            return _bad("'field' must be identity or background_check.")

        if action in ('request_info', 'reject'):
            d.vetting_notes = reason[:2000]
        elif action == 'approve':
            d.vetting_notes = ''
        if new_status != 'approved':
            d.is_available = False
        d.save(update_fields=[
            'is_available',
            'identity_verification_status', 'background_check_status',
            'vetting_notes', 'updated_at',
        ])
        record_decision(d, request.user, action, previous, new_status, reason)
        return Response(_serialise_driver(d, detailed=True))


class DriverVettingDeleteView(APIView):
    """Hard-delete a driver profile + user."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, driver_id):
        if not _has(request, 'manage_drivers'):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_related('user').get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')
        d.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═════════════════════════════════════════════════════════════════════
# Vendor + Driver self-service: submit KYC application
# ═════════════════════════════════════════════════════════════════════
#
# Vendor / driver-side endpoints that flip their own status to
# `under_review` once they've uploaded all the docs. The endpoints
# refuse if mandatory docs are still missing — the response body
# returns the same `missing_documents` shape the admin sees, so the
# self-service screen on the frontend can show exactly what's
# blocking submission.

@extend_schema_view(
    get=extend_schema(responses={200: VendorSelfVettingSerializer, 403: VettingErrorSerializer}),
    post=extend_schema(request=None, responses={
        200: VendorSelfVettingSerializer, 400: VettingErrorSerializer,
        403: VettingErrorSerializer, 409: VettingErrorSerializer,
    }),
)
class VendorSelfVettingView(APIView):
    unverified_actions = ('get', 'post')
    """Vendor-side endpoint to submit a KYC application + read status.

    GET  → current verification_status + admin notes + missing docs.
    POST → mark the application "under_review" so an admin can vet
           it. Refused with HTTP 400 + missing-docs list if mandatory
           docs are still blank.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _vendor(self, request):
        return getattr(request.user, 'vendor_profile', None)

    def get(self, request):
        v = self._vendor(request)
        if v is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        checklist = vendor_vetting_checklist(v, request)
        return Response({
            'verification_status': v.verification_status,
            'can_trade': v.can_trade,
            'rejection_reason': v.rejection_reason,
            'owner_vetting_passed': v.owner_vetting_passed,
            'business_vetting_passed': v.business_vetting_passed,
            'verified_at': v.verified_at.isoformat() if v.verified_at else None,
            'profile_type': v.profile_type,
            'checklist': checklist['sections'],
            'missing_documents': checklist['missing'],
            'can_submit': checklist['complete'],
        })

    @transaction.atomic
    def post(self, request):
        v = VendorProfile.objects.select_for_update().filter(user=request.user).first()
        if v is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        missing = _vendor_missing_documents(v)
        if missing:
            return Response({
                'error': 'Please upload the missing documents before '
                         'submitting your application.',
                'missing_documents': missing,
            }, status=status.HTTP_400_BAD_REQUEST)
        if v.verification_status == 'verified':
            return Response({
                'error': 'Your profile is already verified.',
                'verification_status': v.verification_status,
            }, status=status.HTTP_409_CONFLICT)
        if v.verification_status == 'suspended':
            return Response({
                'error': 'Your account is suspended. Contact support.',
                'verification_status': v.verification_status,
            }, status=status.HTTP_409_CONFLICT)
        if not request.user.is_verified:
            return _bad('Verify your email before submitting your application.')
        v.verification_status = 'under_review'
        v.save(update_fields=['verification_status', 'updated_at'])
        sync_review_state(v)
        response = self.get(request)
        response.data['submitted_at'] = timezone.now().isoformat()
        return response


@extend_schema_view(post=extend_schema(
    request=VendorDocumentUploadSerializer,
    responses={200: VendorDocumentUploadedSerializer, 400: VettingErrorSerializer,
               403: VettingErrorSerializer},
))
class VendorSelfDocumentUploadView(APIView):
    unverified_actions = ('post',)
    """Vendor uploads (or replaces) a single vetting document from the
    vetting screen. Accepts multipart {code, file} and returns the refreshed
    checklist so the UI can tick the item off immediately."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # Only these document fields may be set through this endpoint.
    FILE_FIELDS = frozenset(VENDOR_DOCUMENT_FIELDS)

    @transaction.atomic
    def post(self, request):
        v = VendorProfile.objects.select_for_update().filter(user=request.user).first()
        if v is None:
            return Response(
                {'detail': "There's no vendor profile on this account, so "
                           "documents can't be uploaded."},
                status=status.HTTP_403_FORBIDDEN)
        code = request.data.get('code')
        upload = request.FILES.get('file')
        if code not in self.FILE_FIELDS:
            return Response(
                {'detail': "That document can't be uploaded here. Choose one "
                           "of the documents shown on your vetting checklist."},
                status=status.HTTP_400_BAD_REQUEST)
        if upload is None:
            return Response({'detail': 'Please choose a file to upload.'},
                            status=status.HTTP_400_BAD_REQUEST)
        validate_document(upload)
        setattr(v, code, upload)
        invalidate_vendor(v)
        v.save()
        sync_review_state(v)

        # Keep the admin-side VettingApplication checklist truthful.
        # (sync_vetting_application swallows its own errors.)
        from business.vetting_sync import sync_vetting_application
        sync_vetting_application(v)

        checklist = vendor_vetting_checklist(v, request)
        remaining = len(checklist['missing'])
        if v.verification_status == 'verified':
            message = 'Document updated. Thanks!'
        elif remaining == 0:
            message = ('Document uploaded — your checklist is complete. '
                       'You can submit for verification now.')
        else:
            message = (f'Document uploaded. {remaining} item'
                       f'{"" if remaining == 1 else "s"} still to go.')
        return Response({
            'message': message,
            'verification_status': v.verification_status,
            'can_trade': v.can_trade,
            'profile_type': v.profile_type,
            'rejection_reason': v.rejection_reason,
            'checklist': checklist['sections'],
            'missing_documents': checklist['missing'],
            'can_submit': checklist['complete'],
        })


@extend_schema_view(
    get=extend_schema(responses={200: DriverSelfVettingSerializer, 403: VettingErrorSerializer}),
    post=extend_schema(request=None, responses={
        200: DriverVettingSubmittedSerializer, 400: VettingErrorSerializer,
        403: VettingErrorSerializer, 409: VettingErrorSerializer,
    }),
)
class DriverSelfVettingView(APIView):
    unverified_actions = ('get', 'post')
    """Driver-side equivalent of `VendorSelfVettingView`."""
    permission_classes = [permissions.IsAuthenticated]

    def _driver(self, request):
        return getattr(request.user, 'driver_profile', None)

    def get(self, request):
        d = self._driver(request)
        if d is None:
            return Response({'error': 'No driver profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response({
            'identity_verification_status': d.identity_verification_status,
            'background_check_status': d.background_check_status,
            'vetting_notes': d.vetting_notes,
            'training_completed': d.training_completed,
            'terms_accepted': d.terms_accepted,
            'missing_documents': _driver_missing_documents(d),
            'can_submit': len(_driver_missing_documents(d)) == 0,
        })

    @transaction.atomic
    def post(self, request):
        d = DeliveryDriver.objects.select_for_update().filter(user=request.user).first()
        if d is None:
            return Response({'error': 'No driver profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        missing = _driver_missing_documents(d)
        if missing:
            return Response({
                'error': 'Please upload the missing documents before '
                         'submitting your application.',
                'missing_documents': missing,
            }, status=status.HTTP_400_BAD_REQUEST)
        if d.identity_verification_status == 'approved':
            return Response({
                'error': 'Your identity is already verified.',
                'identity_verification_status':
                    d.identity_verification_status,
            }, status=status.HTTP_409_CONFLICT)
        if not request.user.is_verified:
            return _bad('Verify your email before submitting your application.')
        d.identity_verification_status = 'under_review'
        d.save(update_fields=[
            'identity_verification_status', 'updated_at',
        ])
        return Response({
            'identity_verification_status': d.identity_verification_status,
            'background_check_status': d.background_check_status,
            'missing_documents': [],
            'submitted_at': timezone.now().isoformat(),
        })


# ═════════════════════════════════════════════════════════════════════════════
# Bank verification — vendor + driver
# ═════════════════════════════════════════════════════════════════════════════

def _bank_can_manage(request) -> bool:
    return _has(request, 'manage_payments', 'financial_access',
                'manage_vendors', 'manage_drivers')


def _active_vendor_recipient(v: VendorProfile):
    """Return the vendor's active (non-archived) Paystack recipient,
    or None. Pulled out so the bank-verification views can share one
    cache-friendly lookup."""
    from payments.wallet_models import PaystackRecipient
    return PaystackRecipient.objects.filter(
        owner_type=PaystackRecipient.OWNER_VENDOR,
        owner_id=str(v.id),
        archived_at__isnull=True,
    ).first()


def _vendor_bank_details(v: VendorProfile, rcp=None) -> dict:
    """Resolve a vendor's bank details by preferring the active
    PaystackRecipient (created via the marketplace wallet flow) over
    the legacy VendorProfile fields. Vendors who submitted via the
    wallet sheet have empty profile fields — without this helper the
    bank verification screen would show blanks and the approve flow
    would reject as "missing".
    """
    if rcp is None:
        rcp = _active_vendor_recipient(v)
    bank_name        = (rcp.bank_name if rcp and rcp.bank_name
                        else v.bank_name)
    account_number   = (rcp.account_number if rcp and rcp.account_number
                        else v.bank_account_number)
    branch_code      = (rcp.bank_code if rcp and rcp.bank_code
                        else v.bank_branch_code)
    account_holder   = (rcp.business_name if rcp and rcp.business_name
                        else v.bank_account_holder or v.name)
    return {
        'bank_name': bank_name or '',
        'account_number': account_number or '',
        'branch_code': branch_code or '',
        'account_holder': account_holder or '',
    }


def _bank_payload_for_vendor(v: VendorProfile, paystack_match=None):
    """Common dict for vendor bank verification screens."""
    rcp = _active_vendor_recipient(v)
    bank = _vendor_bank_details(v, rcp=rcp)
    return {
        'id': str(v.id),
        'kind': 'vendor',
        'name': v.name,
        'trading_name': v.trading_name,
        'email': v.user.email,
        'profile_type': v.profile_type,
        'bank_name': bank['bank_name'],
        'bank_account_number': bank['account_number'],
        'bank_account_last4':
            bank['account_number'][-4:] if bank['account_number'] else '',
        'bank_branch_code': bank['branch_code'],
        'bank_account_holder': bank['account_holder'],
        'verification_status': v.verification_status,
        'recipient': _recipient_summary(rcp),
        'paystack_match': paystack_match,
    }


def _active_driver_recipient(d: DeliveryDriver):
    """Return the driver's active (non-archived) Paystack recipient,
    or None. Drivers only collect bank details via the marketplace
    wallet sheet, so this is the only source — no profile fallback."""
    from payments.wallet_models import PaystackRecipient
    return PaystackRecipient.objects.filter(
        owner_type=PaystackRecipient.OWNER_DRIVER,
        owner_id=str(d.id),
        archived_at__isnull=True,
    ).first()


def _driver_bank_details(d: DeliveryDriver, rcp=None) -> dict:
    """Resolve a driver's bank details by reading the active
    PaystackRecipient. Mirrors `_vendor_bank_details` so the views
    have a consistent shape. Returns blanks (not None) so callers
    can interpolate safely.
    """
    if rcp is None:
        rcp = _active_driver_recipient(d)
    user = d.user
    full_name = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    fallback_holder = full_name or user.email
    return {
        'bank_name': (rcp.bank_name if rcp and rcp.bank_name else '') or '',
        'account_number':
            (rcp.account_number if rcp and rcp.account_number else '') or '',
        'branch_code':
            (rcp.bank_code if rcp and rcp.bank_code else '') or '',
        'account_holder':
            (rcp.business_name if rcp and rcp.business_name
             else fallback_holder) or '',
    }


def _bank_payload_for_driver(d: DeliveryDriver, paystack_match=None):
    """Common dict for driver bank verification screens."""
    rcp = _active_driver_recipient(d)
    bank = _driver_bank_details(d, rcp=rcp)
    user = d.user
    full_name = (f'{user.first_name or ""} {user.last_name or ""}'.strip()
                 or user.email)
    return {
        'id': str(d.id),
        'kind': 'driver',
        'name': full_name,
        'email': user.email,
        'vehicle_type': d.vehicle_type,
        'identity_verification_status': d.identity_verification_status,
        'bank_name': bank['bank_name'],
        'bank_account_number': bank['account_number'],
        'bank_account_last4':
            bank['account_number'][-4:] if bank['account_number'] else '',
        'bank_branch_code': bank['branch_code'],
        'bank_account_holder': bank['account_holder'],
        'recipient': _recipient_summary(rcp),
        'paystack_match': paystack_match,
    }


def _recipient_summary(rcp):
    if rcp is None:
        return None
    return {
        'id': str(rcp.id),
        'recipient_code': rcp.recipient_code,
        'verification_status': rcp.verification_status,
        'bank_verified': rcp.bank_verified,
        'payout_enabled': rcp.payout_enabled,
        'resolved_account_name': rcp.resolved_account_name,
        'submitted_account_name': rcp.submitted_account_name,
        'notes': rcp.notes,
    }


class VendorBankVerificationListView(APIView):
    """List vendors with bank details captured. Filters:
       ?status=pending|verified|missing|all (default pending)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _bank_can_manage(request):
            return _forbidden()
        from payments.wallet_models import PaystackRecipient

        target = (request.query_params.get('status') or 'pending').lower()
        qs = VendorProfile.objects.select_related('user')

        # A vendor counts as having bank details if EITHER their
        # legacy profile fields are populated OR they have an active
        # PaystackRecipient (the modern wallet-flow submission). The
        # old query only checked the profile fields and so silently
        # hid every wallet-flow vendor from the queue.
        recipient_owner_ids = set(
            PaystackRecipient.objects.filter(
                owner_type=PaystackRecipient.OWNER_VENDOR,
                archived_at__isnull=True,
            ).values_list('owner_id', flat=True)
        )
        verified_owner_ids = set(
            PaystackRecipient.objects.filter(
                owner_type=PaystackRecipient.OWNER_VENDOR,
                archived_at__isnull=True,
                bank_verified=True,
            ).values_list('owner_id', flat=True)
        )

        has_bank_q = (
            ~Q(bank_account_number='') & ~Q(bank_name='')
        ) | Q(id__in=list(recipient_owner_ids))

        if target == 'missing':
            qs = qs.exclude(has_bank_q)
        else:
            qs = qs.filter(has_bank_q)
            if target == 'verified':
                qs = qs.filter(id__in=list(verified_owner_ids))
            elif target == 'pending':
                qs = qs.exclude(id__in=list(verified_owner_ids))

        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(trading_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(bank_account_holder__icontains=search),
            )
        qs = qs.order_by('-updated_at')[:200]
        return Response({
            'results': [_bank_payload_for_vendor(v) for v in qs],
        })


class DriverBankVerificationListView(APIView):
    """Drivers route bank info through the marketplace recipient flow,
    so this list is sourced from `PaystackRecipient` rather than from
    a column on the driver model."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _bank_can_manage(request):
            return _forbidden()
        from payments.wallet_models import PaystackRecipient

        target = (request.query_params.get('status') or 'pending').lower()
        recipients = PaystackRecipient.objects.filter(
            owner_type=PaystackRecipient.OWNER_DRIVER,
            archived_at__isnull=True,
        )
        if target == 'verified':
            recipients = recipients.filter(bank_verified=True)
        elif target == 'pending':
            recipients = recipients.filter(bank_verified=False)
        elif target == 'manual_review':
            recipients = recipients.filter(
                verification_status=PaystackRecipient.VERIFICATION_MANUAL_REVIEW,
            )
        elif target == 'rejected':
            recipients = recipients.filter(
                verification_status=PaystackRecipient.VERIFICATION_FAILED,
            )

        # `PaystackRecipient.owner_id` is a CharField (polymorphic
        # across vendors + drivers), but `DeliveryDriver.id` is a
        # BigAutoField. If any recipient row has a non-numeric
        # owner_id (e.g. a stale row pointing at a deleted UUID-keyed
        # entity) Django raises a 500 when it tries to coerce the
        # whole list. Convert defensively and drop anything that
        # isn't a valid integer.
        driver_pks = []
        for raw in recipients.values_list('owner_id', flat=True):
            try:
                driver_pks.append(int(raw))
            except (TypeError, ValueError):
                continue
        drivers = (
            DeliveryDriver.objects.select_related('user')
            .filter(id__in=driver_pks)
            .order_by('-updated_at')[:200]
        )

        search = (request.query_params.get('search') or '').strip()
        if search:
            drivers = drivers.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(vehicle_registration__icontains=search),
            )

        return Response({
            'results': [_bank_payload_for_driver(d) for d in drivers],
        })


class VendorBankResolveView(APIView):
    """Run Paystack `/bank/resolve` for a vendor and report the match.

    Does NOT change the vendor's verification status — only returns
    the resolved name + fuzzy similarity. The admin uses the result
    to decide whether to approve or reject.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, vendor_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_related('user').get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')
        bank = _vendor_bank_details(v)
        if not (bank['account_number'] and bank['branch_code']):
            return _bad('Vendor has no bank account number or branch code.')

        from payments.paystack import paystack_api
        from payments.bank_verification import names_match
        currency = (request.data.get('currency') or 'ZAR').upper()

        try:
            resolve = paystack_api.resolve_account_number(
                bank['account_number'],
                bank['branch_code'],
                currency=currency,
            )
        except Exception as exc:
            return Response(
                {'error': f'Paystack request failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not resolve.get('status'):
            return Response({
                'resolved': False,
                'paystack_message': resolve.get('message'),
                'vendor': _bank_payload_for_vendor(v),
            })

        data = resolve.get('data') or {}
        resolved_name = (data.get('account_name') or '').strip()
        claimed_name = bank['account_holder']
        matched, similarity = names_match(claimed_name, resolved_name)
        match = {
            'resolved': True,
            'resolved_account_name': resolved_name,
            'submitted_account_holder': claimed_name,
            'similarity': float(similarity),
            'matched': matched,
            'currency': currency,
        }
        return Response({
            **match,
            'vendor': _bank_payload_for_vendor(v, paystack_match=match),
        })


class VendorBankApproveView(APIView):
    """Approve the vendor's bank details. Creates the matching
    `PaystackRecipient` (or admin-approves an existing manual-review
    row) so the marketplace payout engine can transfer to that
    account."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, vendor_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_related('user').get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')

        from payments.bank_verification import (
            verify_and_register, approve_manual_review,
        )
        from payments.wallet_models import PaystackRecipient
        currency = (request.data.get('currency') or 'ZAR').upper()

        existing = _active_vendor_recipient(v)

        # When the vendor already has an active PaystackRecipient
        # (the common case — they submitted via the marketplace
        # wallet sheet), that row IS the source of truth. The legacy
        # VendorProfile.bank_* columns are only populated when the
        # vendor entered details on their profile screen, which is
        # rare now. Either way, fall back through the helper.
        bank = _vendor_bank_details(v, rcp=existing)

        # If we already have a manual_review recipient (typical for
        # ZAR submissions through the wallet flow), admin approves
        # it directly — `approve_manual_review` reads the stored
        # account number / bank code from the recipient itself, so
        # we don't need the profile fields here.
        if existing and existing.verification_status == \
                PaystackRecipient.VERIFICATION_MANUAL_REVIEW:
            try:
                result = approve_manual_review(existing, currency=currency)
            except Exception as exc:
                return Response(
                    {'error': str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        else:
            # Net-new submission — verify_and_register expects the
            # raw account number / bank code, so we validate them
            # here.
            if not (bank['account_number'] and bank['branch_code']):
                return _bad(
                    'Vendor has no bank account number or branch code. '
                    'Ask them to submit bank details through their '
                    'wallet / payout screen first.',
                )
            try:
                result = verify_and_register(
                    owner_type=PaystackRecipient.OWNER_VENDOR,
                    owner_id=str(v.id),
                    business_name=bank['account_holder'],
                    bank_code=bank['branch_code'],
                    bank_name=bank['bank_name'],
                    account_number=bank['account_number'],
                    currency=currency,
                )
            except Exception as exc:
                return Response(
                    {'error': str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({
            'verified': result.verified,
            'similarity': float(result.similarity),
            'resolved_account_name': result.resolved_name,
            'error': result.error,
            'vendor': _bank_payload_for_vendor(v),
        })


class VendorBankRejectView(APIView):
    """Reject the vendor's bank details — archives the active
    recipient (if any) and flags the vendor for re-submission."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, vendor_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            v = VendorProfile.objects.select_related('user').get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _missing('Vendor')
        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return _bad("Rejection 'reason' is required.")

        from payments.wallet_models import PaystackRecipient
        rcp = PaystackRecipient.objects.filter(
            owner_type=PaystackRecipient.OWNER_VENDOR,
            owner_id=str(v.id),
            archived_at__isnull=True,
        ).first()
        if rcp is not None:
            rcp.verification_status = PaystackRecipient.VERIFICATION_FAILED
            rcp.bank_verified = False
            rcp.payout_enabled = False
            rcp.notes = (rcp.notes + f'\n[rejected by admin] {reason}').strip()
            rcp.save(update_fields=[
                'verification_status', 'bank_verified', 'payout_enabled',
                'notes', 'updated_at',
            ])
        return Response(_bank_payload_for_vendor(v))


class DriverBankResolveView(APIView):
    """Run Paystack `/bank/resolve` for a driver and report the
    match. Mirrors `VendorBankResolveView` but sources the bank
    details from the driver's active PaystackRecipient.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, driver_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_related('user').get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')
        bank = _driver_bank_details(d)
        if not (bank['account_number'] and bank['branch_code']):
            return _bad('Driver has no bank account number or branch code.')

        from payments.paystack import paystack_api
        from payments.bank_verification import names_match
        currency = (request.data.get('currency') or 'ZAR').upper()

        try:
            resolve = paystack_api.resolve_account_number(
                bank['account_number'],
                bank['branch_code'],
                currency=currency,
            )
        except Exception as exc:
            return Response(
                {'error': f'Paystack request failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not resolve.get('status'):
            return Response({
                'resolved': False,
                'paystack_message': resolve.get('message'),
                'driver': _bank_payload_for_driver(d),
            })

        data = resolve.get('data') or {}
        resolved_name = (data.get('account_name') or '').strip()
        claimed_name = bank['account_holder']
        matched, similarity = names_match(claimed_name, resolved_name)
        match = {
            'resolved': True,
            'resolved_account_name': resolved_name,
            'submitted_account_holder': claimed_name,
            'similarity': float(similarity),
            'matched': matched,
            'currency': currency,
        }
        return Response({
            **match,
            'driver': _bank_payload_for_driver(d, paystack_match=match),
        })


class DriverBankApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, driver_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_related('user').get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')
        from payments.wallet_models import PaystackRecipient
        from payments.bank_verification import (
            approve_manual_review, verify_and_register,
        )

        rcp = _active_driver_recipient(d)
        currency = (request.data.get('currency') or 'ZAR').upper()

        # Three scenarios:
        #
        #   • Already verified           → no-op success.
        #   • Recipient in manual_review → admin approves directly
        #                                  (typical ZAR wallet-flow
        #                                  case — works without
        #                                  re-hitting Paystack).
        #   • No recipient yet (or stale failed row) → mint a fresh
        #     one if the driver provided account details somehow,
        #     otherwise return an actionable error.
        if rcp is not None and rcp.bank_verified:
            return Response({
                'verified': True,
                'similarity': 1.0,
                'resolved_account_name': rcp.resolved_account_name,
                'error': None,
                'driver': _bank_payload_for_driver(d),
            })

        if rcp is not None and rcp.verification_status == \
                PaystackRecipient.VERIFICATION_MANUAL_REVIEW:
            try:
                result = approve_manual_review(rcp, currency=currency)
            except Exception as exc:
                return Response(
                    {'error': str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        else:
            bank = _driver_bank_details(d, rcp=rcp)
            if not (bank['account_number'] and bank['branch_code']):
                return _bad(
                    'Driver has not submitted bank details yet. '
                    'Ask them to add a bank account through their '
                    'wallet / payout screen first.',
                )
            try:
                result = verify_and_register(
                    owner_type=PaystackRecipient.OWNER_DRIVER,
                    owner_id=str(d.id),
                    business_name=bank['account_holder'],
                    bank_code=bank['branch_code'],
                    bank_name=bank['bank_name'],
                    account_number=bank['account_number'],
                    currency=currency,
                )
            except Exception as exc:
                return Response(
                    {'error': str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({
            'verified': result.verified,
            'similarity': float(result.similarity),
            'resolved_account_name': result.resolved_name,
            'error': result.error,
            'driver': _bank_payload_for_driver(d),
        })


class DriverBankRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, driver_id):
        if not _bank_can_manage(request):
            return _forbidden()
        try:
            d = DeliveryDriver.objects.select_related('user').get(id=driver_id)
        except DeliveryDriver.DoesNotExist:
            return _missing('Driver')
        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return _bad("Rejection 'reason' is required.")
        from payments.wallet_models import PaystackRecipient
        rcp = PaystackRecipient.objects.filter(
            owner_type=PaystackRecipient.OWNER_DRIVER,
            owner_id=str(d.id),
            archived_at__isnull=True,
        ).first()
        if rcp is not None:
            rcp.verification_status = PaystackRecipient.VERIFICATION_FAILED
            rcp.bank_verified = False
            rcp.payout_enabled = False
            rcp.notes = (rcp.notes + f'\n[rejected by admin] {reason}').strip()
            rcp.save(update_fields=[
                'verification_status', 'bank_verified', 'payout_enabled',
                'notes', 'updated_at',
            ])
        return Response(_bank_payload_for_driver(d))

"""
Views for business app
"""
import logging

from rest_framework import viewsets, generics, serializers, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from .verification_workflow import (invalidate_vendor, sync_review_state, VENDOR_EVIDENCE_FIELDS)
from django.utils import timezone

from .models import (
    IndividualVendorProfile, BusinessVendorProfile, VendorProfile,
    VendorDocument, VettingApplication, Address,
    BusinessFollower,
)
from .serializers import (
    IndividualVendorProfileSerializer, IndividualVendorProfileCreateSerializer,
    IndividualVendorProfileUpdateSerializer,
    BusinessVendorProfileSerializer, BusinessVendorProfileCreateSerializer,
    BusinessVendorProfileUpdateSerializer,
    VendorProfileSerializer,
    VendorDocumentSerializer, VendorDocumentAdminSerializer,
    VettingApplicationSerializer, VettingApplicationAdminSerializer,
    AddressSerializer,
    BusinessFollowerSerializer, BusinessFollowerCreateSerializer,
    _resolve_vendor_user,
)
from core.permissions import IsOwnerOrAdmin, IsAdminUser, IsVendorOrAdmin

User = get_user_model()
logger = logging.getLogger('sanoa.business')


def _is_platform_admin(user):
    """True for Django staff AND platform_admin users."""
    profile = getattr(user, 'admin_profile', None)
    return user.is_superuser or user.is_staff or bool(profile and profile.has_permission('manage_vendors'))


# Legacy field name → unified VendorProfile field name. Only fields that
# exist on BOTH models are copied; anything missing is skipped safely.
_LEGACY_FIELD_MAP = {
    # shared / naming
    'store_name': 'name',
    'store_description': 'description',
    'store_logo': 'logo',
    'business_name': 'name',
    'business_trading_name': 'trading_name',
    'business_description': 'description',
    'business_type': 'business_type',
    'business_category': 'business_category',
    'vendor_type': 'vendor_type',
    'name': 'name',
    'trading_name': 'trading_name',
    'description': 'description',
    'business_logo': 'logo',
    'logo': 'logo',
    # individual KYC
    'id_number': 'id_number',
    'id_document': 'id_document',
    'proof_of_address': 'proof_of_address',
    'selfie_with_id': 'selfie_with_id',
    # business KYC
    'cipc_registration_number': 'cipc_registration_number',
    'cipc_document': 'cipc_document',
    'tax_number': 'tax_number',
    'tax_clearance_certificate': 'tax_clearance_certificate',
    'vat_number': 'vat_number',
    'bee_certificate': 'bee_certificate',
    'owner_full_name': 'owner_full_name',
    'owner_id_number': 'owner_id_number',
    'owner_id_document': 'owner_id_document',
    'owner_proof_of_address': 'owner_proof_of_address',
    # address
    'street_address': 'street_address',
    'city': 'city',
    'province': 'province',
    'postal_code': 'postal_code',
    'country': 'country',
    'latitude': 'latitude',
    'longitude': 'longitude',
    # banking
    'bank_name': 'bank_name',
    'bank_account_number': 'bank_account_number',
    'bank_branch_code': 'bank_branch_code',
    'bank_account_holder': 'bank_account_holder',
}


def _is_unset(instance, field_name):
    """True when a field holds nothing the user actually chose.

    Empty/None obviously counts, and so does a value still equal to the
    field's model default — that's a placeholder the vendor never picked,
    so registration input is free to replace it.
    """
    value = getattr(instance, field_name, None)
    if value in (None, ''):
        return True
    try:
        default = instance._meta.get_field(field_name).get_default()
    except Exception:
        return False
    return value == default


def sync_legacy_profile_to_unified(legacy, user, profile_type, changed_fields=None):
    """Mirror a legacy Individual/Business vendor profile onto the unified
    ``VendorProfile``.

    Registration writes to the legacy tables, but the vetting checklist,
    the store banner, the product gate and the admin vetting board all read
    the unified model. Without this mirror a business vendor would be judged
    against individual requirements and their uploaded CIPC / owner
    documents would never be seen.

    Runs inside the caller transaction; synchronization failure rolls back onboarding.
    """
    try:
        unified, _ = VendorProfile.objects.get_or_create(
            user=user, defaults={'profile_type': profile_type, 'name': ''},
        )
        changed = []
        if unified.profile_type != profile_type:
            changed.append('profile_type')
            unified.profile_type = profile_type
        for src, dest in _LEGACY_FIELD_MAP.items():
            if changed_fields is not None and src not in changed_fields:
                continue
            if not hasattr(legacy, src) or not hasattr(unified, dest):
                continue
            value = getattr(legacy, src, None)
            if changed_fields is None and value in (None, ''):
                continue
            # Don't clobber something already captured on the unified row —
            # but a field still sitting on its MODEL DEFAULT was never
            # captured, it's just a placeholder. Treating the default as
            # "already set" is what silently discarded a vendor's
            # `business_category='restaurant'` choice (default 'retail'),
            # leaving food businesses stuck on the retail storefront.
            if (changed_fields is not None or _is_unset(unified, dest)) and getattr(unified, dest) != value:
                setattr(unified, dest, value)
                changed.append(dest)
        if changed_fields and set(changed) & VENDOR_EVIDENCE_FIELDS:
            invalidate_vendor(unified)
        unified.save()
        sync_review_state(unified)
        return unified
    except Exception:
        logger.exception(
            'Could not mirror legacy vendor profile %s onto the unified '
            'VendorProfile for user %s', getattr(legacy, 'pk', '?'),
            getattr(user, 'pk', '?'),
        )
        raise


# =============================================================================
# Individual Vendor Views
# =============================================================================

class IndividualVendorProfileViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve', 'create', 'update', 'partial_update', 'documents', 'vetting_status', 'upload_document')
    """
    ViewSet for individual vendor profiles (tuck shops, street vendors, etc.).
    Creating a profile automatically triggers owner vetting.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'create':
            return IndividualVendorProfileCreateSerializer
        if self.action in ('update', 'partial_update'):
            return IndividualVendorProfileUpdateSerializer
        return IndividualVendorProfileSerializer

    def get_queryset(self):
        if _is_platform_admin(self.request.user):
            return IndividualVendorProfile.objects.all().select_related('user')
        return IndividualVendorProfile.objects.filter(
            user=self.request.user
        ).select_related('user')

    @transaction.atomic
    def perform_update(self, serializer):
        changed = set(serializer.validated_data)
        legacy = serializer.save()
        sync_legacy_profile_to_unified(legacy, legacy.user, 'individual', changed_fields=changed)

    @transaction.atomic
    def perform_create(self, serializer):
        vendor = serializer.save(user=self.request.user)
        # Auto-generate QR code linked to the vendor
        vendor.generate_qr_code()
        vendor.save()
        # Auto-create owner vetting application
        VettingApplication.objects.create(
            individual_vendor=vendor,
            vetting_type='individual_owner',
            status='pending',
        )
        # Mirror onto the unified VendorProfile the vetting flow reads.
        sync_legacy_profile_to_unified(vendor, self.request.user, 'individual')
        # Stash the saved instance so `create()` can re-serialize it
        # through the full read serializer below.
        self._created_instance = vendor

    def create(self, request, *args, **kwargs):
        # DRF's default `create` echoes the *create* serializer's data
        # back to the client — which only contains the input fields and
        # is missing `id`, `user_email`, `verification_status`, etc.
        # The Flutter parser non-null casts those, throws, and surfaces
        # a generic "Profile Creation Failed" toast even though the row
        # saved fine. Re-run the full read serializer over the saved
        # instance so the response matches what the client expects.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        read_data = IndividualVendorProfileSerializer(
            self._created_instance, context=self.get_serializer_context(),
        ).data
        return Response(read_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['get'])
    def vetting_status(self, request, pk=None):
        """Get the vetting status for this vendor"""
        vendor = self.get_object()
        applications = vendor.vetting_applications.all()
        serializer = VettingApplicationSerializer(applications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """List additional documents for this vendor"""
        vendor = self.get_object()
        docs = vendor.documents.all()
        serializer = VendorDocumentSerializer(docs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='upload-document')
    def upload_document(self, request, pk=None):
        """Upload an additional supporting document"""
        vendor = self.get_object()
        serializer = VendorDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(individual_vendor=vendor)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# =============================================================================
# Business Vendor Views
# =============================================================================

class BusinessVendorProfileViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve', 'create', 'update', 'partial_update', 'documents', 'vetting_status', 'upload_document')
    """
    ViewSet for business vendor profiles (with CIPC / business registration).
    Creating a profile automatically triggers both owner and business vetting.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'create':
            return BusinessVendorProfileCreateSerializer
        if self.action in ('update', 'partial_update'):
            return BusinessVendorProfileUpdateSerializer
        return BusinessVendorProfileSerializer

    def get_queryset(self):
        if _is_platform_admin(self.request.user):
            return BusinessVendorProfile.objects.all().select_related('user')
        return BusinessVendorProfile.objects.filter(
            user=self.request.user
        ).select_related('user')

    @transaction.atomic
    def perform_update(self, serializer):
        changed = set(serializer.validated_data)
        legacy = serializer.save()
        sync_legacy_profile_to_unified(legacy, legacy.user, 'business', changed_fields=changed)

    @transaction.atomic
    def perform_create(self, serializer):
        vendor = serializer.save(user=self.request.user)
        # Auto-generate QR code linked to the business
        vendor.generate_qr_code()
        vendor.save()
        # Auto-create both owner AND business vetting applications
        VettingApplication.objects.bulk_create([
            VettingApplication(
                business_vendor=vendor,
                vetting_type='business_owner',
                status='pending',
            ),
            VettingApplication(
                business_vendor=vendor,
                vetting_type='business_entity',
                status='pending',
            ),
        ])
        # Mirror onto the unified VendorProfile — that's what the vetting
        # checklist, the store banner, the product gate and the admin
        # vetting board all read. Without this a business vendor would be
        # judged against INDIVIDUAL requirements (ID + selfie) and their
        # CIPC / owner documents would be invisible to vetting.
        sync_legacy_profile_to_unified(vendor, self.request.user, 'business')
        self._created_instance = vendor

    def create(self, request, *args, **kwargs):
        # Same rationale as IndividualVendorProfileViewSet.create —
        # the create serializer doesn't expose enough fields for the
        # frontend parser, so re-serialize through the full read one.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        read_data = BusinessVendorProfileSerializer(
            self._created_instance, context=self.get_serializer_context(),
        ).data
        return Response(read_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['get'])
    def vetting_status(self, request, pk=None):
        """Get the vetting status for this vendor"""
        vendor = self.get_object()
        applications = vendor.vetting_applications.all()
        serializer = VettingApplicationSerializer(applications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """List additional documents for this vendor"""
        vendor = self.get_object()
        docs = vendor.documents.all()
        serializer = VendorDocumentSerializer(docs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='upload-document')
    def upload_document(self, request, pk=None):
        """Upload an additional supporting document"""
        vendor = self.get_object()
        serializer = VendorDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(business_vendor=vendor)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# =============================================================================
# Vetting Administration Views
# =============================================================================

class VettingApplicationViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve')
    """
    Admin viewset for managing vetting applications.
    Vendors can only view their own applications. Admins can review all.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if _is_platform_admin(self.request.user):
            return VettingApplicationAdminSerializer
        return VettingApplicationSerializer

    def get_queryset(self):
        qs = VettingApplication.objects.all().select_related(
            'individual_vendor__user', 'business_vendor__user', 'assigned_to'
        )
        if _is_platform_admin(self.request.user):
            status_filter = self.request.query_params.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
            vetting_type = self.request.query_params.get('vetting_type')
            if vetting_type:
                qs = qs.filter(vetting_type=vetting_type)
            return qs
        # Vendors see only their own
        return qs.filter(
            Q(individual_vendor__user=self.request.user) |
            Q(business_vendor__user=self.request.user)
        )

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'approve', 'reject']:
            from core.permissions import IsPlatformAdmin
            return [permissions.IsAuthenticated(), IsPlatformAdmin()]
        return super().get_permissions()

    http_method_names = ['get', 'post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Applications are created during onboarding.'}, status=405)

    def _review(self, request, decision):
        from platform_admin.vetting_views import VendorVettingActionView
        application = self.get_object()
        legacy = application.individual_vendor or application.business_vendor
        unified = VendorProfile.objects.filter(user=legacy.user).first()
        if unified is None:
            return Response({'detail': 'Complete the vendor profile before review.'}, status=400)
        # Reuse the same completeness, permission, transition and audit checks.
        request._full_data = {**request.data, 'action': decision}
        return VendorVettingActionView().post(request, unified.pk)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._review(request, 'approve')

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._review(request, 'reject')

    @action(detail=True, methods=['post'], url_path='request-resubmission')
    def request_resubmission(self, request, pk=None):
        return self._review(request, 'request_info')


# =============================================================================
# Vendor Document Admin Views
# =============================================================================

class VendorDocumentViewSet(viewsets.ModelViewSet):
    """Admin viewset for reviewing vendor documents"""
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    serializer_class = VendorDocumentAdminSerializer

    def get_queryset(self):
        qs = VendorDocument.objects.all().select_related(
            'individual_vendor__user', 'business_vendor__user', 'reviewed_by'
        )
        doc_status = self.request.query_params.get('status')
        if doc_status:
            qs = qs.filter(status=doc_status)
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a document"""
        doc = self.get_object()
        doc.status = 'approved'
        doc.review_notes = request.data.get('notes', '')
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.save()
        return Response(VendorDocumentAdminSerializer(doc).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a document"""
        doc = self.get_object()
        doc.status = 'rejected'
        doc.review_notes = request.data.get('notes', '')
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.save()
        return Response(VendorDocumentAdminSerializer(doc).data)


# =============================================================================
# Address Views
# =============================================================================

def _vendor_profile_addresses(user):
    """
    Build address-shaped dicts from a vendor's profile.

    Priority order:
      1. Explicit Address rows linked to the VendorProfile  ← proper address table
      2. Address fields embedded directly on VendorProfile  ← filled during onboarding
      3. Legacy IndividualVendorProfile / BusinessVendorProfile fields

    Returns [] if the user has no vendor profile of any kind.
    """
    def _decimal(value):
        return str(value) if value is not None else None

    vp = getattr(user, 'vendor_profile', None)
    if vp is not None:
        # ── 1. Explicit Address rows (vendor saved via AddressViewSet) ──────────
        address_rows = list(vp.addresses.order_by('-is_default', '-created_at'))
        if address_rows:
            results = []
            for addr in address_rows:
                results.append({
                    'id': str(addr.id),
                    'source': 'vendor_address',
                    'profile_type': vp.profile_type,
                    'address_type': addr.address_type,
                    'full_name': addr.full_name,
                    'phone_number': addr.phone_number or user.phone_number,
                    'street_address': addr.street_address,
                    'apartment_number': addr.apartment_number,
                    'city': addr.city,
                    'state_province': addr.state_province,
                    'postal_code': addr.postal_code,
                    'country': addr.country,
                    'latitude': _decimal(addr.latitude),
                    'longitude': _decimal(addr.longitude),
                    'is_default': addr.is_default,
                    'delivery_instructions': addr.delivery_instructions,
                })
            return results

        # ── 2. Embedded VendorProfile address fields ────────────────────────────
        if vp.street_address or vp.city or vp.latitude:
            return [{
                'id': str(vp.id),
                'source': 'vendor_profile',
                'profile_type': vp.profile_type,
                'address_type': 'business',
                'full_name': vp.trading_name or vp.name,
                'phone_number': user.phone_number,
                'street_address': vp.street_address,
                'apartment_number': '',
                'city': vp.city,
                'state_province': vp.province,
                'postal_code': vp.postal_code,
                'country': vp.country,
                'latitude': _decimal(vp.latitude),
                'longitude': _decimal(vp.longitude),
                'is_default': True,
                'delivery_instructions': '',
            }]

        # VendorProfile exists but has no address data at all — fall through
        # to legacy profiles below.

    results = []
    ivp = getattr(user, 'individual_vendor_profile', None)
    if ivp is not None:
        results.append({
            'id': ivp.id,
            'source': 'individual_vendor_profile',
            'profile_type': 'individual',
            'address_type': 'business',
            'full_name': ivp.store_name,
            'phone_number': user.phone_number,
            'street_address': ivp.trading_address,
            'apartment_number': '',
            'city': ivp.trading_city,
            'state_province': ivp.trading_province,
            'postal_code': ivp.trading_postal_code,
            'country': 'South Africa',
            'latitude': _decimal(ivp.latitude),
            'longitude': _decimal(ivp.longitude),
            'is_default': True,
            'delivery_instructions': '',
        })
    bvp = getattr(user, 'business_vendor_profile', None)
    if bvp is not None:
        results.append({
            'id': bvp.id,
            'source': 'business_vendor_profile',
            'profile_type': 'business',
            'address_type': 'business',
            'full_name': bvp.business_trading_name or bvp.business_name,
            'phone_number': user.phone_number,
            'street_address': bvp.business_street_address,
            'apartment_number': '',
            'city': bvp.business_city,
            'state_province': bvp.business_province,
            'postal_code': bvp.business_postal_code,
            'country': bvp.business_country,
            'latitude': _decimal(bvp.latitude),
            'longitude': _decimal(bvp.longitude),
            'is_default': True,
            'delivery_instructions': '',
        })
    return results


class AddressViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve', 'create', 'update', 'partial_update', 'destroy')
    """
    Vendor business addresses (linked to VendorProfile).

    A vendor can CRUD their own business addresses here. Staff can see
    all. Customer shipping addresses live in a separate endpoint:
    `/api/orders/shipping-addresses/`.
    """
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Address.objects.select_related('vendor', 'vendor__user')
        if self.request.user.is_staff:
            return qs
        return qs.filter(vendor__user=self.request.user)

    def perform_create(self, serializer):
        vendor_profile = getattr(self.request.user, 'vendor_profile', None)
        if vendor_profile is None:
            raise permissions.exceptions.PermissionDenied(
                'You must have a vendor profile to create a business address.'
            )
        serializer.save(vendor=vendor_profile)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set an address as default"""
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response(AddressSerializer(address).data)

    @action(detail=False, methods=['get'], url_path='by-user/(?P<user_id>[^/.]+)')
    def by_user(self, request, user_id=None):
        """
        List addresses for a specific user by id.

        - Customers: returns personal shipping addresses from
          `orders.ShippingAddress` (same rows the customer CRUDs at
          `/api/orders/shipping-addresses/`).
        - Vendors (individual or business): returns the vendor's business
          / trading address(es) pulled from their vendor profile.
        """
        try:
            from django.db.models import Prefetch
            from .models import Address as VendorAddressModel
            user = User.objects.select_related(
                'vendor_profile',
                'individual_vendor_profile',
                'business_vendor_profile',
            ).prefetch_related(
                Prefetch(
                    'vendor_profile__addresses',
                    queryset=VendorAddressModel.objects.order_by('-is_default', '-created_at'),
                )
            ).get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.user_type == 'vendor':
            results = _vendor_profile_addresses(user)
            # Report whichever source was actually used
            source = results[0]['source'] if results else 'vendor_profile'
        else:
            from orders.models import ShippingAddress
            from orders.serializers import ShippingAddressSerializer
            qs = ShippingAddress.objects.filter(user=user).order_by(
                '-is_default', '-created_at'
            )
            results = ShippingAddressSerializer(qs, many=True).data
            for item in results:
                item['source'] = 'shipping_address'
            source = 'shipping_address'

        return Response({
            'user_id': user.id,
            'user_email': user.email,
            'user_type': user.user_type,
            'source': source,
            'count': len(results),
            'results': results,
        })


# =============================================================================
# Store Discovery Views
# =============================================================================

class StoreDiscoveryView(generics.GenericAPIView):
    """
    Discover stores/vendors based on user interest categories and proximity.
    Nearby stores (within 15km) sorted by distance.
    Recommended stores sorted by category match, rating, and distance.

    Query params:
    - latitude: override user's stored latitude
    - longitude: override user's stored longitude
    - business_category: 'retail' or 'restaurant' — filters stores to the
      mode the frontend toggle is currently showing (Shopping vs Restaurants).
    """
    permission_classes = [permissions.IsAuthenticated]

    ALLOWED_BUSINESS_CATEGORIES = {'retail', 'restaurant'}

    def get(self, request):
        from core.recommendations import StoreDiscoveryEngine

        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        business_category = request.query_params.get('business_category')
        if business_category and business_category not in self.ALLOWED_BUSINESS_CATEGORIES:
            return Response(
                {'error': "business_category must be one of 'retail' or 'restaurant'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engine = StoreDiscoveryEngine()
        results = engine.discover_stores(
            user=request.user,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            business_category=business_category,
        )
        return Response(results)


# =============================================================================
# Business Follower Views
# =============================================================================

class BusinessFollowerViewSet(viewsets.GenericViewSet):
    """
    Follow/unfollow vendors and list followed businesses.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BusinessFollower.objects.filter(
            user=self.request.user
        ).select_related('vendor')

    @action(detail=False, methods=['get'], url_path='my-following')
    def my_following(self, request):
        """List all businesses the current user follows."""
        queryset = self.get_queryset()
        serializer = BusinessFollowerSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def follow(self, request):
        """Follow a vendor/business."""
        serializer = BusinessFollowerCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        follower = serializer.save()
        return Response(
            BusinessFollowerSerializer(follower).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def unfollow(self, request):
        """Unfollow a vendor/business. Body: {"vendor_id": "<UUID or int>"}"""
        vendor_user = _resolve_vendor_user(request.data.get('vendor_id'))
        if vendor_user is None:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        deleted, _ = BusinessFollower.objects.filter(
            user=request.user, vendor=vendor_user
        ).delete()
        if deleted:
            return Response({'status': 'unfollowed'})
        return Response(
            {'error': 'You are not following this business.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=['get'], url_path='followers/(?P<vendor_id>[^/.]+)')
    def vendor_followers(self, request, vendor_id=None):
        """Get follower count for a vendor (public)."""
        vendor_user = _resolve_vendor_user(vendor_id)
        if vendor_user is None:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        count = BusinessFollower.objects.filter(vendor=vendor_user).count()
        is_following = BusinessFollower.objects.filter(
            user=request.user, vendor=vendor_user
        ).exists() if request.user.is_authenticated else False
        return Response({
            'vendor_id': vendor_id,
            'follower_count': count,
            'is_following': is_following,
        })


# =============================================================================
# Unified VendorProfile
# =============================================================================

class VendorProfileViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve', 'create', 'update', 'partial_update', 'me')
    """Unified CRUD for a vendor's single profile."""
    serializer_class = VendorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = VendorProfile.objects.select_related('user').prefetch_related('categories')
        user = self.request.user
        if _is_platform_admin(user):
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        # One profile per user
        if VendorProfile.objects.filter(user=self.request.user).exists():
            raise serializers.ValidationError(
                {'detail': 'Vendor profile already exists for this user.'}
            )
        profile = serializer.save(user=self.request.user)
        self._sync_checklist(profile)

    def perform_update(self, serializer):
        profile = serializer.save()
        self._sync_checklist(profile)

    @staticmethod
    def _sync_checklist(profile):
        """Documents may have changed — retick the vetting checklist so the
        admin board reflects what's actually on file."""
        from business.vetting_sync import sync_vetting_application
        sync_vetting_application(profile)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Return the authenticated user's vendor profile, enriched with live
        stats (real revenue / orders / rating) and structured Mon–Sun hours so
        the profile screen shows accurate figures rather than cached counters."""
        profile = (
            VendorProfile.objects
            .select_related('user')
            .prefetch_related('categories')
            .filter(user=request.user)
            .first()
        )
        if not profile:
            return Response(
                {'detail': 'No vendor profile for this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        from .store_ops import compute_vendor_stats, serialize_hours
        data = VendorProfileSerializer(profile, context={'request': request}).data
        data['stats'] = compute_vendor_stats(profile)
        data['operating_hours_detail'] = serialize_hours(profile.opening_hours)
        return Response(data)

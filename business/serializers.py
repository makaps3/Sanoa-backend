from core.document_validation import DocumentValidationMixin
from django.db import transaction
from .verification_workflow import evidence_changed, invalidate_vendor, sync_review_state
"""
Serializers for business app
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    IndividualVendorProfile, BusinessVendorProfile, VendorProfile,
    VendorDocument, VettingApplication, Address,
    BusinessFollower,
)

User = get_user_model()


# =============================================================================
# Choice normalisation
# =============================================================================
# Clients (the Flutter app, the website) historically posted the *human
# label* — "Private Company (Pty Ltd)" — where the model stores a code
# (`pty_ltd`), producing `"…" is not a valid choice`. Both clients now send
# codes, but older builds and cached web bundles are still out there, so we
# accept either form and normalise to the code.

_BUSINESS_TYPE_ALIASES = {
    'sole proprietorship': 'sole_proprietor',
    'sole proprietor': 'sole_proprietor',
    'sole trader': 'sole_proprietor',
    'partnership': 'partnership',
    'private company (pty ltd)': 'pty_ltd',
    'private company': 'pty_ltd',
    'pty ltd': 'pty_ltd',
    '(pty) ltd': 'pty_ltd',
    'close corporation (cc)': 'cc',
    'close corporation': 'cc',
    'non-profit company (npc)': 'npc',
    'non-profit organization': 'npc',
    'non-profit organisation': 'npc',
    'non profit company': 'npc',
    'npo': 'npc',
    'co-operative': 'cooperative',
    'cooperative': 'cooperative',
    'public company': 'other',
    'other': 'other',
}


def normalise_choice(value, valid_codes, aliases):
    """Return a valid choice code for `value`, accepting the code itself,
    its human label, or a known alias. Returns the input unchanged when
    nothing matches so DRF still raises its normal validation error."""
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if raw in valid_codes:
        return raw
    lowered = raw.lower()
    if lowered in valid_codes:
        return lowered
    if lowered in aliases:
        return aliases[lowered]
    # Fall back to matching the model's own display label.
    for code, label in valid_codes.items():
        if str(label).lower() == lowered:
            return code
    return value


class _BusinessTypeToleranceMixin:
    """Accept a ``business_type`` code OR its human label.

    The rewrite happens in ``to_internal_value`` because DRF's ChoiceField
    rejects an unknown value during field validation, i.e. *before* any
    ``validate_business_type`` hook would ever run.
    """

    def to_internal_value(self, data):
        raw = data.get('business_type') if hasattr(data, 'get') else None
        if isinstance(raw, str) and raw:
            codes = dict(self.Meta.model.BUSINESS_TYPE_CHOICES)
            fixed = normalise_choice(raw, codes, _BUSINESS_TYPE_ALIASES)
            if fixed != raw:
                # QueryDict (multipart/form posts) is immutable — copy first.
                data = data.copy() if hasattr(data, 'copy') else dict(data)
                data['business_type'] = fixed
        return super().to_internal_value(data)


# =============================================================================
# Individual Vendor Serializers
# =============================================================================

class CategorySummarySerializer(serializers.Serializer):
    """Lightweight category serializer for embedding in vendor profiles."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField()
    image = serializers.ImageField()


class IndividualVendorProfileSerializer(serializers.ModelSerializer):
    """Serializer for IndividualVendorProfile - vendors without CIPC"""

    user_email = serializers.CharField(source='user.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(read_only=True)
    is_open_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = IndividualVendorProfile
        fields = [
            'id', 'user_email', 'owner_name',
            # Vendor type / storefront mode
            'vendor_type', 'business_category',
            # Store info
            'store_name', 'store_description', 'store_logo',
            # QR Code
            'qr_code', 'qr_code_identifier',
            # Owner documents (for vetting)
            'id_number', 'id_document', 'proof_of_address', 'selfie_with_id',
            # Owner role on their own team
            'role', 'department', 'role_title', 'status',
            # Verification
            'verification_status', 'rejection_reason', 'verified_at', 'is_verified',
            # Metrics
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            # Settings
            'commission_rate', 'store_active', 'accepts_returns', 'return_window_days',
            # Opening hours / restaurant availability
            'opening_hours', 'is_temporarily_closed', 'is_open_now',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'qr_code', 'qr_code_identifier',
            'verification_status', 'rejection_reason', 'verified_at',
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            'commission_rate', 'store_active', 'is_open_now',
            'created_at', 'updated_at',
        ]

    def get_owner_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


class IndividualVendorProfileCreateSerializer(DocumentValidationMixin, serializers.ModelSerializer):
    """Serializer for creating an individual vendor profile"""

    class Meta:
        model = IndividualVendorProfile
        fields = [
            'vendor_type', 'business_category',
            'store_name', 'store_description', 'store_logo',
            'id_number', 'id_document', 'proof_of_address', 'selfie_with_id',
            'role', 'department', 'role_title',
        ]

    def validate(self, data):
        data = super().validate(data)
        user = self.context['request'].user
        if user.user_type != 'vendor':
            raise serializers.ValidationError("Only users with vendor account type can create a vendor profile.")
        if IndividualVendorProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("You already have an individual vendor profile.")
        if BusinessVendorProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "You already have a business vendor profile. A user can only have one vendor profile."
            )
        return data


class IndividualVendorProfileUpdateSerializer(DocumentValidationMixin, serializers.ModelSerializer):
    """Update an individual vendor profile. Banking handled via Paystack subaccount."""

    class Meta:
        model = IndividualVendorProfile
        fields = [
            'vendor_type', 'business_category',
            'store_name', 'store_description', 'store_logo',
            'id_number', 'id_document', 'proof_of_address', 'selfie_with_id',
            'opening_hours', 'is_temporarily_closed',
            'accepts_returns', 'return_window_days',
            'role', 'department', 'role_title',
        ]


# =============================================================================
# Business Vendor Serializers
# =============================================================================

class BusinessVendorProfileSerializer(serializers.ModelSerializer):
    """Serializer for BusinessVendorProfile - vendors with CIPC / business docs"""

    user_email = serializers.CharField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_fully_vetted = serializers.BooleanField(read_only=True)
    is_open_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = BusinessVendorProfile
        fields = [
            'id', 'user_email',
            # Business identity
            'business_name', 'business_trading_name', 'business_type',
            'business_category',
            'business_description', 'business_logo', 'business_website',
            # QR Code
            'qr_code', 'qr_code_identifier',
            # CIPC and registration
            'cipc_registration_number', 'cipc_document',
            'tax_number', 'tax_clearance_certificate', 'vat_number', 'bee_certificate',
            # Owner details
            'owner_full_name', 'owner_id_number', 'owner_id_document', 'owner_proof_of_address',
            # Owner role on their own team
            'role', 'department', 'role_title', 'status',
            # Verification
            'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
            'rejection_reason', 'verified_at', 'is_verified', 'is_fully_vetted',
            # Metrics
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            # Settings
            'commission_rate', 'store_active', 'accepts_returns', 'return_window_days',
            # Opening hours / restaurant availability
            'opening_hours', 'is_temporarily_closed', 'is_open_now',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'qr_code', 'qr_code_identifier',
            'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
            'rejection_reason', 'verified_at',
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            'commission_rate', 'store_active', 'is_open_now',
            'created_at', 'updated_at',
        ]


class BusinessVendorProfileCreateSerializer(DocumentValidationMixin, _BusinessTypeToleranceMixin,
                                            serializers.ModelSerializer):
    """Serializer for creating a business vendor profile"""

    class Meta:
        model = BusinessVendorProfile
        fields = [
            'business_name', 'business_trading_name', 'business_type',
            'business_category',
            'business_description', 'business_logo', 'business_website',
            'cipc_registration_number', 'cipc_document',
            'tax_number', 'tax_clearance_certificate', 'vat_number', 'bee_certificate',
            'owner_full_name', 'owner_id_number', 'owner_id_document', 'owner_proof_of_address',
            'role', 'department', 'role_title',
        ]

    def validate(self, data):
        data = super().validate(data)
        user = self.context['request'].user
        if user.user_type != 'vendor':
            raise serializers.ValidationError("Only users with vendor account type can create a vendor profile.")
        if BusinessVendorProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("You already have a business vendor profile.")
        if IndividualVendorProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "You already have an individual vendor profile. A user can only have one vendor profile."
            )
        for field in ('cipc_registration_number', 'cipc_document'):
            if not data.get(field):
                raise serializers.ValidationError({field: 'Required for business vendors.'})
        return data


class BusinessVendorProfileUpdateSerializer(DocumentValidationMixin, _BusinessTypeToleranceMixin,
                                            serializers.ModelSerializer):
    """Update a business vendor profile. Banking handled via Paystack subaccount."""

    class Meta:
        model = BusinessVendorProfile
        fields = [
            'business_name', 'business_trading_name', 'business_type',
            'business_category',
            'business_description', 'business_logo', 'business_website',
            'cipc_registration_number', 'cipc_document',
            'tax_number', 'tax_clearance_certificate', 'vat_number', 'bee_certificate',
            'owner_full_name', 'owner_id_number', 'owner_id_document', 'owner_proof_of_address',
            'opening_hours', 'is_temporarily_closed',
            'accepts_returns', 'return_window_days',
            'role', 'department', 'role_title',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field in ('cipc_registration_number', 'cipc_document'):
            if not attrs.get(field, getattr(self.instance, field, None)):
                raise serializers.ValidationError({field: 'Required for business vendors.'})
        return attrs


# =============================================================================
# Vendor Document Serializers
# =============================================================================

class VendorDocumentSerializer(DocumentValidationMixin, serializers.ModelSerializer):
    """Serializer for additional vendor documents"""

    class Meta:
        model = VendorDocument
        fields = [
            'id', 'document_type', 'document_file', 'document_name',
            'status', 'review_notes', 'uploaded_at',
        ]
        read_only_fields = ['id', 'status', 'review_notes', 'uploaded_at']


class VendorDocumentAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for reviewing vendor documents"""

    class Meta:
        model = VendorDocument
        fields = [
            'id', 'individual_vendor', 'business_vendor',
            'document_type', 'document_file', 'document_name',
            'status', 'review_notes', 'reviewed_by', 'reviewed_at', 'uploaded_at',
        ]
        read_only_fields = ['id', 'uploaded_at']


# =============================================================================
# Vetting Application Serializers
# =============================================================================

class VettingApplicationSerializer(serializers.ModelSerializer):
    """Serializer for viewing vetting applications"""

    class Meta:
        model = VettingApplication
        fields = [
            'id', 'vetting_type', 'status',
            'id_verified', 'address_verified', 'selfie_verified',
            'cipc_verified', 'tax_verified', 'bank_verified',
            'rejection_reason',
            'submitted_at', 'reviewed_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'vetting_type', 'status',
            'id_verified', 'address_verified', 'selfie_verified',
            'cipc_verified', 'tax_verified', 'bank_verified',
            'rejection_reason',
            'submitted_at', 'reviewed_at', 'completed_at',
        ]


class VettingApplicationAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for processing vetting applications"""

    vendor_info = serializers.SerializerMethodField()

    class Meta:
        model = VettingApplication
        fields = [
            'id', 'individual_vendor', 'business_vendor', 'vendor_info',
            'vetting_type', 'status',
            'id_verified', 'address_verified', 'selfie_verified',
            'cipc_verified', 'tax_verified', 'bank_verified',
            'notes', 'rejection_reason',
            'assigned_to', 'submitted_at', 'reviewed_at', 'completed_at',
        ]
        read_only_fields = ['id', 'submitted_at']

    def get_vendor_info(self, obj):
        if obj.individual_vendor:
            return {
                'type': 'individual',
                'name': obj.individual_vendor.store_name,
                'owner_email': obj.individual_vendor.user.email,
            }
        if obj.business_vendor:
            return {
                'type': 'business',
                'name': obj.business_vendor.business_name,
                'owner_email': obj.business_vendor.user.email,
                'cipc_number': obj.business_vendor.cipc_registration_number,
            }
        return None


class AddressSerializer(serializers.ModelSerializer):
    """Vendor business address serializer.

    `Address.vendor` is a VendorProfile FK; customer shipping addresses
    live in `orders.ShippingAddress` instead.
    """

    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = Address
        fields = [
            'id', 'vendor', 'vendor_name',
            'address_type', 'full_name', 'phone_number',
            'street_address', 'apartment_number', 'city',
            'state_province', 'postal_code', 'country',
            'latitude', 'longitude',
            'is_default', 'delivery_instructions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'vendor_name', 'created_at', 'updated_at']

    def get_vendor_name(self, obj):
        vp = obj.vendor
        if vp is None:
            return None
        return vp.trading_name or vp.name or None


# =============================================================================
# Business Follower Serializers
# =============================================================================

class BusinessFollowerSerializer(serializers.ModelSerializer):
    """Serializer for viewing follows."""

    user_email = serializers.CharField(source='user.email', read_only=True)
    vendor_email = serializers.CharField(source='vendor.email', read_only=True)
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = BusinessFollower
        fields = ['id', 'user', 'user_email', 'vendor', 'vendor_email', 'vendor_name', 'created_at']
        read_only_fields = ['id', 'user', 'user_email', 'vendor_email', 'vendor_name', 'created_at']

    def get_vendor_name(self, obj):
        vendor = obj.vendor
        if hasattr(vendor, 'individual_vendor_profile'):
            return vendor.individual_vendor_profile.store_name
        if hasattr(vendor, 'business_vendor_profile'):
            return vendor.business_vendor_profile.business_name
        return vendor.email


def _resolve_vendor_user(vendor_id):
    """
    Resolve a vendor identifier to a User object regardless of which profile
    type the caller is using.  Accepted formats:

      UUID string  →  VendorProfile.id          (unified profile, Flutter default)
      integer      →  IndividualVendorProfile.id (informal-trader profile)
      integer      →  BusinessVendorProfile.id   (CIPC-registered profile)
      integer      →  User.id  with user_type=vendor  (raw user ID, legacy)

    Returns the vendor's User instance, or None if nothing matched.
    """
    import uuid as _uuid_mod
    if vendor_id is None:
        return None
    value = str(vendor_id).strip()

    # ── UUID → unified VendorProfile ─────────────────────────────────────────
    try:
        _uuid_mod.UUID(value)
        vp = VendorProfile.objects.select_related('user').get(id=value)
        return vp.user
    except (ValueError, VendorProfile.DoesNotExist, Exception):
        pass

    # ── Integer → one of the two legacy profile tables, or raw User.id ───────
    try:
        int_id = int(value)
    except (ValueError, TypeError):
        return None

    # IndividualVendorProfile (informal traders, tuck shops, etc.)
    try:
        return IndividualVendorProfile.objects.select_related('user').get(id=int_id).user
    except IndividualVendorProfile.DoesNotExist:
        pass

    # BusinessVendorProfile (CIPC-registered companies)
    try:
        return BusinessVendorProfile.objects.select_related('user').get(id=int_id).user
    except BusinessVendorProfile.DoesNotExist:
        pass

    # Last resort: treat int as User.id directly
    try:
        return User.objects.get(id=int_id, user_type='vendor')
    except User.DoesNotExist:
        return None


class BusinessFollowerCreateSerializer(serializers.Serializer):
    """Follow a vendor/business. Accepts vendor_id as VendorProfile UUID or User integer ID."""

    vendor_id = serializers.CharField()

    def validate_vendor_id(self, value):
        vendor_user = _resolve_vendor_user(value)
        if vendor_user is None:
            raise serializers.ValidationError("Vendor not found.")

        user = self.context['request'].user
        if user.id == vendor_user.id:
            raise serializers.ValidationError("You cannot follow yourself.")
        if BusinessFollower.objects.filter(user=user, vendor=vendor_user).exists():
            raise serializers.ValidationError("You are already following this business.")

        # Return the resolved User object so create() doesn't need to re-query
        return vendor_user

    def create(self, validated_data):
        user = self.context['request'].user
        vendor_user = validated_data['vendor_id']   # already a User instance
        return BusinessFollower.objects.create(user=user, vendor=vendor_user)


# =============================================================================
# Unified VendorProfile serializer
# =============================================================================

class VendorProfileSerializer(DocumentValidationMixin, _BusinessTypeToleranceMixin,
                              serializers.ModelSerializer):
    """Unified read/write serializer for the merged VendorProfile model."""

    user_email = serializers.CharField(source='user.email', read_only=True)
    logo_url = serializers.SerializerMethodField()
    is_open_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = VendorProfile
        fields = [
            'id', 'user', 'user_email',
            'profile_type', 'business_category',
            'vendor_type', 'business_type',
            'name', 'trading_name', 'description',
            'logo', 'logo_url', 'website',
            'qr_code', 'qr_code_identifier',
            # Individual-only
            'id_number', 'id_document', 'proof_of_address', 'selfie_with_id',
            # Business-only
            'cipc_registration_number', 'cipc_document',
            'tax_number', 'tax_clearance_certificate',
            'vat_number', 'bee_certificate',
            'owner_full_name', 'owner_id_number',
            'owner_id_document', 'owner_proof_of_address',
            # Address
            'street_address', 'city', 'province', 'postal_code', 'country',
            'latitude', 'longitude',
            # Banking
            'bank_name', 'bank_account_number', 'bank_branch_code', 'bank_account_holder',
            'proof_of_bank',
            # Owner role on their own team — see VENDOR_OWNER_ROLE_CHOICES.
            'role', 'department', 'role_title', 'status',
            # Verification / metrics / ops
            'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
            'rejection_reason', 'verified_at', 'verified_by',
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            'commission_rate', 'store_active', 'accepts_returns',
            'return_window_days', 'opening_hours', 'is_temporarily_closed',
            'is_open_now',
            'categories',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_email', 'qr_code', 'qr_code_identifier',
            # Verification is admin-controlled — a vendor must never be able to
            # self-verify or flip their own vetting flags by PATCHing these.
            'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
            'rejection_reason', 'verified_at', 'verified_by',
            'total_sales', 'total_orders', 'average_rating', 'total_reviews',
            'created_at', 'updated_at', 'status', 'commission_rate', 'store_active',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.context['request'].user.user_type != 'vendor':
            raise serializers.ValidationError('Only vendor accounts can edit a vendor profile.')
        current = self.instance
        kind = attrs.get('profile_type', current.profile_type if current else 'individual')
        if current and current.name and kind != current.profile_type:
            raise serializers.ValidationError({'profile_type': 'Contact support to change your vendor type.'})
        if kind == 'business':
            errors = {}
            for field in ('cipc_registration_number', 'cipc_document'):
                if not attrs.get(field, getattr(current, field, None)):
                    errors[field] = 'Required for business vendors.'
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = VendorProfile.objects.select_for_update().get(pk=instance.pk)
        if evidence_changed(instance, validated_data):
            invalidate_vendor(instance)
        instance = super().update(instance, validated_data)
        sync_review_state(instance)
        return instance

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

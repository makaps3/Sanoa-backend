from core.private_documents import private_document_storage
"""
Business app models.

Contains all vendor/business-related models:
- IndividualVendorProfile (informal traders)
- BusinessVendorProfile (CIPC-registered businesses)
- VendorDocument (supporting documents)
- VettingApplication (verification process)
- BusinessFollower (customer follows vendor)
- Address (user addresses)
"""
import io
import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image
import qrcode

AUTH_USER_MODEL = settings.AUTH_USER_MODEL


# =============================================================================
# Shared choices
# =============================================================================

# High-level discriminator used by the frontend to switch between
# the "Shopping" experience (retail product grid) and the "Restaurants"
# experience (food menu / fast-food ordering flow). Both vendor profile
# types carry this so the same toggle works regardless of vendor tier.
BUSINESS_CATEGORY_CHOICES = [
    ('retail', 'Groceries'),
    ('restaurant', 'Fast Food'),
]


def _is_open_now(opening_hours, is_temporarily_closed):
    """
    Shared helper used by both vendor profile types to compute whether the
    store is currently open. Returns False if the manual override is set,
    if no hours are configured, or if 'now' falls outside today's windows.
    """
    if is_temporarily_closed:
        return False
    if not opening_hours:
        # No hours configured — treat as always open so existing retail
        # vendors are unaffected by this change.
        return True
    now = timezone.localtime()
    weekday_key = str(now.weekday())  # 0=Mon..6=Sun
    windows = opening_hours.get(weekday_key) or []
    current = now.strftime('%H:%M')
    for window in windows:
        open_t = window.get('open')
        close_t = window.get('close')
        if not open_t or not close_t:
            continue
        if open_t <= current <= close_t:
            return True
    return False


# =============================================================================
# Vendor owner role / department / status — used on all three vendor
# profile flavours below (IndividualVendorProfile, BusinessVendorProfile,
# the unified VendorProfile) so the founder/CEO/owner can describe how
# they sit on their own team. Mirrors the shape of
# `platform_admin.AdminProfile` (role + department + role_title + status)
# so the two screens feel like siblings.
# =============================================================================

VENDOR_OWNER_ROLE_CHOICES = [
    ('founder',     'Founder'),
    ('ceo',         'CEO'),
    ('owner',       'Owner'),
    ('co_owner',    'Co-owner'),
    ('director',    'Director'),
    ('partner',     'Partner'),
    ('manager',     'Manager'),
    ('operator',    'Sole operator'),
]

VENDOR_DEPARTMENT_CHOICES = [
    ('operations',     'Operations'),
    ('management',     'Management'),
    ('sales',          'Sales'),
    ('finance',        'Finance'),
    ('marketing',      'Marketing'),
    ('customer_care',  'Customer Care'),
    ('logistics',      'Logistics / Delivery'),
    ('kitchen',        'Kitchen / Production'),
    ('admin',          'Admin / Owner'),
    ('other',          'Other'),
]

VENDOR_PROFILE_STATUS_CHOICES = [
    ('active',     'Active'),
    ('suspended',  'Suspended'),
]


def _default_owner_role(profile_type: str = '') -> str:
    """Sensible default role for newly-created profiles. Business
    profiles default to "CEO" (CIPC-registered companies usually have
    one), informal/individual profiles default to "Sole operator"."""
    return 'ceo' if profile_type == 'business' else 'operator'


# =============================================================================
# Individual Vendor Profile
# =============================================================================

class IndividualVendorProfile(models.Model):
    """
    Profile for individual vendors / informal traders.
    For vendors WITHOUT CIPC registration: tuck shops, street vendors,
    local brands, home businesses, freelancers, craftspersons.
    """

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    VENDOR_TYPE_CHOICES = [
        ('street_vendor', 'Street Vendor'),
        ('freelancer', 'Freelancer'),
        ('tuck_shop', 'Tuck Shop'),
        ('home_business', 'Home Business'),
        ('local_brand', 'Local Brand'),
        ('craftsperson', 'Craftsperson'),
        ('food_vendor', 'Food Vendor'),
        ('market_trader', 'Market Trader'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='individual_vendor_profile'
    )

    vendor_type = models.CharField(
        max_length=20, choices=VENDOR_TYPE_CHOICES, default='other',
        help_text="Type of vendor or business"
    )
    business_category = models.CharField(
        max_length=20, choices=BUSINESS_CATEGORY_CHOICES, default='retail',
        help_text=(
            "High-level mode for the storefront. 'restaurant' enables the "
            "fast-food / menu ordering UI on the frontend; 'retail' uses the "
            "standard shopping product grid."
        ),
    )
    store_name = models.CharField(max_length=200)
    store_description = models.TextField(max_length=1000, blank=True)
    store_logo = models.ImageField(
        upload_to='logos/vendors/individual/', null=True, blank=True
    )

    qr_code = models.ImageField(
        upload_to='qrcodes/vendors/individual/', null=True, blank=True
    )
    qr_code_identifier = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )

    id_number = models.CharField(max_length=20)
    id_document = models.FileField(storage=private_document_storage, upload_to='documents/vendors/individual/id/')
    proof_of_address = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/individual/address/'
    )
    selfie_with_id = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/individual/selfie/',
        null=True, blank=True
    )

    trading_address = models.CharField(max_length=255, blank=True)
    trading_city = models.CharField(max_length=100, blank=True)
    trading_province = models.CharField(max_length=100, blank=True)
    trading_postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    categories = models.ManyToManyField(
        'products.Category', blank=True, related_name='individual_vendors'
    )

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_branch_code = models.CharField(max_length=20, blank=True)
    bank_account_holder = models.CharField(max_length=200, blank=True)

    # Owner role on their own team (see VENDOR_OWNER_ROLE_CHOICES).
    role = models.CharField(
        max_length=20, choices=VENDOR_OWNER_ROLE_CHOICES,
        blank=True, default='',
    )
    department = models.CharField(
        max_length=20, choices=VENDOR_DEPARTMENT_CHOICES,
        blank=True, default='',
    )
    role_title = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=VENDOR_PROFILE_STATUS_CHOICES,
        default='active',
    )

    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending'
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='individual_vendors_verified'
    )

    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=8.00,
        help_text="Platform commission percentage"
    )

    store_active = models.BooleanField(default=False)
    accepts_returns = models.BooleanField(default=True)
    return_window_days = models.PositiveIntegerField(default=14)

    # Opening hours — used by the Restaurants UI to show "Open now" / "Closed".
    # Stored as JSON keyed by weekday (0=Mon..6=Sun), each value being a list
    # of {"open": "HH:MM", "close": "HH:MM"} pairs to support split shifts.
    # Example:
    #   {"0": [{"open": "08:00", "close": "21:00"}], "6": []}
    opening_hours = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Weekly opening hours keyed by weekday number (0=Mon..6=Sun). "
            "Each day is a list of {'open': 'HH:MM', 'close': 'HH:MM'} pairs."
        ),
    )
    is_temporarily_closed = models.BooleanField(
        default=False,
        help_text="Manual override — vendor can mark themselves closed even during opening hours."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_individualvendorprofile'
        verbose_name = 'Individual Vendor Profile'
        verbose_name_plural = 'Individual Vendor Profiles'

    def __str__(self):
        return f"{self.store_name} ({self.user.email})"

    @property
    def is_verified(self):
        return self.verification_status == 'verified'

    @property
    def is_open_now(self):
        return _is_open_now(self.opening_hours, self.is_temporarily_closed)

    def generate_qr_code(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(f"sanoa://vendor/{self.qr_code_identifier}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        filename = f"vendor_individual_{self.qr_code_identifier}.png"
        self.qr_code.save(filename, ContentFile(buffer.read()), save=False)


# =============================================================================
# Business Vendor Profile
# =============================================================================

class BusinessVendorProfile(models.Model):
    """
    Profile for registered businesses with CIPC.
    """

    BUSINESS_TYPE_CHOICES = [
        ('sole_proprietor', 'Sole Proprietor'),
        ('partnership', 'Partnership'),
        ('pty_ltd', 'Pty Ltd'),
        ('cc', 'Close Corporation'),
        ('npc', 'Non-Profit Company'),
        ('cooperative', 'Co-operative'),
        ('other', 'Other'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('owner_verified', 'Owner Verified'),
        ('under_review', 'Under Review'),
        ('verified', 'Fully Verified'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='business_vendor_profile'
    )

    business_name = models.CharField(max_length=200)
    business_trading_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES)
    business_category = models.CharField(
        max_length=20, choices=BUSINESS_CATEGORY_CHOICES, default='retail',
        help_text=(
            "High-level mode for the storefront. 'restaurant' enables the "
            "fast-food / menu ordering UI on the frontend; 'retail' uses the "
            "standard shopping product grid."
        ),
    )
    business_description = models.TextField(max_length=2000, blank=True)
    business_logo = models.ImageField(
        upload_to='logos/vendors/business/', null=True, blank=True
    )
    business_website = models.URLField(blank=True)

    qr_code = models.ImageField(
        upload_to='qrcodes/vendors/business/', null=True, blank=True
    )
    qr_code_identifier = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )

    cipc_registration_number = models.CharField(max_length=50, unique=True)
    cipc_document = models.FileField(storage=private_document_storage, upload_to='documents/vendors/business/cipc/')
    tax_number = models.CharField(max_length=50, blank=True)
    tax_clearance_certificate = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/business/tax/', null=True, blank=True
    )
    vat_number = models.CharField(max_length=20, blank=True)
    bee_certificate = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/business/bee/', null=True, blank=True
    )

    owner_full_name = models.CharField(max_length=200)
    owner_id_number = models.CharField(max_length=20)
    owner_id_document = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/business/owner_id/'
    )
    owner_proof_of_address = models.FileField(storage=private_document_storage, 
        upload_to='documents/vendors/business/owner_address/'
    )

    business_street_address = models.CharField(max_length=255, blank=True)
    business_city = models.CharField(max_length=100, blank=True)
    business_province = models.CharField(max_length=100, blank=True)
    business_postal_code = models.CharField(max_length=20, blank=True)
    business_country = models.CharField(max_length=100, blank=True, default='South Africa')

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    categories = models.ManyToManyField(
        'products.Category', blank=True, related_name='business_vendors'
    )

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_branch_code = models.CharField(max_length=20, blank=True)
    bank_account_holder = models.CharField(max_length=200, blank=True)

    # Owner role on their own team (see VENDOR_OWNER_ROLE_CHOICES).
    role = models.CharField(
        max_length=20, choices=VENDOR_OWNER_ROLE_CHOICES,
        blank=True, default='',
    )
    department = models.CharField(
        max_length=20, choices=VENDOR_DEPARTMENT_CHOICES,
        blank=True, default='',
    )
    role_title = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=VENDOR_PROFILE_STATUS_CHOICES,
        default='active',
    )

    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending'
    )
    owner_vetting_passed = models.BooleanField(default=False)
    business_vetting_passed = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='business_vendors_verified'
    )

    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        help_text="Platform commission percentage"
    )

    store_active = models.BooleanField(default=False)
    accepts_returns = models.BooleanField(default=True)
    return_window_days = models.PositiveIntegerField(default=30)

    # See IndividualVendorProfile.opening_hours for the schema.
    opening_hours = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Weekly opening hours keyed by weekday number (0=Mon..6=Sun). "
            "Each day is a list of {'open': 'HH:MM', 'close': 'HH:MM'} pairs."
        ),
    )
    is_temporarily_closed = models.BooleanField(
        default=False,
        help_text="Manual override — vendor can mark themselves closed even during opening hours."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_businessvendorprofile'
        verbose_name = 'Business Vendor Profile'
        verbose_name_plural = 'Business Vendor Profiles'

    def __str__(self):
        return f"{self.business_name} ({self.user.email})"

    @property
    def is_verified(self):
        return self.verification_status == 'verified'

    @property
    def is_fully_vetted(self):
        return self.owner_vetting_passed and self.business_vetting_passed

    @property
    def is_open_now(self):
        return _is_open_now(self.opening_hours, self.is_temporarily_closed)

    def generate_qr_code(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(f"sanoa://vendor/{self.qr_code_identifier}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        filename = f"vendor_business_{self.qr_code_identifier}.png"
        self.qr_code.save(filename, ContentFile(buffer.read()), save=False)


# =============================================================================
# Vendor Document
# =============================================================================

class VendorDocument(models.Model):
    """Additional supporting documents for either vendor type."""

    DOCUMENT_TYPE_CHOICES = [
        ('id_document', 'ID Document'),
        ('proof_of_address', 'Proof of Address'),
        ('cipc_certificate', 'CIPC Registration Certificate'),
        ('tax_clearance', 'Tax Clearance Certificate'),
        ('bee_certificate', 'B-BBEE Certificate'),
        ('bank_confirmation', 'Bank Confirmation Letter'),
        ('trading_licence', 'Trading Licence'),
        ('health_certificate', 'Health & Safety Certificate'),
        ('other', 'Other Supporting Document'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    individual_vendor = models.ForeignKey(
        IndividualVendorProfile, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documents'
    )
    business_vendor = models.ForeignKey(
        BusinessVendorProfile, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documents'
    )

    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    document_file = models.FileField(storage=private_document_storage, upload_to='documents/vendors/additional/')
    document_name = models.CharField(
        max_length=200, help_text="Brief description of this document"
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documents_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_vendordocument'
        verbose_name = 'Vendor Document'
        verbose_name_plural = 'Vendor Documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.document_name}"

    def clean(self):
        if not self.individual_vendor and not self.business_vendor:
            raise ValidationError(
                "Document must be linked to either an individual or business vendor."
            )
        if self.individual_vendor and self.business_vendor:
            raise ValidationError(
                "Document cannot be linked to both vendor types."
            )


# =============================================================================
# Vetting Application
# =============================================================================

class VettingApplication(models.Model):
    """
    Tracks the vetting/verification process for vendor accounts.
    """

    VETTING_TYPE_CHOICES = [
        ('individual_owner', 'Individual Vendor - Owner Vetting'),
        ('business_owner', 'Business Vendor - Owner Vetting'),
        ('business_entity', 'Business Vendor - Business Entity Vetting'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('requires_resubmission', 'Requires Resubmission'),
    ]

    individual_vendor = models.ForeignKey(
        IndividualVendorProfile, on_delete=models.CASCADE,
        null=True, blank=True, related_name='vetting_applications'
    )
    business_vendor = models.ForeignKey(
        BusinessVendorProfile, on_delete=models.CASCADE,
        null=True, blank=True, related_name='vetting_applications'
    )

    vetting_type = models.CharField(max_length=20, choices=VETTING_TYPE_CHOICES)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')

    id_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    selfie_verified = models.BooleanField(default=False)
    cipc_verified = models.BooleanField(default=False)
    tax_verified = models.BooleanField(default=False)
    bank_verified = models.BooleanField(default=False)

    notes = models.TextField(blank=True, help_text="Internal review notes")
    rejection_reason = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_vettings'
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'accounts_vettingapplication'
        verbose_name = 'Vetting Application'
        verbose_name_plural = 'Vetting Applications'
        ordering = ['-submitted_at']

    def __str__(self):
        vendor = self.individual_vendor or self.business_vendor
        return f"{self.get_vetting_type_display()} - {vendor} ({self.status})"

    def clean(self):
        if not self.individual_vendor and not self.business_vendor:
            raise ValidationError(
                "Vetting must be linked to either an individual or business vendor."
            )
        if self.individual_vendor and self.business_vendor:
            raise ValidationError(
                "Vetting cannot be linked to both vendor types."
            )


# =============================================================================
# Address
# =============================================================================

class Address(models.Model):
    """
    Vendor business address.

    Scope: this table stores addresses tied to a **VendorProfile** (a store /
    business location). Customer shipping addresses live in
    `orders.ShippingAddress` — do NOT add customer rows here.
    """

    ADDRESS_TYPE_CHOICES = [
        ('billing', 'Billing Address'),
        ('shipping', 'Shipping Address'),
        ('both', 'Billing & Shipping'),
        ('business', 'Business Address'),
    ]

    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='addresses',
        help_text='The vendor profile (store) that owns this address.',
    )
    address_type = models.CharField(
        max_length=10, choices=ADDRESS_TYPE_CHOICES, default='business'
    )
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=17)

    street_address = models.CharField(max_length=255)
    apartment_number = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='South Africa')

    is_default = models.BooleanField(default=False)
    delivery_instructions = models.TextField(blank=True, max_length=500)

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Latitude for delivery distance calculation',
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Longitude for delivery distance calculation',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_address'
        verbose_name = 'Vendor Address'
        verbose_name_plural = 'Vendor Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.state_province}"

    def save(self, *args, **kwargs):
        # Only one default address per (vendor, address_type).
        if self.is_default:
            Address.objects.filter(
                vendor=self.vendor,
                address_type=self.address_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        # Auto-geocode whenever the client didn't supply coordinates —
        # the vendor's stored lat/lng drives delivery-fare distance
        # calculations and the storefront map pin. No-op if
        # GOOGLE_MAPS_API_KEY isn't configured.
        if self.latitude is None or self.longitude is None:
            from core.geocoding import geocode_address
            lat, lng = geocode_address(
                street_address=self.street_address,
                apartment_number=self.apartment_number,
                city=self.city,
                state_province=self.state_province,
                postal_code=self.postal_code,
                country=self.country,
            )
            if lat is not None and lng is not None:
                self.latitude = lat
                self.longitude = lng
        super().save(*args, **kwargs)


# =============================================================================
# Business Followers
# =============================================================================

class BusinessFollower(models.Model):
    """
    Tracks which customers follow which vendors/businesses.
    Required for debit purchase eligibility.
    """

    user = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following',
        limit_choices_to={'user_type': 'customer'}
    )
    vendor = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers',
        limit_choices_to={'user_type': 'vendor'}
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_businessfollower'
        verbose_name = 'Business Follower'
        verbose_name_plural = 'Business Followers'
        unique_together = ['user', 'vendor']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} follows {self.vendor.email}"


# =============================================================================
# Unified VendorProfile (merges Individual + Business)
# =============================================================================

class VendorProfile(models.Model):
    """
    Single source of truth for a vendor's profile.
    Replaces IndividualVendorProfile and BusinessVendorProfile, using
    `profile_type` as a discriminator. Fields unique to each legacy model
    are nullable and only populated for the corresponding profile_type.
    """

    PROFILE_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
    ]

    BUSINESS_CATEGORY_CHOICES = [
        ('retail', 'Groceries'),
        ('restaurant', 'Fast Food'),
    ]

    VENDOR_TYPE_CHOICES = [
        ('street_vendor', 'Street Vendor'),
        ('freelancer', 'Freelancer'),
        ('tuck_shop', 'Tuck Shop'),
        ('home_business', 'Home Business'),
        ('local_brand', 'Local Brand'),
        ('craftsperson', 'Craftsperson'),
        ('food_vendor', 'Food Vendor'),
        ('market_trader', 'Market Trader'),
        ('other', 'Other'),
    ]

    BUSINESS_TYPE_CHOICES = [
        ('sole_proprietor', 'Sole Proprietor'),
        ('partnership', 'Partnership'),
        ('pty_ltd', 'Pty Ltd'),
        ('cc', 'Close Corporation'),
        ('npc', 'Non-Profit Company'),
        ('cooperative', 'Cooperative'),
        ('other', 'Other'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('owner_verified', 'Owner Verified'),
        ('under_review', 'Under Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='vendor_profile',
        limit_choices_to={'user_type': 'vendor'},
    )
    profile_type = models.CharField(
        max_length=15, choices=PROFILE_TYPE_CHOICES,
    )
    business_category = models.CharField(
        max_length=20, choices=BUSINESS_CATEGORY_CHOICES, default='retail',
    )

    # Individual-only discriminator
    vendor_type = models.CharField(
        max_length=20, choices=VENDOR_TYPE_CHOICES, blank=True,
    )
    # Business-only discriminator
    business_type = models.CharField(
        max_length=20, choices=BUSINESS_TYPE_CHOICES, blank=True,
    )

    # Identity & branding (unified: 'name' replaces store_name / business_name)
    name = models.CharField(max_length=200)
    trading_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(max_length=2000, blank=True)
    logo = models.ImageField(
        upload_to='logos/vendors/', null=True, blank=True,
    )
    website = models.URLField(blank=True)

    qr_code = models.ImageField(upload_to='qr/vendors/', null=True, blank=True)
    qr_code_identifier = models.UUIDField(default=uuid.uuid4, unique=True)

    # Individual-only documents (nullable)
    id_number = models.CharField(max_length=20, blank=True)
    id_document = models.FileField(storage=private_document_storage, upload_to='docs/id/', null=True, blank=True)
    proof_of_address = models.FileField(storage=private_document_storage, upload_to='docs/poa/', null=True, blank=True)
    selfie_with_id = models.FileField(storage=private_document_storage, upload_to='docs/selfie/', null=True, blank=True)

    # Business-only CIPC / tax fields (nullable)
    cipc_registration_number = models.CharField(max_length=50, blank=True)
    cipc_document = models.FileField(storage=private_document_storage, upload_to='docs/cipc/', null=True, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    tax_clearance_certificate = models.FileField(storage=private_document_storage, 
        upload_to='docs/tax/', null=True, blank=True,
    )
    vat_number = models.CharField(max_length=20, blank=True)
    bee_certificate = models.FileField(storage=private_document_storage, upload_to='docs/bee/', null=True, blank=True)
    owner_full_name = models.CharField(max_length=200, blank=True)
    owner_id_number = models.CharField(max_length=20, blank=True)
    owner_id_document = models.FileField(storage=private_document_storage, upload_to='docs/owner-id/', null=True, blank=True)
    owner_proof_of_address = models.FileField(storage=private_document_storage, upload_to='docs/owner-poa/', null=True, blank=True)

    # Address (unified naming)
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='South Africa')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Banking
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_branch_code = models.CharField(max_length=20, blank=True)
    bank_account_holder = models.CharField(max_length=200, blank=True)
    # Proof of bank account (bank confirmation letter / stamped statement).
    proof_of_bank = models.FileField(storage=private_document_storage, 
        upload_to='docs/proof-of-bank/', null=True, blank=True)

    # ── Owner role on their own team ────────────────────────────
    # Mirrors `AdminProfile` (role + department + role_title +
    # status). Filled in by the vendor when they create the profile;
    # the auto-manager signal copies these onto the
    # `VendorEmployee(is_manager=True)` row so the team screen and
    # the profile stay in sync.
    role = models.CharField(
        max_length=20, choices=VENDOR_OWNER_ROLE_CHOICES,
        blank=True, default='',
        help_text='How the vendor describes their position '
                  '(Founder, CEO, Owner, etc.).',
    )
    department = models.CharField(
        max_length=20, choices=VENDOR_DEPARTMENT_CHOICES,
        blank=True, default='',
        help_text='Which side of the business the owner runs '
                  'day-to-day. Defaults to "Admin / Owner".',
    )
    role_title = models.CharField(
        max_length=100, blank=True,
        help_text='Free-form job title (e.g. "Co-founder & Head of '
                  'Operations"). Shown alongside the role on the '
                  'team screen.',
    )
    status = models.CharField(
        max_length=20, choices=VENDOR_PROFILE_STATUS_CHOICES,
        default='active',
        help_text='Operational status. Suspended profiles can\'t '
                  'log in to the vendor app.',
    )

    # Verification
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending',
    )
    owner_vetting_passed = models.BooleanField(default=False)
    business_vetting_passed = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vendor_profiles_verified',
    )

    # Metrics
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.PositiveIntegerField(default=0)

    # Operations
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    store_active = models.BooleanField(default=True)
    accepts_returns = models.BooleanField(default=True)
    return_window_days = models.PositiveIntegerField(default=14)
    opening_hours = models.JSONField(default=dict, blank=True)
    is_temporarily_closed = models.BooleanField(default=False)

    categories = models.ManyToManyField(
        'products.Category', related_name='vendor_profiles', blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_vendorprofile'
        verbose_name = 'Vendor Profile'
        verbose_name_plural = 'Vendor Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.profile_type}) — {self.user.email}"

    @property
    def logo_url(self):
        return self.logo.url if self.logo else None

    @property
    def can_trade(self):
        return (self.verification_status == 'verified' and self.store_active
                and self.status != 'suspended' and self.user.is_active
                and self.user.is_verified and not self.user.is_suspended)

    @property
    def is_open_now(self):
        """Whether the store is currently open — honours the manual override
        (`is_temporarily_closed`) and today's configured opening windows."""
        return _is_open_now(self.opening_hours, self.is_temporarily_closed)

    # Employee headcount caps. The first person on the profile is
    # auto-created as a manager; remaining seats are filled via
    # `VendorEmployeeInvitation`. Cap is hard-enforced by
    # `VendorEmployee.clean()` and by the invite endpoint.
    INDIVIDUAL_EMPLOYEE_CAP = 2
    BUSINESS_EMPLOYEE_CAP   = 10

    @property
    def employee_cap(self) -> int:
        return (self.BUSINESS_EMPLOYEE_CAP
                if self.profile_type == 'business'
                else self.INDIVIDUAL_EMPLOYEE_CAP)


# =============================================================================
# Vendor Employee
# =============================================================================

class VendorEmployee(models.Model):
    """One person attached to a `VendorProfile`.

    The first record on a profile is the **manager** (auto-created
    when the vendor profile is saved for the first time). The
    manager is the CEO/founder/owner — once the platform admin
    verifies them, they themselves become responsible for vetting
    the remaining employees on the profile.

    Cap:
      * Individual vendors → 2 employees total (manager + 1).
      * Business vendors   → 10 employees total (manager + 9).

    Verification mirrors the vendor profile state machine so admins
    don't have to learn two vocabularies:

      pending        → employee just joined, no verification yet
      under_review   → manager is reviewing their documents
      verified       → manager (or admin) approved their KYC
      rejected       → manager (or admin) rejected them
      suspended      → temporarily blocked by manager/admin
    """

    DEPARTMENT_CHOICES = [
        ('operations',     'Operations'),
        ('sales',          'Sales'),
        ('finance',        'Finance'),
        ('marketing',      'Marketing'),
        ('customer_care',  'Customer Care'),
        ('logistics',      'Logistics / Delivery'),
        ('kitchen',        'Kitchen / Production'),
        ('admin',          'Admin / Owner'),
        ('other',          'Other'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('pending',        'Pending'),
        ('under_review',   'Under Review'),
        ('verified',       'Verified'),
        ('rejected',       'Rejected'),
        ('suspended',      'Suspended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='employees',
    )
    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='vendor_employment',
        help_text='The user account this employee uses to sign in.',
    )

    role_title = models.CharField(
        max_length=100,
        help_text="What the employee does on this team "
                  "(e.g. 'Head Chef', 'Sales Lead').",
    )
    department = models.CharField(
        max_length=20, choices=DEPARTMENT_CHOICES, default='operations',
    )

    is_manager = models.BooleanField(
        default=False,
        help_text='True for the original profile owner. Managers can '
                  'verify or reject the other employees on the '
                  'profile once they themselves are verified by '
                  'platform admin.',
    )

    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='The user who flipped this employee to verified — '
                  'either the vendor manager or a platform admin.',
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Cleared to block sign-in / dashboard access '
                  'without deleting the record.',
    )

    # Per-employee permission grants set by the manager. Mirrors the
    # AdminProfile.permissions pattern: a flat dict of
    # ``{key: bool}``. Managers always have everything; employees
    # default to a minimal viewer set and the manager toggles keys
    # individually on the add / edit screen.
    permissions = models.JSONField(
        default=dict, blank=True,
        help_text=(
            'Per-employee permission grants. See '
            '`VENDOR_EMPLOYEE_PERMISSION_KEYS` for the canonical '
            'set; values are booleans.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vendor Employee'
        verbose_name_plural = 'Vendor Employees'
        ordering = ['-is_manager', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['vendor'],
                condition=models.Q(is_manager=True),
                name='unique_manager_per_vendor',
            ),
        ]

    def __str__(self):
        tag = 'MGR' if self.is_manager else 'EMP'
        return f"[{tag}] {self.user.email} @ {self.vendor.name}"

    def clean(self):
        super().clean()
        if (
            self.vendor_id
            and not self.pk
            and self.vendor.employees.count() >= self.vendor.employee_cap
        ):
            raise ValidationError(
                f'{self.vendor.get_profile_type_display()} vendors are '
                f'capped at {self.vendor.employee_cap} employees.',
            )

    @property
    def is_verified(self) -> bool:
        return self.verification_status == 'verified'

    # ── Permissions ────────────────────────────────────────────────
    #
    # Vocabulary the manager toggles on a per-employee basis. Keep
    # the list short — each key gates a chunk of vendor-app
    # functionality. Add new keys here and the rest of the system
    # (serializer, frontend service, UI) reads from this single
    # source.
    PERMISSION_KEYS = [
        ('manage_orders',        'Manage orders'),
        ('manage_products',      'Manage products'),
        ('manage_inventory',     'Manage inventory / stock'),
        ('manage_negotiations',  'Handle price negotiations'),
        ('manage_payments',      'Wallet, payouts & refunds'),
        ('manage_employees',     'Add or remove other employees'),
        ('manage_settings',      'Edit profile, hours & banking'),
        ('manage_promotions',    'Banners, vouchers & promos'),
        ('view_analytics',       'See dashboards & reports'),
        ('view_customers',       'Browse customer data'),
    ]

    @classmethod
    def default_permissions_for(cls, *, is_manager: bool) -> dict:
        """Seed permission set.

        Managers get every key set to True. Employees default to a
        viewer-only set (orders + analytics) and the manager
        toggles the rest on at creation time.
        """
        if is_manager:
            return {k: True for k, _ in cls.PERMISSION_KEYS}
        return {k: False for k, _ in cls.PERMISSION_KEYS}

    def has_perm(self, key: str) -> bool:
        if not self.is_active:
            return False
        if self.is_manager:
            return True
        return bool((self.permissions or {}).get(key, False))



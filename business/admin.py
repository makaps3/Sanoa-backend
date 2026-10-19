from django.contrib import admin
from .models import (
    IndividualVendorProfile, BusinessVendorProfile,
    VendorProfile, VendorEmployee,
    VendorDocument, VettingApplication, Address,
    BusinessFollower,
)


class IndividualVendorDocumentInline(admin.TabularInline):
    model = VendorDocument
    fk_name = 'individual_vendor'
    extra = 0
    fields = ['document_type', 'document_name', 'document_file', 'status', 'review_notes']
    readonly_fields = ['uploaded_at']


class IndividualVettingInline(admin.TabularInline):
    model = VettingApplication
    fk_name = 'individual_vendor'
    extra = 0
    fields = ['vetting_type', 'status', 'id_verified', 'address_verified', 'selfie_verified', 'submitted_at']
    readonly_fields = ['submitted_at']


@admin.register(IndividualVendorProfile)
class IndividualVendorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'store_name', 'user', 'vendor_type', 'role', 'department',
        'status', 'verification_status',
        'store_active', 'total_sales', 'average_rating', 'created_at'
    ]
    list_filter = [
        'vendor_type', 'role', 'department', 'status',
        'verification_status', 'store_active', 'created_at',
    ]
    search_fields = [
        'store_name', 'user__email', 'user__first_name', 'user__last_name',
        'id_number', 'role_title',
    ]
    readonly_fields = [
        'qr_code', 'qr_code_identifier',
        'total_sales', 'total_orders', 'average_rating', 'total_reviews',
        'verified_at', 'created_at', 'updated_at'
    ]
    inlines = [IndividualVendorDocumentInline, IndividualVettingInline]

    fieldsets = [
        ('Owner', {
            'fields': ['user']
        }),
        ('Owner Role', {
            # Mirrors the AdminProfile pattern — role + department +
            # title + status. Synced onto the manager's
            # `VendorEmployee` row by `business.signals`.
            'fields': ['role', 'department', 'role_title', 'status'],
        }),
        ('Store Info', {
            'fields': ['vendor_type', 'store_name', 'store_description', 'store_logo', 'categories']
        }),
        ('QR Code', {
            'fields': ['qr_code', 'qr_code_identifier']
        }),
        ('Owner Identity (Vetting)', {
            'fields': ['id_number', 'id_document', 'proof_of_address', 'selfie_with_id']
        }),
        ('Trading Location', {
            'fields': ['trading_address', 'trading_city', 'trading_province', 'trading_postal_code']
        }),
        ('Banking', {
            'fields': ['bank_name', 'bank_account_number', 'bank_branch_code', 'bank_account_holder']
        }),
        ('Verification', {
            'fields': [
                'verification_status', 'rejection_reason',
                'verified_at', 'verified_by'
            ]
        }),
        ('Performance Metrics', {
            'fields': ['total_sales', 'total_orders', 'average_rating', 'total_reviews', 'commission_rate'],
            'classes': ['collapse']
        }),
        ('Store Settings', {
            'fields': ['store_active', 'accepts_returns', 'return_window_days']
        }),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class BusinessVendorDocumentInline(admin.TabularInline):
    model = VendorDocument
    fk_name = 'business_vendor'
    extra = 0
    fields = ['document_type', 'document_name', 'document_file', 'status', 'review_notes']
    readonly_fields = ['uploaded_at']


class BusinessVettingInline(admin.TabularInline):
    model = VettingApplication
    fk_name = 'business_vendor'
    extra = 0
    fields = [
        'vetting_type', 'status',
        'id_verified', 'address_verified', 'cipc_verified', 'tax_verified', 'bank_verified',
        'submitted_at'
    ]
    readonly_fields = ['submitted_at']


@admin.register(BusinessVendorProfile)
class BusinessVendorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'business_name', 'user', 'business_type', 'cipc_registration_number',
        'role', 'department', 'status',
        'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
        'store_active', 'total_sales', 'created_at'
    ]
    list_filter = [
        'business_type', 'role', 'department', 'status',
        'verification_status',
        'owner_vetting_passed', 'business_vetting_passed',
        'store_active', 'created_at'
    ]
    search_fields = [
        'business_name', 'user__email', 'cipc_registration_number',
        'tax_number', 'owner_full_name', 'owner_id_number', 'role_title',
    ]
    readonly_fields = [
        'qr_code', 'qr_code_identifier',
        'total_sales', 'total_orders', 'average_rating', 'total_reviews',
        'verified_at', 'created_at', 'updated_at'
    ]
    inlines = [BusinessVendorDocumentInline, BusinessVettingInline]

    fieldsets = [
        ('Owner Account', {
            'fields': ['user']
        }),
        ('Owner Role', {
            'fields': ['role', 'department', 'role_title', 'status'],
        }),
        ('Business Identity', {
            'fields': [
                'business_name', 'business_trading_name', 'business_type',
                'business_description', 'business_logo', 'business_website'
            ]
        }),
        ('QR Code', {
            'fields': ['qr_code', 'qr_code_identifier']
        }),
        ('CIPC & Registration', {
            'fields': [
                'cipc_registration_number', 'cipc_document',
                'tax_number', 'tax_clearance_certificate',
                'vat_number', 'bee_certificate'
            ]
        }),
        ('Owner / Director (Vetting)', {
            'fields': [
                'owner_full_name', 'owner_id_number',
                'owner_id_document', 'owner_proof_of_address'
            ]
        }),
        ('Business Address', {
            'fields': [
                'business_street_address', 'business_city',
                'business_province', 'business_postal_code', 'business_country'
            ]
        }),
        ('Banking', {
            'fields': ['bank_name', 'bank_account_number', 'bank_branch_code', 'bank_account_holder']
        }),
        ('Verification', {
            'fields': [
                'verification_status', 'owner_vetting_passed', 'business_vetting_passed',
                'rejection_reason', 'verified_at', 'verified_by'
            ]
        }),
        ('Performance Metrics', {
            'fields': ['total_sales', 'total_orders', 'average_rating', 'total_reviews', 'commission_rate'],
            'classes': ['collapse']
        }),
        ('Store Settings', {
            'fields': ['store_active', 'accepts_returns', 'return_window_days']
        }),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(VendorDocument)
class VendorDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_name', 'document_type', 'status', 'get_vendor', 'uploaded_at']
    list_filter = ['document_type', 'status', 'uploaded_at']
    search_fields = ['document_name', 'individual_vendor__store_name', 'business_vendor__business_name']
    readonly_fields = ['uploaded_at']

    def get_vendor(self, obj):
        if obj.individual_vendor:
            return f"[Individual] {obj.individual_vendor.store_name}"
        if obj.business_vendor:
            return f"[Business] {obj.business_vendor.business_name}"
        return '-'
    get_vendor.short_description = 'Vendor'


@admin.register(VettingApplication)
class VettingApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'get_vendor', 'vetting_type', 'status',
        'id_verified', 'address_verified', 'cipc_verified',
        'assigned_to', 'submitted_at', 'completed_at'
    ]
    list_filter = ['vetting_type', 'status', 'submitted_at']
    search_fields = [
        'individual_vendor__store_name', 'individual_vendor__user__email',
        'business_vendor__business_name', 'business_vendor__user__email'
    ]
    readonly_fields = ['submitted_at']

    fieldsets = [
        ('Vendor', {
            'fields': ['individual_vendor', 'business_vendor']
        }),
        ('Vetting Details', {
            'fields': ['vetting_type', 'status', 'assigned_to']
        }),
        ('Verification Checklist', {
            'fields': [
                'id_verified', 'address_verified', 'selfie_verified',
                'cipc_verified', 'tax_verified', 'bank_verified'
            ]
        }),
        ('Notes', {
            'fields': ['notes', 'rejection_reason']
        }),
        ('Dates', {
            'fields': ['submitted_at', 'reviewed_at', 'completed_at']
        }),
    ]

    def get_vendor(self, obj):
        if obj.individual_vendor:
            return f"[Individual] {obj.individual_vendor.store_name}"
        if obj.business_vendor:
            return f"[Business] {obj.business_vendor.business_name}"
        return '-'
    get_vendor.short_description = 'Vendor'


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Vendor business addresses — linked to VendorProfile."""

    list_display = [
        'vendor_display', 'address_type', 'full_name', 'city',
        'state_province', 'country', 'is_default',
        'latitude', 'longitude',
    ]
    list_filter = ['address_type', 'country', 'is_default']
    search_fields = [
        'vendor__name', 'vendor__trading_name',
        'full_name', 'street_address',
        'city', 'state_province', 'postal_code',
    ]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        ('Vendor & Type', {'fields': ['vendor', 'address_type', 'is_default']}),
        ('Contact', {'fields': ['full_name', 'phone_number']}),
        ('Address', {
            'fields': [
                'street_address', 'apartment_number', 'city',
                'state_province', 'postal_code', 'country'
            ]
        }),
        ('Coordinates', {
            'fields': ['latitude', 'longitude'],
            'description': 'Used for delivery distance / fare calculation.',
        }),
        ('Additional Info', {'fields': ['delivery_instructions']}),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        from .admin_helpers import vendor_profile_label
        return vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            from .admin_helpers import vendor_profile_formfield
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor', 'vendor__user')


@admin.register(BusinessFollower)
class BusinessFollowerAdmin(admin.ModelAdmin):
    list_display = ['user', 'vendor', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'vendor__email']
    readonly_fields = ['created_at']


# =============================================================================
# Unified VendorProfile + VendorEmployee
# =============================================================================
#
# Both new tables exposed in Django admin so the platform team can
# inspect / patch role + department + status data inline without
# round-tripping through the REST API. Mirrors the columns surfaced
# on the AdminProfile admin so the look-and-feel stays consistent.

class VendorEmployeeInline(admin.TabularInline):
    """Team roster shown inline on the VendorProfile change page."""
    model = VendorEmployee
    extra = 0
    fields = [
        'user', 'is_manager', 'role_title', 'department',
        'verification_status', 'is_active', 'created_at',
    ]
    readonly_fields = ['created_at']
    show_change_link = True


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'user', 'profile_type', 'business_category',
        'role', 'department', 'status',
        'verification_status', 'store_active', 'created_at',
    ]
    list_filter = [
        'profile_type', 'business_category',
        'role', 'department', 'status',
        'verification_status', 'owner_vetting_passed',
        'business_vetting_passed', 'store_active', 'created_at',
    ]
    search_fields = [
        'name', 'trading_name', 'user__email',
        'role_title', 'cipc_registration_number',
        'owner_full_name', 'owner_id_number',
    ]
    readonly_fields = [
        'id', 'qr_code', 'qr_code_identifier',
        'total_sales', 'total_orders', 'average_rating', 'total_reviews',
        'verified_at', 'created_at', 'updated_at',
    ]
    fieldsets = [
        ('Owner', {'fields': ['user', 'profile_type']}),
        ('Owner Role', {
            'fields': ['role', 'department', 'role_title', 'status'],
        }),
        ('Identity & Branding', {
            'fields': [
                'name', 'trading_name', 'description', 'logo', 'website',
                'business_category', 'vendor_type', 'business_type',
                'qr_code', 'qr_code_identifier',
            ],
        }),
        ('Individual-only documents', {
            'classes': ['collapse'],
            'fields': [
                'id_number', 'id_document', 'proof_of_address', 'selfie_with_id',
            ],
        }),
        ('Business-only documents', {
            'classes': ['collapse'],
            'fields': [
                'cipc_registration_number', 'cipc_document',
                'tax_number', 'tax_clearance_certificate',
                'vat_number', 'bee_certificate',
                'owner_full_name', 'owner_id_number',
                'owner_id_document', 'owner_proof_of_address',
            ],
        }),
        ('Address', {
            'fields': [
                'street_address', 'city', 'province', 'postal_code', 'country',
                'latitude', 'longitude',
            ],
        }),
        ('Banking', {
            'fields': [
                'bank_name', 'bank_account_number',
                'bank_branch_code', 'bank_account_holder',
            ],
        }),
        ('Verification', {
            'fields': [
                'verification_status',
                'owner_vetting_passed', 'business_vetting_passed',
                'rejection_reason', 'verified_at', 'verified_by',
            ],
        }),
        ('Performance', {
            'classes': ['collapse'],
            'fields': [
                'total_sales', 'total_orders',
                'average_rating', 'total_reviews', 'commission_rate',
            ],
        }),
        ('Operations', {
            'fields': [
                'store_active', 'accepts_returns', 'return_window_days',
                'opening_hours', 'is_temporarily_closed',
            ],
        }),
        ('Timestamps', {
            'classes': ['collapse'],
            'fields': ['created_at', 'updated_at'],
        }),
    ]
    inlines = [VendorEmployeeInline]
    filter_horizontal = ['categories']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(VendorEmployee)
class VendorEmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'vendor', 'is_manager', 'role_title', 'department',
        'verification_status', 'is_active', 'created_at',
    ]
    list_filter = [
        'is_manager', 'is_active', 'department',
        'verification_status', 'created_at',
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'role_title', 'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at',
        'verified_at',
    ]
    fieldsets = [
        ('Membership', {
            'fields': ['vendor', 'user', 'is_manager', 'is_active'],
        }),
        ('Role', {
            'fields': ['role_title', 'department'],
        }),
        ('Verification', {
            'fields': [
                'verification_status', 'rejection_reason',
                'verified_at', 'verified_by',
            ],
        }),
        ('Permissions', {
            'description': 'JSON `{key: bool}` map. See '
                           '`VendorEmployee.PERMISSION_KEYS` for the '
                           'canonical key list.',
            'fields': ['permissions'],
        }),
        ('Timestamps', {
            'classes': ['collapse'],
            'fields': ['created_at', 'updated_at'],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'vendor')

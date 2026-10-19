from django.contrib import admin
from .models import AdminProfile, AdminInvitation, PlatformFee


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'role', 'department', 'status',
        'work_email', 'invited_by_display', 'last_login_at', 'created_at',
    ]
    list_filter = ['role', 'department', 'status']
    search_fields = ['user__email', 'work_email', 'role_title']
    readonly_fields = [
        'id', 'user', 'invited_by', 'permissions',
        'last_login_at', 'created_at', 'updated_at',
    ]
    ordering = ['role', 'user__email']

    fieldsets = [
        ('Identity', {
            'fields': ['id', 'user', 'work_email', 'profile_photo'],
        }),
        ('Role', {
            'fields': ['role', 'department', 'role_title', 'status'],
        }),
        ('Hierarchy', {
            'fields': ['invited_by'],
        }),
        ('Permissions', {
            'fields': ['permissions'],
            'classes': ['collapse'],
        }),
        ('Timestamps', {
            'fields': ['last_login_at', 'created_at', 'updated_at'],
        }),
    ]

    @admin.display(description='User Email')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Invited By')
    def invited_by_display(self, obj):
        if obj.invited_by:
            return obj.invited_by.user.email
        return '—'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'invited_by__user')


@admin.register(AdminInvitation)
class AdminInvitationAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'role', 'department', 'status',
        'invited_by_display', 'accepted_by_display',
        'expires_at', 'created_at',
    ]
    list_filter = ['role', 'department', 'status']
    search_fields = ['email', 'invited_by__user__email']
    readonly_fields = [
        'id', 'token', 'invited_by', 'accepted_by',
        'expires_at', 'created_at',
    ]
    ordering = ['-created_at']

    fieldsets = [
        ('Invitation', {
            'fields': ['id', 'email', 'role', 'department', 'token', 'status'],
        }),
        ('Participants', {
            'fields': ['invited_by', 'accepted_by'],
        }),
        ('Timestamps', {
            'fields': ['expires_at', 'created_at'],
        }),
    ]

    @admin.display(description='Invited By')
    def invited_by_display(self, obj):
        return obj.invited_by.user.email

    @admin.display(description='Accepted By')
    def accepted_by_display(self, obj):
        if obj.accepted_by:
            return obj.accepted_by.user.email
        return '—'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'invited_by__user', 'accepted_by__user',
        )


@admin.register(PlatformFee)
class PlatformFeeAdmin(admin.ModelAdmin):
    list_display = [
        'business_type',
        'customer_service_fee_range',
        'merchant_commission_range',
        'is_active', 'updated_at',
    ]
    list_filter = ['business_type', 'is_active']
    readonly_fields = [
        'id', 'updated_by',
        'customer_service_fee_range', 'merchant_commission_range',
        'created_at', 'updated_at',
    ]
    fieldsets = [
        ('Business type', {
            'fields': ['id', 'business_type', 'is_active'],
        }),
        ('Customer service fee', {
            'fields': [
                ('customer_service_fee_min', 'customer_service_fee_max'),
                'customer_service_fee_range',
            ],
        }),
        ('Merchant commission', {
            'fields': [
                ('merchant_commission_min', 'merchant_commission_max'),
                'merchant_commission_range',
            ],
        }),
        ('Audit', {
            'fields': ['notes', 'updated_by', 'created_at', 'updated_at'],
        }),
    ]

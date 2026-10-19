from django.contrib import admin
from django.utils.html import format_html
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import CreditAccount, CreditPurchase, CreditRepayment


class CreditPurchaseVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'debit_sales'


class CreditRepaymentInline(admin.TabularInline):
    model = CreditRepayment
    extra = 0
    readonly_fields = [
        'id', 'amount', 'principal_portion', 'penalty_portion',
        'payment_method', 'repayment_type', 'reference', 'created_at',
    ]


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'status_badge', 'credit_limit', 'current_balance',
        'total_penalties', 'is_user_suspended', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'updated_at', 'suspended_at']
    actions = ['suspend_accounts', 'unsuspend_accounts']

    fieldsets = [
        ('User', {'fields': ['user', 'subscription', 'status']}),
        ('Credit', {'fields': ['credit_limit', 'current_balance', 'total_penalties']}),
        ('Suspension', {'fields': ['suspended_at', 'last_penalty_date']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def status_badge(self, obj):
        colors = {'active': 'green', 'suspended': 'red', 'closed': 'gray'}
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def is_user_suspended(self, obj):
        return obj.user.is_suspended
    is_user_suspended.boolean = True
    is_user_suspended.short_description = 'User Suspended'

    def suspend_accounts(self, request, queryset):
        for account in queryset.filter(status='active'):
            account.suspend('Admin-initiated suspension')
        self.message_user(request, f'Suspended {queryset.count()} account(s).')
    suspend_accounts.short_description = 'Suspend selected accounts'

    def unsuspend_accounts(self, request, queryset):
        count = 0
        for account in queryset.filter(status='suspended'):
            if account.unsuspend():
                count += 1
        self.message_user(request, f'Unsuspended {count} account(s).')
    unsuspend_accounts.short_description = 'Unsuspend selected accounts'


@admin.register(CreditPurchase)
class CreditPurchaseAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'get_user', 'vendor_display', 'total_amount', 'deposit_amount',
        'remaining_amount', 'amount_paid', 'penalty_amount',
        'status_badge', 'due_date', 'grace_end_date', 'created_at',
    ]
    list_filter = [CreditPurchaseVendorFilter, 'status', 'created_at', 'due_date']
    search_fields = [
        'credit_account__user__email',
        'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'defaulted_at']
    inlines = [CreditRepaymentInline]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        return vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'credit_account__user', 'vendor', 'vendor__user',
        )

    fieldsets = [
        ('Purchase Info', {
            'fields': ['id', 'credit_account', 'vendor', 'order', 'status'],
        }),
        ('Amounts', {
            'fields': [
                'total_amount', 'deposit_amount', 'remaining_amount',
                'amount_paid', 'penalty_amount', 'penalty_paid',
            ],
        }),
        ('Dates', {
            'fields': [
                'due_date', 'grace_end_date', 'paid_at', 'defaulted_at',
                'created_at', 'updated_at',
            ],
        }),
    ]

    def get_user(self, obj):
        return obj.credit_account.user.email
    get_user.short_description = 'Customer'

    def status_badge(self, obj):
        colors = {
            'active': 'blue', 'paid': 'green', 'defaulted': 'red',
            'pending': 'orange', 'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'


@admin.register(CreditRepayment)
class CreditRepaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'purchase', 'amount', 'principal_portion', 'penalty_portion',
        'payment_method', 'repayment_type', 'reference', 'created_at',
    ]
    list_filter = ['payment_method', 'repayment_type', 'created_at']
    search_fields = ['purchase__credit_account__user__email', 'reference']
    readonly_fields = ['id', 'created_at']

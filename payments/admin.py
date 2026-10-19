from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import (
    PaystackSubaccount, TransactionSplit, TransactionSplitSubaccount,
    Transaction, Refund, Dispute, PaymentLog, PaystackWebhookEvent,
)


class SubaccountVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'paystack_subaccount'


# ── Subaccount ───────────────────────────────────────────────

@admin.register(PaystackSubaccount)
class PaystackSubaccountAdmin(admin.ModelAdmin):
    list_display = [
        'business_name', 'vendor_display', 'subaccount_code',
        'settlement_bank', 'account_number', 'percentage_charge',
        'is_active', 'created_at',
    ]
    list_filter = [SubaccountVendorFilter, 'is_active', 'created_at']
    search_fields = [
        'business_name', 'subaccount_code', 'account_number',
        'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = ['id', 'subaccount_code', 'paystack_subaccount_id', 'account_name', 'created_at', 'updated_at']

    fieldsets = [
        ('Vendor', {'fields': ['id', 'vendor']}),
        ('Paystack', {'fields': ['subaccount_code', 'paystack_subaccount_id']}),
        ('Bank Details', {'fields': [
            'business_name', 'settlement_bank', 'account_number',
            'bank_name', 'account_name',
        ]}),
        ('Commission', {'fields': ['percentage_charge', 'flat_charge']}),
        ('Settings', {'fields': ['primary_contact_email', 'is_active', 'metadata']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        return vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor', 'vendor__user')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor')


# ── Transaction Split ────────────────────────────────────────

class TransactionSplitSubaccountInline(admin.TabularInline):
    model = TransactionSplitSubaccount
    extra = 0
    raw_id_fields = ['subaccount']


@admin.register(TransactionSplit)
class TransactionSplitAdmin(admin.ModelAdmin):
    list_display = ['name', 'paystack_split_code', 'split_type', 'currency', 'bearer_type', 'is_active']
    list_filter = ['split_type', 'currency', 'is_active']
    search_fields = ['name', 'paystack_split_code']
    readonly_fields = ['id', 'paystack_split_id', 'paystack_split_code', 'created_at', 'updated_at']
    inlines = [TransactionSplitSubaccountInline]

    fieldsets = [
        ('Info', {'fields': ['id', 'name', 'paystack_split_code', 'paystack_split_id']}),
        ('Configuration', {'fields': ['split_type', 'currency', 'bearer_type', 'bearer_subaccount']}),
        ('Settings', {'fields': ['is_active', 'metadata']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


# ── Transaction ──────────────────────────────────────────────

class PaymentLogInline(admin.TabularInline):
    model = PaymentLog
    extra = 0
    readonly_fields = ['created_at']
    fields = ['log_type', 'message', 'http_status_code', 'created_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'user', 'vendor_display', 'amount', 'currency',
        'status', 'channel', 'payment_intent', 'created_at',
    ]
    list_filter = ['status', 'channel', 'payment_intent', 'currency', 'created_at']
    search_fields = [
        'reference', 'user__email', 'paystack_transaction_id',
        'order__order_number', 'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = [
        'id', 'reference', 'paystack_transaction_id', 'access_code',
        'authorization_url', 'authorization_code',
        'is_successful', 'is_refundable', 'net_amount', 'amount_in_kobo',
        'created_at', 'updated_at', 'paid_at',
    ]
    raw_id_fields = ['order', 'user', 'vendor', 'subscription', 'vendor_tier_subscription', 'subaccount', 'split']
    inlines = [PaymentLogInline]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        vp = obj.vendor
        if not vp:
            return '—'
        user = vp.user
        individual = getattr(user, 'individual_vendor_profile', None)
        business = getattr(user, 'business_vendor_profile', None)
        if individual:
            name = individual.store_name
            url = reverse('admin:business_individualvendorprofile_change', args=[individual.pk])
        elif business:
            name = business.business_trading_name or business.business_name
            url = reverse('admin:business_businessvendorprofile_change', args=[business.pk])
        else:
            return vendor_profile_label(vp) or '—'
        return format_html('<a href="{}">{}</a>', url, name)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            return vendor_profile_formfield(formfield)
        return formfield

    fieldsets = [
        ('Basic Info', {'fields': [
            'id', 'reference', 'payment_intent',
            'order', 'subscription', 'vendor_tier_subscription', 'user', 'vendor',
        ]}),
        ('Amount', {'fields': [
            'amount', 'currency', 'paystack_fees', 'net_amount', 'amount_in_kobo',
        ]}),
        ('Status', {'fields': [
            'status', 'channel', 'gateway_response',
        ]}),
        ('Paystack', {'fields': [
            'paystack_transaction_id', 'access_code', 'authorization_url',
        ]}),
        ('Authorization (Card)', {'fields': [
            'authorization_code', 'card_type', 'last4', 'exp_month', 'exp_year', 'bank',
        ], 'classes': ['collapse']}),
        ('Split / Subaccount', {'fields': ['split', 'subaccount'], 'classes': ['collapse']}),
        ('Customer', {'fields': ['paystack_customer_code'], 'classes': ['collapse']}),
        ('Metadata', {'fields': ['ip_address', 'metadata', 'paystack_response'], 'classes': ['collapse']}),
        ('Failure', {'fields': ['failure_reason'], 'classes': ['collapse']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at', 'paid_at'], 'classes': ['collapse']}),
        ('Properties', {'fields': ['is_successful', 'is_refundable'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user',
            'vendor', 'vendor__user',
            'vendor__user__individual_vendor_profile',
            'vendor__user__business_vendor_profile',
            'order', 'subscription', 'vendor_tier_subscription',
            'subaccount', 'split',
        )


# ── Refund ───────────────────────────────────────────────────

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'transaction', 'user', 'amount',
        'reason', 'status', 'created_at',
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = [
        'user__email', 'transaction__reference', 'paystack_refund_id',
    ]
    readonly_fields = [
        'id', 'paystack_refund_id', 'is_successful',
        'created_at', 'updated_at', 'processed_at', 'approved_at',
    ]
    raw_id_fields = ['transaction', 'order', 'user', 'approved_by']

    fieldsets = [
        ('Info', {'fields': ['id', 'transaction', 'order', 'user']}),
        ('Refund Details', {'fields': ['amount', 'currency', 'reason', 'customer_note', 'merchant_note']}),
        ('Status', {'fields': ['status', 'paystack_refund_id']}),
        ('Admin', {'fields': ['approved_by', 'admin_notes', 'approved_at'], 'classes': ['collapse']}),
        ('Paystack', {'fields': ['paystack_response'], 'classes': ['collapse']}),
        ('Failure', {'fields': ['failure_reason'], 'classes': ['collapse']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at', 'processed_at'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('transaction', 'user', 'order', 'approved_by')


# ── Dispute ──────────────────────────────────────────────────

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'paystack_dispute_id', 'transaction', 'user', 'amount',
        'status', 'category', 'due_at', 'created_at',
    ]
    list_filter = ['status', 'category', 'created_at']
    search_fields = [
        'paystack_dispute_id', 'user__email', 'transaction__reference',
    ]
    readonly_fields = [
        'id', 'paystack_dispute_id', 'created_at', 'updated_at', 'resolved_at',
    ]
    raw_id_fields = ['transaction', 'user']

    fieldsets = [
        ('Info', {'fields': ['id', 'paystack_dispute_id', 'transaction', 'user']}),
        ('Dispute Details', {'fields': [
            'amount', 'currency', 'status', 'category', 'message',
        ]}),
        ('Response', {'fields': ['resolution', 'merchant_response']}),
        ('Evidence', {'fields': ['evidence', 'attachments'], 'classes': ['collapse']}),
        ('Paystack Data', {'fields': ['paystack_response'], 'classes': ['collapse']}),
        ('Dates', {'fields': ['due_at', 'resolved_at', 'created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('transaction', 'user')


# ── Payment Log ──────────────────────────────────────────────

@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ['log_type', 'message', 'transaction', 'http_status_code', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['message', 'transaction__reference']
    readonly_fields = ['created_at']
    raw_id_fields = ['transaction', 'refund', 'dispute']

    fieldsets = [
        ('Log', {'fields': ['transaction', 'refund', 'dispute', 'log_type', 'message']}),
        ('Data', {'fields': ['request_data', 'response_data'], 'classes': ['collapse']}),
        ('HTTP', {'fields': ['http_status_code', 'ip_address'], 'classes': ['collapse']}),
        ('Timestamp', {'fields': ['created_at']}),
    ]


# ── Webhook Events ───────────────────────────────────────────

@admin.register(PaystackWebhookEvent)
class PaystackWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'event_id', 'status', 'transaction', 'created_at']
    list_filter = ['event_type', 'status', 'created_at']
    search_fields = ['event_type', 'event_id']
    readonly_fields = ['created_at', 'processed_at']
    raw_id_fields = ['transaction']

    fieldsets = [
        ('Event', {'fields': ['event_type', 'event_id', 'status']}),
        ('Data', {'fields': ['raw_data', 'processed_data'], 'classes': ['collapse']}),
        ('Processing', {'fields': ['processing_error', 'transaction']}),
        ('Timestamps', {'fields': ['created_at', 'processed_at']}),
    ]

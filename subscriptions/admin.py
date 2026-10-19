from django.contrib import admin
from .models import Plan, Subscription, SubscriptionCancellation


@admin.register(SubscriptionCancellation)
class SubscriptionCancellationAdmin(admin.ModelAdmin):
    list_display = ['subscription_code', 'reason', 'attempts', 'next_attempt_at', 'completed_at']
    list_filter = ['completed_at']
    readonly_fields = ['subscription_code', 'reason', 'attempts', 'next_attempt_at',
                       'completed_at', 'last_error', 'created_at']
    exclude = ['email_token']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'plan_tier', 'billing_cycle', 'price', 'credit_limit',
        'interest_rate', 'deposit_percent', 'max_items_on_credit', 'is_active', 'sort_order',
    ]
    list_filter = ['is_active', 'plan_tier', 'billing_cycle', 'requires_follower']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = [
        ('Plan Details', {'fields': [
            'id', 'name', 'slug', 'description', 'plan_tier', 'billing_cycle', 'price',
        ]}),
        ('Credit Terms', {'fields': [
            'credit_limit', 'interest_rate', 'deposit_percent', 'max_items_on_credit',
        ]}),
        ('Repayment', {'fields': [
            'repayment_days', 'grace_period_days', 'late_payment_penalty_percent',
        ]}),
        ('Fee Discounts', {'fields': [
            'service_fee_discount_percent', 'delivery_fee_discount_percent',
        ]}),
        ('Duration', {'fields': ['duration', 'duration_unit', 'trial_days']}),
        ('Features', {'fields': ['features']}),
        ('Requirements', {'fields': ['requires_follower']}),
        ('Display', {'fields': ['is_active', 'sort_order']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end', 'created_at']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['user__email', 'plan__name']
    readonly_fields = ['id', 'started_at', 'created_at', 'updated_at']

    fieldsets = [
        ('User & Plan', {'fields': ['id', 'user', 'plan', 'status']}),
        ('Period', {'fields': ['current_period_start', 'current_period_end']}),
        ('Cancellation', {'fields': ['cancelled_at']}),
        ('Timestamps', {'fields': ['started_at', 'created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

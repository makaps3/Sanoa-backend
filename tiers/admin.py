from django.contrib import admin
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import BusinessTier, VendorTierSubscription


class TierSubscriptionVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'tier_subscription'


@admin.register(BusinessTier)
class BusinessTierAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'price', 'tier_level', 'commission_discount',
        'max_products', 'negotiation_enabled', 'is_active', 'sort_order'
    ]
    list_filter = ['is_active', 'negotiation_enabled', 'featured_listings']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        ('Tier Info', {
            'fields': ['name', 'slug', 'description', 'price', 'tier_level']
        }),
        ('Billing', {
            'fields': ['duration', 'duration_unit', 'trial_days']
        }),
        ('Business Limits', {
            'fields': ['max_products', 'commission_discount',
                       'commission_rate']
        }),
        ('Search & Visibility', {
            'fields': ['search_priority_boost', 'featured_listings']
        }),
        ('Negotiation', {
            'fields': ['negotiation_enabled', 'max_markup_percent', 'max_discount_percent']
        }),
        ('Features', {
            'fields': ['features']
        }),
        ('Display', {
            'fields': ['is_active', 'sort_order']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(VendorTierSubscription)
class VendorTierSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'vendor_display', 'tier', 'status',
        'current_period_start', 'current_period_end', 'cancelled_at'
    ]
    list_filter = [TierSubscriptionVendorFilter, 'status', 'tier', 'created_at']
    search_fields = [
        'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        ('Subscription', {
            'fields': ['vendor', 'tier', 'status']
        }),
        ('Period', {
            'fields': ['current_period_start', 'current_period_end', 'cancelled_at']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
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
        return super().get_queryset(request).select_related('vendor', 'vendor__user', 'tier')

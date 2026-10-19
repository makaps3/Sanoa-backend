from django.contrib import admin

from .models import (
    AppliedCoupon,
    Coupon,
    CouponRedemption,
    Promotion,
    PromotionBanner,
    PromotionRedemption,
)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_type', 'vendor', 'discount_type', 'value',
                    'is_active', 'start_date', 'end_date', 'times_used')
    list_filter = ('owner_type', 'discount_type', 'is_active', 'scope')
    search_fields = ('name', 'description')
    filter_horizontal = ('applicable_products', 'applicable_categories')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'owner_type', 'vendor', 'discount_type',
                    'value', 'is_active', 'times_used', 'max_uses')
    list_filter = ('owner_type', 'discount_type', 'is_active', 'scope')
    search_fields = ('code', 'name', 'description')
    filter_horizontal = ('applicable_products', 'applicable_categories')


@admin.register(AppliedCoupon)
class AppliedCouponAdmin(admin.ModelAdmin):
    list_display = ('cart', 'coupon', 'applied_at')


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order', 'discount_amount', 'redeemed_at')
    search_fields = ('coupon__code',)


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'user', 'order', 'discount_amount',
                    'redeemed_at')


@admin.register(PromotionBanner)
class PromotionBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner_type', 'vendor', 'action_type',
                    'is_active', 'sort_order', 'start_date', 'end_date')
    list_filter = ('owner_type', 'action_type', 'is_active')
    search_fields = ('title', 'subtitle')

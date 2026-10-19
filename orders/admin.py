from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import (
    ShippingAddress, ShoppingCart, CartItem, Order, OrderItem,
    OrderStatusHistory, Coupon,
)


class CartVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'carts'


class OrderItemVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'order_items'


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    """Customer shipping addresses."""

    list_display = [
        'full_name', 'user', 'address_type', 'label', 'city',
        'state_province', 'country', 'is_default',
        'latitude', 'longitude',
    ]
    list_filter = ['address_type', 'country', 'is_default']
    search_fields = [
        'full_name', 'label', 'street_address',
        'city', 'state_province', 'postal_code',
        'user__email', 'user__first_name', 'user__last_name',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']

    fieldsets = [
        ('Customer & Type', {
            'fields': ['id', 'user', 'address_type', 'label', 'is_default'],
        }),
        ('Contact', {'fields': ['full_name', 'phone_number']}),
        ('Address', {
            'fields': [
                'street_address', 'apartment_number', 'city',
                'state_province', 'postal_code', 'country',
            ]
        }),
        ('Coordinates', {
            'fields': ['latitude', 'longitude'],
            'description': 'Used for delivery distance / fare calculation.',
        }),
        ('Additional Info', {'fields': ['delivery_instructions']}),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['price_at_time', 'total_price', 'created_at']
    fields = [
        'product', 'product_variant', 'quantity',
        'price_at_time', 'total_price', 'created_at'
    ]


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ['user', 'vendor_display', 'total_items', 'total_amount', 'created_at', 'updated_at']
    list_filter = [CartVendorFilter, 'created_at', 'updated_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = ['total_items', 'total_amount', 'created_at', 'updated_at']

    inlines = [CartItemInline]

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
            'user', 'vendor', 'vendor__user',
        )


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = [
        'cart', 'product', 'product_variant', 'quantity', 
        'price_at_time', 'total_price', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = [
        'cart__user__email', 'product__name', 'product_variant__name'
    ]
    readonly_fields = ['total_price', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'cart__user', 'product', 'product_variant'
        )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        'product_name', 'product_sku', 'variant_name', 
        'unit_price', 'total_price', 'vendor'
    ]
    fields = [
        'product', 'product_variant', 'product_name', 'variant_name',
        'quantity', 'unit_price', 'total_price', 'vendor'
    ]


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['created_at']
    fields = ['previous_status', 'new_status', 'comment', 'changed_by', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user', 'status', 'payment_status', 
        'total_amount', 'created_at'
    ]
    list_filter = [
        'status', 'payment_status', 'created_at', 
        'shipped_at', 'delivered_at'
    ]
    search_fields = [
        'order_number', 'user__email', 'customer_email',
        'billing_full_name', 'shipping_full_name'
    ]
    readonly_fields = [
        'id', 'order_number', 'created_at', 'updated_at',
        'shipped_at', 'delivered_at', 'is_paid', 'can_be_cancelled'
    ]
    
    fieldsets = [
        ('Order Info', {
            'fields': [
                'id', 'order_number', 'user', 'status', 'payment_status'
            ]
        }),
        ('Pricing', {
            'fields': [
                'subtotal', 'tax_amount', 'shipping_cost', 
                'discount_amount', 'total_amount'
            ]
        }),
        ('Customer Info', {
            'fields': ['customer_email', 'customer_phone']
        }),
        ('Billing Address', {
            'fields': [
                'billing_full_name', 'billing_street_address',
                'billing_apartment_number', 'billing_city',
                'billing_state_province', 'billing_postal_code', 'billing_country'
            ],
            'classes': ['collapse']
        }),
        ('Shipping Address', {
            'fields': [
                'shipping_full_name', 'shipping_street_address',
                'shipping_apartment_number', 'shipping_city',
                'shipping_state_province', 'shipping_postal_code', 'shipping_country'
            ],
            'classes': ['collapse']
        }),
        ('Additional Info', {
            'fields': ['order_notes', 'internal_notes', 'coupon_code'],
            'classes': ['collapse']
        }),
        ('Dates', {
            'fields': [
                'created_at', 'updated_at', 'shipped_at', 'delivered_at'
            ],
            'classes': ['collapse']
        }),
        ('Status Info', {
            'fields': ['is_paid', 'can_be_cancelled'],
            'classes': ['collapse']
        }),
    ]
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered']
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} orders marked as processing.')
    mark_as_processing.short_description = "Mark selected orders as processing"
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        updated = 0
        for order in queryset:
            if order.status in ['pending', 'processing']:
                order.status = 'shipped'
                order.shipped_at = timezone.now()
                order.save()
                updated += 1
        self.message_user(request, f'{updated} orders marked as shipped.')
    mark_as_shipped.short_description = "Mark selected orders as shipped"
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = 0
        for order in queryset:
            if order.status == 'shipped':
                order.status = 'delivered'
                order.delivered_at = timezone.now()
                order.save()
                updated += 1
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = "Mark selected orders as delivered"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'product_name', 'variant_name', 'quantity',
        'unit_price', 'total_price', 'vendor_display'
    ]
    list_filter = [OrderItemVendorFilter, 'created_at']
    search_fields = [
        'order__order_number', 'product_name', 'variant_name',
        'product_sku',
        'vendor__name', 'vendor__trading_name',
    ]
    readonly_fields = [
        'product_name', 'product_sku', 'variant_name',
        'unit_price', 'total_price', 'vendor', 'created_at'
    ]

    fieldsets = [
        ('Order Info', {
            'fields': ['order', 'product', 'product_variant']
        }),
        ('Product Details (at time of order)', {
            'fields': [
                'product_name', 'product_sku', 'variant_name', 'vendor'
            ]
        }),
        ('Pricing', {
            'fields': ['quantity', 'unit_price', 'total_price']
        }),
        ('Timestamps', {
            'fields': ['created_at'],
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
        return super().get_queryset(request).select_related(
            'order', 'product', 'product_variant',
            'vendor', 'vendor__user',
        )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'previous_status', 'new_status', 
        'changed_by', 'created_at'
    ]
    list_filter = ['previous_status', 'new_status', 'created_at']
    search_fields = [
        'order__order_number', 'comment', 'changed_by__email'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = [
        ('Status Change', {
            'fields': ['order', 'previous_status', 'new_status', 'comment']
        }),
        ('Changed By', {
            'fields': ['changed_by', 'created_at']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'changed_by'
        )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'coupon_type', 'value', 'is_active',
        'current_uses', 'max_uses', 'start_date', 'end_date'
    ]
    list_filter = [
        'coupon_type', 'is_active', 'start_date', 'end_date', 'created_at'
    ]
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ['code', 'name', 'description']
        }),
        ('Discount Settings', {
            'fields': ['coupon_type', 'value']
        }),
        ('Usage Limits', {
            'fields': [
                'max_uses', 'max_uses_per_user', 'current_uses',
                'minimum_order_amount'
            ]
        }),
        ('Validity', {
            'fields': ['is_active', 'start_date', 'end_date']
        }),
        ('Applicable Items', {
            'fields': ['applicable_categories', 'applicable_products'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    filter_horizontal = ['applicable_categories', 'applicable_products']

from django.contrib import admin
from django.utils import timezone
from .models import (
    RestaurantCart, RestaurantCartItem,
    RestaurantOrder, RestaurantOrderItem,
    KitchenTicket, RestaurantOrderTrackingEvent,
)


class RestaurantCartItemInline(admin.TabularInline):
    model = RestaurantCartItem
    extra = 0
    readonly_fields = ['price_at_time', 'addons_total', 'total_price', 'created_at']
    fields = ['product', 'product_variant', 'quantity', 'price_at_time', 'addons_total', 'total_price', 'special_instructions']


@admin.register(RestaurantCart)
class RestaurantCartAdmin(admin.ModelAdmin):
    list_display = ['user', 'vendor', 'total_items', 'total_amount', 'created_at']
    search_fields = ['user__email', 'vendor__name', 'vendor__trading_name']
    readonly_fields = ['total_items', 'total_amount', 'created_at', 'updated_at']
    inlines = [RestaurantCartItemInline]


class RestaurantOrderItemInline(admin.TabularInline):
    model = RestaurantOrderItem
    extra = 0
    readonly_fields = ['product_name', 'product_sku', 'variant_name', 'unit_price', 'addons_total', 'total_price']
    fields = ['product', 'product_variant', 'product_name', 'variant_name', 'quantity', 'unit_price', 'addons_total', 'total_price', 'special_instructions']


class TrackingEventInline(admin.TabularInline):
    model = RestaurantOrderTrackingEvent
    extra = 0
    readonly_fields = ['event_type', 'message', 'metadata', 'created_at']
    fields = ['event_type', 'message', 'created_at']


@admin.register(RestaurantOrder)
class RestaurantOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user', 'vendor', 'status', 'payment_status',
        'fulfillment_type', 'total_amount', 'created_at',
    ]
    list_filter = ['status', 'payment_status', 'fulfillment_type', 'created_at']
    search_fields = ['order_number', 'user__email', 'customer_email', 'vendor__name']
    readonly_fields = ['id', 'order_number', 'subtotal', 'total_amount', 'confirmed_at', 'ready_at', 'delivered_at', 'created_at', 'updated_at']
    inlines = [RestaurantOrderItemInline, TrackingEventInline]

    actions = ['confirm_orders']

    def confirm_orders(self, request, queryset):
        updated = 0
        for order in queryset.filter(status='pending'):
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            KitchenTicket.objects.get_or_create(order=order)
            updated += 1
        self.message_user(request, f'{updated} order(s) confirmed.')
    confirm_orders.short_description = 'Confirm selected orders'


@admin.register(KitchenTicket)
class KitchenTicketAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'acknowledged_at', 'started_at', 'ready_at', 'handed_off_at']
    list_filter = ['status']
    search_fields = ['order__order_number']
    readonly_fields = ['id', 'acknowledged_at', 'started_at', 'ready_at', 'handed_off_at', 'created_at', 'updated_at']


@admin.register(RestaurantOrderTrackingEvent)
class RestaurantOrderTrackingEventAdmin(admin.ModelAdmin):
    list_display = ['order', 'event_type', 'message', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['order__order_number', 'message']
    readonly_fields = ['id', 'created_at']

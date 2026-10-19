from django.contrib import admin

from .models import NegotiationMessage, NegotiationOffer, NegotiationRoom, PricePolicy


@admin.register(PricePolicy)
class PricePolicyAdmin(admin.ModelAdmin):
    list_display = [
        'vendor', 'max_markup_percent', 'max_discount_percent',
        'min_floor_percent', 'auto_negotiate', 'is_active', 'updated_at',
    ]
    list_filter = ['auto_negotiate', 'is_active']
    search_fields = ['vendor__name', 'vendor__trading_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(NegotiationRoom)
class NegotiationRoomAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'product', 'buyer', 'vendor', 'mode', 'status',
        'agreed_price', 'offer_expires_at', 'created_at',
    ]
    list_filter = ['mode', 'status', 'created_at']
    search_fields = ['buyer__email', 'product__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['product', 'buyer', 'vendor']


@admin.register(NegotiationMessage)
class NegotiationMessageAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'room', 'sender_type', 'message_type', 'content_preview',
        'price_value', 'is_seen', 'created_at',
    ]
    list_filter = ['sender_type', 'message_type', 'is_seen']
    search_fields = ['content', 'room__id']
    readonly_fields = ['id', 'created_at', 'seen_at']
    raw_id_fields = ['room', 'sender']

    @admin.display(description='Content')
    def content_preview(self, obj):
        return obj.content[:80]


@admin.register(NegotiationOffer)
class NegotiationOfferAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'room', 'offered_by', 'original_price', 'offered_price',
        'counter_offer_price', 'status', 'round_number',
        'ai_action', 'ai_confidence', 'created_at',
    ]
    list_filter = ['offered_by', 'status', 'ai_action']
    search_fields = ['room__id']
    readonly_fields = ['id', 'created_at', 'responded_at', 'expires_at']
    raw_id_fields = ['room', 'message']

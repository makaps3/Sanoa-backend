from decimal import Decimal
from rest_framework import serializers

from orders.models import ShippingAddress
from .models import (
    RestaurantCart, RestaurantCartItem,
    RestaurantOrder, RestaurantOrderItem,
    KitchenTicket, RestaurantOrderTrackingEvent,
)


class RestaurantCartItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    addons_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Mirrors orders.CartItemSerializer so the frontend can use a
    # single set of negotiation getters across retail and restaurant
    # carts — `is_negotiated` flags the row, `negotiation_status` lets
    # the client gate checkout on the room status.
    is_negotiated = serializers.BooleanField(read_only=True)
    negotiation_id = serializers.UUIDField(read_only=True)
    negotiation_status = serializers.SerializerMethodField()
    negotiation_agreed_price = serializers.SerializerMethodField()
    # Display fields — without these the Flutter cart renders the
    # product UUID as the line-item title ("Menu item #<uuid>").
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    variant_name = serializers.CharField(source='product_variant.name', read_only=True)

    class Meta:
        model = RestaurantCartItem
        fields = [
            'id', 'product', 'product_name', 'product_image',
            'product_variant', 'variant_name',
            'quantity', 'price_at_time', 'total_price',
            'special_instructions', 'selected_addons', 'addons_total',
            'is_negotiated', 'negotiation_id',
            'negotiation_status', 'negotiation_agreed_price',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'product_name', 'product_image', 'variant_name',
            'price_at_time', 'total_price', 'addons_total',
            'is_negotiated', 'negotiation_id',
            'negotiation_status', 'negotiation_agreed_price',
            'created_at', 'updated_at',
        ]

    def get_negotiation_status(self, obj):
        return obj.negotiation.status if obj.negotiation_id else None

    def get_negotiation_agreed_price(self, obj):
        if obj.negotiation_id and obj.negotiation and obj.negotiation.agreed_price:
            return str(obj.negotiation.agreed_price)
        return None

    def get_product_image(self, obj):
        # Primary image first, otherwise the first uploaded one.
        img = (
            obj.product.images.filter(is_primary=True)
            .values_list('image', flat=True).first()
            or obj.product.images.values_list('image', flat=True).first()
        )
        if not img:
            return None
        request = self.context.get('request')
        url = f'/media/{img}'
        return request.build_absolute_uri(url) if request else url


class RestaurantCartSerializer(serializers.ModelSerializer):
    items = RestaurantCartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantCart
        fields = [
            'id', 'user', 'vendor', 'vendor_name',
            'items', 'total_items', 'total_amount',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'vendor', 'vendor_name', 'items', 'total_items', 'total_amount', 'created_at', 'updated_at']

    def get_vendor_name(self, obj):
        return obj.vendor.trading_name or obj.vendor.name or None


class RestaurantOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantOrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'product_variant', 'variant_name', 'quantity',
            'unit_price', 'addons_total', 'total_price',
            'special_instructions', 'selected_addons',
            'vendor', 'created_at',
        ]
        read_only_fields = fields


class RestaurantOrderTrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantOrderTrackingEvent
        fields = ['id', 'event_type', 'message', 'metadata', 'created_at']
        read_only_fields = fields


class KitchenTicketSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    fulfillment_type = serializers.CharField(source='order.fulfillment_type', read_only=True)
    estimated_prep_minutes = serializers.IntegerField(source='order.estimated_prep_minutes', read_only=True)
    items = RestaurantOrderItemSerializer(source='order.items', many=True, read_only=True)

    class Meta:
        model = KitchenTicket
        fields = [
            'id', 'order', 'order_number', 'status',
            'fulfillment_type', 'estimated_prep_minutes',
            'items',
            'acknowledged_at', 'started_at', 'ready_at', 'handed_off_at',
            'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'order', 'order_number', 'fulfillment_type', 'table_number',
            'estimated_prep_minutes', 'items',
            'acknowledged_at', 'started_at', 'ready_at', 'handed_off_at',
            'created_at', 'updated_at',
        ]


class RestaurantOrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    # Dashboards show who placed the order; the retail list serializer
    # exposes these, so mirror them here for a consistent shape.
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantOrder
        fields = [
            'id', 'order_number', 'vendor', 'vendor_name',
            'status', 'payment_status', 'fulfillment_type',
            # `total_amount` is the customer-paid gross (admin views).
            # `subtotal` is the items amount — vendor queue / kitchen
            # cards key off this so service + delivery fees don't
            # inflate the displayed order price.
            # `vendor_payout` is `subtotal − commission`.
            'subtotal', 'total_amount', 'vendor_payout',
            'commission_amount', 'commission_percent',
            'items_count',
            'user_email', 'user_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_items_count(self, obj):
        return obj.items.count()

    def get_user_email(self, obj):
        return (getattr(obj.user, 'email', '') if obj.user_id
                else obj.customer_email) or ''

    def get_user_name(self, obj):
        u = obj.user if obj.user_id else None
        if u is None:
            return ''
        return f'{u.first_name} {u.last_name}'.strip() or (u.email or '')

    def get_vendor_name(self, obj):
        return obj.vendor.trading_name or obj.vendor.name or None


class RestaurantOrderDetailSerializer(serializers.ModelSerializer):
    items = RestaurantOrderItemSerializer(many=True, read_only=True)
    tracking_events = RestaurantOrderTrackingEventSerializer(many=True, read_only=True)
    vendor_name = serializers.SerializerMethodField()
    has_kitchen_ticket = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantOrder
        fields = [
            'id', 'order_number', 'user', 'vendor', 'vendor_name',
            'status', 'payment_status', 'fulfillment_type',
            'estimated_prep_minutes', 'scheduled_for',
            'subtotal', 'tax_amount', 'delivery_fee', 'discount_amount', 'total_amount',
            # Financial split — see core.order_financials.
            'service_fee', 'service_fee_percent',
            'commission_percent', 'commission_amount',
            'paystack_fee', 'vendor_payout', 'platform_payout',
            'customer_email', 'customer_phone',
            'shipping_address',
            'shipping_full_name', 'shipping_street_address', 'shipping_apartment_number',
            'shipping_city', 'shipping_state_province', 'shipping_postal_code', 'shipping_country',
            'coupon_code', 'order_notes', 'internal_notes',
            'confirmed_at', 'ready_at', 'delivered_at',
            'has_kitchen_ticket',
            'items', 'tracking_events',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'order_number', 'subtotal', 'total_amount',
            'service_fee', 'service_fee_percent',
            'commission_percent', 'commission_amount',
            'paystack_fee', 'vendor_payout', 'platform_payout',
            'confirmed_at', 'ready_at', 'delivered_at', 'created_at', 'updated_at',
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.trading_name or obj.vendor.name or None

    def get_has_kitchen_ticket(self, obj):
        return hasattr(obj, 'kitchen_ticket')


class RestaurantOrderCreateSerializer(serializers.ModelSerializer):
    """Used by customers to place a restaurant order from their cart."""
    cart_id = serializers.UUIDField(write_only=True)
    shipping_address_id = serializers.UUIDField(write_only=True, required=False)

    SNAPSHOT_FIELDS = (
        'shipping_full_name', 'shipping_street_address', 'shipping_apartment_number',
        'shipping_city', 'shipping_state_province', 'shipping_postal_code', 'shipping_country',
    )

    class Meta:
        model = RestaurantOrder
        fields = [
            'cart_id', 'shipping_address_id',
            'customer_email', 'customer_phone',
            'fulfillment_type', 'scheduled_for',
            'coupon_code', 'order_notes',
        ]

    def validate(self, data):
        ftype = data.get('fulfillment_type', 'delivery')
        if ftype == 'delivery':
            if not data.get('shipping_address_id'):
                raise serializers.ValidationError(
                    {'shipping_address_id': "Required when fulfillment_type is 'delivery'."}
                )
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            try:
                addr = ShippingAddress.objects.get(id=data['shipping_address_id'], user=user)
            except ShippingAddress.DoesNotExist:
                raise serializers.ValidationError(
                    {'shipping_address_id': 'Shipping address not found or not yours.'}
                )
            data['_addr'] = addr
        else:
            data.pop('shipping_address_id', None)
        return data

    def create(self, validated_data):
        addr = validated_data.pop('_addr', None)
        validated_data.pop('shipping_address_id', None)
        if addr is not None:
            validated_data['shipping_address'] = addr
            validated_data['shipping_full_name'] = addr.full_name
            validated_data['shipping_street_address'] = addr.street_address
            validated_data['shipping_apartment_number'] = addr.apartment_number
            validated_data['shipping_city'] = addr.city
            validated_data['shipping_state_province'] = addr.state_province
            validated_data['shipping_postal_code'] = addr.postal_code
            validated_data['shipping_country'] = addr.country
        else:
            for f in self.SNAPSHOT_FIELDS:
                validated_data.setdefault(f, '')
        return super().create(validated_data)

from rest_framework import serializers
from .models import (
    ShippingAddress, ShoppingCart, CartItem, Order, OrderItem,
    OrderStatusHistory, Coupon,
)
from products.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product_data = ProductListSerializer(source='product', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    negotiation_id = serializers.UUIDField(write_only=True, required=False)
    is_negotiated = serializers.BooleanField(read_only=True)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    negotiation_status = serializers.SerializerMethodField()
    negotiation_agreed_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_data', 'product_variant',
            'quantity', 'price_at_time', 'total_price',
            'is_negotiated', 'negotiation_id', 'original_price',
            'negotiation_status', 'negotiation_agreed_price',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'price_at_time', 'total_price',
            'is_negotiated', 'original_price',
            'negotiation_status', 'negotiation_agreed_price',
            'created_at', 'updated_at',
        ]

    def get_negotiation_status(self, obj):
        return obj.negotiation.status if obj.negotiation_id else None

    def get_negotiation_agreed_price(self, obj):
        return str(obj.negotiation.agreed_price) if obj.negotiation_id and obj.negotiation.agreed_price else None


class ShoppingCartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    vendor_info = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCart
        fields = [
            'id', 'user', 'vendor', 'vendor_email', 'vendor_name', 'vendor_info',
            'items', 'total_items', 'total_amount',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'vendor', 'vendor_email', 'vendor_name', 'vendor_info',
            'items', 'total_items', 'total_amount', 'created_at', 'updated_at',
        ]

    def get_vendor_name(self, obj):
        from business.utils import build_vendor_info
        info = build_vendor_info(obj.vendor.user)
        return info['name'] if info else None

    def get_vendor_info(self, obj):
        from business.utils import build_vendor_info
        return build_vendor_info(obj.vendor.user, self.context.get('request'))


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'product_variant', 'variant_name', 'quantity',
            'unit_price', 'total_price',
            'vendor', 'created_at',
        ]
        read_only_fields = fields


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source='changed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'order', 'previous_status', 'new_status',
            'changed_by', 'changed_by_email', 'comment', 'created_at',
        ]
        read_only_fields = fields


def _first_vendor(order):
    for item in order.items.all():
        if item.vendor_id:
            return item.vendor
    return None


class OrderListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    vendor_id = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user_email', 'user_name', 'status',
            'payment_status',
            # `total_amount` is the customer's gross — useful for admin.
            # `subtotal` is the items amount (cart total) — what the
            # vendor screens key off, because service + delivery fees
            # never flow to the vendor.
            # `vendor_payout` is `subtotal − commission` — what we
            # actually credit to the vendor wallet.
            'subtotal', 'total_amount', 'vendor_payout',
            'commission_amount', 'commission_percent',
            'items_count',
            'vendor_id', 'vendor_name', 'fulfillment_type',
            'created_at',
        ]
        read_only_fields = fields

    def get_items_count(self, obj):
        return len(obj.items.all())

    def get_user_name(self, obj):
        """Best-effort customer display name.

        Falls back through: ``user.get_full_name()`` → shipping/billing name
        → first part of email → empty string. Vendor/admin order cards prefer
        this over the email so they show a human name.
        """
        user = obj.user
        if user is not None:
            full = user.get_full_name().strip() if hasattr(user, 'get_full_name') else ''
            if full:
                return full
        shipping = (getattr(obj, 'shipping_full_name', '') or '').strip()
        if shipping:
            return shipping
        billing = (getattr(obj, 'billing_full_name', '') or '').strip()
        if billing:
            return billing
        email = getattr(user, 'email', '') if user is not None else ''
        if email and '@' in email:
            return email.split('@', 1)[0]
        return ''

    def get_vendor_id(self, obj):
        vendor = _first_vendor(obj)
        return str(vendor.id) if vendor else None

    def get_vendor_name(self, obj):
        vendor = _first_vendor(obj)
        if vendor is None:
            return None
        return vendor.trading_name or vendor.name or None


class OrderDetailSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    vendor_id = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()

    def get_vendor_id(self, obj):
        vendor = _first_vendor(obj)
        return str(vendor.id) if vendor else None

    def get_vendor_name(self, obj):
        vendor = _first_vendor(obj)
        if vendor is None:
            return None
        return vendor.trading_name or vendor.name or None

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'user_email', 'status',
            'payment_status',
            'vendor_id', 'vendor_name',
            'subtotal', 'tax_amount', 'shipping_cost',
            'discount_amount', 'total_amount',
            # Financial split — see core.order_financials.
            'service_fee', 'service_fee_percent',
            'commission_percent', 'commission_amount',
            'paystack_fee', 'vendor_payout', 'platform_payout',
            'customer_email', 'customer_phone',
            'billing_full_name', 'billing_street_address',
            'billing_apartment_number', 'billing_city',
            'billing_state_province', 'billing_postal_code', 'billing_country',
            'shipping_address',
            'shipping_full_name', 'shipping_street_address',
            'shipping_apartment_number', 'shipping_city',
            'shipping_state_province', 'shipping_postal_code', 'shipping_country',
            'fulfillment_type',
            'coupon_code', 'order_notes', 'internal_notes',
            'shipped_at', 'delivered_at',
            'items', 'status_history',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'order_number', 'subtotal', 'tax_amount',
            'discount_amount', 'total_amount',
            'service_fee', 'service_fee_percent',
            'commission_percent', 'commission_amount',
            'paystack_fee', 'vendor_payout', 'platform_payout',
            'shipped_at',
            'delivered_at', 'created_at', 'updated_at',
        ]


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'address_type', 'label', 'full_name', 'phone_number',
            'street_address', 'apartment_number', 'city',
            'state_province', 'postal_code', 'country',
            'latitude', 'longitude',
            'is_default', 'delivery_instructions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    cart_id = serializers.UUIDField(write_only=True)
    shipping_address_id = serializers.UUIDField(write_only=True, required=False)

    SHIPPING_SNAPSHOT_FIELDS = (
        'shipping_full_name', 'shipping_street_address',
        'shipping_apartment_number', 'shipping_city',
        'shipping_state_province', 'shipping_postal_code', 'shipping_country',
    )

    class Meta:
        model = Order
        fields = [
            'cart_id', 'shipping_address_id',
            'customer_email', 'customer_phone',
            'fulfillment_type',
            'coupon_code', 'order_notes',
        ]

    def validate(self, data):
        ftype = data.get('fulfillment_type', 'delivery')
        if ftype == 'delivery':
            if not data.get('shipping_address_id'):
                raise serializers.ValidationError({
                    'shipping_address_id': "Required when fulfillment_type is 'delivery'."
                })
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            try:
                addr = ShippingAddress.objects.get(
                    id=data['shipping_address_id'],
                    user=user,
                )
            except ShippingAddress.DoesNotExist:
                raise serializers.ValidationError({
                    'shipping_address_id': 'Shipping address not found or not yours.'
                })
            data['_shipping_address_obj'] = addr
        else:
            data.pop('shipping_address_id', None)
        return data

    def create(self, validated_data):
        addr = validated_data.pop('_shipping_address_obj', None)
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
            for f in self.SHIPPING_SNAPSHOT_FIELDS:
                validated_data.setdefault(f, '')

        validated_data['billing_full_name'] = validated_data['shipping_full_name']
        validated_data['billing_street_address'] = validated_data['shipping_street_address']
        validated_data['billing_apartment_number'] = validated_data['shipping_apartment_number']
        validated_data['billing_city'] = validated_data['shipping_city']
        validated_data['billing_state_province'] = validated_data['shipping_state_province']
        validated_data['billing_postal_code'] = validated_data['shipping_postal_code']
        validated_data['billing_country'] = validated_data['shipping_country']
        return super().create(validated_data)


class CouponSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(source='current_uses', read_only=True)

    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'name', 'description', 'coupon_type',
            'value', 'minimum_order_amount', 'max_uses',
            'max_uses_per_user', 'usage_count', 'start_date', 'end_date',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']

from django.utils import timezone
from rest_framework import serializers

from .models import NegotiationMessage, NegotiationOffer, NegotiationRoom, PricePolicy


class PricePolicySerializer(serializers.ModelSerializer):
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)

    class Meta:
        model = PricePolicy
        fields = [
            'id', 'vendor', 'vendor_email',
            'max_markup_percent', 'max_discount_percent', 'min_floor_percent',
            'auto_negotiate', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'vendor', 'vendor_email', 'created_at', 'updated_at']


class PricePolicyCreateUpdateSerializer(serializers.Serializer):
    # No `default=` on these fields on purpose: the same serializer
    # serves both first-time creation and partial toggles (e.g. flip
    # just `is_active`), and DRF defaults would otherwise overwrite
    # unrelated columns back to their default on every toggle. The
    # model field defaults handle first-creation gaps instead.
    max_markup_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False,
    )
    max_discount_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False,
    )
    min_floor_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False,
    )
    auto_negotiate = serializers.BooleanField(required=False)
    # Lets the vendor flip their own policy on/off from the policy
    # screen without needing a separate admin-only PATCH endpoint —
    # `set-policy` is the only vendor-scoped write path on the policy
    # viewset.
    is_active = serializers.BooleanField(required=False)

    def _check_range(self, value, name):
        if not (0 <= value <= 50):
            raise serializers.ValidationError(f"{name} must be between 0 and 50.")
        return value

    def validate_max_markup_percent(self, v):
        return self._check_range(v, 'max_markup_percent')

    def validate_max_discount_percent(self, v):
        return self._check_range(v, 'max_discount_percent')

    def validate_min_floor_percent(self, v):
        return self._check_range(v, 'min_floor_percent')

    def create(self, validated_data):
        vendor = getattr(self.context['request'].user, 'vendor_profile', None)
        if vendor is None:
            raise serializers.ValidationError({'vendor': 'Vendor profile required.'})
        policy, _ = PricePolicy.objects.update_or_create(
            vendor=vendor, defaults=validated_data,
        )
        return policy


class NegotiationMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationMessage
        fields = [
            'id', 'room', 'sender_type', 'sender', 'sender_email',
            'content', 'message_type', 'price_value',
            'is_seen', 'seen_at', 'created_at',
        ]
        read_only_fields = fields

    def get_sender_email(self, obj):
        return obj.sender.email if obj.sender_id else None


class NegotiationOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = NegotiationOffer
        fields = [
            'id', 'room', 'offered_by',
            'original_price', 'offered_price', 'counter_offer_price',
            'status', 'ai_confidence', 'ai_action',
            'round_number', 'expires_at', 'created_at', 'responded_at',
        ]
        read_only_fields = fields


class NegotiationRoomSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price', max_digits=10, decimal_places=2, read_only=True,
    )
    product_image = serializers.SerializerMethodField()
    buyer_email = serializers.CharField(source='buyer.email', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    latest_offer = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationRoom
        fields = [
            'id', 'product', 'product_name', 'product_price', 'product_image',
            'buyer', 'buyer_email', 'vendor', 'vendor_name',
            'mode', 'status', 'agreed_price', 'offer_expires_at',
            'time_remaining_seconds',
            'latest_offer', 'unread_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_product_image(self, obj):
        request = self.context.get('request')
        img = (
            obj.product.images.filter(is_primary=True)
            .values_list('image', flat=True)
            .first()
        )
        return request.build_absolute_uri(f'/media/{img}') if img and request else None

    def get_vendor_name(self, obj):
        return (
            getattr(obj.vendor, 'trading_name', None)
            or getattr(obj.vendor, 'name', None)
            or str(obj.vendor_id)
        )

    def get_latest_offer(self, obj):
        latest = obj.offers.order_by('-created_at').first()
        return NegotiationOfferSerializer(latest).data if latest else None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request:
            return 0
        user = request.user
        if obj.buyer_id == user.id:
            return obj.messages.filter(is_seen=False).exclude(sender=user).count()
        return obj.messages.filter(is_seen=False, sender=obj.buyer).count()

    def get_time_remaining_seconds(self, obj):
        # offer_expires_at is repurposed during `pending_vendor` as the
        # vendor's 24 h approval window; surface a countdown for both
        # phases so the frontend can render either banner from the
        # same field.
        if obj.status not in ('agreed', 'pending_vendor') or not obj.offer_expires_at:
            return None
        delta = obj.offer_expires_at - timezone.now()
        return max(int(delta.total_seconds()), 0)


class NegotiationRoomCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    mode = serializers.ChoiceField(
        choices=['ai', 'manual'], default='ai', required=False,
    )

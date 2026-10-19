"""Serializers for promotions & coupons (read + vendor/admin write)."""
from rest_framework import serializers

from .models import (
    Coupon,
    CouponRedemption,
    OwnerType,
    Promotion,
    PromotionBanner,
    PromotionRedemption,
    Scope,
)


class _RuleReadMixin(serializers.ModelSerializer):
    """Shared read fields for Promotion/Coupon."""

    status = serializers.SerializerMethodField()
    discount_display = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    product_ids = serializers.SerializerMethodField()
    category_ids = serializers.SerializerMethodField()
    target_user_emails = serializers.SerializerMethodField()
    is_targeted = serializers.SerializerMethodField()

    def get_status(self, obj):
        return obj.window_status()

    def get_target_user_emails(self, obj):
        return list(obj.target_users.values_list('email', flat=True))

    def get_is_targeted(self, obj):
        return obj.target_users.exists()

    def get_discount_display(self, obj):
        if obj.discount_type == 'percentage':
            base = f'{obj.value:g}% off'
            if obj.max_discount_amount:
                base += f' (up to R{obj.max_discount_amount:g})'
            return base
        if obj.discount_type == 'fixed_amount':
            return f'R{obj.value:g} off'
        return 'Free shipping'

    def get_vendor_name(self, obj):
        if obj.vendor_id and obj.vendor:
            return obj.vendor.name or obj.vendor.trading_name or 'Store'
        return 'Sanoa'

    def get_product_ids(self, obj):
        return [str(p) for p in
                obj.applicable_products.values_list('pk', flat=True)]

    def get_category_ids(self, obj):
        return [str(c) for c in
                obj.applicable_categories.values_list('pk', flat=True)]


class PromotionSerializer(_RuleReadMixin):
    class Meta:
        model = Promotion
        fields = [
            'id', 'owner_type', 'vendor', 'vendor_name', 'name', 'description',
            'discount_type', 'discount_display', 'value', 'max_discount_amount',
            'scope', 'product_ids', 'category_ids', 'minimum_order_amount',
            'minimum_quantity', 'priority', 'stackable_with_coupon',
            'usage_limit', 'times_used', 'banner_color',
            'target_user_emails', 'is_targeted',
            'is_active', 'status', 'start_date', 'end_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at']


class CouponSerializer(_RuleReadMixin):
    uses_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'owner_type', 'vendor', 'vendor_name', 'name',
            'description', 'discount_type', 'discount_display', 'value',
            'max_discount_amount', 'scope', 'product_ids', 'category_ids',
            'minimum_order_amount', 'max_uses', 'max_uses_per_user',
            'times_used', 'uses_remaining', 'target_user_emails', 'is_targeted',
            'is_active', 'status',
            'start_date', 'end_date', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at']

    def get_uses_remaining(self, obj):
        if obj.max_uses is None:
            return None
        return max(0, obj.max_uses - obj.times_used)


class _RuleWriteMixin(serializers.ModelSerializer):
    """Validation shared by promotion/coupon create+update."""

    # Restrict to specific customers by email. Empty/omitted == open to all.
    # Unknown emails are silently skipped (they may not have an account yet).
    target_user_emails = serializers.ListField(
        child=serializers.EmailField(), write_only=True, required=False)

    def validate(self, attrs):
        discount_type = attrs.get(
            'discount_type', getattr(self.instance, 'discount_type', None))
        value = attrs.get('value', getattr(self.instance, 'value', None))
        if discount_type == 'percentage' and value is not None \
                and (value <= 0 or value > 100):
            raise serializers.ValidationError(
                {'value': 'Percentage must be between 0 and 100.'})
        if discount_type == 'fixed_amount' and value is not None and value <= 0:
            raise serializers.ValidationError(
                {'value': 'Amount must be greater than zero.'})

        start = attrs.get('start_date',
                          getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_date': 'End date must be after the start date.'})
        return attrs

    def _resolve_users(self, emails):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        found = []
        for e in emails:
            u = User.objects.filter(email__iexact=e.strip()).first()
            if u is not None:
                found.append(u)
        return found

    def create(self, validated_data):
        emails = validated_data.pop('target_user_emails', None)
        instance = super().create(validated_data)
        if emails is not None:
            instance.target_users.set(self._resolve_users(emails))
        return instance

    def update(self, instance, validated_data):
        emails = validated_data.pop('target_user_emails', None)
        instance = super().update(instance, validated_data)
        if emails is not None:
            instance.target_users.set(self._resolve_users(emails))
        return instance


class PromotionWriteSerializer(_RuleWriteMixin):
    class Meta:
        model = Promotion
        fields = [
            'name', 'description', 'discount_type', 'value',
            'max_discount_amount', 'scope', 'applicable_products',
            'applicable_categories', 'minimum_order_amount',
            'minimum_quantity', 'priority', 'stackable_with_coupon',
            'usage_limit', 'banner_color', 'is_active',
            'start_date', 'end_date', 'owner_type', 'vendor',
            'target_user_emails',
        ]


class CouponWriteSerializer(_RuleWriteMixin):
    class Meta:
        model = Coupon
        fields = [
            'code', 'name', 'description', 'discount_type', 'value',
            'max_discount_amount', 'scope', 'applicable_products',
            'applicable_categories', 'minimum_order_amount', 'max_uses',
            'max_uses_per_user', 'is_active', 'start_date', 'end_date',
            'owner_type', 'vendor', 'target_user_emails',
        ]

    def validate_code(self, value):
        code = (value or '').strip().upper()
        if not code:
            raise serializers.ValidationError('Code is required.')
        qs = Coupon.objects.filter(code=code)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('That code is already in use.')
        return code


class CouponRedemptionSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='coupon.code', read_only=True)
    customer = serializers.SerializerMethodField()

    class Meta:
        model = CouponRedemption
        fields = ['id', 'code', 'customer', 'order', 'discount_amount',
                  'redeemed_at']

    def get_customer(self, obj):
        u = obj.user
        return getattr(u, 'email', None) or getattr(u, 'username', None)


class PromotionRedemptionSerializer(serializers.ModelSerializer):
    promotion_name = serializers.CharField(
        source='promotion.name', read_only=True)

    class Meta:
        model = PromotionRedemption
        fields = ['id', 'promotion_name', 'order', 'discount_amount',
                  'redeemed_at']


class PromotionBannerSerializer(serializers.ModelSerializer):
    """Read serializer — returns an absolute image URL for the app."""

    image_url = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    promotion_id = serializers.CharField(source='promotion.id', read_only=True,
                                         default=None)
    category_id = serializers.SerializerMethodField()

    class Meta:
        model = PromotionBanner
        fields = [
            'id', 'owner_type', 'vendor', 'vendor_name', 'title', 'subtitle',
            'image_url', 'cta_text', 'action_type', 'promotion_id',
            'category_id', 'background_color', 'text_color',
            'is_active', 'status', 'sort_order', 'start_date', 'end_date',
            'created_at',
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_vendor_name(self, obj):
        if obj.vendor_id and obj.vendor:
            return obj.vendor.name or obj.vendor.trading_name or 'Store'
        return 'Sanoa'

    def get_status(self, obj):
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return 'inactive'
        if obj.start_date and now < obj.start_date:
            return 'scheduled'
        if obj.end_date and now > obj.end_date:
            return 'expired'
        return 'active'

    def get_category_id(self, obj):
        return str(obj.category_id) if obj.category_id else None


class PromotionBannerWriteSerializer(serializers.ModelSerializer):
    # In multipart form data an omitted BooleanField defaults to False; force
    # the sensible "active on create" default so a banner isn't born hidden.
    is_active = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = PromotionBanner
        fields = [
            'title', 'subtitle', 'image', 'cta_text', 'action_type',
            'promotion', 'category', 'background_color', 'text_color',
            'is_active', 'sort_order', 'start_date', 'end_date',
            'owner_type', 'vendor',
        ]

    def validate_image(self, value):
        # 5 MB cap keeps home-feed payloads snappy.
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 5 MB.')
        return value

    def validate(self, attrs):
        # A promotion link only makes sense for the 'promotion' action; clear
        # it otherwise so a stale FK doesn't linger when the action changes.
        if 'action_type' in attrs and attrs.get('action_type') != 'promotion':
            attrs['promotion'] = None
        return attrs

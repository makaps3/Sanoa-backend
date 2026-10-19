"""
Serializers for the Business Tiers app (vendor tiers).
Integrated with Paystack for payment processing.
"""
import calendar
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import BusinessTier, VendorTierSubscription

User = get_user_model()

# A free tier never expires — park its period end ~100 years out.
FREE_TIER_DAYS = 36500


def _add_months(start, months):
    """Add whole months to `start`, clamping the day to the target
    month's length (e.g. 31 Jan + 1 month → 28/29 Feb)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def _add_years(start, years):
    """Add whole years, landing on the same month/day next year
    (29 Feb → 28 Feb on non-leap years)."""
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def compute_period_end(start, tier):
    """The next billing date for a subscription that starts at `start`.

    Monthly tiers (seeded as duration=30, unit='days') run one calendar month;
    yearly tiers (duration=1, unit='years') land on the same calendar
    date the following year. Always measured from the subscription day.
    """
    if tier.is_free:
        return start + timedelta(days=FREE_TIER_DAYS)
    from subscriptions.billing import period_end
    return period_end(start, tier)


class BusinessTierSerializer(serializers.ModelSerializer):
    product_limit_display = serializers.CharField(read_only=True)
    is_free = serializers.BooleanField(read_only=True)
    callback_url = serializers.SerializerMethodField()

    class Meta:
        model = BusinessTier
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'tier_level',
            'duration', 'duration_unit',
            'max_products', 'product_limit_display',
            'commission_rate', 'commission_discount',
            'search_priority_boost', 'featured_listings',
            'features', 'negotiation_enabled',
            'max_markup_percent', 'max_discount_percent',
            'trial_days', 'is_free', 'is_active',
            'paystack_plan_code', 'callback_url',
        ]

    def get_callback_url(self, obj):
        return settings.PAYSTACK_CALLBACK_URL or None


class VendorTierSubscriptionSerializer(serializers.ModelSerializer):
    tier_name = serializers.CharField(source='tier.name', read_only=True)
    tier_price = serializers.DecimalField(
        source='tier.price', max_digits=8, decimal_places=2, read_only=True
    )
    tier_level = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = VendorTierSubscription
        fields = [
            'id', 'vendor', 'tier', 'tier_name', 'tier_price', 'tier_level',
            'status', 'is_active',
            'started_at', 'current_period_start', 'current_period_end',
            'cancelled_at',
            'paystack_subscription_code', 'paystack_customer_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'vendor', 'status', 'started_at',
            'current_period_start', 'current_period_end',
            'created_at', 'updated_at',
        ]


class AdminBusinessTierSerializer(serializers.ModelSerializer):
    """Writable serializer for admin CRUD on BusinessTier."""
    product_limit_display = serializers.CharField(read_only=True)
    is_free = serializers.BooleanField(read_only=True)

    class Meta:
        model = BusinessTier
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'tier_level',
            'duration', 'duration_unit',
            'max_products', 'product_limit_display',
            'commission_rate', 'commission_discount',
            'search_priority_boost', 'featured_listings',
            'features', 'negotiation_enabled',
            'max_markup_percent', 'max_discount_percent',
            'trial_days', 'is_free', 'is_active', 'sort_order',
            'paystack_plan_code', 'paystack_plan_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'product_limit_display', 'is_free', 'created_at', 'updated_at']


class AdminVendorTierSubscriptionSerializer(serializers.ModelSerializer):
    """Full read serializer for admin — includes vendor info."""
    tier_name = serializers.CharField(source='tier.name', read_only=True)
    tier_price = serializers.DecimalField(source='tier.price', max_digits=8, decimal_places=2, read_only=True)
    tier_level = serializers.IntegerField(read_only=True)
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = VendorTierSubscription
        fields = [
            'id', 'vendor', 'vendor_email', 'vendor_name',
            'tier', 'tier_name', 'tier_price', 'tier_level',
            'status', 'is_active',
            'started_at', 'current_period_start', 'current_period_end',
            'cancelled_at',
            'paystack_subscription_code', 'paystack_customer_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'vendor', 'vendor_email', 'vendor_name',
            'tier_name', 'tier_price', 'tier_level', 'is_active',
            'started_at', 'current_period_start', 'current_period_end',
            'created_at', 'updated_at',
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.trading_name or obj.vendor.name or str(obj.vendor_id)


class AdminVendorTierAssignSerializer(serializers.Serializer):
    """Admin assigns a tier directly to a vendor (no Paystack)."""
    tier_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=['active', 'cancelled', 'expired', 'past_due', 'trialing'],
        default='active',
    )

    def validate_tier_id(self, value):
        try:
            BusinessTier.objects.get(id=value)
        except BusinessTier.DoesNotExist:
            raise serializers.ValidationError('Tier not found.')
        return value


class VendorTierSubscribeSerializer(serializers.Serializer):
    tier_id = serializers.UUIDField()
    callback_url = serializers.URLField(
        required=False,
        help_text="URL to redirect after payment on Paystack checkout",
    )

    def validate_tier_id(self, value):
        try:
            BusinessTier.objects.get(id=value, is_active=True)
        except BusinessTier.DoesNotExist:
            raise serializers.ValidationError("Tier not found or not available.")
        return value

    def validate(self, data):
        user = self.context['request'].user
        if user.user_type != 'vendor':
            raise serializers.ValidationError("Only vendors can subscribe to business tiers.")
        if getattr(user, 'vendor_profile', None) is None:
            raise serializers.ValidationError("You must have a vendor profile to subscribe to a tier.")
        return data

    def create(self, validated_data):
        from subscriptions.billing import start_subscription
        user = self.context['request'].user
        tier = BusinessTier.objects.get(pk=validated_data['tier_id'], is_active=True)
        subscription, payment = start_subscription(
            user, tier, vendor=user.vendor_profile,
            callback_url=validated_data.get('callback_url') or settings.PAYSTACK_CALLBACK_URL,
        )
        self.context['paystack_data'] = payment
        return subscription

    @staticmethod
    def _sync_tier_to_paystack(tier):
        """Create the tier plan on Paystack and save the plan code."""
        from payments.paystack import paystack_api

        # Map duration_unit to Paystack interval
        from subscriptions.billing import paystack_interval
        interval = paystack_interval(tier)

        result = paystack_api.create_plan(
            name=f'Vendor Tier: {tier.name}',
            interval=interval,
            amount=int(tier.price * 100),
            currency='ZAR',
            description=tier.description or tier.name,
        )

        if result.get('status'):
            ps_data = result['data']
            tier.paystack_plan_code = ps_data.get('plan_code', '')
            tier.paystack_plan_id = ps_data.get('id')
            tier.save(update_fields=['paystack_plan_code', 'paystack_plan_id', 'updated_at'])

        return tier

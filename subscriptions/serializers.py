"""
Serializers for the Subscriptions app (buyer credit plans).
Integrated with Paystack for payment processing.
"""
from datetime import timedelta

from rest_framework import serializers
from django.conf import settings
from django.utils import timezone

from .models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    """Serializer for viewing buyer credit plan details."""

    callback_url = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'slug', 'description',
            'plan_tier', 'billing_cycle', 'price',
            'duration', 'duration_unit',
            'credit_limit', 'interest_rate', 'deposit_percent',
            'max_items_on_credit',
            'repayment_days', 'grace_period_days', 'late_payment_penalty_percent',
            'service_fee_discount_percent', 'delivery_fee_discount_percent',
            'features', 'requires_follower', 'trial_days', 'sort_order',
            'paystack_plan_code', 'callback_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_callback_url(self, obj):
        return settings.PAYSTACK_CALLBACK_URL or None


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for viewing subscription details."""

    is_active = serializers.BooleanField(read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(
        source='plan.price', max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'plan_name', 'plan_price', 'status',
            'is_active', 'started_at', 'current_period_start',
            'current_period_end', 'cancelled_at',
            'paystack_subscription_code', 'paystack_customer_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class AdminPlanSerializer(serializers.ModelSerializer):
    """Writable serializer for admin CRUD on Plan."""

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'slug', 'description',
            'plan_tier', 'billing_cycle', 'price',
            'duration', 'duration_unit',
            'credit_limit', 'interest_rate', 'deposit_percent',
            'max_items_on_credit',
            'repayment_days', 'grace_period_days', 'late_payment_penalty_percent',
            'service_fee_discount_percent', 'delivery_fee_discount_percent',
            'features', 'requires_follower', 'trial_days', 'sort_order', 'is_active',
            'paystack_plan_code', 'paystack_plan_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdminSubscriptionSerializer(serializers.ModelSerializer):
    """Full read serializer for admin — includes user info."""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(source='plan.price', max_digits=8, decimal_places=2, read_only=True)
    plan_tier = serializers.CharField(source='plan.plan_tier', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'user_email',
            'plan', 'plan_name', 'plan_price', 'plan_tier',
            'status', 'is_active',
            'started_at', 'current_period_start', 'current_period_end',
            'cancelled_at',
            'paystack_subscription_code', 'paystack_customer_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_email',
            'plan_name', 'plan_price', 'plan_tier', 'is_active',
            'started_at', 'current_period_start', 'current_period_end',
            'created_at', 'updated_at',
        ]


class AdminSubscriptionAssignSerializer(serializers.Serializer):
    """Admin assigns a plan directly to a customer (no Paystack)."""
    user_id = serializers.IntegerField()
    plan_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=['active', 'cancelled', 'expired', 'past_due', 'trialing'],
        default='active',
    )

    def validate_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=value, user_type='customer')
        except User.DoesNotExist:
            raise serializers.ValidationError('Customer user not found.')
        return value

    def validate_plan_id(self, value):
        try:
            Plan.objects.get(id=value)
        except Plan.DoesNotExist:
            raise serializers.ValidationError('Plan not found.')
        return value


class SubscriptionCreateSerializer(serializers.Serializer):
    """Subscribe to a Sanoa buyer credit plan via Paystack."""

    plan_id = serializers.UUIDField(help_text="ID of the credit plan to subscribe to")
    callback_url = serializers.URLField(
        required=False,
        help_text="URL to redirect after payment on Paystack checkout",
    )

    def validate_plan_id(self, value):
        try:
            Plan.objects.get(id=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan not found or not available.")
        return value

    def validate(self, data):
        user = self.context['request'].user

        if user.user_type != 'customer':
            raise serializers.ValidationError(
                "Only customers can subscribe to credit plans. "
                "Vendors should subscribe to a business tier instead."
            )

        existing = getattr(user, 'subscription', None)
        if existing and existing.is_active:
            raise serializers.ValidationError("You already have an active subscription.")

        plan = Plan.objects.get(id=data['plan_id'])
        data['plan'] = plan
        return data

    # Fixed-length free trial granted to first-time subscribers.
    FREE_TRIAL_DAYS = 14

    def create(self, validated_data):
        from .billing import start_subscription
        subscription, payment = start_subscription(
            self.context['request'].user, validated_data['plan'],
            callback_url=validated_data.get('callback_url') or settings.PAYSTACK_CALLBACK_URL,
        )
        self.context['paystack_data'] = payment
        return subscription

    @staticmethod
    def _sync_plan_to_paystack(plan):
        """Create the plan on Paystack and save the plan code."""
        from payments.paystack import paystack_api

        interval_map = {
            'monthly': 'monthly',
            'yearly': 'annually',
        }
        interval = interval_map.get(plan.billing_cycle, 'monthly')

        result = paystack_api.create_plan(
            name=plan.name,
            interval=interval,
            amount=int(plan.price * 100),
            currency='ZAR',
            description=plan.description or plan.name,
        )

        if result.get('status'):
            ps_data = result['data']
            plan.paystack_plan_code = ps_data.get('plan_code', '')
            plan.paystack_plan_id = ps_data.get('id')
            plan.save(update_fields=['paystack_plan_code', 'paystack_plan_id', 'updated_at'])

        return plan

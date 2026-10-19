"""
Models for the Subscriptions app.
Manages Sanoa buyer credit plans and subscriptions.
Subscribers can purchase items on credit (debit system).
Non-subscribers buy normally like any e-commerce platform.
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """
    A buyer credit plan offered by the Sanoa platform.
    Subscribers can purchase items on credit via the debit system.
    Non-subscribers purchase normally without credit access.
    """

    DURATION_UNIT_CHOICES = [
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]

    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    PLAN_TIER_CHOICES = [
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('plus', 'Plus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    plan_tier = models.CharField(
        max_length=10, choices=PLAN_TIER_CHOICES, default='basic',
        help_text="Plan tier level (basic, premium, plus)"
    )
    billing_cycle = models.CharField(
        max_length=10, choices=BILLING_CYCLE_CHOICES, default='monthly',
        help_text="Billing cycle: monthly (30 days) or yearly (10 months paid, 2 months free)"
    )
    price = models.DecimalField(max_digits=8, decimal_places=2, help_text="Subscription price per billing cycle (ZAR)")
    duration = models.PositiveIntegerField(default=30, help_text="Duration value (e.g. 30)")
    duration_unit = models.CharField(
        max_length=10, choices=DURATION_UNIT_CHOICES, default='days',
        help_text="Unit for the duration field"
    )

    # ── Credit terms ─────────────────────────────
    credit_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Maximum credit amount the buyer can use per billing cycle (ZAR)"
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Interest rate on outstanding credit balance (%)"
    )
    deposit_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Minimum upfront deposit required on credit purchases (%)"
    )
    max_items_on_credit = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of items that can be on credit simultaneously"
    )

    # ── Repayment ────────────────────────────────
    repayment_days = models.PositiveIntegerField(
        default=30,
        help_text="Maximum number of days the buyer has to fully repay credit"
    )
    grace_period_days = models.PositiveIntegerField(
        default=3,
        help_text="Grace period (days) after due date before late penalty applies"
    )
    late_payment_penalty_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.00,
        help_text="Additional penalty rate applied after grace period (%)"
    )

    # ── Fee discounts ────────────────────────────
    service_fee_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text="Discount on platform service fees for this plan (%)"
    )
    delivery_fee_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text="Discount on delivery fees for this plan (%)"
    )

    features = models.JSONField(
        default=list, blank=True,
        help_text="List of features included in this plan"
    )
    requires_follower = models.BooleanField(
        default=False,
        help_text="Whether the user must be following at least one business to subscribe"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this plan is currently available")
    sort_order = models.PositiveIntegerField(default=0, help_text="Display order (lower = first)")
    trial_days = models.PositiveIntegerField(default=0, help_text="Number of free trial days")

    # Paystack integration
    paystack_plan_code = models.CharField(
        max_length=100, blank=True, unique=True, null=True,
        help_text="Paystack plan code (PLN_xxx) – synced automatically",
    )
    paystack_plan_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Paystack numeric plan ID",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'
        ordering = ['sort_order', 'price']

    def __str__(self):
        return f"{self.name} - R{self.price}/{self.get_duration_unit_display().lower()}"


class Subscription(models.Model):
    """
    A buyer's subscription to a Sanoa credit plan.
    Subscribers can purchase items on credit via the debit system.
    Only customers (buyers) can subscribe — vendors use business tiers instead.
    """

    STATUS_CHOICES = [
        ('pending', 'Awaiting Payment'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription',
        limit_choices_to={'user_type': 'customer'},
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    started_at = models.DateTimeField(auto_now_add=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    pending_reference = models.CharField(max_length=200, blank=True)
    last_payment_reference = models.CharField(max_length=200, blank=True)

    # Paystack integration
    paystack_subscription_code = models.CharField(
        max_length=100, blank=True,
        help_text="Paystack subscription code (SUB_xxx)",
    )
    paystack_email_token = models.CharField(
        max_length=200, blank=True,
        help_text="Paystack email token for managing the subscription",
    )
    paystack_customer_code = models.CharField(
        max_length=100, blank=True,
        help_text="Paystack customer code (CUS_xxx)",
    )
    paystack_authorization_code = models.CharField(
        max_length=200, blank=True,
        help_text="Paystack card authorization code for recurring charges",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"

    @property
    def is_active(self):
        return self.status in ('active', 'trialing') and self.current_period_end > timezone.now()

    @property
    def is_overdue(self):
        """True when the billing period has lapsed but we still have a paid
        plan attached — Paystack failed to recharge or the customer cancelled
        their card. Drives the downgrade cascade."""
        if self.status in ('cancelled', 'expired'):
            return True
        if self.status in ('past_due',):
            return True
        return self.status != 'pending' and self.current_period_end <= timezone.now()

    def expire_and_downgrade(self, *, reason='Billing period lapsed'):
        """Mark this subscription as expired and downgrade the linked
        Buy-Now-Pay-Later (CreditAccount) so the customer no longer has
        access to credit-based purchases.

        Idempotent — calling on an already-expired subscription with a
        zeroed credit account is a no-op. Returns True when a change
        was actually applied, False otherwise.

        Cascade:
          • Subscription.status   → 'expired' (if not already)
          • Subscription.cancelled_at filled if missing
          • CreditAccount.credit_limit → 0
          • CreditAccount.status remains 'active' so the customer can
            still see and repay outstanding balances. We don't suspend
            here — the debit Celery task handles suspension based on
            its own overdue-purchase logic so policies stay separate.

        Existing CreditPurchases keep their repayment schedule.
        """
        from .billing import expire_subscription
        return expire_subscription(self, reason=reason)


class SubscriptionCancellation(models.Model):
    """Durable remote cancellation; retry this operation, never the charge."""

    subscription_code = models.CharField(max_length=100, unique=True)
    email_token = models.CharField(max_length=200, blank=True)
    reason = models.CharField(max_length=250)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['completed_at', 'next_attempt_at'])]

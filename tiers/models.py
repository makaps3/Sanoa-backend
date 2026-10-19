"""
Models for the Business Tiers app.
Manages vendor subscription tiers that determine platform visibility,
commission rates, product limits, and negotiation power.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BusinessTier(models.Model):
    """
    A business tier plan that vendors can subscribe to.
    Determines their platform benefits, commission rate, and search ranking.
    """

    DURATION_UNIT_CHOICES = [
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Monthly price in ZAR (0 for free tier)"
    )

    # Tier level for ordering and comparison (higher = better)
    tier_level = models.PositiveIntegerField(
        default=0,
        help_text="Numeric level for tier comparison (0=free, 1=growth, etc.)"
    )

    # Duration & billing
    duration = models.PositiveIntegerField(default=30, help_text="Billing cycle duration value")
    duration_unit = models.CharField(
        max_length=10, choices=DURATION_UNIT_CHOICES, default='days',
        help_text="Unit for the duration field"
    )

    # Business limits
    max_products = models.PositiveIntegerField(
        default=20,
        help_text="Maximum number of products the vendor can list (0 = unlimited)"
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text=(
            "DEPRECATED — kept for migration. The platform commission "
            "now lives on `platform_admin.PlatformFee` and is reduced "
            "per-vendor by `commission_discount`."
        ),
    )
    # Per-tier rebate subtracted from the platform's merchant
    # commission % when this vendor's orders settle. Stored as a
    # percentage-points value (e.g. 5.00 → 5 % off the platform fee).
    commission_discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text=(
            "Percentage points removed from the platform's merchant "
            "commission when this tier's vendors settle. Capped at the "
            "platform fee so the effective rate never goes negative."
        ),
    )

    # Search & visibility
    search_priority_boost = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
        help_text="Boost to search ranking score (0.00 - 1.00)"
    )
    featured_listings = models.BooleanField(
        default=False,
        help_text="Whether vendor can have featured/promoted listings"
    )

    # Features (stored as JSON list for flexibility)
    features = models.JSONField(
        default=list, blank=True,
        help_text="List of feature strings included in this tier"
    )

    # Negotiation
    negotiation_enabled = models.BooleanField(
        default=False,
        help_text="Whether vendor has access to the price negotiation engine"
    )
    max_markup_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Maximum markup percentage allowed in negotiations"
    )
    max_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        help_text="Maximum discount percentage allowed in negotiations"
    )

    # Trial
    trial_days = models.PositiveIntegerField(default=0, help_text="Number of free trial days")

    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this tier is available for new subscriptions")
    sort_order = models.PositiveIntegerField(default=0, help_text="Display order (lower = first)")

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
        verbose_name = 'Business Tier'
        verbose_name_plural = 'Business Tiers'
        ordering = ['sort_order', 'price']

    def __str__(self):
        if self.price == 0:
            return f"{self.name} (Free)"
        return f"{self.name} - R{self.price}/month"

    @property
    def is_free(self):
        return self.price == 0

    @property
    def product_limit_display(self):
        return 'Unlimited' if self.max_products == 0 else str(self.max_products)

 
class VendorTierSubscription(models.Model):
    """
    A vendor's active subscription to a business tier.
    Each vendor can only have one active tier subscription at a time.
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
    vendor = models.OneToOneField(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='tier_subscription',
    )
    tier = models.ForeignKey(
        BusinessTier, on_delete=models.PROTECT,
        related_name='subscriptions'
    )
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
        verbose_name = 'Vendor Tier Subscription'
        verbose_name_plural = 'Vendor Tier Subscriptions'

    def __str__(self):
        vendor_label = self.vendor.trading_name or self.vendor.name or f"vendor {self.vendor_id}"
        return f"{vendor_label} - {self.tier.name} ({self.status})"

    @property
    def is_active(self):
        if self.tier.is_free:
            return self.status in ('active', 'trialing')
        return self.status in ('active', 'trialing') and self.current_period_end > timezone.now()

    @property
    def is_overdue(self):
        return (self.status in ('expired', 'cancelled', 'past_due') or
                (not self.tier.is_free and self.status in ('active', 'trialing')
                 and self.current_period_end <= timezone.now()))

    def expire_and_downgrade(self, *, reason='Billing period lapsed'):
        from subscriptions.billing import expire_subscription
        return expire_subscription(self, reason=reason)

    @property
    def tier_level(self):
        return self.tier.tier_level if self.is_active else 0

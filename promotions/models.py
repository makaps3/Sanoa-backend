"""
Promotions & Coupons.

Two customer-facing discount mechanisms, both owned either by a *vendor*
(applies only to that vendor's cart) or by the *platform* (applies to any
cart):

  * Promotion — an AUTOMATIC discount. No code. The discount engine
    (``promotions.services``) applies every live, eligible promotion to a
    cart automatically as items are added.

  * Coupon — a CODE-based discount the customer types on the cart screen.
    One coupon per cart. Usage is metered (total + per-user caps).

Both share the same discount vocabulary (percentage / fixed amount /
free shipping) and the same targeting scope (whole cart / specific
products / specific categories). Money is ``Decimal(10, 2)`` in ZAR, the
project-wide convention.

The existing (orphaned) ``orders.Coupon`` model is intentionally left
untouched — this app is the canonical, checkout-wired system.
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

TWOPLACES = Decimal('0.01')


def money(value) -> Decimal:
    """Coerce anything money-ish to a 2dp Decimal (never negative-NaN)."""
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'Percentage off'
    FIXED_AMOUNT = 'fixed_amount', 'Fixed amount off'
    FREE_SHIPPING = 'free_shipping', 'Free shipping'


class OwnerType(models.TextChoices):
    VENDOR = 'vendor', 'Vendor'
    PLATFORM = 'platform', 'Platform'


class Scope(models.TextChoices):
    ALL = 'all', 'Entire cart'
    PRODUCTS = 'products', 'Specific products'
    CATEGORIES = 'categories', 'Specific categories'


class DiscountRuleMixin(models.Model):
    """Shared discount vocabulary + targeting for Promotion and Coupon."""

    owner_type = models.CharField(
        max_length=10, choices=OwnerType.choices, default=OwnerType.VENDOR)
    # Null vendor == platform-wide (owner_type should then be 'platform').
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        null=True, blank=True, related_name='%(class)ss')

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE)
    # Percentage (0–100) OR fixed amount in ZAR. Ignored for free_shipping.
    value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))])
    # Optional ceiling on a percentage discount, e.g. "20% off, up to R100".
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))])

    scope = models.CharField(
        max_length=12, choices=Scope.choices, default=Scope.ALL)
    applicable_products = models.ManyToManyField(
        'products.Product', blank=True, related_name='%(class)ss')
    applicable_categories = models.ManyToManyField(
        'products.Category', blank=True, related_name='%(class)ss')

    minimum_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))])

    # Restrict the rule to specific customers. Empty == open to everyone.
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='+')

    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    # ── discount vocabulary ──────────────────────────────────────────

    @property
    def is_free_shipping(self):
        return self.discount_type == DiscountType.FREE_SHIPPING

    @property
    def is_platform(self):
        return self.owner_type == OwnerType.PLATFORM or self.vendor_id is None

    def window_status(self, now=None):
        """'scheduled' | 'active' | 'expired' | 'inactive'."""
        now = now or timezone.now()
        if not self.is_active:
            return 'inactive'
        if self.start_date and now < self.start_date:
            return 'scheduled'
        if self.end_date and now > self.end_date:
            return 'expired'
        return 'active'

    def in_window(self, now=None):
        return self.window_status(now) == 'active'

    def applies_to_user(self, user):
        """True when this rule is available to `user` — either it targets
        everyone (no target_users) or `user` is one of the targets."""
        if not self.target_users.exists():
            return True
        if user is None or not getattr(user, 'is_authenticated', False):
            return False
        return self.target_users.filter(pk=user.pk).exists()

    def matches_item(self, product, category_id=None):
        """Does this rule target the given product?"""
        if self.scope == Scope.ALL:
            return True
        if self.scope == Scope.PRODUCTS:
            return self.applicable_products.filter(pk=product.pk).exists()
        if self.scope == Scope.CATEGORIES:
            cat_id = category_id if category_id is not None else \
                getattr(product, 'category_id', None)
            if cat_id is None:
                return False
            return self.applicable_categories.filter(pk=cat_id).exists()
        return False

    def compute_discount(self, base_amount) -> Decimal:
        """Discount on an eligible base subtotal (never exceeds it)."""
        base = money(base_amount)
        if base <= 0 or self.is_free_shipping:
            return Decimal('0.00')
        if self.discount_type == DiscountType.PERCENTAGE:
            raw = base * (money(self.value) / Decimal('100'))
            if self.max_discount_amount:
                raw = min(raw, money(self.max_discount_amount))
        else:  # fixed amount
            raw = money(self.value)
        return money(min(raw, base))


class Promotion(DiscountRuleMixin):
    """An automatically-applied discount (no code needed)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # When two automatic promotions target the same item, the higher
    # priority wins (each item is discounted by at most one promotion).
    priority = models.IntegerField(default=0)
    # Whether this promotion still applies when a coupon is also on the cart.
    stackable_with_coupon = models.BooleanField(default=True)

    minimum_quantity = models.PositiveIntegerField(default=0)
    # Optional total-redemption cap across all customers.
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    banner_color = models.CharField(max_length=9, blank=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['owner_type', 'vendor']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_discount_type_display()})'

    def is_live(self, now=None):
        if not self.in_window(now):
            return False
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False
        return True


class Coupon(DiscountRuleMixin):
    """A code-based discount the customer applies manually."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(max_length=40, unique=True, db_index=True)

    max_uses = models.PositiveIntegerField(null=True, blank=True)
    max_uses_per_user = models.PositiveIntegerField(default=1)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['owner_type', 'vendor']),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_live(self, now=None):
        if not self.in_window(now):
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def uses_by(self, user):
        if user is None or not getattr(user, 'is_authenticated', False):
            return 0
        return self.redemptions.filter(user=user).count()

    def validate_for(self, user, subtotal, vendor_id=None):
        """
        Returns ``(ok: bool, message: str)``. ``message`` is a customer-safe
        explanation when ``ok`` is False.
        """
        now = timezone.now()
        status = self.window_status(now)
        if status == 'inactive':
            return False, 'This coupon is no longer available.'
        if status == 'scheduled':
            return False, 'This coupon is not active yet.'
        if status == 'expired':
            return False, 'This coupon has expired.'
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False, 'This coupon has reached its usage limit.'
        if (not self.is_platform and vendor_id is not None
                and str(self.vendor_id) != str(vendor_id)):
            return False, 'This coupon is not valid for this store.'
        if not self.applies_to_user(user):
            return False, 'This coupon is not available for your account.'
        if money(subtotal) < money(self.minimum_order_amount):
            return (False,
                    f'Add R{money(self.minimum_order_amount)} worth of items '
                    f'to use this coupon.')
        if user is not None and self.uses_by(user) >= self.max_uses_per_user:
            return False, 'You have already used this coupon.'
        return True, 'Coupon applied.'


class AppliedCoupon(models.Model):
    """The single coupon currently attached to a shopping cart (if any)."""

    cart = models.OneToOneField(
        'orders.ShoppingCart', on_delete=models.CASCADE,
        related_name='applied_coupon')
    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name='cart_applications')
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.coupon.code} on cart {self.cart_id}'


class CouponRedemption(models.Model):
    """A recorded, completed use of a coupon (created at checkout)."""

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='coupon_redemptions')
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupon_redemptions')
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'))
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-redeemed_at']
        indexes = [models.Index(fields=['coupon', 'user'])]

    def __str__(self):
        return f'{self.coupon.code} by {self.user_id}'


class PromotionRedemption(models.Model):
    """A recorded use of an automatic promotion (created at checkout)."""

    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='promotion_redemptions')
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotion_redemptions')
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'))
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-redeemed_at']

    def __str__(self):
        return f'{self.promotion_id} by {self.user_id}'


class BannerAction(models.TextChoices):
    NONE = 'none', 'No action'
    PROMOTION = 'promotion', 'Open a promotion'
    VENDOR = 'vendor', 'Open a store'
    CATEGORY = 'category', 'Open a category'
    PROMOTIONS_HUB = 'promotions', 'Open all promotions'


class PromotionBanner(models.Model):
    """A visual promotional banner shown in the customer home carousel.

    Owned by the platform (admin) or a vendor. Each banner carries an image
    and an optional call-to-action that deep-links into a promotion, a store,
    a category, or the promotions hub.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner_type = models.CharField(
        max_length=10, choices=OwnerType.choices, default=OwnerType.PLATFORM)
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        null=True, blank=True, related_name='promotion_banners')

    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=180, blank=True)
    image = models.ImageField(upload_to='promotion_banners/')

    cta_text = models.CharField(max_length=30, blank=True, default='Shop Now')
    action_type = models.CharField(
        max_length=12, choices=BannerAction.choices, default=BannerAction.NONE)
    promotion = models.ForeignKey(
        Promotion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banners')
    category = models.ForeignKey(
        'products.Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotion_banners')

    # Optional brand colours for the text overlay / gradient scrim.
    background_color = models.CharField(max_length=9, blank=True)
    text_color = models.CharField(max_length=9, blank=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['owner_type', 'vendor']),
        ]

    def __str__(self):
        return self.title

    @property
    def is_platform(self):
        return self.owner_type == OwnerType.PLATFORM or self.vendor_id is None

    def is_live(self, now=None):
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

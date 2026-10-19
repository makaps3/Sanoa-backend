from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class ShippingAddress(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('shipping', 'Shipping Address'),
        ('billing', 'Billing Address'),
        ('both', 'Billing & Shipping'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='shipping_addresses',
        limit_choices_to={'user_type': 'customer'},
    )
    address_type = models.CharField(
        max_length=10, choices=ADDRESS_TYPE_CHOICES, default='shipping',
    )
    label = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=17)

    street_address = models.CharField(max_length=255)
    apartment_number = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='South Africa')

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    is_default = models.BooleanField(default=False)
    delivery_instructions = models.TextField(blank=True, max_length=500)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shipping Address'
        verbose_name_plural = 'Shipping Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.state_province}"

    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingAddress.objects.filter(
                user=self.user, is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        # Auto-geocode the address whenever the client didn't supply
        # usable coordinates. The geocoder is a no-op when
        # GOOGLE_MAPS_API_KEY isn't configured, so this is safe in dev
        # environments too. Treat (0, 0) and NULL as "missing" — some
        # clients default to zero rather than omitting the fields, and
        # (0, 0) is the middle of the Atlantic, never a real address.
        def _missing_coord(v):
            return v is None or v == 0

        if _missing_coord(self.latitude) or _missing_coord(self.longitude):
            from core.geocoding import geocode_address
            lat, lng = geocode_address(
                street_address=self.street_address,
                apartment_number=self.apartment_number,
                city=self.city,
                state_province=self.state_province,
                postal_code=self.postal_code,
                country=self.country,
            )
            if lat is not None and lng is not None:
                self.latitude = lat
                self.longitude = lng
        super().save(*args, **kwargs)


class ShoppingCart(models.Model):
    """Retail shopping cart — one per vendor, max 3 per user."""
    MAX_CARTS_PER_USER = 3

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopping_carts')
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='carts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shopping Cart'
        verbose_name_plural = 'Shopping Carts'
        unique_together = ['user', 'vendor']

    def __str__(self):
        vendor_label = (
            self.vendor.trading_name or self.vendor.name or self.vendor.user.email
        )
        return f"{self.user.email}'s Cart (vendor: {vendor_label})"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    """Retail cart item — no food add-ons or special instructions."""

    cart = models.ForeignKey(ShoppingCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    negotiation = models.ForeignKey(
        'negotiations.NegotiationRoom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        variant_text = f" ({self.product_variant.name})" if self.product_variant else ""
        return f"{self.product.name}{variant_text} x {self.quantity}"

    @property
    def is_negotiated(self):
        return self.negotiation_id is not None

    @property
    def original_price(self):
        if self.product_variant:
            return self.product_variant.effective_price
        return self.product.price

    @property
    def total_price(self):
        return self.quantity * (self.price_at_time or Decimal('0.00'))

    def save(self, *args, **kwargs):
        if not self.price_at_time:
            if self.negotiation:
                self.price_at_time = self.negotiation.agreed_price
            elif self.product_variant:
                self.price_at_time = self.product_variant.effective_price
            else:
                self.price_at_time = self.product.price
        super().save(*args, **kwargs)


class Order(models.Model):
    """Retail order only."""

    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),          # vendor confirmed they received the order
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    FULFILLMENT_TYPE_CHOICES = [
        ('delivery', 'Delivery'),
        ('pickup', 'Pickup'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')

    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # How `discount_amount` splits by who funds it. A vendor-funded discount
    # is absorbed by the vendor (commission is charged on the discounted goods
    # value); a platform-funded discount comes out of the platform's slice.
    # Both default 0 so pre-promotion orders keep their original split.
    vendor_funded_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_funded_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # ── Order financial split (see core.order_financials) ───────────────
    # `service_fee` is the customer-side markup; `commission_*` is the
    # cut Sanoa keeps from the vendor's settlement; `vendor_payout` and
    # `platform_payout` are the resulting net amounts. `paystack_fee`
    # starts at 0 and is updated once the payment transaction settles.
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paystack_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vendor_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=17, blank=True)

    billing_full_name = models.CharField(max_length=100)
    billing_street_address = models.CharField(max_length=255)
    billing_apartment_number = models.CharField(max_length=20, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state_province = models.CharField(max_length=100)
    billing_postal_code = models.CharField(max_length=20)
    billing_country = models.CharField(max_length=100)

    shipping_address = models.ForeignKey(
        'orders.ShippingAddress', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
    )
    shipping_full_name = models.CharField(max_length=100)
    shipping_street_address = models.CharField(max_length=255)
    shipping_apartment_number = models.CharField(max_length=20, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state_province = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)

    fulfillment_type = models.CharField(
        max_length=20, choices=FULFILLMENT_TYPE_CHOICES, default='delivery',
    )

    order_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    coupon_code = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import datetime
            today = datetime.date.today()
            prefix = f"ORD-{today.strftime('%Y%m%d')}-"
            last_order = Order.objects.filter(
                order_number__startswith=prefix
            ).order_by('order_number').last()
            if last_order:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = f"{last_num + 1:04d}"
            else:
                new_num = "0001"
            self.order_number = f"{prefix}{new_num}"
        super().save(*args, **kwargs)

    def calculate_totals(self):
        def _d(value):
            return value if isinstance(value, Decimal) else Decimal(str(value or 0))

        subtotal = sum(
            (item.total_price for item in self.items.all()),
            Decimal('0.00'),
        )
        self.subtotal = subtotal

        # Apply the platform fee split. The customer-side service fee
        # is rolled into total_amount; the merchant-side commission
        # split lands on `vendor_payout` / `platform_payout` so the
        # vendor dashboard can show the after-commission figure
        # without recomputing every render.
        #
        # Discounts are attributed by who funds them:
        #   • vendor-funded  → the vendor absorbs it, so commission and
        #     vendor payout are computed on the *discounted* goods value.
        #   • platform-funded → the vendor is paid as if full price; the
        #     discount is subtracted from the platform's slice.
        # The customer-facing service fee stays on the gross subtotal so
        # what they were shown at checkout doesn't shift.
        from core.order_financials import (
            derive_from_platform_fee, lookup_platform_fee,
        )
        vendor = self.primary_vendor
        vendor_funded = _d(self.vendor_funded_discount)
        platform_funded = _d(self.platform_funded_discount)
        commission_base = max(subtotal - vendor_funded, Decimal('0.00'))

        if self.service_fee:
            service_fee_arg = _d(self.service_fee)
        else:
            fee_row = lookup_platform_fee(vendor)
            if fee_row is not None:
                csf_pct = _d(fee_row.customer_service_fee_percent)
                service_fee_arg = (subtotal * csf_pct / Decimal('100'))
            else:
                service_fee_arg = None

        split = derive_from_platform_fee(
            vendor=vendor,
            order_amount=commission_base,
            delivery_fee=self.shipping_cost,
            fulfillment_type=self.fulfillment_type,
            paystack_fee=self.paystack_fee,
            service_fee=service_fee_arg,
        )
        self.service_fee = split.service_fee
        self.commission_amount = split.commission_amount
        self.vendor_payout = split.vendor_payout
        # The platform absorbs any platform-funded discount out of its slice.
        self.platform_payout = split.platform_payout - platform_funded
        if vendor is not None:
            from platform_admin.models import PlatformFee
            fee_row = PlatformFee.for_business_category(
                getattr(vendor, 'business_category', None),
            )
            if fee_row is not None:
                self.service_fee_percent = fee_row.customer_service_fee_percent
                self.commission_percent = fee_row.merchant_commission_percent

        self.total_amount = (
            subtotal
            + _d(self.tax_amount)
            + _d(self.shipping_cost)
            + _d(self.service_fee)
            - _d(self.discount_amount)
        )
        self.save()

    @property
    def primary_vendor(self):
        """The vendor settling this order.

        Retail carts are single-vendor (orders/views.py guards on
        `cart.vendor`), so any item's vendor is the right answer.
        Returns None when the order has no items yet (e.g. mid-create).
        """
        item = self.items.select_related('vendor').first()
        return item.vendor if item else None

    def update_paystack_fee(self, fee):
        """Refresh `paystack_fee` + `platform_payout` after Paystack
        settles the transaction. Vendor payout is unaffected."""
        from core.order_financials import compute_order_financials
        split = compute_order_financials(
            order_amount=self.subtotal,
            delivery_fee=self.shipping_cost,
            fulfillment_type=self.fulfillment_type,
            service_fee=self.service_fee,
            commission_percent=self.commission_percent,
            paystack_fee=fee,
        )
        self.paystack_fee = Decimal(str(fee or 0))
        self.platform_payout = split.platform_payout
        self.save(update_fields=['paystack_fee', 'platform_payout', 'updated_at'])

    @property
    def is_paid(self):
        return self.payment_status == 'paid'

    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'confirmed', 'processing']


class OrderItem(models.Model):
    """Retail order line item — no food add-ons."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    product_name = models.CharField(max_length=300)
    product_sku = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=200, blank=True)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='order_items',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        variant_text = f" ({self.variant_name})" if self.variant_name else ""
        return f"{self.product_name}{variant_text} x {self.quantity}"

    def save(self, *args, **kwargs):
        if not self.product_name:
            self.product_name = self.product.name
            self.product_sku = self.product.sku
            if not getattr(self, 'vendor_id', None):
                self.vendor = self.product.vendor
            if self.product_variant:
                self.variant_name = self.product_variant.name
                self.unit_price = self.product_variant.effective_price
            else:
                self.unit_price = self.product.price
            self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    comment = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order.order_number} - {self.previous_status} -> {self.new_status}"


class Coupon(models.Model):
    COUPON_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPE_CHOICES, default='percentage')
    value = models.DecimalField(max_digits=10, decimal_places=2)

    max_uses = models.PositiveIntegerField(null=True, blank=True)
    max_uses_per_user = models.PositiveIntegerField(default=1)
    current_uses = models.PositiveIntegerField(default=0)

    minimum_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )

    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)

    applicable_categories = models.ManyToManyField('products.Category', blank=True)
    applicable_products = models.ManyToManyField('products.Product', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_valid(self, user=None, order_amount=None):
        from django.utils import timezone
        if not self.is_active:
            return False, "Coupon is not active"
        now = timezone.now()
        if now < self.start_date:
            return False, "Coupon is not yet valid"
        if self.end_date and now > self.end_date:
            return False, "Coupon has expired"
        if self.max_uses and self.current_uses >= self.max_uses:
            return False, "Coupon usage limit reached"
        if user:
            user_uses = Order.objects.filter(user=user, coupon_code=self.code).count()
            if user_uses >= self.max_uses_per_user:
                return False, "You have already used this coupon the maximum number of times"
        if self.minimum_order_amount and order_amount and order_amount < self.minimum_order_amount:
            return False, f"Minimum order amount of R{self.minimum_order_amount} required"
        return True, "Coupon is valid"

    def calculate_discount(self, order_amount):
        if self.coupon_type == 'percentage':
            return order_amount * (self.value / 100)
        elif self.coupon_type == 'fixed_amount':
            return min(self.value, order_amount)
        else:
            return Decimal('0.00')

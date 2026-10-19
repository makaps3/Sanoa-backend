from decimal import Decimal
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class RestaurantCart(models.Model):
    """Restaurant cart — one per vendor per user, max 3 carts per user."""

    # Mirrors orders.ShoppingCart.MAX_CARTS_PER_USER. Enforced in the
    # add-item endpoint when a customer tries to open a cart at a
    # vendor they don't already have a cart with.
    MAX_CARTS_PER_USER = 3

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurant_carts')
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='restaurant_carts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'vendor']
        verbose_name = 'Restaurant Cart'
        verbose_name_plural = 'Restaurant Carts'

    def __str__(self):
        label = self.vendor.trading_name or self.vendor.name or self.vendor.user.email
        return f"{self.user.email}'s restaurant cart @ {label}"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

    def clear(self):
        self.items.all().delete()


class RestaurantCartItem(models.Model):
    """
    A line in a restaurant cart.
    selected_addons is a JSON snapshot: [{id, name, price_delta}, ...]
    """

    cart = models.ForeignKey(RestaurantCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Mirrors `orders.CartItem.negotiation`: when a buyer agrees a
    # restaurant item via the negotiation chat, this FK lets the
    # checkout view gate on the linked room's status (pending_vendor →
    # blocked, agreed → cleared) and lets the vendor reject / expiry
    # paths purge the cart row by joining on this column.
    negotiation = models.ForeignKey(
        'negotiations.NegotiationRoom', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    special_instructions = models.CharField(max_length=500, blank=True)
    selected_addons = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Restaurant Cart Item'
        verbose_name_plural = 'Restaurant Cart Items'

    def __str__(self):
        variant = f" ({self.product_variant.name})" if self.product_variant else ""
        return f"{self.product.name}{variant} x {self.quantity}"

    @property
    def addons_total(self):
        total = Decimal('0.00')
        for addon in self.selected_addons or []:
            try:
                total += Decimal(str(addon.get('price_delta', '0')))
            except (ArithmeticError, ValueError, TypeError):
                continue
        return total

    @property
    def total_price(self):
        unit = (self.price_at_time or Decimal('0.00')) + self.addons_total
        return self.quantity * unit

    @property
    def is_negotiated(self):
        return self.negotiation_id is not None

    def save(self, *args, **kwargs):
        if not self.price_at_time:
            # Negotiated rooms win — the agreed_price set by the chat is
            # the contract, the variant/product price is just the
            # fallback when there's no live negotiation.
            if self.negotiation:
                self.price_at_time = self.negotiation.agreed_price
            elif self.product_variant:
                self.price_at_time = self.product_variant.effective_price
            else:
                self.price_at_time = self.product.price
        super().save(*args, **kwargs)


class RestaurantOrder(models.Model):
    """A customer order placed at a restaurant vendor."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    FULFILLMENT_CHOICES = [
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurant_orders')
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='restaurant_orders',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='delivery')

    estimated_prep_minutes = models.PositiveIntegerField(null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # ── Order financial split (see core.order_financials) ───────────────
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    service_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paystack_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    vendor_payout = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    platform_payout = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=17, blank=True)

    # Delivery address FK + immutable snapshot
    shipping_address = models.ForeignKey(
        'orders.ShippingAddress', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='restaurant_orders',
    )
    shipping_full_name = models.CharField(max_length=100, blank=True)
    shipping_street_address = models.CharField(max_length=255, blank=True)
    shipping_apartment_number = models.CharField(max_length=20, blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state_province = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_country = models.CharField(max_length=100, blank=True)

    coupon_code = models.CharField(max_length=50, blank=True)
    order_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Restaurant Order'
        verbose_name_plural = 'Restaurant Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"ROrder {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import datetime
            today = datetime.date.today()
            prefix = f"RST-{today.strftime('%Y%m%d')}-"
            last = RestaurantOrder.objects.filter(
                order_number__startswith=prefix
            ).order_by('order_number').last()
            if last:
                last_num = int(last.order_number.split('-')[-1])
                new_num = f"{last_num + 1:04d}"
            else:
                new_num = "0001"
            self.order_number = f"{prefix}{new_num}"
        super().save(*args, **kwargs)

    def calculate_totals(self):
        def _d(v):
            return v if isinstance(v, Decimal) else Decimal(str(v or 0))

        subtotal = sum(
            (item.total_price for item in self.items.all()),
            Decimal('0.00'),
        )
        self.subtotal = subtotal

        # Apply the platform fee split — see core.order_financials.
        from core.order_financials import derive_from_platform_fee
        client_service_fee = _d(self.service_fee) if self.service_fee else None
        split = derive_from_platform_fee(
            vendor=self.vendor,
            order_amount=subtotal,
            delivery_fee=self.delivery_fee,
            fulfillment_type=self.fulfillment_type,
            paystack_fee=self.paystack_fee,
            service_fee=client_service_fee,
        )
        self.service_fee = split.service_fee
        self.commission_amount = split.commission_amount
        self.vendor_payout = split.vendor_payout
        self.platform_payout = split.platform_payout
        from platform_admin.models import PlatformFee
        fee_row = PlatformFee.for_business_category(
            getattr(self.vendor, 'business_category', None),
        )
        if fee_row is not None:
            self.service_fee_percent = fee_row.customer_service_fee_percent
            self.commission_percent = fee_row.merchant_commission_percent

        self.total_amount = (
            subtotal
            + _d(self.tax_amount)
            + _d(self.delivery_fee)
            + _d(self.service_fee)
            - _d(self.discount_amount)
        )
        self.save()

    def update_paystack_fee(self, fee):
        """Refresh `paystack_fee` + `platform_payout` after Paystack
        settles the transaction."""
        from core.order_financials import compute_order_financials
        split = compute_order_financials(
            order_amount=self.subtotal,
            delivery_fee=self.delivery_fee,
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
        return self.status in ['pending', 'confirmed']


class RestaurantOrderItem(models.Model):
    """Line item in a restaurant order, with add-on and instruction snapshots."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(RestaurantOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        'products.ProductVariant', on_delete=models.CASCADE,
        null=True, blank=True,
    )

    product_name = models.CharField(max_length=300)
    product_sku = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=200, blank=True)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    addons_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    special_instructions = models.CharField(max_length=500, blank=True)
    selected_addons = models.JSONField(default=list, blank=True)

    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='restaurant_order_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Restaurant Order Item'
        verbose_name_plural = 'Restaurant Order Items'

    def __str__(self):
        variant = f" ({self.variant_name})" if self.variant_name else ""
        return f"{self.product_name}{variant} x {self.quantity}"

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
            self.total_price = self.quantity * (self.unit_price + self.addons_total)
        super().save(*args, **kwargs)


class KitchenTicket(models.Model):
    """
    Kitchen-side view of a confirmed restaurant order.
    Created automatically when the order transitions to 'confirmed'.
    """

    STATUS_CHOICES = [
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('handed_off', 'Handed Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        RestaurantOrder, on_delete=models.CASCADE, related_name='kitchen_ticket',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    acknowledged_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    handed_off_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kitchen Ticket'
        verbose_name_plural = 'Kitchen Tickets'
        ordering = ['created_at']

    def __str__(self):
        return f"Ticket for {self.order.order_number} [{self.status}]"


class RestaurantOrderTrackingEvent(models.Model):
    """
    Immutable timeline event for an order — pushed via WebSocket to customers.
    """

    EVENT_TYPE_CHOICES = [
        ('order_placed', 'Order Placed'),
        ('payment_confirmed', 'Payment Confirmed'),
        ('order_confirmed', 'Order Confirmed'),
        ('preparing', 'Kitchen is Preparing'),
        ('ready', 'Ready'),
        ('driver_assigned', 'Driver Assigned'),
        ('driver_at_vendor', 'Driver at Restaurant'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        RestaurantOrder, on_delete=models.CASCADE, related_name='tracking_events',
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Tracking Event'
        verbose_name_plural = 'Order Tracking Events'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.order.order_number} — {self.event_type}"

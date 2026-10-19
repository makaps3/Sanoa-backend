import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class PricePolicy(models.Model):
    vendor = models.OneToOneField(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='price_policy',
    )
    max_markup_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum price increase % the AI can apply for high-demand items",
    )
    max_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum discount % the AI will ever offer a buyer",
    )
    min_floor_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Hard floor: AI won't accept offers below (price - min_floor%)",
    )
    auto_negotiate = models.BooleanField(
        default=True,
        help_text="Allow AI chatbot to negotiate on your behalf",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Price Policy'
        verbose_name_plural = 'Price Policies'

    def __str__(self):
        name = getattr(self.vendor, 'trading_name', None) or getattr(self.vendor, 'name', None)
        return f"{name or self.vendor_id} — markup {self.max_markup_percent}% / discount {self.max_discount_percent}%"


class NegotiationRoom(models.Model):
    """
    A chat room for negotiating the price of a single product.

    mode='ai'     — XGBoost bot replies on behalf of the vendor.
    mode='manual' — vendor types replies themselves.

    Once both sides agree, status becomes 'agreed' and offer_expires_at is
    set 24 hours out.  Celery auto-expires the room if no checkout happens.
    """
    MODE_AI = 'ai'
    MODE_MANUAL = 'manual'
    MODE_CHOICES = [
        (MODE_AI, 'AI Chatbot'),
        (MODE_MANUAL, 'Manual Vendor Chat'),
    ]

    STATUS_OPEN = 'open'
    # AI mode only: the bot recommended accepting the buyer's offer but
    # the deal is not final until the vendor confirms. Lives for 24 h,
    # then auto-expires if the vendor doesn't act.
    STATUS_PENDING_VENDOR = 'pending_vendor'
    STATUS_AGREED = 'agreed'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PENDING_VENDOR, 'Awaiting vendor confirmation'),
        (STATUS_AGREED, 'Agreed — awaiting checkout'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'products.Product', on_delete=models.CASCADE,
        related_name='negotiation_rooms',
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='negotiation_rooms_as_buyer',
        limit_choices_to={'user_type': 'customer'},
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='negotiation_rooms',
    )
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_AI)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Buyer must checkout before this (24 h after agreement)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Negotiation Room'
        verbose_name_plural = 'Negotiation Rooms'
        ordering = ['-created_at']

    def __str__(self):
        return f"Room {self.id}: {self.product.name} | {self.buyer.email} ({self.status})"

    def set_agreed(self, price):
        from decimal import Decimal
        self.agreed_price = Decimal(str(price))
        self.status = self.STATUS_AGREED
        # Always give the buyer a fresh 24 h checkout window from this
        # moment — important when the room was previously in
        # `pending_vendor` and the vendor confirmed near the end of
        # their own 24 h approval window.
        self.offer_expires_at = timezone.now() + timedelta(hours=24)
        self.save(update_fields=['agreed_price', 'status', 'offer_expires_at', 'updated_at'])

    def set_pending_vendor(self, price):
        """AI accepted the buyer's offer; vendor has 24 h to confirm."""
        from decimal import Decimal
        self.agreed_price = Decimal(str(price))
        self.status = self.STATUS_PENDING_VENDOR
        self.offer_expires_at = timezone.now() + timedelta(hours=24)
        self.save(update_fields=['agreed_price', 'status', 'offer_expires_at', 'updated_at'])


class NegotiationMessage(models.Model):
    SENDER_BUYER = 'buyer'
    SENDER_VENDOR = 'vendor'
    SENDER_AI = 'ai'
    SENDER_SYSTEM = 'system'
    SENDER_CHOICES = [
        (SENDER_BUYER, 'Buyer'),
        (SENDER_VENDOR, 'Vendor'),
        (SENDER_AI, 'AI Bot'),
        (SENDER_SYSTEM, 'System'),
    ]

    TYPE_TEXT = 'text'
    TYPE_OFFER = 'offer'
    TYPE_COUNTER = 'counter_offer'
    TYPE_ACCEPTED = 'accepted'
    TYPE_REJECTED = 'rejected'
    TYPE_EXPIRED = 'expired'
    TYPE_SYSTEM = 'system'
    TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_OFFER, 'Price Offer'),
        (TYPE_COUNTER, 'Counter Offer'),
        (TYPE_ACCEPTED, 'Accepted'),
        (TYPE_REJECTED, 'Rejected'),
        (TYPE_EXPIRED, 'Expired'),
        (TYPE_SYSTEM, 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        NegotiationRoom, on_delete=models.CASCADE, related_name='messages',
    )
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='negotiation_messages',
    )
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT)
    price_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Price carried by this message (offers/counters)",
    )
    is_seen = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Negotiation Message'
        verbose_name_plural = 'Negotiation Messages'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.sender_type}] {self.message_type}: {self.content[:60]}"

    def mark_seen(self):
        if not self.is_seen:
            self.is_seen = True
            self.seen_at = timezone.now()
            self.save(update_fields=['is_seen', 'seen_at'])


class NegotiationOffer(models.Model):
    OFFERED_BY_CHOICES = [
        ('buyer', 'Buyer'),
        ('vendor', 'Vendor'),
        ('ai', 'AI Bot'),
    ]
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_COUNTERED = 'countered'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COUNTERED, 'Countered'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        NegotiationRoom, on_delete=models.CASCADE, related_name='offers',
    )
    message = models.OneToOneField(
        NegotiationMessage, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offer_detail',
    )
    offered_by = models.CharField(max_length=10, choices=OFFERED_BY_CHOICES)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    offered_price = models.DecimalField(max_digits=10, decimal_places=2)
    counter_offer_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # AI metadata
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_action = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="AI decision: accept / counter / reject",
    )

    round_number = models.PositiveSmallIntegerField(default=1)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Negotiation Offer'
        verbose_name_plural = 'Negotiation Offers'
        ordering = ['-created_at']

    def __str__(self):
        return f"Offer {self.id}: R{self.offered_price} by {self.offered_by} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

"""
Payment models – fully integrated with Paystack.
Covers: Transactions, Transaction Splits, Subaccounts, Refunds, Disputes,
Webhook logs, and Payment audit logs.
"""
import uuid
import datetime

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# Subaccount – maps vendors to Paystack subaccounts
# ═══════════════════════════════════════════════════════════════

class PaystackSubaccount(models.Model):
    """
    Paystack subaccount for a vendor.
    Each vendor gets a subaccount so that split payments can route
    the vendor's share directly to their bank account.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.OneToOneField(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='paystack_subaccount',
    )

    # Paystack identifiers
    subaccount_code = models.CharField(
        max_length=100, unique=True, blank=True,
        help_text='Paystack subaccount code (ACCT_xxx)',
    )
    paystack_subaccount_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Paystack numeric subaccount ID',
    )

    # Bank details (mirrored from vendor profile for Paystack)
    business_name = models.CharField(max_length=255)
    settlement_bank = models.CharField(
        max_length=100,
        help_text='Paystack bank code for settlement',
    )
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=200, blank=True)
    account_name = models.CharField(
        max_length=200, blank=True,
        help_text='Resolved account name from Paystack',
    )

    # Commission / split configuration. Auto-set from the linked
    # PlatformFee at subaccount creation — vendors no longer pick
    # their own percentage. Paystack's gateway fee is absorbed by
    # the platform out of this commission.
    percentage_charge = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text='Auto-derived from PlatformFee.merchant_commission_percent.',
    )
    platform_fee = models.ForeignKey(
        'platform_admin.PlatformFee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='Fee row this subaccount\'s commission was derived from.',
    )
    flat_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Flat fee in kobo/cents retained for the main account per txn',
    )
    primary_contact_email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paystack Subaccount'
        verbose_name_plural = 'Paystack Subaccounts'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.business_name} ({self.subaccount_code})'


# ═══════════════════════════════════════════════════════════════
# Transaction Split
# ═══════════════════════════════════════════════════════════════

class TransactionSplit(models.Model):
    """
    Paystack transaction split configuration.
    Splits allow automatic revenue sharing between the main account
    and one or more subaccounts on every qualifying transaction.
    """

    SPLIT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('flat', 'Flat'),
    ]

    BEARER_TYPE_CHOICES = [
        ('subaccount', 'Subaccount'),
        ('account', 'Main Account'),
        ('all-proportional', 'All Proportional'),
        ('all', 'All'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    paystack_split_id = models.PositiveIntegerField(null=True, blank=True)
    paystack_split_code = models.CharField(max_length=100, unique=True, blank=True)
    split_type = models.CharField(max_length=12, choices=SPLIT_TYPE_CHOICES, default='percentage')
    currency = models.CharField(max_length=3, default='ZAR')
    bearer_type = models.CharField(max_length=20, choices=BEARER_TYPE_CHOICES, default='account')
    bearer_subaccount = models.CharField(
        max_length=100, blank=True,
        help_text='Subaccount code of the bearer (if bearer_type is subaccount)',
    )

    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction Split'
        verbose_name_plural = 'Transaction Splits'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.split_type})'


class TransactionSplitSubaccount(models.Model):
    """A subaccount entry within a transaction split."""

    split = models.ForeignKey(
        TransactionSplit, on_delete=models.CASCADE, related_name='subaccounts',
    )
    subaccount = models.ForeignKey(
        PaystackSubaccount, on_delete=models.CASCADE, related_name='split_entries',
    )
    share = models.PositiveIntegerField(
        help_text='Share value – percentage (0-100) or flat amount in kobo/cents',
    )

    class Meta:
        verbose_name = 'Split Subaccount Entry'
        verbose_name_plural = 'Split Subaccount Entries'
        unique_together = ['split', 'subaccount']

    def __str__(self):
        return f'{self.subaccount.business_name} – {self.share}'


# ═══════════════════════════════════════════════════════════════
# Transaction (Payment)
# ═══════════════════════════════════════════════════════════════

class Transaction(models.Model):
    """
    A Paystack payment transaction.
    Replaces the old Payment model with full Paystack field mapping.
    """

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
        ('reversed', 'Reversed'),
    ]

    CHANNEL_CHOICES = [
        ('card', 'Card'),
        ('bank', 'Bank'),
        ('ussd', 'USSD'),
        ('qr', 'QR'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('eft', 'EFT'),
    ]

    PAYMENT_INTENT_CHOICES = [
        ('order_payment', 'Order Payment'),
        ('subscription_payment', 'Subscription Payment'),
        ('tier_payment', 'Tier Payment'),
        ('credit_payment', 'Credit Repayment'),
        ('deposit', 'Deposit'),
    ]

    # Basic info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        max_length=200, unique=True,
        help_text='Unique transaction reference (sent to Paystack)',
    )
    payment_intent = models.CharField(
        max_length=20, choices=PAYMENT_INTENT_CHOICES, default='order_payment',
    )

    # Related objects
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, related_name='transactions',
        null=True, blank=True,
    )
    # Restaurant orders live in their own table, so they need their own link —
    # without this a restaurant checkout can't be paid for at all.
    restaurant_order = models.ForeignKey(
        'restaurant.RestaurantOrder', on_delete=models.SET_NULL,
        related_name='transactions', null=True, blank=True,
        help_text='Linked restaurant order when the payment is for one.',
    )
    subscription = models.ForeignKey(
        'subscriptions.Subscription', on_delete=models.SET_NULL,
        related_name='transactions', null=True, blank=True,
    )
    vendor_tier_subscription = models.ForeignKey(
        'tiers.VendorTierSubscription', on_delete=models.SET_NULL,
        related_name='transactions', null=True, blank=True,
    )
    credit_purchase = models.ForeignKey(
        'debit.CreditPurchase', on_delete=models.SET_NULL,
        related_name='transactions', null=True, blank=True,
        help_text='Linked credit purchase when payment_intent is credit_payment',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',
        help_text='Vendor receiving funds on this transaction (set from subaccount)',
    )

    # Amounts (stored in major currency units – ZAR rands)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Amount in rands',
    )
    currency = models.CharField(max_length=3, default='ZAR')
    paystack_fees = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Paystack processing fees (rands)',
    )

    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, blank=True)
    gateway_response = models.CharField(max_length=500, blank=True)

    # Paystack identifiers
    paystack_transaction_id = models.BigIntegerField(
        null=True, blank=True, unique=True,
        help_text='Paystack numeric transaction ID',
    )
    access_code = models.CharField(max_length=100, blank=True)
    authorization_url = models.URLField(max_length=500, blank=True)

    # Authorization (for recurring charges)
    authorization_code = models.CharField(max_length=200, blank=True)
    card_type = models.CharField(max_length=50, blank=True)
    last4 = models.CharField(max_length=4, blank=True)
    exp_month = models.CharField(max_length=2, blank=True)
    exp_year = models.CharField(max_length=4, blank=True)
    bank = models.CharField(max_length=100, blank=True)

    # Customer
    paystack_customer_code = models.CharField(max_length=100, blank=True)

    # Split
    split = models.ForeignKey(
        TransactionSplit, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',
    )
    subaccount = models.ForeignKey(
        PaystackSubaccount, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',
    )

    # IP & metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    paystack_response = models.JSONField(
        default=dict, blank=True,
        help_text='Full Paystack API response',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Failure
    failure_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f'TXN {self.reference} – R{self.amount} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.reference:
            today = datetime.date.today()
            prefix = f"TXN-{today.strftime('%Y%m%d')}-"
            last = Transaction.objects.filter(
                reference__startswith=prefix,
            ).order_by('reference').last()
            if last:
                num = int(last.reference.split('-')[-1]) + 1
            else:
                num = 1
            self.reference = f'{prefix}{num:06d}'
        super().save(*args, **kwargs)

    @property
    def is_successful(self):
        return self.status == 'success'

    @property
    def is_refundable(self):
        return self.status == 'success'

    @property
    def net_amount(self):
        """Amount after Paystack fees."""
        if self.amount is None or self.paystack_fees is None:
            return None
        return self.amount - Decimal(str(self.paystack_fees))

    @property
    def amount_in_kobo(self):
        """Amount in kobo/cents for Paystack API calls."""
        if self.amount is None:
            return None
        return int(self.amount * 100)


# ═══════════════════════════════════════════════════════════════
# Refund
# ═══════════════════════════════════════════════════════════════

class Refund(models.Model):
    """Paystack refund – linked to a transaction."""

    REFUND_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    ]

    REFUND_REASON_CHOICES = [
        ('customer_request', 'Customer Request'),
        ('damaged_product', 'Damaged Product'),
        ('wrong_product', 'Wrong Product'),
        ('not_as_described', 'Not as Described'),
        ('duplicate_payment', 'Duplicate Payment'),
        ('fraud', 'Fraud'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Paystack identifiers
    paystack_refund_id = models.BigIntegerField(null=True, blank=True, unique=True)

    # Related
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name='refunds',
    )
    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='refunds',
        null=True, blank=True,
    )
    # Restaurant checkouts live in their own table. Without this the refund
    # could not name the order it belonged to, and the vendor saw a refund
    # against nothing.
    restaurant_order = models.ForeignKey(
        'restaurant.RestaurantOrder', on_delete=models.CASCADE,
        related_name='refunds', null=True, blank=True,
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.SET_NULL,
        related_name='refunds', null=True, blank=True,
        help_text='Store the refunded order was placed with',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refunds')

    # Refund details
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Refund amount in rands',
    )
    currency = models.CharField(max_length=3, default='ZAR')
    reason = models.CharField(max_length=20, choices=REFUND_REASON_CHOICES, default='customer_request')
    customer_note = models.TextField(blank=True)
    merchant_note = models.TextField(blank=True)

    # Status
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')

    # Admin approval
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_refunds',
        limit_choices_to={'user_type': 'admin'},
    )
    admin_notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    # Paystack response
    paystack_response = models.JSONField(default=dict, blank=True)

    # Failure
    failure_reason = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund R{self.amount} on {self.transaction.reference} ({self.status})'

    @property
    def is_successful(self):
        return self.status == 'processed'

    @property
    def amount_in_kobo(self):
        return int(self.amount * 100)


# ═══════════════════════════════════════════════════════════════
# Dispute
# ═══════════════════════════════════════════════════════════════

class Dispute(models.Model):
    """
    Paystack dispute / chargeback.
    Created via webhook when a customer disputes a charge.
    """

    DISPUTE_STATUS_CHOICES = [
        ('awaiting-merchant-feedback', 'Awaiting Merchant Feedback'),
        ('awaiting-bank-feedback', 'Awaiting Bank Feedback'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('merchant-accepted', 'Merchant Accepted'),
        ('declined', 'Declined'),
    ]

    RESOLUTION_CHOICES = [
        ('merchant-accepted', 'Merchant Accepted'),
        ('declined', 'Declined'),
    ]

    CATEGORY_CHOICES = [
        ('product-not-delivered', 'Product Not Delivered'),
        ('product-not-as-described', 'Product Not As Described'),
        ('unauthorized-transaction', 'Unauthorized Transaction'),
        ('duplicate-charge', 'Duplicate Charge'),
        ('general', 'General'),
    ]

    # Where the dispute came from. Paystack chargebacks arrive over the
    # webhook; everything a customer raises in-app is 'customer' and is
    # settled by us, never by Paystack.
    SOURCE_CUSTOMER = 'customer'
    SOURCE_PAYSTACK = 'paystack'
    SOURCE_CHOICES = [
        (SOURCE_CUSTOMER, 'Raised by customer'),
        (SOURCE_PAYSTACK, 'Paystack chargeback'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Paystack identifiers
    paystack_dispute_id = models.BigIntegerField(null=True, blank=True, unique=True)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default=SOURCE_PAYSTACK,
    )

    # Related
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name='disputes',
    )
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, related_name='disputes',
        null=True, blank=True,
    )
    restaurant_order = models.ForeignKey(
        'restaurant.RestaurantOrder', on_delete=models.SET_NULL,
        related_name='disputes', null=True, blank=True,
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.SET_NULL,
        related_name='disputes', null=True, blank=True,
        help_text='Store the disputed order was placed with',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='disputes',
        help_text='Customer who raised the dispute',
    )

    # Dispute details
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Disputed amount in rands',
    )
    currency = models.CharField(max_length=3, default='ZAR')
    status = models.CharField(max_length=30, choices=DISPUTE_STATUS_CHOICES, default='pending')
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default='general',
    )
    resolution = models.CharField(
        max_length=20, choices=RESOLUTION_CHOICES, blank=True,
    )
    message = models.TextField(blank=True, help_text='Dispute message from customer')
    merchant_response = models.TextField(blank=True)
    vendor_responded_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_disputes',
    )
    resolution_note = models.TextField(
        blank=True, help_text='What the admin decided and why',
    )

    # Evidence
    evidence = models.JSONField(default=dict, blank=True)
    attachments = models.JSONField(default=list, blank=True)

    # Paystack data
    paystack_response = models.JSONField(default=dict, blank=True)

    # Dates
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dispute'
        verbose_name_plural = 'Disputes'
        ordering = ['-created_at']

    def __str__(self):
        return f'Dispute #{self.paystack_dispute_id} – R{self.amount} ({self.status})'


# ═══════════════════════════════════════════════════════════════
# Payment Log & Webhook
# ═══════════════════════════════════════════════════════════════

class PaymentLog(models.Model):
    """Audit trail for all payment-related activities."""

    LOG_TYPE_CHOICES = [
        ('transaction_initialized', 'Transaction Initialized'),
        ('transaction_verified', 'Transaction Verified'),
        ('transaction_success', 'Transaction Success'),
        ('transaction_failed', 'Transaction Failed'),
        ('charge_authorization', 'Charge Authorization'),
        ('refund_requested', 'Refund Requested'),
        ('refund_processed', 'Refund Processed'),
        ('refund_failed', 'Refund Failed'),
        ('dispute_created', 'Dispute Created'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('subaccount_created', 'Subaccount Created'),
        ('split_created', 'Split Created'),
        ('subscription_created', 'Subscription Created'),
        ('webhook_received', 'Webhook Received'),
        ('api_call', 'API Call'),
        ('error', 'Error'),
    ]

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name='logs',
        null=True, blank=True,
    )
    refund = models.ForeignKey(
        Refund, on_delete=models.CASCADE, related_name='logs',
        null=True, blank=True,
    )
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name='logs',
        null=True, blank=True,
    )

    log_type = models.CharField(max_length=30, choices=LOG_TYPE_CHOICES)
    message = models.TextField()

    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)

    http_status_code = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Payment Log'
        verbose_name_plural = 'Payment Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.log_type} – {self.created_at}'


class PaystackWebhookEvent(models.Model):
    """
    Stores every Paystack webhook event for idempotency & debugging.
    """

    WEBHOOK_STATUS_CHOICES = [
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('ignored', 'Ignored'),
    ]

    event_type = models.CharField(max_length=100, help_text='e.g. charge.success')
    event_id = models.CharField(
        max_length=200, unique=True,
        help_text='Unique event identifier for idempotency',
    )

    raw_data = models.JSONField(default=dict)
    processed_data = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=WEBHOOK_STATUS_CHOICES, default='received')
    processing_error = models.TextField(blank=True)

    # Linked records (populated after processing)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='webhook_events',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Paystack Webhook Event'
        verbose_name_plural = 'Paystack Webhook Events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} – {self.status}'


# ─────────────────────────────────────────────────────────────────────────────
# Marketplace wallet / payout system
# ─────────────────────────────────────────────────────────────────────────────
# Imported here so Django's app loader picks up the models for the
# migrations machinery and admin discovery. The implementation lives in
# `wallet_models.py` to keep this file focused on the legacy Paystack
# split flow.
from .wallet_models import (  # noqa: E402,F401
    PaystackRecipient,
    Wallet,
    WalletTransaction,
    Payout,
)

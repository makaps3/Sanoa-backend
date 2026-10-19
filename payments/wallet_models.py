"""Internal wallet ledger + Paystack transfer recipients + scheduled payouts.

Replaces the on-Paystack `PaystackSubaccount` split flow with an internal
ledger. The customer always pays the platform Paystack account; the order
settlement engine credits vendor / driver / platform-revenue wallets, and a
scheduled job batches each wallet into a single Paystack transfer using the
stored Transfer-Recipient code (RCP_xxx).

See: docs/payments — "Marketplace Payment Collection" and "Bank Account
Verification and Paystack Recipient Management".
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Transfer Recipient
# ─────────────────────────────────────────────────────────────────────────────

class PaystackRecipient(models.Model):
    """Verified Paystack transfer-recipient for a vendor or driver.

    Created once during bank verification and reused for every future
    payout. When bank details change, the old recipient is archived and
    a fresh one is created so we never silently send money to an old
    account.
    """

    OWNER_VENDOR = 'vendor'
    OWNER_DRIVER = 'driver'
    OWNER_CHOICES = [
        (OWNER_VENDOR, 'Vendor'),
        (OWNER_DRIVER, 'Driver'),
    ]

    VERIFICATION_PENDING        = 'pending'
    VERIFICATION_VERIFIED       = 'verified'
    VERIFICATION_MANUAL_REVIEW  = 'manual_review'
    VERIFICATION_FAILED         = 'failed'
    VERIFICATION_CHOICES = [
        (VERIFICATION_PENDING,       'Pending'),
        (VERIFICATION_VERIFIED,      'Verified'),
        (VERIFICATION_MANUAL_REVIEW, 'Manual review'),
        (VERIFICATION_FAILED,        'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner_type = models.CharField(max_length=10, choices=OWNER_CHOICES)
    # Vendor recipients link to a VendorProfile; driver recipients link to
    # a DriverProfile. Stored as a UUID/int via `owner_id` (any FK
    # converted to str) so this table doesn't need polymorphic FKs.
    owner_id = models.CharField(max_length=64, db_index=True)

    # Submitted account details (what the user typed).
    business_name        = models.CharField(max_length=255)
    bank_code            = models.CharField(max_length=20)
    bank_name            = models.CharField(max_length=120, blank=True)
    account_number       = models.CharField(max_length=32)
    submitted_account_name = models.CharField(max_length=200, blank=True)

    # Resolved by Paystack `/bank/resolve` — what Paystack says the
    # account is registered under. Authoritative for the name check.
    resolved_account_name = models.CharField(max_length=200, blank=True)

    # Paystack identifiers, populated once `/transferrecipient` returns.
    recipient_code = models.CharField(max_length=100, blank=True, db_index=True)
    paystack_recipient_id = models.PositiveBigIntegerField(null=True, blank=True)

    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES,
        default=VERIFICATION_PENDING,
    )
    bank_verified  = models.BooleanField(default=False)
    payout_enabled = models.BooleanField(default=False)

    # When bank details change we never edit the row — we mark the
    # previous recipient archived and create a new one. Keeps an audit
    # trail and avoids accidental transfers to the wrong account.
    archived_at = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True)

    paystack_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paystack Recipient'
        verbose_name_plural = 'Paystack Recipients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner_type', 'owner_id', 'archived_at']),
        ]
        constraints = [
            # At most one active recipient per owner.
            models.UniqueConstraint(
                fields=['owner_type', 'owner_id'],
                condition=models.Q(archived_at__isnull=True),
                name='unique_active_recipient_per_owner',
            ),
        ]

    def __str__(self):
        return f"{self.owner_type}:{self.owner_id} → {self.recipient_code or 'unverified'}"

    def archive(self, *, reason=''):
        self.archived_at = timezone.now()
        self.payout_enabled = False
        if reason:
            self.notes = (self.notes + f"\n[archived] {reason}").strip()
        self.save(update_fields=[
            'archived_at', 'payout_enabled', 'notes', 'updated_at',
        ])


# ─────────────────────────────────────────────────────────────────────────────
# Wallet + ledger
# ─────────────────────────────────────────────────────────────────────────────

class Wallet(models.Model):
    """Internal balance for a vendor, driver, or the platform revenue ledger.

    Money moves through `WalletTransaction` records only — never set
    `balance` directly. Use `credit()` / `debit()` so the ledger row
    and the running balance are always written in the same atomic
    transaction.
    """

    OWNER_VENDOR   = 'vendor'
    OWNER_DRIVER   = 'driver'
    OWNER_PLATFORM = 'platform'  # singleton revenue ledger
    OWNER_CHOICES = [
        (OWNER_VENDOR,   'Vendor'),
        (OWNER_DRIVER,   'Driver'),
        (OWNER_PLATFORM, 'Platform Revenue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_type = models.CharField(max_length=10, choices=OWNER_CHOICES)
    owner_id   = models.CharField(max_length=64, db_index=True, blank=True)

    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    is_frozen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        constraints = [
            models.UniqueConstraint(
                fields=['owner_type', 'owner_id'],
                name='unique_wallet_per_owner',
            ),
        ]

    def __str__(self):
        return f"{self.owner_type}:{self.owner_id or 'platform'} = R{self.balance}"

    # ── Money movements ────────────────────────────────────────────────
    #
    # Credit/debit always create a WalletTransaction in the same DB
    # transaction so the ledger is the source of truth. Use these from
    # the settlement engine and the payout job — never write to
    # `balance` from view code.

    def credit(self, amount, *, transaction_type, reference='',
               order=None, restaurant_order=None, description=''):
        from django.db import transaction
        amount = _money(amount)
        if amount <= 0:
            return None
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            wallet.balance = wallet.balance + amount
            wallet.save(update_fields=['balance', 'updated_at'])
            self.balance = wallet.balance
            return WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=transaction_type,
                credit=amount,
                debit=Decimal('0.00'),
                reference=reference,
                order=order,
                restaurant_order=restaurant_order,
                description=description,
                status=WalletTransaction.STATUS_SUCCESS,
            )

    def debit(self, amount, *, transaction_type, reference='', payout=None,
              order=None, restaurant_order=None,
              description='', allow_overdraft=None):
        """Subtract `amount` from the wallet and write a debit row.

        `allow_overdraft` defaults to True for the platform revenue
        ledger (it's a running revenue account that legitimately goes
        negative when Paystack fees outstrip a small order's
        contribution) and False everywhere else — vendor / driver
        wallets must never overdraft.
        """
        from django.db import transaction
        amount = _money(amount)
        if amount <= 0:
            return None
        if allow_overdraft is None:
            allow_overdraft = (self.owner_type == self.OWNER_PLATFORM)
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            if wallet.balance < amount and not allow_overdraft:
                raise ValueError(
                    f'Insufficient wallet balance: R{wallet.balance} < R{amount}'
                )
            wallet.balance = wallet.balance - amount
            wallet.save(update_fields=['balance', 'updated_at'])
            self.balance = wallet.balance
            return WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=transaction_type,
                credit=Decimal('0.00'),
                debit=amount,
                reference=reference,
                payout=payout,
                order=order,
                restaurant_order=restaurant_order,
                description=description,
                status=WalletTransaction.STATUS_SUCCESS,
            )

    # ── Resolvers ──────────────────────────────────────────────────────

    @classmethod
    def for_vendor(cls, vendor):
        wallet, _ = cls.objects.get_or_create(
            owner_type=cls.OWNER_VENDOR,
            owner_id=str(vendor.id),
        )
        return wallet

    @classmethod
    def for_driver(cls, driver):
        wallet, _ = cls.objects.get_or_create(
            owner_type=cls.OWNER_DRIVER,
            owner_id=str(driver.id),
        )
        return wallet

    @classmethod
    def platform_ledger(cls):
        wallet, _ = cls.objects.get_or_create(
            owner_type=cls.OWNER_PLATFORM, owner_id='',
        )
        return wallet


def _money(value):
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal('0.01'))


class WalletTransaction(models.Model):
    """Single credit-or-debit line on a wallet's ledger."""

    TYPE_ORDER_SETTLEMENT = 'order_settlement'
    TYPE_DRIVER_EARNING   = 'driver_earning'
    TYPE_PLATFORM_REVENUE = 'platform_revenue'
    TYPE_DELIVERY_ESCROW  = 'delivery_escrow'
    TYPE_PAYSTACK_FEE     = 'paystack_fee'
    TYPE_PAYOUT           = 'payout'
    TYPE_REVERSAL         = 'reversal'
    TYPE_ADJUSTMENT       = 'adjustment'
    TYPE_CHOICES = [
        (TYPE_ORDER_SETTLEMENT, 'Order Settlement'),
        (TYPE_DRIVER_EARNING,   'Driver Earning'),
        (TYPE_PLATFORM_REVENUE, 'Platform Revenue'),
        (TYPE_DELIVERY_ESCROW,  'Delivery Fee Escrow'),
        (TYPE_PAYSTACK_FEE,     'Paystack Gateway Fee'),
        (TYPE_PAYOUT,           'Payout'),
        (TYPE_REVERSAL,         'Reversal'),
        (TYPE_ADJUSTMENT,       'Manual Adjustment'),
    ]

    STATUS_SUCCESS = 'success'
    STATUS_PENDING = 'pending'
    STATUS_FAILED  = 'failed'
    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_FAILED,  'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name='transactions',
    )
    transaction_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    debit  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Linkbacks — at most one populated. References tie the row to its
    # originating order or payout for the audit trail.
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wallet_transactions',
    )
    restaurant_order = models.ForeignKey(
        'restaurant.RestaurantOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='wallet_transactions',
    )
    payout = models.ForeignKey(
        'payments.Payout', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
    )

    reference   = models.CharField(max_length=120, blank=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    status      = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_SUCCESS)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['transaction_type', '-created_at']),
        ]

    def __str__(self):
        sign = f"+R{self.credit}" if self.credit else f"−R{self.debit}"
        return f"{self.transaction_type} {sign} ({self.reference})"


# ─────────────────────────────────────────────────────────────────────────────
# Payout (Paystack transfer execution)
# ─────────────────────────────────────────────────────────────────────────────

class Payout(models.Model):
    """A single Paystack transfer batched out of a wallet."""

    OWNER_VENDOR = 'vendor'
    OWNER_DRIVER = 'driver'
    OWNER_CHOICES = [
        (OWNER_VENDOR, 'Vendor'),
        (OWNER_DRIVER, 'Driver'),
    ]

    STATUS_PENDING    = 'pending'      # local row created, transfer not yet initiated
    STATUS_PROCESSING = 'processing'   # transfer initiated on Paystack
    STATUS_SUCCESS    = 'success'
    STATUS_FAILED     = 'failed'
    STATUS_REVERSED   = 'reversed'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SUCCESS,    'Success'),
        (STATUS_FAILED,     'Failed'),
        (STATUS_REVERSED,   'Reversed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_type = models.CharField(max_length=10, choices=OWNER_CHOICES)
    owner_id   = models.CharField(max_length=64, db_index=True)

    recipient = models.ForeignKey(
        PaystackRecipient, on_delete=models.PROTECT, related_name='payouts',
    )

    amount    = models.DecimalField(max_digits=14, decimal_places=2)
    currency  = models.CharField(max_length=3, default='ZAR')
    reason    = models.CharField(max_length=255, blank=True)

    # Paystack identifiers populated once the transfer is initiated.
    reference     = models.CharField(max_length=120, unique=True)
    transfer_code = models.CharField(max_length=100, blank=True, db_index=True)
    paystack_transfer_id = models.PositiveBigIntegerField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    failure_reason = models.TextField(blank=True)
    paystack_response = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Payout'
        verbose_name_plural = 'Payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner_type', 'owner_id', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Payout {self.reference} ({self.status}) R{self.amount}"

    def mark_success(self, *, transfer_code='', transfer_id=None, response=None):
        self.status = self.STATUS_SUCCESS
        if transfer_code:
            self.transfer_code = transfer_code
        if transfer_id is not None:
            self.paystack_transfer_id = transfer_id
        if response is not None:
            self.paystack_response = response
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'status', 'transfer_code', 'paystack_transfer_id',
            'paystack_response', 'completed_at', 'updated_at',
        ])

    def mark_failed(self, reason, *, response=None):
        self.status = self.STATUS_FAILED
        self.failure_reason = reason
        if response is not None:
            self.paystack_response = response
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'status', 'failure_reason', 'paystack_response',
            'completed_at', 'updated_at',
        ])

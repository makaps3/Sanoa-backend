"""
Models for the Credit System (Buy Now, Pay Later).

Eligibility requirements:
- Must be an active Sanoa platform subscriber
- Must follow the vendor they are buying from
- Must have at least 3 completed orders with the vendor
- Must pay a minimum 10% deposit upfront

Enforcement:
- When a purchase is overdue (past due_date + grace_period_days),
  the user's account is suspended and they are blocked from the platform.
- Suspended users can ONLY make payments / repayments.
- Once all overdue balances are settled, the suspension is lifted automatically.
"""
import uuid
from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class CreditAccount(models.Model):
    """
    A customer's credit account on the Sanoa platform.
    Credit limit is derived from the customer's subscription plan.
    Tracks outstanding balance and suspension state.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    ]

    MIN_DEPOSIT_PERCENT = Decimal('10.00')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='debit_account')
    subscription = models.OneToOneField(
        'subscriptions.Subscription', on_delete=models.PROTECT,
        related_name='debit_account', null=True, blank=True,
        help_text='The subscription that determines credit limit',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    credit_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Credit limit from subscription plan',
    )
    current_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Total outstanding amount owed',
    )
    total_penalties = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Total penalty fees accrued from late payments',
    )

    # Suspension tracking
    suspended_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the credit account was suspended due to overdue payment',
    )
    last_penalty_date = models.DateField(
        null=True, blank=True,
        help_text='Last date a late penalty was applied (prevents double-charging)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Credit Account'
        verbose_name_plural = 'Credit Accounts'

    def __str__(self):
        return f'{self.user.email} – Balance: R{self.current_balance} ({self.status})'

    @property
    def available_credit(self):
        if self.subscription is None or not self.subscription.is_active:
            return Decimal('0.00')
        return max(self.credit_limit - self.current_balance, Decimal('0.00'))

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def total_owed(self):
        """Total balance including penalties."""
        return self.current_balance + self.total_penalties

    @property
    def has_overdue_purchases(self):
        """Check if this account has any overdue purchases past the grace period."""
        return self.purchases.filter(
            status='active',
            is_grace_expired=True,
        ).exists()

    def suspend(self, reason='Overdue credit payment'):
        """Suspend this credit account and the user."""
        self.status = 'suspended'
        self.suspended_at = timezone.now()
        self.save(update_fields=['status', 'suspended_at', 'updated_at'])

        self.user.is_suspended = True
        self.user.suspended_at = timezone.now()
        self.user.suspension_reason = reason
        self.user.save(update_fields=['is_suspended', 'suspended_at', 'suspension_reason'])

    def unsuspend(self):
        """Lift suspension if no more overdue purchases."""
        if self.has_overdue_purchases:
            return False

        self.status = 'active'
        self.suspended_at = None
        self.save(update_fields=['status', 'suspended_at', 'updated_at'])

        self.user.is_suspended = False
        self.user.suspended_at = None
        self.user.suspension_reason = ''
        self.user.save(update_fields=['is_suspended', 'suspended_at', 'suspension_reason'])
        return True


class CreditPurchase(models.Model):
    """
    A purchase made using the credit (buy now pay later) facility.
    The buyer must pay a minimum 10% deposit upfront; the rest is owed.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending Deposit'),
        ('active', 'Active – Repaying'),
        ('paid', 'Fully Paid'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credit_account = models.ForeignKey(
        CreditAccount, on_delete=models.CASCADE, related_name='purchases',
    )
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='debit_purchase',
        null=True, blank=True,
        help_text='The order this credit purchase is linked to',
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='debit_sales',
    )

    # Amounts
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Total purchase amount',
    )
    deposit_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Upfront deposit paid (minimum 10% of total)',
    )
    remaining_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Amount still owed after deposit',
    )
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Total repayments made so far (excluding deposit)',
    )
    penalty_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Late payment penalty accrued on this purchase',
    )
    penalty_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Penalty amount already paid',
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    # Dates
    due_date = models.DateField(
        help_text='Final date by which the remaining balance must be paid',
    )
    grace_end_date = models.DateField(
        null=True, blank=True,
        help_text='Date after which late penalties apply and user gets suspended',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    defaulted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Credit Purchase'
        verbose_name_plural = 'Credit Purchases'
        ordering = ['-created_at']

    def __str__(self):
        return f'Credit {self.id} – R{self.total_amount} ({self.status})'

    @property
    def outstanding_balance(self):
        """Principal amount still owed."""
        return max(self.remaining_amount - self.amount_paid, Decimal('0.00'))

    @property
    def outstanding_penalty(self):
        """Penalty amount still owed."""
        return max(self.penalty_amount - self.penalty_paid, Decimal('0.00'))

    @property
    def total_outstanding(self):
        """Total owed including penalties."""
        return self.outstanding_balance + self.outstanding_penalty

    @property
    def is_fully_paid(self):
        return self.outstanding_balance <= 0 and self.outstanding_penalty <= 0

    @property
    def is_overdue(self):
        """Past due date but not yet past grace period."""
        if self.status not in ('active', 'defaulted'):
            return False
        return self.due_date < timezone.now().date() and not self.is_fully_paid

    @property
    def is_grace_expired(self):
        """Past grace period — user should be suspended."""
        if self.status not in ('active', 'defaulted'):
            return False
        if not self.grace_end_date:
            return False
        return self.grace_end_date < timezone.now().date() and not self.is_fully_paid

    @property
    def days_overdue(self):
        """Number of days past due date."""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def deposit_percentage(self):
        if self.total_amount > 0:
            return (self.deposit_amount / self.total_amount) * 100
        return Decimal('0.00')


class CreditRepayment(models.Model):
    """Individual repayment towards a credit purchase."""

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Card Payment'),
        ('eft', 'EFT / Bank Transfer'),
        ('wallet', 'Sanoa Wallet'),
        ('cash', 'Cash'),
        ('paystack', 'Paystack'),
    ]

    REPAYMENT_TYPE_CHOICES = [
        ('principal', 'Principal Repayment'),
        ('penalty', 'Penalty Payment'),
        ('mixed', 'Principal + Penalty'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        CreditPurchase, on_delete=models.CASCADE, related_name='repayments',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    principal_portion = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Portion of payment applied to principal balance',
    )
    penalty_portion = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Portion of payment applied to penalty fees',
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD_CHOICES, default='card',
    )
    repayment_type = models.CharField(
        max_length=10, choices=REPAYMENT_TYPE_CHOICES, default='principal',
    )
    reference = models.CharField(
        max_length=200, blank=True, help_text='Payment reference / Paystack transaction ref',
    )
    paystack_transaction_id = models.CharField(
        max_length=200, blank=True,
        help_text='Linked Paystack transaction UUID if paid via Paystack',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Credit Repayment'
        verbose_name_plural = 'Credit Repayments'
        ordering = ['-created_at']

    def __str__(self):
        return f'Repayment R{self.amount} on {self.purchase_id}'

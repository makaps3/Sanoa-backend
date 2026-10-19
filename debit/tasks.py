"""
Celery tasks for the Credit System.

Run `check_overdue_credit_purchases` periodically (e.g. daily via Celery Beat)
to enforce payment deadlines, apply late penalties, and suspend defaulting users.
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('sanoa.debit')


@shared_task
def check_overdue_credit_purchases():
    """
    Daily task to:
    1. Apply late payment penalties to purchases past their grace period.
    2. Mark purchases as defaulted.
    3. Suspend users who have overdue balances past the grace period.
    4. Auto-unsuspend users who have cleared all overdue balances.

    Schedule this via Celery Beat to run once daily.
    """
    from .models import CreditAccount, CreditPurchase

    today = timezone.now().date()
    processed = {'penalties_applied': 0, 'defaulted': 0, 'suspended': 0, 'unsuspended': 0}

    # ── Step 1: Find purchases past grace period that are still active ──
    overdue_purchases = CreditPurchase.objects.filter(
        status='active',
        grace_end_date__lt=today,
    ).select_related('credit_account', 'credit_account__user', 'credit_account__subscription__plan')

    for purchase in overdue_purchases:
        if purchase.is_fully_paid:
            continue

        account = purchase.credit_account
        plan = account.subscription.plan if account.subscription else None
        penalty_rate = plan.late_payment_penalty_percent if plan else Decimal('2.00')

        # Apply penalty once per day (check last_penalty_date on account)
        if account.last_penalty_date != today:
            penalty = purchase.outstanding_balance * (penalty_rate / Decimal('100'))
            if penalty > 0:
                purchase.penalty_amount += penalty
                purchase.save(update_fields=['penalty_amount', 'updated_at'])

                account.total_penalties += penalty
                account.last_penalty_date = today
                account.save(update_fields=['total_penalties', 'last_penalty_date', 'updated_at'])

                processed['penalties_applied'] += 1
                logger.info(
                    'Late penalty R%.2f applied to purchase %s (user: %s)',
                    penalty, purchase.id, account.user.email,
                )

        # Mark as defaulted if not already
        if purchase.status != 'defaulted':
            purchase.status = 'defaulted'
            purchase.defaulted_at = timezone.now()
            purchase.save(update_fields=['status', 'defaulted_at', 'updated_at'])
            processed['defaulted'] += 1

        # Suspend the user and credit account
        if not account.user.is_suspended:
            account.suspend(
                reason=(
                    f'Overdue credit payment of R{purchase.total_outstanding:.2f} '
                    f'on purchase {purchase.id}. Due date was {purchase.due_date}.'
                )
            )
            processed['suspended'] += 1
            logger.warning(
                'User %s SUSPENDED for overdue credit payment (purchase %s, '
                'outstanding: R%.2f)',
                account.user.email, purchase.id, purchase.total_outstanding,
            )

    # ── Step 2: Check if any suspended users have cleared their balances ──
    suspended_accounts = CreditAccount.objects.filter(
        status='suspended',
    ).select_related('user')

    for account in suspended_accounts:
        has_overdue = False
        for p in account.purchases.filter(status__in=('active', 'defaulted')):
            if p.is_grace_expired and not p.is_fully_paid:
                has_overdue = True
                break

        if not has_overdue:
            account.unsuspend()
            processed['unsuspended'] += 1
            logger.info(
                'User %s UNSUSPENDED – all overdue balances cleared.',
                account.user.email,
            )

    logger.info(
        'Credit check complete: %d penalties, %d defaulted, %d suspended, %d unsuspended',
        processed['penalties_applied'], processed['defaulted'],
        processed['suspended'], processed['unsuspended'],
    )

    return processed


@shared_task
def send_overdue_reminder_email(purchase_id):
    """Send a reminder email for an overdue credit purchase."""
    from .models import CreditPurchase
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        purchase = CreditPurchase.objects.select_related(
            'credit_account__user',
        ).get(id=purchase_id)
    except CreditPurchase.DoesNotExist:
        return

    user = purchase.credit_account.user
    send_mail(
        subject=f'Overdue Credit Payment – R{purchase.total_outstanding:.2f}',
        message=(
            f'Dear {user.first_name or user.email},\n\n'
            f'Your credit purchase of R{purchase.total_amount} is overdue.\n\n'
            f'Outstanding balance: R{purchase.outstanding_balance:.2f}\n'
            f'Penalty fees: R{purchase.outstanding_penalty:.2f}\n'
            f'Total owed: R{purchase.total_outstanding:.2f}\n'
            f'Due date: {purchase.due_date}\n'
            f'Grace period ends: {purchase.grace_end_date}\n\n'
            f'Please make a payment as soon as possible to avoid '
            f'account suspension and additional penalty fees.\n\n'
            f'If your grace period has passed, your account will be suspended '
            f'until all outstanding balances are settled.\n\n'
            f'Regards,\nSanoa Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    logger.info('Overdue reminder sent to %s for purchase %s', user.email, purchase.id)


@shared_task
def send_suspension_notification_email(user_id):
    """Notify a user that their account has been suspended."""
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    send_mail(
        subject='Account Suspended – Overdue Credit Payment',
        message=(
            f'Dear {user.first_name or user.email},\n\n'
            f'Your Sanoa account has been suspended due to an overdue credit payment.\n\n'
            f'Reason: {user.suspension_reason}\n\n'
            f'You can still log in and make payments to settle your outstanding balance.\n'
            f'Once all overdue balances are cleared, your account will be '
            f'automatically reactivated and you will regain full platform access.\n\n'
            f'Regards,\nSanoa Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    logger.info('Suspension notification sent to %s', user.email)

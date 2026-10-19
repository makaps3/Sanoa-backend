"""
Celery tasks for the Paystack-integrated payments app.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('sanoa.payments')


# Failed-payout retention. Anything past this window is auto-deleted
# by the scheduled `prune_failed_payouts` task. Admins can still
# manually delete failed rows sooner from the admin screen.
FAILED_PAYOUT_TTL_HOURS = 48


@shared_task(name='payments.prune_failed_payouts')
def prune_failed_payouts():
    """Auto-delete failed payouts older than 48 hours.

    A failed Paystack transfer is just an audit breadcrumb — the
    money never left the platform Paystack account and the wallet
    has already been refunded via a reversal row. After 48 hours we
    delete the failed Payout so the admin queue stays clean. The
    refund + original debit rows on the wallet ledger stay (the
    payout FK is set to NULL) so the audit trail for the wallet is
    preserved.

    Idempotent — safe to run as often as you like.
    """
    from .wallet_models import Payout, WalletTransaction

    cutoff = timezone.now() - timedelta(hours=FAILED_PAYOUT_TTL_HOURS)
    stale = Payout.objects.filter(
        status=Payout.STATUS_FAILED,
        updated_at__lt=cutoff,
    )
    count = stale.count()
    if count == 0:
        return {'deleted': 0}
    # Detach ledger rows so the FK doesn't cascade-delete the audit
    # trail — the wallet history must outlive the payout row.
    WalletTransaction.objects.filter(payout__in=stale).update(payout=None)
    stale.delete()
    logger.info(
        'prune_failed_payouts: removed %s failed payout(s) older than %sh',
        count, FAILED_PAYOUT_TTL_HOURS,
    )
    return {'deleted': count}


@shared_task
def send_payment_confirmation_email(transaction_id):
    """Send payment confirmation email after successful Paystack transaction."""
    from .models import Transaction
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        txn = Transaction.objects.select_related('user', 'order').get(id=transaction_id)
        send_mail(
            subject=f'Payment Received - {txn.reference}',
            message=(
                f'Your payment of R{txn.amount} {txn.currency} '
                f'has been processed successfully.\n\n'
                f'Reference: {txn.reference}\n'
                f'Channel: {txn.get_channel_display() if txn.channel else "N/A"}\n'
                f'Date: {txn.paid_at or txn.created_at}\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[txn.user.email],
            fail_silently=False,
        )
        logger.info('Payment confirmation sent for %s', txn.reference)
    except Transaction.DoesNotExist:
        logger.error('Transaction %s not found for confirmation email', transaction_id)


@shared_task
def send_refund_notification_email(refund_id):
    """Send refund notification email after Paystack refund is processed."""
    from .models import Refund
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        refund = Refund.objects.select_related('user', 'transaction').get(id=refund_id)
        send_mail(
            subject=f'Refund Processed - {refund.transaction.reference}',
            message=(
                f'Your refund of R{refund.amount} {refund.currency} '
                f'for transaction {refund.transaction.reference} has been processed.\n\n'
                f'Reason: {refund.get_reason_display()}\n'
                f'Status: {refund.get_status_display()}\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[refund.user.email],
            fail_silently=False,
        )
        logger.info('Refund notification sent for transaction %s', refund.transaction.reference)
    except Refund.DoesNotExist:
        logger.error('Refund %s not found for notification email', refund_id)


@shared_task
def sync_paystack_transaction(reference):
    """Verify and sync a transaction from Paystack by reference."""
    from .models import Transaction, PaymentLog
    from .paystack import paystack_api

    result = paystack_api.verify_transaction(reference)
    if not result.get('status'):
        logger.error('Failed to verify transaction %s: %s', reference, result.get('message'))
        return

    ps_data = result['data']

    try:
        txn = Transaction.objects.get(reference=reference)
    except Transaction.DoesNotExist:
        logger.warning('Transaction %s not found locally for sync', reference)
        return

    if txn.payment_intent in ('subscription_payment', 'tier_payment'):
        from subscriptions.billing import apply_subscription_payment
        apply_subscription_payment(txn, ps_data)
    txn.status = ps_data.get('status', txn.status)
    txn.channel = ps_data.get('channel', '')
    txn.gateway_response = ps_data.get('gateway_response', '')
    txn.paystack_transaction_id = ps_data.get('id')
    txn.paystack_fees = ps_data.get('fees', 0) / 100
    txn.paystack_response = ps_data

    auth = ps_data.get('authorization', {})
    if auth:
        txn.authorization_code = auth.get('authorization_code', '')
        txn.card_type = auth.get('card_type', '')
        txn.last4 = auth.get('last4', '')
        txn.bank = auth.get('bank', '')

    if ps_data.get('paid_at'):
        from django.utils.dateparse import parse_datetime
        txn.paid_at = parse_datetime(ps_data['paid_at'])

    txn.save()

    PaymentLog.objects.create(
        transaction=txn,
        log_type='transaction_verified',
        message=f'Transaction synced via task: {reference} → {txn.status}',
        response_data=result,
    )

    logger.info('Transaction %s synced: %s', reference, txn.status)


@shared_task
def sync_plans_to_paystack():
    """Sync all active plans and tiers to Paystack."""
    from subscriptions.models import Plan
    from tiers.models import BusinessTier
    from .paystack import paystack_api

    # Sync customer plans
    for plan in Plan.objects.filter(is_active=True, paystack_plan_code=''):
        interval_map = {'monthly': 'monthly', 'yearly': 'annually'}
        interval = interval_map.get(plan.billing_cycle, 'monthly')

        result = paystack_api.create_plan(
            name=plan.name,
            interval=interval,
            amount=int(plan.price * 100),
            currency='ZAR',
            description=plan.description or plan.name,
        )

        if result.get('status'):
            ps_data = result['data']
            plan.paystack_plan_code = ps_data.get('plan_code', '')
            plan.paystack_plan_id = ps_data.get('id')
            plan.save(update_fields=['paystack_plan_code', 'paystack_plan_id', 'updated_at'])
            logger.info('Plan %s synced to Paystack: %s', plan.name, plan.paystack_plan_code)

    # Sync vendor tiers (paid only)
    for tier in BusinessTier.objects.filter(is_active=True, paystack_plan_code='').exclude(price=0):
        from subscriptions.billing import paystack_interval
        interval = paystack_interval(tier)

        result = paystack_api.create_plan(
            name=f'Vendor Tier: {tier.name}',
            interval=interval,
            amount=int(tier.price * 100),
            currency='ZAR',
            description=tier.description or tier.name,
        )

        if result.get('status'):
            ps_data = result['data']
            tier.paystack_plan_code = ps_data.get('plan_code', '')
            tier.paystack_plan_id = ps_data.get('id')
            tier.save(update_fields=['paystack_plan_code', 'paystack_plan_id', 'updated_at'])
            logger.info('Tier %s synced to Paystack: %s', tier.name, tier.paystack_plan_code)

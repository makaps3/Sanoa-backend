"""
Celery tasks for scheduled / time-based notifications:
  - Negotiation 24 hr expiry reminders
  - Subscription expiry warnings (3 days / 30 hr)
  - Vendor tier subscription expiry warnings (7 days)
  - Low credit balance alerts
  - Overdue credit payment reminders
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Notification
from .service import notify

logger = logging.getLogger('sanoa.notifications')


@shared_task(name='notifications.send_negotiation_reminders')
def send_negotiation_reminders():
    """
    Send a 24-hour reminder to buyer + vendor for every NegotiationRoom
    whose agreed offer expires within the next 24 hours.
    Runs every hour via Celery Beat.
    """
    from negotiations.models import NegotiationRoom

    now = timezone.now()
    window_start = now
    window_end = now + timedelta(hours=24)

    rooms = NegotiationRoom.objects.filter(
        status='agreed',
        offer_expires_at__gte=window_start,
        offer_expires_at__lte=window_end,
    ).select_related('buyer', 'vendor__user', 'product')

    sent = 0
    for room in rooms:
        # Avoid double-sending: check if we already sent a reminder today
        already_sent_buyer = Notification.objects.filter(
            recipient=room.buyer,
            notification_type=Notification.NEGOTIATION_REMINDER,
            data__room_id=str(room.id),
            created_at__date=now.date(),
        ).exists()

        product_name = room.product.name if room.product else 'Item'
        expires_in = room.offer_expires_at - now
        hours_left = int(expires_in.total_seconds() // 3600)

        if not already_sent_buyer:
            notify(
                room.buyer,
                Notification.NEGOTIATION_REMINDER,
                'Offer Expiring Soon!',
                f'Your agreed price for "{product_name}" expires in ~{hours_left} hours. '
                'Complete checkout now to secure the deal.',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id), 'hours_left': hours_left,
                      'product': product_name,
                      'agreed_price': str(room.agreed_price or '')},
            )
            sent += 1

        already_sent_vendor = Notification.objects.filter(
            recipient=room.vendor.user,
            notification_type=Notification.VENDOR_NEGOTIATION_REMINDER,
            data__room_id=str(room.id),
            created_at__date=now.date(),
        ).exists()

        if not already_sent_vendor:
            notify(
                room.vendor.user,
                Notification.VENDOR_NEGOTIATION_REMINDER,
                'Pending Offer Expiring Soon',
                f'Your agreed price for "{product_name}" expires in ~{hours_left} hours. '
                'The buyer has not checked out yet.',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id), 'hours_left': hours_left,
                      'product': product_name},
            )
            sent += 1

    logger.info('send_negotiation_reminders: sent %d reminders', sent)
    return sent


@shared_task(name='notifications.send_subscription_expiry_warnings')
def send_subscription_expiry_warnings():
    """
    Warn customers whose subscription renews/expires within 3 days.
    Runs daily via Celery Beat.
    """
    from subscriptions.models import Subscription

    now = timezone.now()
    warn_before = now + timedelta(days=3)

    subs = Subscription.objects.filter(
        status='active',
        current_period_end__gte=now,
        current_period_end__lte=warn_before,
    ).select_related('user', 'plan')

    sent = 0
    for sub in subs:
        already_sent = Notification.objects.filter(
            recipient=sub.user,
            notification_type=Notification.SUBSCRIPTION_EXPIRING,
            created_at__date=now.date(),
        ).exists()

        if not already_sent:
            days_left = (sub.current_period_end - now).days
            notify(
                sub.user,
                Notification.SUBSCRIPTION_EXPIRING,
                'Subscription Expiring Soon',
                f'Your {sub.plan.name} subscription expires in {days_left} day(s). '
                'Renew now to keep your credit access and benefits.',
                category=Notification.CAT_SUBSCRIPTION,
                data={'subscription_id': str(sub.id), 'plan': sub.plan.name,
                      'days_left': days_left,
                      'expires_at': sub.current_period_end.isoformat()},
            )
            sent += 1

    logger.info('send_subscription_expiry_warnings: sent %d warnings', sent)
    return sent


@shared_task(name='notifications.send_subscription_due_soon_alerts')
def send_subscription_due_soon_alerts():
    """
    Send an urgent warning to customers whose subscription expires within 30 hours.
    Runs every hour via Celery Beat.
    Uses warning_type='30hr' in data to dedup independently of the 3-day daily warning.
    """
    from subscriptions.models import Subscription

    now = timezone.now()
    window_end = now + timedelta(hours=30)

    subs = Subscription.objects.filter(
        status='active',
        current_period_end__gte=now,
        current_period_end__lte=window_end,
    ).select_related('user', 'plan')

    sent = 0
    for sub in subs:
        already_sent = Notification.objects.filter(
            recipient=sub.user,
            notification_type=Notification.SUBSCRIPTION_EXPIRING,
            data__warning_type='30hr',
            created_at__gte=now - timedelta(hours=25),
        ).exists()

        if already_sent:
            continue

        hours_left = int((sub.current_period_end - now).total_seconds() // 3600)
        notify(
            sub.user,
            Notification.SUBSCRIPTION_EXPIRING,
            'Subscription Expiring in Under 30 Hours!',
            f'Your {sub.plan.name} subscription expires in ~{hours_left} hour(s). '
            'Renew now to avoid losing access to your benefits.',
            category=Notification.CAT_SUBSCRIPTION,
            data={
                'warning_type': '30hr',
                'subscription_id': str(sub.id),
                'plan': sub.plan.name,
                'hours_left': hours_left,
                'expires_at': sub.current_period_end.isoformat(),
            },
        )
        sent += 1

    logger.info('send_subscription_due_soon_alerts: sent %d alerts', sent)
    return sent


@shared_task(name='notifications.send_low_credit_alerts')
def send_low_credit_alerts():
    """
    Alert customers whose available credit has dropped below 20% of their limit.
    Runs daily via Celery Beat.
    """
    from debit.models import CreditAccount
    from decimal import Decimal

    accounts = CreditAccount.objects.filter(
        status='active',
        credit_limit__gt=0,
    ).select_related('user')

    sent = 0
    now = timezone.now()
    threshold = Decimal('0.20')

    for account in accounts:
        if account.credit_limit == 0:
            continue
        ratio = account.available_credit / account.credit_limit
        if ratio > threshold:
            continue

        already_sent = Notification.objects.filter(
            recipient=account.user,
            notification_type=Notification.CREDIT_LOW_BALANCE,
            created_at__date=now.date(),
        ).exists()

        if not already_sent:
            pct = int(ratio * 100)
            notify(
                account.user,
                Notification.CREDIT_LOW_BALANCE,
                'Low Credit Balance',
                f'Only R{account.available_credit:.2f} ({pct}%) of your credit limit '
                'remains. Repay outstanding purchases to restore your limit.',
                category=Notification.CAT_CREDIT,
                data={'available_credit': str(account.available_credit),
                      'credit_limit': str(account.credit_limit),
                      'percent_remaining': pct},
            )
            sent += 1

    logger.info('send_low_credit_alerts: sent %d alerts', sent)
    return sent


@shared_task(name='notifications.send_overdue_credit_reminders')
def send_overdue_credit_reminders():
    """
    Remind customers of overdue credit purchases daily.
    Sends an escalated message after the grace period expires.
    Runs daily via Celery Beat.
    """
    from debit.models import CreditPurchase

    now = timezone.now()
    purchases = CreditPurchase.objects.filter(
        status__in=('active', 'defaulted'),
        due_date__lt=now.date(),
    ).select_related('credit_account__user')

    sent = 0
    for purchase in purchases:
        if purchase.is_fully_paid:
            continue

        user = purchase.credit_account.user
        already_sent = Notification.objects.filter(
            recipient=user,
            notification_type=Notification.CREDIT_OVERDUE,
            data__purchase_id=str(purchase.id),
            created_at__date=now.date(),
        ).exists()

        if already_sent:
            continue

        if purchase.is_grace_expired:
            body = (
                f'Your credit payment of R{purchase.total_outstanding:.2f} is severely overdue. '
                'Your account may be suspended. Please repay immediately.'
            )
        else:
            days = purchase.days_overdue
            body = (
                f'Your credit purchase of R{purchase.total_amount:.2f} is {days} day(s) overdue. '
                f'Outstanding: R{purchase.total_outstanding:.2f}. '
                'Please repay to avoid suspension.'
            )

        notify(
            user,
            Notification.CREDIT_OVERDUE,
            'Credit Payment Overdue',
            body,
            category=Notification.CAT_CREDIT,
            data={'purchase_id': str(purchase.id),
                  'outstanding': str(purchase.total_outstanding),
                  'days_overdue': purchase.days_overdue},
        )
        sent += 1

    logger.info('send_overdue_credit_reminders: sent %d reminders', sent)
    return sent


@shared_task(name='notifications.send_vendor_tier_expiry_warnings')
def send_vendor_tier_expiry_warnings():
    """
    Warn vendors whose paid tier subscription expires within 7 days.
    Runs daily via Celery Beat.
    Deduplicates using data__warning_type='7day' so the same vendor only
    gets one heads-up per subscription period.
    """
    from tiers.models import VendorTierSubscription

    now = timezone.now()
    warn_before = now + timedelta(days=7)

    subs = VendorTierSubscription.objects.filter(
        status='active',
        end_date__gte=now.date(),
        end_date__lte=warn_before.date(),
    ).select_related('vendor__user', 'tier')

    sent = 0
    for sub in subs:
        vendor_user = sub.vendor.user
        tier_name = sub.tier.name
        days_left = (sub.end_date - now.date()).days

        already_sent = Notification.objects.filter(
            recipient=vendor_user,
            notification_type=Notification.VENDOR_TIER_EXPIRING,
            data__subscription_id=str(sub.id),
            data__warning_type='7day',
        ).exists()

        if already_sent:
            continue

        notify(
            vendor_user,
            Notification.VENDOR_TIER_EXPIRING,
            f'{tier_name} Plan Expiring in {days_left} Day(s)',
            f'Your {tier_name} business tier expires in {days_left} day(s). '
            'Renew now to keep your commission savings and store features.',
            category=Notification.CAT_SUBSCRIPTION,
            data={
                'warning_type': '7day',
                'subscription_id': str(sub.id),
                'tier': tier_name,
                'tier_level': sub.tier.tier_level,
                'days_left': days_left,
                'vendor_id': str(sub.vendor.id),
            },
        )
        sent += 1

    logger.info('send_vendor_tier_expiry_warnings: sent %d warnings', sent)
    return sent

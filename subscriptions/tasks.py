"""Expiry and durable cancellation only. These jobs never charge a customer."""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger('sanoa.subscriptions')


@shared_task
def enforce_overdue_subscriptions():
    from .models import Subscription
    from tiers.models import VendorTierSubscription

    counters = {'examined': 0, 'downgraded': 0}
    for model in (Subscription, VendorTierSubscription):
        overdue = Q(status__in=['past_due', 'expired', 'cancelled']) | Q(
            status__in=['active', 'trialing'], current_period_end__lte=timezone.now())
        qs = model.objects.filter(overdue)
        if model is VendorTierSubscription:
            qs = qs.exclude(tier__price=0, status__in=['active', 'trialing'])
        for sub in qs.iterator():
            counters['examined'] += 1
            counters['downgraded'] += sub.expire_and_downgrade(reason='Subscription period ended or payment failed')
    return counters


@shared_task
def process_subscription_cancellations():
    from .models import SubscriptionCancellation
    from payments.paystack import paystack_api

    completed = 0
    ids = list(SubscriptionCancellation.objects.filter(
        completed_at__isnull=True, next_attempt_at__lte=timezone.now(),
    ).order_by('next_attempt_at').values_list('pk', flat=True)[:100])
    for pk in ids:
        with transaction.atomic():
            job = SubscriptionCancellation.objects.select_for_update().get(pk=pk)
            if job.completed_at or job.next_attempt_at > timezone.now():
                continue
            job.attempts += 1
            job.next_attempt_at = timezone.now() + timedelta(minutes=5)
            job.save(update_fields=['attempts', 'next_attempt_at'])
        try:
            if not job.email_token:
                result = paystack_api.fetch_subscription(job.subscription_code)
                if not result.get('status'):
                    raise ValueError('Unable to fetch subscription for cancellation')
                data = result.get('data') or {}
                if data.get('status') in ('cancelled', 'complete', 'non-renewing'):
                    job.completed_at = timezone.now()
                job.email_token = data.get('email_token') or ''
            if not job.completed_at:
                if not job.email_token:
                    raise ValueError('Paystack did not return a cancellation token')
                result = paystack_api.disable_subscription(job.subscription_code, job.email_token)
                if not result.get('status'):
                    raise ValueError('Paystack did not confirm cancellation')
                job.completed_at = timezone.now()
            job.last_error = ''
            completed += 1
        except Exception as exc:
            logger.warning('Cancellation pending for %s: %s', job.subscription_code, type(exc).__name__)
            job.last_error = str(exc)[:500]
            job.next_attempt_at = timezone.now() + timedelta(minutes=min(60, 2 ** min(job.attempts, 6)))
        job.save(update_fields=['email_token', 'completed_at', 'last_error', 'next_attempt_at'])
    return {'completed': completed}

"""Subscription lifecycle: payment grants access; expiry never initiates a charge."""
import calendar
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError


def period_end(start, offering):
    count, unit = offering.duration, offering.duration_unit
    # Legacy monthly tiers were seeded as 30 days. Keep gateway and local
    # calendar periods consistent instead of turning them into daily plans.
    if unit == 'days' and count == 30:
        count, unit = 1, 'months'
    if unit == 'years':
        count, unit = count * 12, 'months'
    if unit == 'months':
        index = start.month - 1 + count
        year, month = start.year + index // 12, index % 12 + 1
        return start.replace(year=year, month=month,
                             day=min(start.day, calendar.monthrange(year, month)[1]))
    return start + timedelta(days=count)


def paystack_interval(offering):
    intervals = {
        ('days', 1): 'daily', ('days', 7): 'weekly', ('days', 30): 'monthly',
        ('months', 1): 'monthly', ('months', 3): 'quarterly',
        ('months', 6): 'biannually', ('months', 12): 'annually',
        ('years', 1): 'annually',
    }
    try:
        return intervals[(offering.duration_unit, offering.duration)]
    except KeyError:
        raise ValidationError('This duration cannot be represented by a Paystack recurring plan.')


def queue_cancellation(code, token='', reason='Subscription expired'):
    from .models import SubscriptionCancellation
    if not code:
        return
    job, _ = SubscriptionCancellation.objects.get_or_create(
        subscription_code=code,
        defaults={'email_token': token, 'reason': reason[:250]},
    )
    if token and not job.email_token:
        job.email_token = token
        job.save(update_fields=['email_token'])


@transaction.atomic
def expire_subscription(subscription, *, reason, force=False, status='expired'):
    """Lock and recheck so a stale expiry worker cannot undo a newer payment."""
    current = type(subscription).objects.select_for_update().get(pk=subscription.pk)
    if not force and not current.is_overdue:
        subscription.refresh_from_db()
        return False
    changed = current.status != status
    needs_save = changed or bool(current.pending_reference) or current.cancelled_at is None
    current.status = status
    current.cancelled_at = current.cancelled_at or timezone.now()
    # An abandoned checkout must not resurrect a cancelled subscription later.
    current.pending_reference = ''
    if needs_save:
        current.save(update_fields=['status', 'cancelled_at', 'pending_reference', 'updated_at'])
    queue_cancellation(current.paystack_subscription_code, current.paystack_email_token, reason)
    if current._meta.label_lower == 'subscriptions.subscription':
        from debit.models import CreditAccount
        changed = bool(CreditAccount.objects.filter(subscription=current).exclude(
            credit_limit=0).update(credit_limit=0, updated_at=timezone.now())) or changed
    subscription.refresh_from_db()
    return changed


@transaction.atomic
def start_subscription(user, offering, *, callback_url='', vendor=None):
    """A new checkout buys one period. No plan/card authorization is sent."""
    from accounts.models import User
    from debit.models import CreditAccount
    from payments.models import Transaction
    from payments.paystack import paystack_api
    from tiers.models import VendorTierSubscription
    from .models import Subscription

    user = User.objects.select_for_update().get(pk=user.pk)
    model = VendorTierSubscription if vendor else Subscription
    lookup = {'vendor': vendor} if vendor else {'user': user}
    offer_field = 'tier' if vendor else 'plan'
    sub = model.objects.select_for_update().filter(**lookup).first()
    first = sub is None
    now = timezone.now()
    if sub and sub.is_active and getattr(sub, f'{offer_field}_id') == offering.pk:
        raise ValidationError('This subscription is already active.')
    if sub and sub.status == 'pending' and getattr(sub, f'{offer_field}_id') == offering.pk:
        existing = Transaction.objects.filter(reference=sub.pending_reference, status='pending').first()
        if existing and existing.authorization_url:
            return sub, {key: getattr(existing, key) for key in
                         ('authorization_url', 'access_code', 'reference')}

    trial_days = (offering.trial_days if vendor else 14) if first and (
        vendor or not user.had_trial) else 0
    free = offering.price == 0
    state = 'active' if free else ('trialing' if trial_days else 'pending')
    end = (now + timedelta(days=36500) if free else
           now + timedelta(days=trial_days) if trial_days else now)
    if sub:
        queue_cancellation(sub.paystack_subscription_code, sub.paystack_email_token,
                           'Replaced by a new subscription')
    defaults = {
        offer_field: offering, 'status': state, 'current_period_start': now,
        'current_period_end': end, 'cancelled_at': None, 'pending_reference': '',
        'last_payment_reference': '', 'paystack_subscription_code': '',
        'paystack_email_token': '', 'paystack_authorization_code': '',
    }
    sub, _ = model.objects.update_or_create(**lookup, defaults=defaults)
    if not vendor:
        CreditAccount.objects.filter(user=user).update(
            subscription=sub, credit_limit=offering.credit_limit if state != 'pending' else 0,
            updated_at=now,
        )
        if trial_days:
            user.had_trial = True
            user.save(update_fields=['had_trial', 'updated_at'])
    if state != 'pending':
        return sub, {}

    reference = f'SUB-{uuid.uuid4().hex}'
    intent = 'tier_payment' if vendor else 'subscription_payment'
    metadata = {'payment_intent': intent, 'user_id': str(user.pk),
                'offering_id': str(offering.pk), 'subscription_id': str(sub.pk),
                'duration': offering.duration, 'duration_unit': offering.duration_unit}
    payload = {'email': user.email, 'amount': int(offering.price * 100),
               'currency': 'ZAR', 'reference': reference, 'metadata': metadata}
    if callback_url:
        payload['callback_url'] = callback_url
    result = paystack_api.initialize_transaction(**payload)
    data = result.get('data') or {}
    if not result.get('status') or not data.get('authorization_url') or data.get('reference') != reference:
        raise ValidationError('Unable to start subscription payment. Please retry.')
    Transaction.objects.create(
        reference=reference, user=user, amount=offering.price, currency='ZAR',
        payment_intent=intent, status='pending', metadata=metadata,
        **{'vendor_tier_subscription' if vendor else 'subscription': sub},
        authorization_url=data['authorization_url'], access_code=data.get('access_code', ''),
    )
    sub.pending_reference = reference
    sub.save(update_fields=['pending_reference', 'updated_at'])
    return sub, {key: data.get(key, '') for key in ('authorization_url', 'access_code', 'reference')}


@transaction.atomic
def apply_subscription_payment(txn, data):
    """Only a verified, matching checkout can reactivate access, exactly once."""
    from debit.models import CreditAccount
    sub = txn.vendor_tier_subscription if txn.payment_intent == 'tier_payment' else (
        txn.subscription if txn.payment_intent == 'subscription_payment' else None)
    if sub is None or data.get('status') != 'success':
        return False
    sub = type(sub).objects.select_for_update().get(pk=sub.pk)
    if sub.last_payment_reference == txn.reference or sub.pending_reference != txn.reference:
        return False
    if (data.get('reference') != txn.reference or data.get('currency') != txn.currency
            or Decimal(str(data.get('amount', 0))) != txn.amount * 100):
        raise ValidationError('Subscription payment amount, currency or reference does not match.')
    vendor = sub._meta.label_lower == 'tiers.vendortiersubscription'
    owner_id = sub.vendor.user_id if vendor else sub.user_id
    offering = sub.tier if vendor else sub.plan
    if txn.user_id != owner_id or txn.metadata.get('offering_id') != str(offering.pk):
        raise ValidationError('Subscription payment does not match the current subscriber or plan.')
    from types import SimpleNamespace
    from django.utils.dateparse import parse_datetime
    start = parse_datetime(data.get('paid_at') or '')
    if start is None or timezone.is_naive(start):
        raise ValidationError('A valid payment timestamp is required.')
    duration = SimpleNamespace(duration=int(txn.metadata['duration']),
                               duration_unit=txn.metadata['duration_unit'])
    sub.current_period_start = start
    sub.current_period_end = period_end(start, duration)
    sub.status = 'active' if sub.current_period_end > timezone.now() else 'expired'
    sub.last_payment_reference = txn.reference
    sub.pending_reference = ''
    sub.cancelled_at = None
    sub.save(update_fields=['current_period_start', 'current_period_end', 'status',
                            'last_payment_reference', 'pending_reference', 'cancelled_at', 'updated_at'])
    if not vendor:
        CreditAccount.objects.filter(user_id=owner_id).update(
            subscription=sub, credit_limit=offering.credit_limit if sub.is_active else 0,
            updated_at=timezone.now(),
        )
    return True

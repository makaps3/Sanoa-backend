import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from business.models import VendorProfile
from core.order_financials import vendor_tier_commission_discount
from debit.models import CreditAccount
from payments.models import Transaction
from payments.views import PaystackWebhookView
from subscriptions.billing import (
    apply_subscription_payment, expire_subscription, paystack_interval,
    period_end, queue_cancellation, start_subscription,
)
from subscriptions.models import Plan, Subscription, SubscriptionCancellation
from subscriptions.tasks import enforce_overdue_subscriptions, process_subscription_cancellations
from tiers.entitlements import effective_tier, negotiation_allowed, product_limit
from tiers.models import BusinessTier, VendorTierSubscription

pytestmark = pytest.mark.django_db


@pytest.fixture(params=['customer', 'vendor'])
def subscriber(request):
    user = User.objects.create_user(username='subscriber', email='subscriber@example.com',
                                    user_type=request.param, is_verified=True, had_trial=True)
    now = timezone.now()
    if request.param == 'vendor':
        vendor = VendorProfile.objects.get(user=user)
        offering = BusinessTier.objects.create(name='Premium Monthly Test', slug='premium-test',
            price=699, duration=30, duration_unit='days', trial_days=0,
            tier_level=2, max_products=150, negotiation_enabled=True, commission_discount=8)
        sub = VendorTierSubscription.objects.create(vendor=vendor, tier=offering,
            status='expired', current_period_start=now-timedelta(days=31), current_period_end=now-timedelta(days=1))
    else:
        vendor = None
        offering = Plan.objects.create(name='Customer Plan Test', slug='customer-test',
            price=99, credit_limit=1000, duration=30, duration_unit='days')
        sub = Subscription.objects.create(user=user, plan=offering, status='expired',
            current_period_start=now-timedelta(days=31), current_period_end=now-timedelta(days=1))
        CreditAccount.objects.create(user=user, subscription=sub, credit_limit=1000, current_balance=200)
    return SimpleNamespace(user=user, vendor=vendor, offering=offering, sub=sub)


def checkout_response(**payload):
    return {'status': True, 'data': {'reference': payload['reference'],
        'authorization_url': 'https://checkout.paystack.com/test', 'access_code': 'access'}}


def checkout(person):
    with patch('payments.paystack.paystack_api.initialize_transaction', side_effect=checkout_response) as api:
        sub, data = start_subscription(person.user, person.offering, vendor=person.vendor)
        assert 'plan' not in api.call_args.kwargs
        assert 'authorization_code' not in api.call_args.kwargs
    return sub, Transaction.objects.get(reference=data['reference'])


def success(txn):
    return {'status': 'success', 'reference': txn.reference, 'amount': int(txn.amount*100),
            'currency': 'ZAR', 'paid_at': timezone.now().isoformat()}


def test_checkout_never_grants_unpaid_access_and_is_reused(subscriber):
    sub, txn = checkout(subscriber)
    assert sub.status == 'pending' and not sub.is_active
    with patch('payments.paystack.paystack_api.initialize_transaction') as api:
        again, data = start_subscription(subscriber.user, subscriber.offering, vendor=subscriber.vendor)
    api.assert_not_called()
    assert again.pk == sub.pk and data['reference'] == txn.reference
    if not subscriber.vendor:
        account = CreditAccount.objects.get(user=subscriber.user)
        assert account.credit_limit == 0 and account.available_credit == 0


def test_payment_restores_exactly_one_period_and_duplicate_cannot_revive_expired(subscriber):
    sub, txn = checkout(subscriber)
    data = success(txn)
    assert apply_subscription_payment(txn, data)
    sub.refresh_from_db()
    assert sub.is_active
    if not subscriber.vendor:
        account = CreditAccount.objects.get(user=subscriber.user)
        assert account.credit_limit == 1000 and account.available_credit == 800
    end = sub.current_period_end
    assert not apply_subscription_payment(txn, data)
    expire_subscription(sub, force=True, reason='Failed renewal')
    assert not apply_subscription_payment(txn, data)
    sub.refresh_from_db()
    assert sub.status == 'expired' and not sub.is_active and sub.current_period_end == end
    if not subscriber.vendor:
        account = CreditAccount.objects.get(user=subscriber.user)
        assert account.credit_limit == 0 and account.current_balance == 200


@pytest.mark.parametrize('field,value', [('amount', 1), ('currency', 'USD'), ('paid_at', None)])
def test_payment_must_match_checkout(subscriber, field, value):
    sub, txn = checkout(subscriber)
    data = success(txn)
    data[field] = value
    with pytest.raises(ValidationError):
        apply_subscription_payment(txn, data)
    sub.refresh_from_db()
    assert not sub.is_active


def test_abandoned_old_checkout_cannot_replace_new_plan(subscriber):
    sub, txn = checkout(subscriber)
    expire_subscription(sub, force=True, reason='Cancelled checkout')
    replacement, new_txn = checkout(subscriber)
    assert not apply_subscription_payment(txn, success(txn))
    assert apply_subscription_payment(new_txn, success(new_txn))


def test_failed_invoice_expires_immediately_and_queues_remote_stop(subscriber):
    sub = subscriber.sub
    sub.status = 'active'
    sub.current_period_end = timezone.now() + timedelta(days=3)
    sub.paystack_subscription_code = 'SUB_legacy'
    sub.save()
    PaystackWebhookView()._handle_invoice_payment_failed(
        {'subscription': {'subscription_code': 'SUB_legacy'}}, None)
    sub.refresh_from_db()
    assert sub.status == 'expired' and not sub.is_active
    assert SubscriptionCancellation.objects.filter(subscription_code='SUB_legacy').exists()


def test_scheduled_expiry_covers_customer_and_vendor_without_charges(subscriber):
    sub = subscriber.sub
    sub.status = 'active'
    sub.paystack_subscription_code = 'SUB_overdue'
    sub.save()
    with patch('payments.paystack.paystack_api.charge_authorization') as charge:
        enforce_overdue_subscriptions()
        enforce_overdue_subscriptions()
    charge.assert_not_called()
    sub.refresh_from_db()
    assert sub.status == 'expired'
    assert SubscriptionCancellation.objects.filter(subscription_code='SUB_overdue').count() == 1


def test_expiry_rechecks_current_database_after_payment(subscriber):
    stale = subscriber.sub
    sub, txn = checkout(subscriber)
    apply_subscription_payment(txn, success(txn))
    assert not stale.expire_and_downgrade()
    assert stale.is_active


def test_subscription_create_is_not_payment_and_empty_events_do_not_match(subscriber):
    handler = PaystackWebhookView()
    handler._handle_subscription_create({'subscription_code': 'SUB_old', 'email_token': 'token'}, None)
    handler._handle_invoice_payment_failed({'subscription': {}}, None)
    subscriber.sub.refresh_from_db()
    assert subscriber.sub.status == 'expired'
    assert SubscriptionCancellation.objects.filter(subscription_code='SUB_old').exists()


def test_cancellation_fetches_missing_token_and_retries_failure():
    queue_cancellation('SUB_old')
    with patch('payments.paystack.paystack_api.fetch_subscription', return_value={
        'status': True, 'data': {'email_token': 'token', 'status': 'active'}}), patch(
        'payments.paystack.paystack_api.disable_subscription', return_value={'status': False}):
        process_subscription_cancellations()
    job = SubscriptionCancellation.objects.get()
    assert job.completed_at is None and job.attempts == 1 and job.last_error
    job.next_attempt_at = timezone.now()
    job.save()
    with patch('payments.paystack.paystack_api.disable_subscription', return_value={'status': True}) as disable:
        process_subscription_cancellations()
        process_subscription_cancellations()
        disable.assert_called_once_with('SUB_old', 'token')
    job.refresh_from_db()
    assert job.completed_at is not None


def test_monthly_plan_is_not_daily_and_calendar_handles_month_end():
    offering = SimpleNamespace(duration=30, duration_unit='days')
    assert paystack_interval(offering) == 'monthly'
    start = timezone.now().replace(year=2026, month=1, day=31)
    assert period_end(start, offering) == start.replace(month=2, day=28)
    with pytest.raises(ValidationError):
        paystack_interval(SimpleNamespace(duration=10, duration_unit='days'))


def test_expired_vendor_has_no_premium_benefits(subscriber):
    if not subscriber.vendor:
        return
    BusinessTier.objects.create(name='Free Test', slug='free-test', price=0, tier_level=0,
                                max_products=20, negotiation_enabled=False)
    assert not negotiation_allowed(subscriber.vendor)
    assert product_limit(subscriber.vendor) == 20
    assert vendor_tier_commission_discount(subscriber.vendor) == Decimal('0')
    assert effective_tier(subscriber.vendor).price == 0


def test_unsigned_webhook_is_refused():
    response = APIClient().post('/api/payments/webhooks/paystack/', {'event': 'charge.success', 'data': {}}, format='json')
    assert response.status_code == 400


def test_signed_webhook_retries_failed_processing(settings, subscriber):
    settings.PAYSTACK_SECRET_KEY = 'test-webhook-key'
    settings.PAYSTACK_WEBHOOK_SECRET = ''
    sub = subscriber.sub
    sub.paystack_subscription_code = 'SUB_failed'
    sub.status = 'active'
    sub.save()
    payload = json.dumps({'event': 'invoice.payment_failed', 'data': {
        'id': 987, 'subscription': {'subscription_code': 'SUB_failed'}}})
    signature = hmac.new(b'test-webhook-key', payload.encode(), hashlib.sha512).hexdigest()
    client = APIClient()
    with patch.object(PaystackWebhookView, '_process_event', side_effect=RuntimeError('Temporary failure')):
        response = client.post('/api/payments/webhooks/paystack/', payload, content_type='application/json',
                               HTTP_X_PAYSTACK_SIGNATURE=signature)
    assert response.status_code == 500
    response = client.post('/api/payments/webhooks/paystack/', payload, content_type='application/json',
                           HTTP_X_PAYSTACK_SIGNATURE=signature)
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.status == 'expired'


def test_paid_webhook_and_api_verification_do_not_extend_twice(settings, subscriber):
    settings.PAYSTACK_SECRET_KEY = 'test-webhook-key'
    settings.PAYSTACK_WEBHOOK_SECRET = ''
    sub, txn = checkout(subscriber)
    data = success(txn)
    data['id'] = 123456
    payload = json.dumps({'event': 'charge.success', 'data': data})
    signature = hmac.new(b'test-webhook-key', payload.encode(), hashlib.sha512).hexdigest()
    client = APIClient()
    with patch('payments.tasks.send_payment_confirmation_email.delay'), patch('core.email.send_subscription_invoice_email'):
        result = client.post('/api/payments/webhooks/paystack/', payload, content_type='application/json',
                             HTTP_X_PAYSTACK_SIGNATURE=signature)
    assert result.status_code == 200
    sub.refresh_from_db()
    assert sub.is_active
    end = sub.current_period_end
    client.force_authenticate(user=subscriber.user)
    with patch('payments.paystack.paystack_api.verify_transaction', return_value={'status': True, 'data': data}):
        result = client.get('/api/payments/transactions/verify/', {'reference': txn.reference})
    assert result.status_code == 200
    sub.refresh_from_db()
    assert sub.current_period_end == end


def test_repair_command_dry_run_then_apply(subscriber):
    from django.core.management import call_command
    from io import StringIO
    offering = subscriber.offering
    offering.paystack_plan_code = 'PLN_test'
    offering.paystack_plan_id = 3702704
    offering.save()
    remote = {'status': True, 'data': {'id': 3702704, 'interval': 'daily'}}
    listing = {'status': True, 'data': [{'subscription_code': 'SUB_repair', 'status': 'active',
                                       'email_token': 'token'}], 'meta': {'pageCount': 1}}
    with patch('payments.paystack.paystack_api.fetch_plan', return_value=remote), patch(
        'payments.paystack.paystack_api.list_subscriptions', return_value=listing), patch(
        'payments.paystack.paystack_api.disable_subscription') as disable:
        call_command('repair_subscription_billing', plan_id=3702704, stdout=StringIO())
        disable.assert_not_called()
    assert not SubscriptionCancellation.objects.exists()
    fixed = {'status': True, 'data': {'id': 3702704, 'interval': 'monthly'}}
    with patch('payments.paystack.paystack_api.fetch_plan', side_effect=[remote, fixed]), patch(
        'payments.paystack.paystack_api.list_subscriptions', return_value=listing), patch(
        'payments.paystack.paystack_api.disable_subscription', return_value={'status': True}) as disable, patch(
        'payments.paystack.paystack_api.update_plan', return_value={'status': True}) as update:
        call_command('repair_subscription_billing', plan_id=3702704, apply=True, stdout=StringIO())
        disable.assert_called_once_with('SUB_repair', 'token')
        update.assert_called_once_with('PLN_test', interval='monthly', update_existing_subscriptions=False)
    assert SubscriptionCancellation.objects.get().completed_at is not None


def test_free_tier_never_expires_and_vendor_trial_cannot_repeat():
    user = User.objects.create_user(username='trialvendor', email='trial@example.com', user_type='vendor')
    vendor = VendorProfile.objects.get(user=user)
    tier = BusinessTier.objects.create(name='Trial Tier', slug='trial-tier', price=200,
                                       trial_days=14, duration=30, duration_unit='days')
    with patch('payments.paystack.paystack_api.initialize_transaction') as api:
        sub, data = start_subscription(user, tier, vendor=vendor)
        api.assert_not_called()
    assert sub.status == 'trialing' and sub.current_period_end <= timezone.now() + timedelta(days=14)
    expire_subscription(sub, force=True, reason='Trial finished')
    with patch('payments.paystack.paystack_api.initialize_transaction', side_effect=checkout_response):
        sub, data = start_subscription(user, tier, vendor=vendor)
    assert sub.status == 'pending' and data['authorization_url']
    free = BusinessTier.objects.create(name='Free Tier', slug='free-tier', price=0)
    sub, data = start_subscription(user, free, vendor=vendor)
    sub.current_period_end = timezone.now() - timedelta(days=1)
    sub.save()
    enforce_overdue_subscriptions()
    sub.refresh_from_db()
    assert sub.is_active and sub.status == 'active'

"""
Paystack API service module.
Handles all communication with the Paystack REST API.
Reference: https://paystack.com/docs/api/
"""
import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger('sanoa.payments')


class PaystackAPI:
    """Client for the Paystack REST API."""

    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }

    # ── helpers ──────────────────────────────────────────────

    def _request(self, method, endpoint, data=None, params=None):
        """Make a request to the Paystack API and return the JSON response."""
        if not self.secret_key:
            # Without a key Paystack only answers "Format is Authorization
            # Bearer [secret key]" - name the real problem instead.
            logger.error('Paystack call skipped: PAYSTACK_SECRET_KEY is not set (%s %s)', method, endpoint)
            return {
                'status': False,
                'message': 'Payments are not configured on the server (PAYSTACK_SECRET_KEY is missing).',
            }
        url = f'{self.base_url}{endpoint}'
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30,
            )
            result = response.json()
            if not result.get('status'):
                logger.warning('Paystack API error: %s %s -> %s', method, endpoint, result.get('message'))
            return result
        except requests.RequestException as exc:
            logger.error('Paystack request failed: %s %s → %s', method, endpoint, exc)
            return {'status': False, 'message': str(exc)}

    def _get(self, endpoint, params=None):
        return self._request('GET', endpoint, params=params)

    def _post(self, endpoint, data=None):
        return self._request('POST', endpoint, data=data)

    def _put(self, endpoint, data=None):
        return self._request('PUT', endpoint, data=data)

    def _delete(self, endpoint):
        return self._request('DELETE', endpoint)

    # ── Transactions ─────────────────────────────────────────

    def initialize_transaction(self, email, amount, **kwargs):
        """
        Initialize a transaction.
        amount: in kobo / cents (integer).
        Returns authorization_url, access_code, reference.
        """
        payload = {'email': email, 'amount': amount, **kwargs}
        return self._post('/transaction/initialize', data=payload)

    def verify_transaction(self, reference):
        """Verify a transaction by reference."""
        return self._get(f'/transaction/verify/{reference}')

    def list_transactions(self, **params):
        """List transactions on the integration."""
        return self._get('/transaction', params=params)

    def fetch_transaction(self, transaction_id):
        """Fetch a transaction by its ID."""
        return self._get(f'/transaction/{transaction_id}')

    def charge_authorization(self, email, amount, authorization_code, **kwargs):
        """Charge a returning customer using their authorization code."""
        payload = {
            'email': email,
            'amount': amount,
            'authorization_code': authorization_code,
            **kwargs,
        }
        return self._post('/transaction/charge_authorization', data=payload)

    def view_transaction_timeline(self, id_or_reference):
        """View the timeline of a transaction."""
        return self._get(f'/transaction/timeline/{id_or_reference}')

    def transaction_totals(self, **params):
        """Get totals for transactions."""
        return self._get('/transaction/totals', params=params)

    def export_transactions(self, **params):
        """Export transactions as CSV."""
        return self._get('/transaction/export', params=params)

    # ── Transaction Splits ───────────────────────────────────

    def create_split(self, name, split_type, currency, subaccounts, **kwargs):
        """
        Create a transaction split.
        subaccounts: list of dicts with subaccount code and share.
        """
        payload = {
            'name': name,
            'type': split_type,
            'currency': currency,
            'subaccounts': subaccounts,
            **kwargs,
        }
        return self._post('/split', data=payload)

    def list_splits(self, **params):
        """List transaction splits."""
        return self._get('/split', params=params)

    def fetch_split(self, split_id):
        """Fetch a transaction split."""
        return self._get(f'/split/{split_id}')

    def update_split(self, split_id, **kwargs):
        """Update a transaction split."""
        return self._put(f'/split/{split_id}', data=kwargs)

    def add_subaccount_to_split(self, split_id, subaccount, share):
        """Add a subaccount to a split."""
        return self._post(f'/split/{split_id}/subaccount/add', data={
            'subaccount': subaccount,
            'share': share,
        })

    def remove_subaccount_from_split(self, split_id, subaccount):
        """Remove a subaccount from a split."""
        return self._post(f'/split/{split_id}/subaccount/remove', data={
            'subaccount': subaccount,
        })

    # ── Subaccounts ──────────────────────────────────────────

    def create_subaccount(self, business_name, settlement_bank, account_number,
                          percentage_charge, **kwargs):
        """Create a subaccount for a vendor."""
        payload = {
            'business_name': business_name,
            'settlement_bank': settlement_bank,
            'account_number': account_number,
            'percentage_charge': percentage_charge,
            **kwargs,
        }
        return self._post('/subaccount', data=payload)

    def list_subaccounts(self, **params):
        """List subaccounts on the integration."""
        return self._get('/subaccount', params=params)

    def fetch_subaccount(self, id_or_code):
        """Fetch a subaccount."""
        return self._get(f'/subaccount/{id_or_code}')

    def update_subaccount(self, id_or_code, **kwargs):
        """Update a subaccount."""
        return self._put(f'/subaccount/{id_or_code}', data=kwargs)

    # ── Plans ────────────────────────────────────────────────

    def create_plan(self, name, interval, amount, **kwargs):
        """
        Create a plan.
        interval: hourly, daily, weekly, monthly, quarterly, biannually, annually
        amount: in kobo / cents.
        """
        payload = {'name': name, 'interval': interval, 'amount': amount, **kwargs}
        return self._post('/plan', data=payload)

    def list_plans(self, **params):
        """List plans on the integration."""
        return self._get('/plan', params=params)

    def fetch_plan(self, id_or_code):
        """Fetch a plan."""
        return self._get(f'/plan/{id_or_code}')

    def update_plan(self, id_or_code, **kwargs):
        """Update a plan."""
        return self._put(f'/plan/{id_or_code}', data=kwargs)

    # ── Subscriptions ────────────────────────────────────────

    def create_subscription(self, customer, plan, **kwargs):
        """
        Create a subscription.
        customer: customer code or email.
        plan: plan code.
        """
        payload = {'customer': customer, 'plan': plan, **kwargs}
        return self._post('/subscription', data=payload)

    def list_subscriptions(self, **params):
        """List subscriptions."""
        return self._get('/subscription', params=params)

    def fetch_subscription(self, id_or_code):
        """Fetch a subscription."""
        return self._get(f'/subscription/{id_or_code}')

    def enable_subscription(self, code, token):
        """Enable a subscription."""
        return self._post('/subscription/enable', data={'code': code, 'token': token})

    def disable_subscription(self, code, token):
        """Disable a subscription."""
        return self._post('/subscription/disable', data={'code': code, 'token': token})

    def generate_subscription_link(self, code):
        """Generate a link for updating a subscription card."""
        return self._get(f'/subscription/{code}/manage/link')

    # ── Customers ────────────────────────────────────────────

    def create_customer(self, email, **kwargs):
        """Create a customer on Paystack."""
        payload = {'email': email, **kwargs}
        return self._post('/customer', data=payload)

    def list_customers(self, **params):
        """List customers."""
        return self._get('/customer', params=params)

    def fetch_customer(self, email_or_code):
        """Fetch a customer."""
        return self._get(f'/customer/{email_or_code}')

    def update_customer(self, code, **kwargs):
        """Update a customer."""
        return self._put(f'/customer/{code}', data=kwargs)

    def validate_customer(self, code, **kwargs):
        """Validate a customer's identity."""
        return self._post(f'/customer/{code}/identification', data=kwargs)

    def set_risk_action(self, customer, risk_action='default'):
        """Whitelist or blacklist a customer."""
        return self._post('/customer/set_risk_action', data={
            'customer': customer,
            'risk_action': risk_action,
        })

    def deactivate_authorization(self, authorization_code):
        """Deactivate an authorization."""
        return self._post('/customer/deactivate_authorization', data={
            'authorization_code': authorization_code,
        })

    # ── Refunds ──────────────────────────────────────────────

    def create_refund(self, transaction, **kwargs):
        """
        Create a refund.
        transaction: transaction reference or id.
        """
        payload = {'transaction': transaction, **kwargs}
        return self._post('/refund', data=payload)

    def list_refunds(self, **params):
        """List refunds."""
        return self._get('/refund', params=params)

    def fetch_refund(self, reference):
        """Fetch a refund."""
        return self._get(f'/refund/{reference}')

    # ── Disputes ─────────────────────────────────────────────

    def list_disputes(self, **params):
        """List disputes."""
        return self._get('/dispute', params=params)

    def fetch_dispute(self, dispute_id):
        """Fetch a dispute."""
        return self._get(f'/dispute/{dispute_id}')

    def list_transaction_disputes(self, transaction_id):
        """List disputes for a transaction."""
        return self._get(f'/dispute/transaction/{transaction_id}')

    def update_dispute(self, dispute_id, **kwargs):
        """Update a dispute."""
        return self._put(f'/dispute/{dispute_id}', data=kwargs)

    def add_evidence(self, dispute_id, **kwargs):
        """Add evidence to a dispute."""
        return self._post(f'/dispute/{dispute_id}/evidence', data=kwargs)

    def get_upload_url(self, dispute_id, **kwargs):
        """Get a URL to upload dispute evidence."""
        return self._get(f'/dispute/{dispute_id}/upload_url', params=kwargs)

    def resolve_dispute(self, dispute_id, resolution, message, **kwargs):
        """Resolve a dispute."""
        payload = {'resolution': resolution, 'message': message, **kwargs}
        return self._put(f'/dispute/{dispute_id}/resolve', data=payload)

    def export_disputes(self, **params):
        """Export disputes."""
        return self._get('/dispute/export', params=params)

    # ── Banks ────────────────────────────────────────────────

    def list_banks(self, country='south africa', **params):
        """List banks supported by Paystack."""
        params['country'] = country
        return self._get('/bank', params=params)

    def resolve_account_number(self, account_number, bank_code, currency=None):
        """Resolve an account number to get the account name.

        Paystack's `/bank/resolve` only supports NGN, USD, GHS and KES.
        ZAR (South African Rand) is **not** accepted — that has to be
        handled by callers, who should send those vendors to manual
        review instead of calling this endpoint.
        """
        params = {
            'account_number': account_number,
            'bank_code': bank_code,
        }
        if currency:
            params['currency'] = currency
        return self._get('/bank/resolve', params=params)

    # ── Transfer recipients (replaces Subaccounts) ───────────
    #
    # Marketplace flow: customer pays the platform Paystack account
    # (no on-Paystack split). The platform credits internal wallets,
    # then runs scheduled transfers to vendors / drivers using the
    # transfer-recipient API. One recipient per bank account; the
    # RCP_xxx code is stored on the vendor / driver and reused for
    # every future payout.

    def create_transfer_recipient(self, *, name, account_number, bank_code,
                                  recipient_type='nuban', currency='ZAR',
                                  **kwargs):
        """Create a Paystack Transfer Recipient.

        For ZAR (South Africa) the official `type` is `basa` per
        Paystack's docs, but `nuban` also works and is what most
        existing integrations use — callers can override via the
        `recipient_type` kwarg.
        """
        body = {
            'type': recipient_type,
            'name': name,
            'account_number': account_number,
            'bank_code': bank_code,
            'currency': currency,
        }
        body.update(kwargs)
        return self._post('/transferrecipient', body)

    def fetch_transfer_recipient(self, code):
        return self._get(f'/transferrecipient/{code}')

    def delete_transfer_recipient(self, code):
        return self._delete(f'/transferrecipient/{code}')

    def initiate_transfer(self, *, source, recipient, amount, reason='',
                          reference=None, currency='ZAR'):
        """Initiate a single transfer.

        `amount` is in kobo/cents (multiply rands by 100). `source`
        is almost always `'balance'`. Returns the Paystack response
        body — the TRF_xxx transfer code lives in `data.transfer_code`
        and the final status arrives via the `transfer.success` /
        `transfer.failed` webhook.
        """
        body = {
            'source': source,
            'recipient': recipient,
            'amount': int(amount),
            'currency': currency,
        }
        if reason:
            body['reason'] = reason
        if reference:
            body['reference'] = reference
        return self._post('/transfer', body)

    def verify_transfer(self, reference_or_code):
        return self._get(f'/transfer/verify/{reference_or_code}')

    def fetch_transfer(self, id_or_code):
        return self._get(f'/transfer/{id_or_code}')

    # ── Verification ─────────────────────────────────────────

    def resolve_bvn(self, bvn):
        """Resolve a BVN."""
        return self._get(f'/bank/resolve_bvn/{bvn}')

    # ── Webhook verification ─────────────────────────────────

    @staticmethod
    def verify_webhook_signature(payload_body, signature):
        """Verify that a webhook payload is from Paystack."""
        secret = settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
        if not secret or not signature:
            return False
        computed = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(computed, signature)


# Module-level singleton for convenience
paystack_api = PaystackAPI()

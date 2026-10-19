"""
Tests for payments app (Paystack integration)
"""
import pytest
from decimal import Decimal
from rest_framework import status
from payments.models import Transaction, Refund, PaystackSubaccount


# ── Model Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTransactionModel:
    def test_create_transaction(self, customer_user):
        txn = Transaction.objects.create(
            user=customer_user,
            amount=Decimal('99.99'),
            currency='ZAR',
        )
        assert txn.reference.startswith('TXN-')
        assert txn.status == 'pending'
        assert txn.is_successful is False

    def test_net_amount(self, customer_user):
        txn = Transaction.objects.create(
            user=customer_user,
            amount=Decimal('100.00'),
            paystack_fees=Decimal('3.20'),
        )
        assert txn.net_amount == Decimal('96.80')

    def test_amount_in_kobo(self, customer_user):
        txn = Transaction.objects.create(
            user=customer_user,
            amount=Decimal('150.50'),
        )
        assert txn.amount_in_kobo == 15050

    def test_is_refundable(self, customer_user):
        txn = Transaction.objects.create(
            user=customer_user,
            amount=Decimal('50.00'),
            status='success',
        )
        assert txn.is_refundable is True


@pytest.mark.django_db
class TestRefundModel:
    def test_create_refund(self, customer_user):
        txn = Transaction.objects.create(
            user=customer_user,
            amount=Decimal('100.00'),
            status='success',
        )
        refund = Refund.objects.create(
            transaction=txn,
            user=customer_user,
            amount=Decimal('50.00'),
            reason='customer_request',
        )
        assert refund.status == 'pending'
        assert refund.amount_in_kobo == 5000


# ── API Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTransactionAPI:
    def test_list_own_transactions(self, auth_client, customer_user):
        Transaction.objects.create(
            user=customer_user,
            amount=Decimal('99.99'),
        )
        response = auth_client.get('/api/payments/transactions/')
        assert response.status_code == status.HTTP_200_OK

    def test_transactions_require_auth(self, api_client):
        response = api_client.get('/api/payments/transactions/')
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

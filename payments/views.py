"""
Views for the Paystack-integrated payments app.
Covers: Transactions, Transaction Splits, Subaccounts, Refunds,
Disputes, Webhooks, and bank utilities.
"""
import json
import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import generics
from core.permissions import IsAdminUser, IsVendor, IsVendorOrAdmin
from core.pagination import StandardPagination

from .models import (
    PaystackSubaccount, TransactionSplit, TransactionSplitSubaccount,
    Transaction, Refund, Dispute, PaymentLog, PaystackWebhookEvent,
)
from .serializers import (
    PaystackSubaccountSerializer, PaystackSubaccountCreateSerializer,
    TransactionSplitSerializer, TransactionSplitCreateSerializer,
    TransactionSerializer, TransactionInitializeSerializer,
    ChargeAuthorizationSerializer,
    RefundSerializer, RefundCreateSerializer, RefundRejectSerializer,
    DisputeSerializer, DisputeResolveSerializer, DisputeEvidenceSerializer,
    DisputeCreateSerializer, DisputeRespondSerializer,
    PaymentLogSerializer,
    ResolveAccountSerializer,
    _order_number_of,
)
from .paystack import paystack_api
from .settlement import reverse_settlement_for_refund

logger = logging.getLogger('sanoa.payments')


# ─────────────────────────────────────────────────────────────────────────────
# Payment settlement helper
# ─────────────────────────────────────────────────────────────────────────────

def _settle_restaurant_order_payment(txn):
    """Mark a restaurant order paid once its successful payments cover it.

    Mirrors `_settle_order_payment` for `restaurant.RestaurantOrder`, which
    lives in its own table and so is invisible to the retail settlement path.
    Idempotent — recomputed from a DB aggregate every time.
    """
    from decimal import Decimal
    from django.db.models import Sum

    order = txn.restaurant_order
    if order is None or order.payment_status == 'paid':
        return

    total_paid = (
        Transaction.objects
        .filter(restaurant_order=order, status='success',
                payment_intent='order_payment')
        .aggregate(total=Sum('amount'))['total']
    ) or Decimal('0.00')

    if total_paid >= order.total_amount:
        new_ps = 'paid'
    elif total_paid > 0:
        new_ps = 'partially_paid'
    else:
        return

    fields = ['payment_status']
    order.payment_status = new_ps
    # A paid order should leave "pending" so it reaches the kitchen queue.
    if new_ps == 'paid' and order.status == 'pending':
        order.status = 'confirmed'
        fields.append('status')
    if hasattr(order, 'updated_at'):
        fields.append('updated_at')
    order.save(update_fields=fields)
    logger.info(
        'Restaurant order %s payment_status -> %s (paid R%s of R%s)',
        order.order_number, new_ps, total_paid, order.total_amount,
    )

    # ── Marketplace settlement ─────────────────────────────────────
    # Credit the internal wallets exactly like the retail path does —
    # `settle_restaurant_order` already existed but nothing ever called
    # it, so restaurant vendors' wallets and payouts stayed empty.
    if new_ps != 'paid':
        return
    try:
        from payments.settlement import (
            settle_restaurant_order, apply_paystack_fee,
        )
        # Credit the driver directly when one has already taken the job;
        # otherwise the delivery fee is escrowed on the platform ledger.
        assigned_driver = None
        try:
            from delivery.models import DeliveryJob
            job = (DeliveryJob.objects
                   .filter(restaurant_order=order)
                   .select_related('driver').first())
            if job and job.driver_id:
                assigned_driver = job.driver
        except Exception:
            pass
        settle_restaurant_order(order, driver=assigned_driver)
        fee = txn.paystack_fees or Decimal('0')
        if fee:
            apply_paystack_fee(None, fee, restaurant_order=order)
    except Exception:
        logger.exception(
            'Wallet settlement failed for restaurant order %s',
            order.order_number,
        )


def _settle_order_payment(txn):
    """
    Called after a Transaction is saved with status='success'.

    Totals all successful `order_payment` transactions for the linked order
    and updates `order.payment_status`:
      - total_paid >= order.total_amount  → 'paid'
      - 0 < total_paid < total_amount     → 'partially_paid'

    Safe to call multiple times — uses DB aggregate so it's always accurate.
    """
    if txn.payment_intent != 'order_payment':
        return
    order = txn.order
    if order is None:
        # Restaurant checkouts settle against their own table. Without this
        # a paid restaurant order stayed "awaiting payment" forever.
        if getattr(txn, 'restaurant_order_id', None):
            _settle_restaurant_order_payment(txn)
        return
    if order.payment_status == 'paid':
        return  # already settled, nothing to do

    from decimal import Decimal
    from django.db.models import Sum

    total_paid = (
        Transaction.objects
        .filter(order=order, status='success', payment_intent='order_payment')
        .aggregate(total=Sum('amount'))['total']
    ) or Decimal('0.00')

    if total_paid >= order.total_amount:
        new_ps = 'paid'
    elif total_paid > 0:
        new_ps = 'partially_paid'
    else:
        return

    if order.payment_status != new_ps:
        order.payment_status = new_ps
        order.save(update_fields=['payment_status', 'updated_at'])
        logger.info(
            'Order %s payment_status -> %s (paid R%s of R%s)',
            order.order_number, new_ps, total_paid, order.total_amount,
        )

    # ── Marketplace settlement ─────────────────────────────────────
    #
    # New flow: customer money landed in the platform Paystack account
    # (no on-Paystack split). Once the order is fully paid, credit the
    # internal wallets — vendor, optional driver, platform revenue
    # ledger — and stamp the paystack_fee for net-revenue reporting.
    # The actual bank transfer happens later via the scheduled payout
    # job, not here.
    try:
        from decimal import Decimal as _D
        fee = txn.paystack_fees or _D('0')
        if fee and fee != order.paystack_fee:
            order.update_paystack_fee(fee)
        if new_ps == 'paid':
            from payments.settlement import settle_order, apply_paystack_fee
            # If a driver has already accepted the delivery job for
            # this order, credit them directly instead of parking
            # the delivery fee on the platform-ledger escrow.
            assigned_driver = None
            try:
                from delivery.models import DeliveryJob
                job = (
                    DeliveryJob.objects
                    .filter(retail_order=order)
                    .select_related('driver').first()
                )
                if job and job.driver_id:
                    assigned_driver = job.driver
            except Exception:
                pass
            settle_order(order, driver=assigned_driver)
            # Paystack fee may have arrived AFTER settle_order ran the
            # first time (webhook timing). `apply_paystack_fee` is
            # idempotent — only debits the platform ledger the first
            # time the fee crosses the wire.
            if fee:
                apply_paystack_fee(order, fee)
            # Email each vendor on the order their invoice (items +
            # commission only). The payment_status guard above ensures
            # this runs once per order, so invoices aren't duplicated.
            try:
                from core.email import send_vendor_invoice_email
                from business.models import VendorProfile
                vendor_ids = list(
                    order.items.values_list('vendor_id', flat=True).distinct()
                )
                for vid in vendor_ids:
                    if not vid:
                        continue
                    vp = (VendorProfile.objects
                          .select_related('user').filter(pk=vid).first())
                    if vp is not None:
                        send_vendor_invoice_email(order, vp)
            except Exception:
                logger.exception(
                    'vendor invoice emails failed for %s',
                    getattr(order, 'order_number', '?'))
    except Exception as exc:
        logger.warning(
            'order settlement failed for %s: %s',
            getattr(order, 'order_number', '?'), exc,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Charge-breakdown helper
# ─────────────────────────────────────────────────────────────────────────────

def _kobo_to_decimal(value):
    """Safely convert a kobo/cent integer (or None) to a 2dp Decimal in major units."""
    from decimal import Decimal
    if value is None:
        return Decimal('0.00')
    try:
        return (Decimal(str(value)) / Decimal('100')).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


def _decimal(value):
    from decimal import Decimal
    if value is None:
        return Decimal('0.00')
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


def _refresh_paystack_data(txn):
    """Fetch the latest transaction data from Paystack and persist `paystack_response`."""
    if not txn.reference:
        return txn.paystack_response or {}
    result = paystack_api.verify_transaction(txn.reference)
    if result.get('status') and result.get('data'):
        ps_data = result['data']
        txn.paystack_response = ps_data
        if 'fees' in ps_data:
            txn.paystack_fees = _kobo_to_decimal(ps_data.get('fees'))
        txn.save(update_fields=['paystack_response', 'paystack_fees', 'updated_at'])
        return ps_data
    return txn.paystack_response or {}


def compute_charge_breakdown(txn, fresh=False):
    """
    Compute the per-transaction charge breakdown:
      - what the customer paid (gross)
      - Paystack processing fees
      - main account / business (Sanoa) share
      - per-subaccount (vendor) shares

    Pulls actual numbers from `txn.paystack_response` (Paystack's verify payload)
    when available, and falls back to deriving values from the local
    PaystackSubaccount / TransactionSplit records.

    Set ``fresh=True`` to refetch from Paystack before computing.
    """
    from decimal import Decimal

    ps_data = _refresh_paystack_data(txn) if fresh else (txn.paystack_response or {})

    gross = _decimal(txn.amount)
    paystack_fee = _decimal(txn.paystack_fees) or _kobo_to_decimal(ps_data.get('fees'))

    # `fees_split` is Paystack's own breakdown of *who pays the processing fee*
    # — paystack: their cut, integration: deducted from main account,
    # subaccount: deducted from the receiving subaccount.
    fees_split = ps_data.get('fees_split') or {}
    fees_split_normalised = {
        'paystack': _kobo_to_decimal(fees_split.get('paystack')),
        'integration': _kobo_to_decimal(fees_split.get('integration')),
        'subaccount': _kobo_to_decimal(fees_split.get('subaccount')),
    } if fees_split else None

    # ── Build the subaccount-share list ────────────────────────────────
    subaccount_shares = []

    # Prefer Paystack's reported split when present (most accurate)
    ps_split = ps_data.get('split') or {}
    ps_split_subaccounts = ps_split.get('subaccounts') if isinstance(ps_split, dict) else None

    if ps_split_subaccounts:
        for entry in ps_split_subaccounts:
            sub_info = entry.get('subaccount') or {}
            code = sub_info.get('subaccount_code', '')
            local = PaystackSubaccount.objects.filter(
                subaccount_code=code,
            ).select_related('vendor').first() if code else None
            # `amount` on a split-line is in kobo
            line_amount = _kobo_to_decimal(entry.get('amount') or entry.get('share'))
            subaccount_shares.append({
                'subaccount_code': code,
                'business_name': sub_info.get('business_name') or (local.business_name if local else ''),
                'vendor_id': str(local.vendor_id) if local else None,
                'share': entry.get('share'),
                'share_type': ps_data.get('split', {}).get('type') or (txn.split.split_type if txn.split else None),
                'amount': str(line_amount),
            })
    elif txn.split_id:
        # Derive from local split entries when Paystack hasn't echoed them back yet
        split = txn.split
        for entry in split.subaccounts.select_related('subaccount', 'subaccount__vendor').all():
            if split.split_type == 'percentage':
                line_amount = (gross * Decimal(entry.share) / Decimal('100')).quantize(Decimal('0.01'))
            else:
                line_amount = _kobo_to_decimal(entry.share)
            subaccount_shares.append({
                'subaccount_code': entry.subaccount.subaccount_code,
                'business_name': entry.subaccount.business_name,
                'vendor_id': str(entry.subaccount.vendor_id),
                'share': entry.share,
                'share_type': split.split_type,
                'amount': str(line_amount),
            })
    elif txn.subaccount_id:
        # Single-vendor case: subaccount gets gross minus main-account commission.
        sub = txn.subaccount
        pct = _decimal(sub.percentage_charge)
        flat_kobo = _decimal(sub.flat_charge)
        main_account_commission = (
            (gross * pct / Decimal('100')).quantize(Decimal('0.01'))
            + _kobo_to_decimal(flat_kobo)
        )
        vendor_amount = (gross - main_account_commission).quantize(Decimal('0.01'))
        subaccount_shares.append({
            'subaccount_code': sub.subaccount_code,
            'business_name': sub.business_name,
            'vendor_id': str(sub.vendor_id),
            'share': str(pct),
            'share_type': 'percentage_remainder',
            'amount': str(vendor_amount),
        })

    subaccount_total = sum(
        (Decimal(s['amount']) for s in subaccount_shares),
        Decimal('0.00'),
    ).quantize(Decimal('0.01'))

    # Business / main-account share: what's left after Paystack fee and subaccount payouts.
    main_account_share = (gross - paystack_fee - subaccount_total).quantize(Decimal('0.01'))
    net_amount = (gross - paystack_fee).quantize(Decimal('0.01'))

    # ── Customer block ────────────────────────────────────────────────
    ps_customer = ps_data.get('customer') or {}
    customer_block = {
        'id': str(txn.user_id) if txn.user_id else None,
        'email': txn.user.email if txn.user_id else ps_customer.get('email', ''),
        'name': (
            f"{ps_customer.get('first_name', '')} {ps_customer.get('last_name', '')}".strip()
            or (txn.user.get_full_name() if txn.user_id else '')
        ),
        'paystack_customer_code': (
            txn.paystack_customer_code or ps_customer.get('customer_code', '')
        ),
        'amount_paid': str(gross),
    }

    # ── Business / main account block ─────────────────────────────────
    business_block = {
        'name': getattr(settings, 'SANOA_BUSINESS_NAME', 'Sanoa'),
        'main_account_share': str(main_account_share),
        'paystack_integration_fee': str(
            fees_split_normalised['integration']
        ) if fees_split_normalised else None,
    }

    return {
        'transaction': {
            'id': str(txn.id),
            'reference': txn.reference,
            'paystack_transaction_id': txn.paystack_transaction_id,
            'amount': str(gross),
            'currency': txn.currency,
            'status': txn.status,
            'channel': txn.channel,
            'payment_intent': txn.payment_intent,
            'paid_at': txn.paid_at.isoformat() if txn.paid_at else None,
        },
        'customer': customer_block,
        'business': business_block,
        'paystack_fee': str(paystack_fee),
        'fees_split': {
            k: str(v) for k, v in fees_split_normalised.items()
        } if fees_split_normalised else None,
        'split': {
            'id': str(txn.split.id) if txn.split_id else None,
            'code': txn.split.paystack_split_code if txn.split_id else (
                ps_split.get('split_code') if ps_split else None
            ),
            'name': txn.split.name if txn.split_id else ps_split.get('name'),
            'type': txn.split.split_type if txn.split_id else ps_split.get('type'),
            'bearer_type': txn.split.bearer_type if txn.split_id else ps_split.get('bearer_type'),
        } if (txn.split_id or ps_split) else None,
        'subaccounts': subaccount_shares,
        'totals': {
            'gross_amount': str(gross),
            'paystack_fee': str(paystack_fee),
            'net_amount': str(net_amount),
            'subaccount_total': str(subaccount_total),
            'main_account_total': str(main_account_share),
        },
    }


# ═══════════════════════════════════════════════════════════════
# Transactions
# ═══════════════════════════════════════════════════════════════

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List / retrieve transactions.
    Customers see their own; admins see all.
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Transaction.objects.select_related('order', 'user', 'vendor', 'subaccount', 'split')
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile') or getattr(user, 'user_type', '') == 'admin':
            return qs.order_by('-created_at')
        vp = getattr(user, 'vendor_profile', None)
        if vp is not None:
            return qs.filter(vendor=vp).order_by('-created_at')
        return qs.filter(user=user).order_by('-created_at')

    # ── Initialize transaction ───────────────────────────────

    @action(detail=False, methods=['post'], url_path='initialize')
    def initialize(self, request):
        """
        Initialize a Paystack transaction.
        Returns authorization_url for the customer to complete payment.

        For `order_payment` intent the backend **always** derives the charge
        amount from `order.total_amount` (which includes any delivery fee),
        so the client-supplied `amount` field is optional and ignored for
        that intent when an `order_id` is provided.
        """
        serializer = TransactionInitializeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment_intent = data['payment_intent']
        is_subscription = payment_intent in ('subscription_payment', 'tier_payment')
        if is_subscription:
            return Response({'detail': 'Use the subscription subscribe endpoint to start a payment.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── Resolve related entity based on payment_intent ────────────
        order = None
        restaurant_order = None
        subscription = None
        vendor_tier_subscription = None
        credit_purchase = None

        if data.get('order_id'):
            if payment_intent == 'subscription_payment':
                from subscriptions.models import Subscription
                try:
                    subscription = Subscription.objects.get(
                        id=data['order_id'], user=request.user,
                    )
                except Subscription.DoesNotExist:
                    return Response(
                        {'error': 'Subscription not found.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            elif payment_intent == 'tier_payment':
                from tiers.models import VendorTierSubscription
                try:
                    vendor_tier_subscription = VendorTierSubscription.objects.get(
                        id=data['order_id'], vendor__user=request.user,
                    )
                except VendorTierSubscription.DoesNotExist:
                    return Response(
                        {'error': 'Vendor tier subscription not found.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            elif payment_intent == 'credit_payment':
                from debit.models import CreditPurchase
                try:
                    credit_purchase = CreditPurchase.objects.select_related(
                        'credit_account', 'order',
                    ).get(
                        id=data['order_id'],
                        credit_account__user=request.user,
                    )
                except CreditPurchase.DoesNotExist:
                    return Response(
                        {'error': 'Credit purchase not found.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                if credit_purchase.is_fully_paid:
                    return Response(
                        {'error': 'This credit purchase is already fully paid.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Cap the repayment to what is actually owed
                if data.get('amount') and data['amount'] > credit_purchase.total_outstanding:
                    return Response({
                        'error': (
                            f'Repayment amount R{data["amount"]} exceeds outstanding '
                            f'balance R{credit_purchase.total_outstanding}.'
                        ),
                    }, status=status.HTTP_400_BAD_REQUEST)
                # Carry the linked order forward so the transaction is also tied to it
                order = credit_purchase.order
            else:
                # order_payment (or deposit) — load the Order. Restaurant
                # checkouts live in their own table, so look there too;
                # otherwise a restaurant order can never be paid for.
                from orders.models import Order
                from restaurant.models import RestaurantOrder
                try:
                    order = Order.objects.get(id=data['order_id'])
                except Order.DoesNotExist:
                    restaurant_order = RestaurantOrder.objects.filter(
                        id=data['order_id']).first()
                    if restaurant_order is None:
                        return Response(
                            {'detail': "We couldn't find that order. It may "
                                       'have been cancelled — please try '
                                       'checking out again.'},
                            status=status.HTTP_404_NOT_FOUND,
                        )

        # ── Determine the charge amount ───────────────────────────────
        # For order_payment with a loaded order, the backend is the
        # source of truth — use order.total_amount so the delivery fee
        # (calculated server-side) is always included.
        if payment_intent == 'order_payment' and order is not None:
            amount = order.total_amount
        elif payment_intent == 'order_payment' and restaurant_order is not None:
            amount = restaurant_order.total_amount
        else:
            amount = data.get('amount')
            if not amount:
                return Response(
                    {'error': 'amount is required when no order_id is provided.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        amount_kobo = int(amount * 100)

        # ── Build Paystack payload ────────────────────────────────────
        metadata = {
            'user_id': str(request.user.id),
            'payment_intent': payment_intent,
            **data.get('metadata', {}),
        }

        # Include delivery_fare_id in metadata when provided
        if data.get('delivery_fare_id'):
            metadata['delivery_fare_id'] = data['delivery_fare_id']

        # Stamp the linked entity IDs into metadata
        if order:
            metadata['order_id'] = str(order.id)
        if restaurant_order:
            metadata['order_id'] = str(restaurant_order.id)
            metadata['restaurant_order'] = True
        if subscription:
            metadata['subscription_id'] = str(subscription.id)
        if vendor_tier_subscription:
            metadata['vendor_tier_subscription_id'] = str(vendor_tier_subscription.id)
        if credit_purchase:
            metadata['credit_purchase_id'] = str(credit_purchase.id)
            if order:
                metadata['order_id'] = str(order.id)

        payload = {
            'email': request.user.email,
            'amount': amount_kobo,
            'currency': 'ZAR',
            'metadata': metadata,
        }

        if data.get('callback_url'):
            payload['callback_url'] = data['callback_url']
        if data.get('channels'):
            payload['channels'] = data['channels']

        # NOTE: subaccount/split routing on the Paystack side has been
        # retired. Customer payments now land in the platform's main
        # Paystack account and are settled internally — vendor +
        # driver wallets credited on payment success, scheduled
        # transfers run via Paystack Transfer Recipients. Any
        # `subaccount_code` / `split_code` the client still sends is
        # silently ignored here for backwards compatibility, never
        # forwarded to Paystack.

        # Call Paystack
        result = paystack_api.initialize_transaction(**payload)

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to initialize transaction.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']

        # Vendor on the Transaction row drives reporting + ties the
        # later settlement engine to the right wallet. We pull it from
        # the order itself rather than from a subaccount lookup, since
        # subaccounts have been retired from the marketplace flow.
        vendor = None
        if order is not None:
            primary = getattr(order, 'primary_vendor', None)
            if primary is not None:
                vendor = primary
        elif restaurant_order is not None:
            # A restaurant order belongs to exactly one vendor. Without this
            # the transaction saved with an empty vendor, so it never showed
            # up in that store's transaction list or revenue reporting.
            vendor = getattr(restaurant_order, 'vendor', None)

        # Create local transaction record. `subaccount` / `split` FKs
        # stay nullable for backwards-compatible reads of historical
        # rows, but new rows never populate them.
        txn = Transaction.objects.create(
            reference=ps_data['reference'],
            payment_intent=payment_intent,
            order=order,
            restaurant_order=restaurant_order,
            subscription=subscription,
            vendor_tier_subscription=vendor_tier_subscription,
            credit_purchase=credit_purchase,
            user=request.user,
            vendor=vendor,
            amount=amount,       # resolved above: order.total_amount or client-supplied
            currency='ZAR',
            status='pending',
            access_code=ps_data.get('access_code', ''),
            authorization_url=ps_data.get('authorization_url', ''),
            metadata=payload.get('metadata', {}),
            ip_address=self._get_client_ip(request),
        )

        PaymentLog.objects.create(
            transaction=txn,
            log_type='transaction_initialized',
            message=f'Transaction initialized: {txn.reference}',
            response_data=result,
            ip_address=txn.ip_address,
        )

        return Response({
            'authorization_url': ps_data['authorization_url'],
            'access_code': ps_data['access_code'],
            'reference': ps_data['reference'],
            'transaction_id': str(txn.id),
        }, status=status.HTTP_201_CREATED)

    # ── Verify transaction ───────────────────────────────────

    @action(detail=False, methods=['get'], url_path='verify', url_name='verify')
    def verify(self, request, reference=None):
        """Verify a transaction by reference after payment.
        Pass the reference as ?reference=TXNREF query param."""
        reference = request.query_params.get('reference') or reference
        if not reference:
            return Response(
                {'error': 'reference query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self.get_queryset().filter(reference=reference).exists():
            return Response({'detail': 'Transaction not found.'}, status=status.HTTP_404_NOT_FOUND)
        result = paystack_api.verify_transaction(reference)

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Verification failed.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']
        txn = self._update_transaction_from_paystack(ps_data)

        PaymentLog.objects.create(
            transaction=txn,
            log_type='transaction_verified',
            message=f'Transaction verified: {reference} → {ps_data["status"]}',
            response_data=result,
        )

        return Response(TransactionSerializer(txn).data)

    # ── Charge authorization (recurring) ─────────────────────

    @action(detail=False, methods=['post'], url_path='charge-authorization')
    def charge_authorization(self, request):
        """Charge a saved card authorization for a returning customer."""
        serializer = ChargeAuthorizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        amount_kobo = int(data['amount'] * 100)

        if data['payment_intent'] in ('subscription_payment', 'tier_payment'):
            return Response({'detail': 'Start a new subscription checkout to pay for a subscription.'},
                            status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'email': request.user.email,
            'amount': amount_kobo,
            'authorization_code': data['authorization_code'],
            'currency': 'ZAR',
            'metadata': {
                'user_id': str(request.user.id),
                'payment_intent': data['payment_intent'],
                **data.get('metadata', {}),
            },
        }
        if data.get('subaccount_code'):
            payload['subaccount'] = data['subaccount_code']
        if data.get('split_code'):
            payload['split_code'] = data['split_code']

        result = paystack_api.charge_authorization(**payload)

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Charge failed.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']

        order = None
        subscription = None
        vendor_tier_subscription = None
        credit_purchase = None
        payment_intent = data['payment_intent']
        if data.get('order_id'):
            if payment_intent == 'subscription_payment':
                from subscriptions.models import Subscription
                subscription = Subscription.objects.filter(
                    id=data['order_id'], user=request.user,
                ).first()
            elif payment_intent == 'tier_payment':
                from tiers.models import VendorTierSubscription
                vendor_tier_subscription = VendorTierSubscription.objects.filter(
                    id=data['order_id'], vendor__user=request.user,
                ).first()
            elif payment_intent == 'credit_payment':
                from debit.models import CreditPurchase
                credit_purchase = CreditPurchase.objects.filter(
                    id=data['order_id'], credit_account__user=request.user,
                ).select_related('order').first()
                if credit_purchase:
                    order = credit_purchase.order
            else:
                from orders.models import Order
                order = Order.objects.filter(id=data['order_id']).first()

        # Resolve vendor from subaccount_code for charge authorization
        charge_vendor = None
        charge_subaccount_obj = None
        charge_split_obj = None
        if data.get('subaccount_code'):
            charge_subaccount_obj = PaystackSubaccount.objects.filter(
                subaccount_code=data['subaccount_code'],
            ).select_related('vendor').first()
            if charge_subaccount_obj:
                charge_vendor = charge_subaccount_obj.vendor
        if data.get('split_code'):
            charge_split_obj = TransactionSplit.objects.filter(
                paystack_split_code=data['split_code'],
            ).first()

        txn = Transaction.objects.create(
            reference=ps_data.get('reference', ''),
            payment_intent=payment_intent,
            order=order,
            subscription=subscription,
            vendor_tier_subscription=vendor_tier_subscription,
            credit_purchase=credit_purchase,
            user=request.user,
            vendor=charge_vendor,
            amount=data['amount'],
            currency='ZAR',
            status=ps_data.get('status', 'pending'),
            channel=ps_data.get('channel', ''),
            gateway_response=ps_data.get('gateway_response', ''),
            paystack_transaction_id=ps_data.get('id'),
            authorization_code=data['authorization_code'],
            subaccount=charge_subaccount_obj,
            split=charge_split_obj,
            paystack_response=ps_data,
            ip_address=self._get_client_ip(request),
            paid_at=timezone.now() if ps_data.get('status') == 'success' else None,
        )

        # If this is a credit repayment that succeeded immediately, settle now
        if (
            payment_intent == 'credit_payment'
            and credit_purchase
            and ps_data.get('status') == 'success'
        ):
            self._apply_credit_repayment(txn)

        # Extract card details
        auth = ps_data.get('authorization', {})
        if auth:
            txn.card_type = auth.get('card_type', '')
            txn.last4 = auth.get('last4', '')
            txn.exp_month = auth.get('exp_month', '')
            txn.exp_year = auth.get('exp_year', '')
            txn.bank = auth.get('bank', '')
            txn.save(update_fields=['card_type', 'last4', 'exp_month', 'exp_year', 'bank'])

        PaymentLog.objects.create(
            transaction=txn,
            log_type='charge_authorization',
            message=f'Authorization charged: {txn.reference}',
            response_data=result,
            ip_address=txn.ip_address,
        )

        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    # ── Charge / fees / split breakdown ──────────────────────

    @action(detail=True, methods=['get'], url_path='charges')
    def charges(self, request, pk=None):
        """
        GET /api/payments/transactions/<pk>/charges/

        Returns the full Paystack charge breakdown for a single transaction:
        Paystack processing fee, business (main account) share, and the
        per-subaccount vendor shares. Pass ``?fresh=1`` to refetch from
        Paystack before computing (useful when the local
        ``paystack_response`` was never populated, e.g. for older records).
        """
        txn = self.get_object()
        fresh = request.query_params.get('fresh') in ('1', 'true', 'yes')
        return Response(compute_charge_breakdown(txn, fresh=fresh))

    @action(detail=False, methods=['get'], url_path='charges-summary')
    def charges_summary(self, request):
        """
        GET /api/payments/transactions/charges-summary/?from=YYYY-MM-DD&to=YYYY-MM-DD

        Returns aggregated charge totals across the caller's visible
        transactions: gross, Paystack fees, business share, and total paid
        out to subaccounts. Honours ``status`` and ``payment_intent``
        query filters too.
        """
        from decimal import Decimal
        from django.utils.dateparse import parse_date

        qs = self.get_queryset().filter(status='success')

        txn_status = request.query_params.get('status')
        if txn_status:
            qs = qs.filter(status=txn_status)
        payment_intent = request.query_params.get('payment_intent')
        if payment_intent:
            qs = qs.filter(payment_intent=payment_intent)

        date_from = parse_date(request.query_params.get('from', '') or '')
        date_to = parse_date(request.query_params.get('to', '') or '')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        gross = Decimal('0.00')
        fees = Decimal('0.00')
        subaccount_total = Decimal('0.00')
        count = 0

        for txn in qs.iterator():
            breakdown = compute_charge_breakdown(txn, fresh=False)
            gross += Decimal(breakdown['totals']['gross_amount'])
            fees += Decimal(breakdown['totals']['paystack_fee'])
            subaccount_total += Decimal(breakdown['totals']['subaccount_total'])
            count += 1

        main_account_total = (gross - fees - subaccount_total).quantize(Decimal('0.01'))
        net_amount = (gross - fees).quantize(Decimal('0.01'))

        return Response({
            'count': count,
            'filters': {
                'from': date_from.isoformat() if date_from else None,
                'to': date_to.isoformat() if date_to else None,
                'status': txn_status or 'success',
                'payment_intent': payment_intent,
            },
            'totals': {
                'gross_amount': str(gross.quantize(Decimal('0.01'))),
                'paystack_fee': str(fees.quantize(Decimal('0.01'))),
                'net_amount': str(net_amount),
                'subaccount_total': str(subaccount_total.quantize(Decimal('0.01'))),
                'main_account_total': str(main_account_total),
            },
        })

    # ── Helpers ──────────────────────────────────────────────

    def _update_transaction_from_paystack(self, ps_data):
        """Update or create a local Transaction from Paystack verification data."""
        reference = ps_data.get('reference', '')
        try:
            txn = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            txn = Transaction(
                reference=reference,
                user_id=self.request.user.id,
                amount=ps_data.get('amount', 0) / 100,
            )

        if txn.pk and txn.payment_intent in ('subscription_payment', 'tier_payment'):
            from subscriptions.billing import apply_subscription_payment
            apply_subscription_payment(txn, ps_data)
        txn.status = ps_data.get('status', txn.status)
        txn.channel = ps_data.get('channel', '')
        txn.gateway_response = ps_data.get('gateway_response', '')
        txn.paystack_transaction_id = ps_data.get('id')
        txn.paystack_fees = ps_data.get('fees', 0) / 100
        txn.currency = ps_data.get('currency', 'ZAR')
        txn.paystack_response = ps_data
        txn.ip_address = ps_data.get('ip_address', txn.ip_address)

        if ps_data.get('paid_at'):
            from django.utils.dateparse import parse_datetime
            txn.paid_at = parse_datetime(ps_data['paid_at'])

        # Authorization details
        auth = ps_data.get('authorization', {})
        if auth:
            txn.authorization_code = auth.get('authorization_code', '')
            txn.card_type = auth.get('card_type', '')
            txn.last4 = auth.get('last4', '')
            txn.exp_month = auth.get('exp_month', '')
            txn.exp_year = auth.get('exp_year', '')
            txn.bank = auth.get('bank', '')

        # Customer code
        customer = ps_data.get('customer', {})
        if customer:
            txn.paystack_customer_code = customer.get('customer_code', '')

        if ps_data.get('status') == 'failed':
            txn.failure_reason = ps_data.get('gateway_response', '')

        txn.save()

        # Auto-mark the linked order as paid when payment is fully successful
        if ps_data.get('status') == 'success':
            _settle_order_payment(txn)

        return txn

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ═══════════════════════════════════════════════════════════════
# Subaccounts (Vendor)
# ═══════════════════════════════════════════════════════════════

class SubaccountViewSet(viewsets.ModelViewSet):
    unverified_actions = ('list', 'retrieve', 'create', 'update', 'partial_update', 'my_subaccount')
    """
    Manage Paystack subaccounts for vendors.
    Vendors create their own; admins can list all.
    """
    serializer_class = PaystackSubaccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = PaystackSubaccount.objects.select_related('vendor', 'vendor__user')
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile') or getattr(user, 'user_type', '') == 'admin':
            return qs
        vendor_profile = getattr(user, 'vendor_profile', None)
        if vendor_profile is None:
            return qs.none()
        return qs.filter(vendor=vendor_profile)

    def get_serializer_class(self):
        if self.action == 'create':
            return PaystackSubaccountCreateSerializer
        return PaystackSubaccountSerializer

    def create(self, request, *args, **kwargs):
        """DEPRECATED — replaced by Paystack Transfer Recipients.

        The platform no longer splits at the gateway. Customers pay
        the platform Paystack account; the platform credits internal
        wallets and runs scheduled transfers via
        `/api/payments/marketplace/me/vendor-recipient/`. Returning
        410 Gone here stops new vendors from onboarding the old way
        without disrupting reads on historical subaccount rows.
        """
        return Response(
            {
                'error': 'Subaccount creation has been retired.',
                'use_endpoint': '/api/payments/marketplace/me/vendor-recipient/',
                'reason': (
                    'The marketplace now collects customer payments directly '
                    'and pays vendors via Paystack Transfer Recipients.'
                ),
            },
            status=status.HTTP_410_GONE,
        )

    def _deprecated_create(self, request, *args, **kwargs):  # pragma: no cover
        """Old subaccount creation path — retained for reference only."""
        if request.user.user_type != 'vendor':
            return Response(
                {'error': 'Only vendors can create subaccounts.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        vendor_profile = getattr(request.user, 'vendor_profile', None)
        if vendor_profile is None:
            return Response(
                {'error': 'You must have a vendor profile to create a subaccount.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if PaystackSubaccount.objects.filter(vendor=vendor_profile).exists():
            return Response(
                {'error': 'You already have a subaccount.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaystackSubaccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # The vendor no longer chooses a commission — we look up the
        # active PlatformFee row by their business_category and apply
        # `merchant_commission_percent` as Paystack's percentage_charge.
        # Paystack's gateway fee is absorbed by the platform out of
        # this commission. If no row is configured for the category
        # we fall back to 0 so the subaccount still gets created.
        from platform_admin.models import PlatformFee
        platform_fee = PlatformFee.for_business_category(
            getattr(vendor_profile, 'business_category', None)
        )
        commission_pct = float(platform_fee.merchant_commission_percent) if platform_fee else 0.0

        # Create on Paystack
        result = paystack_api.create_subaccount(
            business_name=data['business_name'],
            settlement_bank=data['settlement_bank'],
            account_number=data['account_number'],
            percentage_charge=commission_pct,
            primary_contact_email=data.get('primary_contact_email', request.user.email),
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to create subaccount on Paystack.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']

        subaccount = PaystackSubaccount.objects.create(
            vendor=vendor_profile,
            subaccount_code=ps_data['subaccount_code'],
            paystack_subaccount_id=ps_data.get('id'),
            business_name=data['business_name'],
            settlement_bank=data['settlement_bank'],
            account_number=data['account_number'],
            bank_name=ps_data.get('settlement_bank', ''),
            account_name=ps_data.get('account_name', ''),
            percentage_charge=commission_pct,
            platform_fee=platform_fee,
            primary_contact_email=data.get('primary_contact_email', request.user.email),
            metadata=ps_data,
        )

        PaymentLog.objects.create(
            log_type='subaccount_created',
            message=f'Subaccount created: {subaccount.subaccount_code}',
            response_data=result,
        )

        return Response(
            PaystackSubaccountSerializer(subaccount).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Update a subaccount on Paystack and locally.

        `percentage_charge` is no longer settable by vendors — it's
        owned by the PlatformFee row. To bump the commission on a
        live subaccount, admins change the fee row and resync.
        """
        subaccount = self.get_object()
        serializer = PaystackSubaccountSerializer(subaccount, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Update on Paystack
        update_fields = {}
        for field in ['business_name', 'settlement_bank', 'account_number']:
            if field in request.data:
                update_fields[field] = request.data[field]

        if update_fields:
            result = paystack_api.update_subaccount(
                subaccount.subaccount_code, **update_fields,
            )
            if not result.get('status'):
                return Response(
                    {'error': result.get('message', 'Failed to update on Paystack.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'(?P<vendor_uuid>[0-9a-f-]{36})/subaccount')
    def vendor_subaccount(self, request, vendor_uuid=None):
        """GET /api/payments/subaccounts/<vendor_uuid>/subaccount/

        Ownership check compares ``vp.user_id`` against ``request.user.id``
        directly. The previous implementation used
        ``getattr(request.user, 'vendor_profile', None)`` + model equality,
        which 403'd whenever the reverse OneToOne descriptor's cache was
        cold (common right after login/create) — even for the vendor who
        owns the subaccount.
        """
        from business.models import VendorProfile
        try:
            vp = VendorProfile.objects.only('id', 'user_id').get(id=vendor_uuid)
        except VendorProfile.DoesNotExist:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        is_admin = (
            request.user.is_staff
            or hasattr(request.user, 'admin_profile')
            or getattr(request.user, 'user_type', '') == 'admin'
        )
        if not is_admin and vp.user_id != request.user.id:
            return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            sub = PaystackSubaccount.objects.get(vendor=vp)
            return Response(PaystackSubaccountSerializer(sub).data)
        except PaystackSubaccount.DoesNotExist:
            return Response(
                {'detail': 'No subaccount found. Create one first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=['get'], url_path='my-subaccount')
    def my_subaccount(self, request):
        """GET /api/payments/subaccounts/my-subaccount/ — shortcut using auth token.

        Resolves the vendor profile via a forward query
        (``VendorProfile.objects.filter(user=request.user).first()``) instead
        of the reverse OneToOne descriptor on ``request.user``. The
        descriptor returns None whenever its cache is cold (typical right
        after JWT auth where only the User row is hydrated) — which would
        otherwise 404 here even for vendors who DO have a profile.
        """
        from business.models import VendorProfile
        vendor_profile = VendorProfile.objects.filter(
            user=request.user,
        ).only('id').first()
        if vendor_profile is None:
            return Response(
                {'detail': 'No vendor profile found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            sub = PaystackSubaccount.objects.get(vendor=vendor_profile)
            return Response(PaystackSubaccountSerializer(sub).data)
        except PaystackSubaccount.DoesNotExist:
            return Response(
                {'detail': 'No subaccount found. Create one first.'},
                status=status.HTTP_404_NOT_FOUND,
            )


# ═══════════════════════════════════════════════════════════════
# Transaction Splits
# ═══════════════════════════════════════════════════════════════

class TransactionSplitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Manage Paystack transaction splits.
    Admins can create/update; all authenticated users can read.
    """
    serializer_class = TransactionSplitSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = TransactionSplit.objects.prefetch_related('subaccounts__subaccount')

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminUser])
    def create_split(self, request):
        """Create a transaction split on Paystack (admin only)."""
        serializer = TransactionSplitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = paystack_api.create_split(
            name=data['name'],
            split_type=data['split_type'],
            currency=data['currency'],
            subaccounts=data['subaccounts'],
            bearer_type=data.get('bearer_type', 'account'),
            bearer_subaccount=data.get('bearer_subaccount', ''),
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to create split.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']

        split = TransactionSplit.objects.create(
            name=data['name'],
            paystack_split_id=ps_data.get('id'),
            paystack_split_code=ps_data.get('split_code', ''),
            split_type=data['split_type'],
            currency=data['currency'],
            bearer_type=data.get('bearer_type', 'account'),
            bearer_subaccount=data.get('bearer_subaccount', ''),
            metadata=ps_data,
        )

        # Link local subaccount entries
        for sub_entry in ps_data.get('subaccounts', []):
            sub_code = sub_entry.get('subaccount', {}).get('subaccount_code', '')
            local_sub = PaystackSubaccount.objects.filter(subaccount_code=sub_code).first()
            if local_sub:
                TransactionSplitSubaccount.objects.create(
                    split=split,
                    subaccount=local_sub,
                    share=sub_entry.get('share', 0),
                )

        PaymentLog.objects.create(
            log_type='split_created',
            message=f'Split created: {split.paystack_split_code}',
            response_data=result,
        )

        return Response(
            TransactionSplitSerializer(split).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True, methods=['post'], url_path='add-subaccount',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def add_subaccount(self, request, pk=None):
        """Add a subaccount to an existing split."""
        split = self.get_object()
        subaccount_code = request.data.get('subaccount')
        share = request.data.get('share')

        if not subaccount_code or share is None:
            return Response(
                {'error': 'subaccount and share are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = paystack_api.add_subaccount_to_split(
            split.paystack_split_id, subaccount_code, share,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to add subaccount to split.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_sub = PaystackSubaccount.objects.filter(subaccount_code=subaccount_code).first()
        if local_sub:
            TransactionSplitSubaccount.objects.update_or_create(
                split=split, subaccount=local_sub,
                defaults={'share': share},
            )

        return Response(TransactionSplitSerializer(split).data)

    @action(
        detail=True, methods=['post'], url_path='remove-subaccount',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def remove_subaccount(self, request, pk=None):
        """Remove a subaccount from a split."""
        split = self.get_object()
        subaccount_code = request.data.get('subaccount')

        if not subaccount_code:
            return Response(
                {'error': 'subaccount is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = paystack_api.remove_subaccount_from_split(
            split.paystack_split_id, subaccount_code,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to remove subaccount.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_sub = PaystackSubaccount.objects.filter(subaccount_code=subaccount_code).first()
        if local_sub:
            TransactionSplitSubaccount.objects.filter(
                split=split, subaccount=local_sub,
            ).delete()

        return Response(TransactionSplitSerializer(split).data)


# ═══════════════════════════════════════════════════════════════
# Refunds & disputes — shared access helpers
# ═══════════════════════════════════════════════════════════════

def _is_platform_admin(user) -> bool:
    return bool(
        user.is_staff
        or hasattr(user, 'admin_profile')
        or getattr(user, 'user_type', '') == 'admin'
    )


def _vendor_profile_of(user):
    """The store this user runs, if any. Returns None for customers."""
    from business.models import VendorProfile
    return VendorProfile.objects.filter(user=user).first()


def _vendor_of_transaction(txn):
    """Store behind a payment — via the transaction, or either order table."""
    if getattr(txn, 'vendor_id', None):
        return txn.vendor
    order = getattr(txn, 'order', None)
    if order is not None:
        return getattr(order, 'primary_vendor', None)
    restaurant_order = getattr(txn, 'restaurant_order', None)
    if restaurant_order is not None:
        return getattr(restaurant_order, 'vendor', None)
    return None


def _dispute_payload(dispute):
    return {
        'dispute_id': str(dispute.id),
        'order_number': _order_number_of(dispute),
        'amount': str(dispute.amount),
        'category': dispute.category,
        'status': dispute.status,
    }


def _notify_dispute_raised(dispute):
    """Tell the store and the admins a customer has opened a dispute.

    Notification never blocks the dispute itself — a broken channel layer
    must not stop a customer raising a complaint.
    """
    try:
        from notifications.models import Notification
        from notifications.service import notify, notify_admins

        order_no = _order_number_of(dispute) or 'your order'
        vendor = dispute.vendor or _vendor_of_transaction(dispute.transaction)
        if vendor is not None and getattr(vendor, 'user_id', None):
            notify(
                recipient=vendor.user,
                notification_type=Notification.VENDOR_DISPUTE,
                title='A customer has opened a dispute',
                body=f'{dispute.get_category_display()} on {order_no}. '
                     'Please respond so we can resolve it quickly.',
                category=Notification.CAT_PAYMENT,
                actor=dispute.user,
                data=_dispute_payload(dispute),
            )
        notify_admins(
            notification_type=Notification.ADMIN_DISPUTE,
            title='New dispute filed',
            body=f'R{dispute.amount} disputed on {order_no} '
                 f'({dispute.get_category_display()}).',
            actor=dispute.user,
            data=_dispute_payload(dispute),
        )
    except Exception:
        logger.exception('Could not send dispute notifications for %s', dispute.id)


def _notify_dispute_updated(dispute, body):
    """Keep the customer posted as their dispute moves along."""
    try:
        from notifications.models import Notification
        from notifications.service import notify

        notify(
            recipient=dispute.user,
            notification_type=(
                Notification.DISPUTE_RESOLVED
                if dispute.status == 'resolved'
                else Notification.DISPUTE_CREATED
            ),
            title='Update on your dispute',
            body=body,
            category=Notification.CAT_PAYMENT,
            data=_dispute_payload(dispute),
        )
    except Exception:
        logger.exception('Could not send dispute update for %s', dispute.id)


def _notify_refund_requested(refund):
    """Alert the store and the admins that a refund is waiting on a decision."""
    try:
        from notifications.models import Notification
        from notifications.service import notify, notify_admins

        order_no = _order_number_of(refund) or 'an order'
        vendor = refund.vendor or _vendor_of_transaction(refund.transaction)
        if vendor is not None and getattr(vendor, 'user_id', None):
            notify(
                recipient=vendor.user,
                notification_type=Notification.VENDOR_REFUND_REQUESTED,
                title='Refund requested',
                body=f'R{refund.amount} refund requested on {order_no}.',
                category=Notification.CAT_PAYMENT,
                actor=refund.user,
                data={'refund_id': str(refund.id), 'order_number': order_no},
            )
        notify_admins(
            notification_type=Notification.ADMIN_REFUND_PENDING,
            title='Refund needs approval',
            body=f'R{refund.amount} requested on {order_no}.',
            actor=refund.user,
            data={'refund_id': str(refund.id), 'order_number': order_no},
        )
    except Exception:
        logger.exception('Could not send refund notifications for %s', refund.id)


def _notify_refund_decided(refund, body):
    try:
        from notifications.models import Notification
        from notifications.service import notify

        notify(
            recipient=refund.user,
            notification_type=Notification.REFUND_PROCESSED,
            title='Update on your refund',
            body=body,
            category=Notification.CAT_PAYMENT,
            data={'refund_id': str(refund.id), 'status': refund.status},
        )
    except Exception:
        logger.exception('Could not send refund update for %s', refund.id)


# ═══════════════════════════════════════════════════════════════
# Refunds
# ═══════════════════════════════════════════════════════════════

class RefundViewSet(viewsets.ReadOnlyModelViewSet):
    """Manage refunds. Customers request; admins approve and process via Paystack."""
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Refund.objects.select_related(
            'transaction', 'order', 'restaurant_order', 'vendor', 'user', 'approved_by',
        ).order_by('-created_at')
        user = self.request.user
        if _is_platform_admin(user):
            return qs
        # A vendor needs to see refunds raised against their own sales;
        # everyone else sees only what they themselves requested.
        vendor = _vendor_profile_of(user)
        if vendor is not None:
            return qs.filter(Q(vendor=vendor) | Q(transaction__vendor=vendor) | Q(user=user))
        return qs.filter(user=user)

    @action(detail=False, methods=['post'], url_path='request')
    def request_refund(self, request):
        """Customer requests a refund on a transaction."""
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            txn = Transaction.objects.get(id=data['transaction_id'], user=request.user)
        except Transaction.DoesNotExist:
            return Response(
                {'error': "We couldn't find that payment on your account."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not txn.is_refundable:
            return Response(
                {'error': 'This payment cannot be refunded — only successful '
                          'payments that have not already been refunded are eligible.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = txn.refunds.exclude(status__in=['rejected', 'failed']).first()
        if existing is not None:
            return Response(
                {'error': 'You have already requested a refund on this payment. '
                          f'Its current status is “{existing.get_status_display()}”.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = data.get('amount', txn.amount)
        if amount > txn.amount:
            return Response(
                {'error': 'The refund cannot be more than you paid '
                          f'(R{txn.amount}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund = Refund.objects.create(
            transaction=txn,
            order=txn.order,
            restaurant_order=getattr(txn, 'restaurant_order', None),
            vendor=txn.vendor,
            user=request.user,
            amount=amount,
            reason=data['reason'],
            customer_note=data.get('customer_note', ''),
            merchant_note=data.get('merchant_note', ''),
            status='pending',
        )

        PaymentLog.objects.create(
            transaction=txn,
            refund=refund,
            log_type='refund_requested',
            message=f'Refund requested: R{amount} on {txn.reference}',
        )
        _notify_refund_requested(refund)

        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=['post'], url_path='approve',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def approve(self, request, pk=None):
        """Admin approves and processes a refund via Paystack."""
        refund = self.get_object()

        if refund.status != 'pending':
            return Response(
                {'error': 'Only pending refunds can be approved.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Process via Paystack
        payload = {'transaction': refund.transaction.reference}
        if refund.amount < refund.transaction.amount:
            payload['amount'] = int(refund.amount * 100)
        if refund.merchant_note:
            payload['merchant_note'] = refund.merchant_note
        if refund.customer_note:
            payload['customer_note'] = refund.customer_note

        result = paystack_api.create_refund(**payload)

        if not result.get('status'):
            refund.status = 'failed'
            refund.failure_reason = result.get('message', 'Paystack refund failed')
            refund.save(update_fields=['status', 'failure_reason', 'updated_at'])
            PaymentLog.objects.create(
                transaction=refund.transaction,
                refund=refund,
                log_type='refund_failed',
                message=f'Refund failed: {refund.failure_reason}',
                response_data=result,
            )
            return Response(
                {'error': result.get('message', 'Refund failed on Paystack.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ps_data = result['data']
        refund.status = 'processing'
        refund.paystack_refund_id = ps_data.get('id')
        refund.approved_by = request.user
        refund.approved_at = timezone.now()
        refund.admin_notes = request.data.get('admin_notes', '')
        refund.paystack_response = ps_data
        refund.save()

        # The money is on its way back to the customer out of the platform's
        # Paystack balance, so the wallet credits settlement handed the vendor
        # and the platform have to be undone. Without this the vendor keeps
        # money that has already been returned.
        reversal = reverse_settlement_for_refund(refund)

        PaymentLog.objects.create(
            transaction=refund.transaction,
            refund=refund,
            log_type='refund_processed',
            message=(
                f'Refund approved and sent to Paystack: {ps_data.get("id")}. '
                f'Wallet reversal: {reversal}'
            ),
            response_data=result,
        )

        _notify_refund_decided(
            refund,
            f'Your R{refund.amount} refund was approved and is on its way '
            'back to your account.',
        )

        return Response(RefundSerializer(refund).data)

    @action(
        detail=True, methods=['post'], url_path='reject',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def reject(self, request, pk=None):
        """Admin declines a refund request.

        The dashboards used to PATCH the refund to a 'cancelled' status —
        a status this model has never had, on a read-only viewset that
        rejects PATCH. Declining now has a real endpoint.
        """
        refund = self.get_object()

        if refund.status != 'pending':
            return Response(
                {'error': 'Only refunds still awaiting a decision can be declined. '
                          f'This one is already “{refund.get_status_display()}”.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RefundRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund.status = 'rejected'
        refund.admin_notes = serializer.validated_data['admin_notes']
        refund.approved_by = request.user
        refund.approved_at = timezone.now()
        refund.save(update_fields=[
            'status', 'admin_notes', 'approved_by', 'approved_at', 'updated_at',
        ])

        PaymentLog.objects.create(
            transaction=refund.transaction,
            refund=refund,
            log_type='refund_requested',
            message=f'Refund declined: {refund.admin_notes}',
        )
        _notify_refund_decided(
            refund, f'Your refund request was declined. {refund.admin_notes}',
        )

        return Response(RefundSerializer(refund).data)


# ═══════════════════════════════════════════════════════════════
# Disputes
# ═══════════════════════════════════════════════════════════════

class DisputeViewSet(
    mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    Disputes raised by customers in-app, plus Paystack chargebacks that
    arrive over the webhook.

    Who can do what:
      * customer — raise a dispute on their own paid transaction, read it
      * vendor   — read disputes on their sales, respond to them
      * admin    — read everything, add evidence, resolve, refund
    """
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Dispute.objects.select_related(
            'transaction', 'order', 'restaurant_order', 'vendor', 'user',
        ).prefetch_related('transaction__refunds').order_by('-created_at')
        user = self.request.user
        if _is_platform_admin(user):
            return qs
        vendor = _vendor_profile_of(user)
        if vendor is not None:
            return qs.filter(
                Q(vendor=vendor) | Q(transaction__vendor=vendor) | Q(user=user)
            )
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        """Customer raises a dispute against a payment they made."""
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            txn = Transaction.objects.select_related(
                'order', 'restaurant_order', 'vendor',
            ).get(id=data['transaction_id'], user=request.user)
        except Transaction.DoesNotExist:
            return Response(
                {'error': "We couldn't find that payment on your account."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if txn.status != 'success':
            return Response(
                {'error': 'You can only dispute a payment that went through. '
                          f'This one is “{txn.status}”.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        open_dispute = txn.disputes.exclude(
            status__in=['resolved', 'declined', 'merchant-accepted'],
        ).first()
        if open_dispute is not None:
            return Response(
                {'error': 'You already have an open dispute on this order. '
                          'We will come back to you on that one.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = data.get('amount') or txn.amount
        if amount > txn.amount:
            return Response(
                {'error': f'The disputed amount cannot be more than you paid (R{txn.amount}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute = Dispute.objects.create(
            source=Dispute.SOURCE_CUSTOMER,
            transaction=txn,
            order=txn.order,
            restaurant_order=getattr(txn, 'restaurant_order', None),
            vendor=_vendor_of_transaction(txn),
            user=request.user,
            amount=amount,
            currency=txn.currency or 'ZAR',
            status='awaiting-merchant-feedback',
            category=data['category'],
            message=data['message'],
            attachments=data.get('attachments') or [],
        )

        PaymentLog.objects.create(
            transaction=txn,
            dispute=dispute,
            log_type='dispute_created',
            message=f'Dispute raised by customer: {dispute.get_category_display()}',
        )
        _notify_dispute_raised(dispute)

        return Response(
            DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='respond')
    def respond(self, request, pk=None):
        """Vendor (or admin) replies to a dispute raised against them."""
        dispute = self.get_object()
        user = request.user
        vendor = _vendor_profile_of(user)
        owns_it = vendor is not None and vendor.id in {
            getattr(dispute, 'vendor_id', None),
            getattr(dispute.transaction, 'vendor_id', None),
        }
        if not (_is_platform_admin(user) or owns_it):
            return Response(
                {'error': 'Only the store this dispute was raised against can respond to it.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if dispute.status in ('resolved', 'declined', 'merchant-accepted'):
            return Response(
                {'error': 'This dispute has already been closed, so it can no longer be answered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DisputeRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dispute.merchant_response = data['merchant_response']
        dispute.vendor_responded_at = timezone.now()
        if data.get('attachments'):
            dispute.attachments = list(dispute.attachments or []) + data['attachments']
        # Answered — it now sits with the platform to decide.
        dispute.status = 'pending'
        dispute.save(update_fields=[
            'merchant_response', 'vendor_responded_at', 'attachments',
            'status', 'updated_at',
        ])

        PaymentLog.objects.create(
            transaction=dispute.transaction,
            dispute=dispute,
            log_type='dispute_created',
            message='Vendor responded to dispute',
        )
        _notify_dispute_updated(dispute, 'The store has responded to your dispute.')

        return Response(DisputeSerializer(dispute).data)

    @action(
        detail=True, methods=['post'], url_path='add-evidence',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def add_evidence(self, request, pk=None):
        """Add evidence to a dispute (admin only)."""
        dispute = self.get_object()
        serializer = DisputeEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not dispute.paystack_dispute_id:
            return Response(
                {'error': 'No Paystack dispute ID linked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = paystack_api.add_evidence(
            dispute.paystack_dispute_id, **serializer.validated_data,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to add evidence.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute.evidence = result.get('data', {})
        dispute.save(update_fields=['evidence', 'updated_at'])

        return Response(DisputeSerializer(dispute).data)

    @action(
        detail=True, methods=['post'], url_path='resolve',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def resolve(self, request, pk=None):
        """Resolve a dispute (admin only)."""
        dispute = self.get_object()
        serializer = DisputeResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if dispute.status in ('resolved', 'declined', 'merchant-accepted'):
            return Response(
                {'error': 'This dispute has already been closed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Disputes raised in-app are settled by us, not by Paystack — only
        # a real chargeback has a Paystack dispute to resolve upstream.
        # Previously every in-app dispute dead-ended here with
        # "No Paystack dispute ID linked."
        if not dispute.paystack_dispute_id:
            return self._resolve_internally(request, dispute, data)

        kwargs = {}
        if data.get('refund_amount'):
            kwargs['refund_amount'] = int(data['refund_amount'] * 100)
        if data.get('upload_url'):
            kwargs['upload_url'] = data['upload_url']

        result = paystack_api.resolve_dispute(
            dispute.paystack_dispute_id,
            resolution=data['resolution'],
            message=data['message'],
            **kwargs,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to resolve dispute.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute.status = 'resolved'
        dispute.resolution = data['resolution']
        dispute.merchant_response = data['message']
        dispute.resolved_at = timezone.now()
        dispute.paystack_response = result.get('data', {})
        dispute.save()

        PaymentLog.objects.create(
            transaction=dispute.transaction,
            dispute=dispute,
            log_type='dispute_resolved',
            message=f'Dispute resolved: {data["resolution"]}',
            response_data=result,
        )
        _notify_dispute_updated(
            dispute, f'Your dispute has been resolved: {data["resolution"]}.',
        )

        return Response(DisputeSerializer(dispute).data)

    def _resolve_internally(self, request, dispute, data):
        """Close an in-app dispute ourselves.

        Accepting the customer's claim raises a refund for the agreed
        amount and puts it straight through to Paystack, so the decision
        and the money move together instead of the admin having to
        remember to raise a separate refund afterwards.
        """
        resolution = data['resolution']
        refund_amount = data.get('refund_amount')
        refund = None

        if resolution == 'merchant-accepted':
            amount = refund_amount or dispute.amount
            if amount > dispute.transaction.amount:
                return Response(
                    {'error': 'The refund cannot be more than the customer paid '
                              f'(R{dispute.transaction.amount}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            refund = Refund.objects.create(
                transaction=dispute.transaction,
                order=dispute.order,
                restaurant_order=dispute.restaurant_order,
                vendor=dispute.vendor or _vendor_of_transaction(dispute.transaction),
                user=dispute.user,
                amount=amount,
                reason='not_as_described',
                customer_note=dispute.message[:500],
                merchant_note=data['message'][:500],
                status='pending',
                approved_by=request.user,
                approved_at=timezone.now(),
                admin_notes=f'Auto-raised from dispute {dispute.id}',
            )
            ps = paystack_api.create_refund(
                transaction=dispute.transaction.reference,
                amount=int(amount * 100),
                merchant_note=data['message'][:500],
            )
            if ps.get('status'):
                refund.status = 'processing'
                refund.paystack_refund_id = ps.get('data', {}).get('id')
                refund.paystack_response = ps.get('data', {})
                refund.save()
                reverse_settlement_for_refund(refund)
            else:
                # Keep the dispute decision — the refund stays pending so an
                # admin can retry it from the refunds board rather than the
                # whole resolution failing.
                refund.status = 'failed'
                refund.failure_reason = ps.get(
                    'message', 'Paystack could not process this refund.',
                )
                refund.save(update_fields=[
                    'status', 'failure_reason', 'updated_at',
                ])

        dispute.status = 'resolved'
        dispute.resolution = resolution
        dispute.resolution_note = data['message']
        dispute.resolved_by = request.user
        dispute.resolved_at = timezone.now()
        dispute.save(update_fields=[
            'status', 'resolution', 'resolution_note', 'resolved_by',
            'resolved_at', 'updated_at',
        ])

        PaymentLog.objects.create(
            transaction=dispute.transaction,
            dispute=dispute,
            refund=refund,
            log_type='dispute_resolved',
            message=f'Dispute resolved in-app: {resolution}',
        )
        _notify_dispute_updated(
            dispute,
            'Your dispute was upheld and a refund is on its way.'
            if resolution == 'merchant-accepted'
            else 'Your dispute has been reviewed and closed.',
        )

        payload = DisputeSerializer(dispute).data
        if refund is not None:
            payload['refund'] = RefundSerializer(refund).data
        return Response(payload)

    @action(
        detail=False, methods=['post'], url_path='sync',
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def sync_disputes(self, request):
        """Sync disputes from Paystack (admin only)."""
        result = paystack_api.list_disputes(
            perPage=50,
            status=request.query_params.get('status', ''),
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to fetch disputes.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        synced = 0
        for dispute_data in result.get('data', []):
            ps_id = dispute_data.get('id')
            if Dispute.objects.filter(paystack_dispute_id=ps_id).exists():
                continue

            # Find the related transaction
            txn_ref = dispute_data.get('transaction', {}).get('reference', '')
            txn = Transaction.objects.filter(reference=txn_ref).first()
            if not txn:
                continue

            Dispute.objects.create(
                paystack_dispute_id=ps_id,
                transaction=txn,
                user=txn.user,
                amount=dispute_data.get('amount', 0) / 100,
                currency=dispute_data.get('currency', 'ZAR'),
                status=dispute_data.get('status', 'pending'),
                category=dispute_data.get('category', 'general'),
                message=dispute_data.get('message', ''),
                due_at=dispute_data.get('due_at'),
                paystack_response=dispute_data,
            )
            synced += 1

        return Response({'synced': synced})


# ═══════════════════════════════════════════════════════════════
# Payment Logs
# ═══════════════════════════════════════════════════════════════

class PaymentLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to payment logs (admin only)."""
    serializer_class = PaymentLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    queryset = PaymentLog.objects.select_related('transaction', 'refund', 'dispute')


# ═══════════════════════════════════════════════════════════════
# Bank utilities
# ═══════════════════════════════════════════════════════════════

# Real Paystack South-African bank list, captured from the live API.
# Used ONLY as a last resort: when Paystack is unreachable AND we have
# no cached copy, so the vendor's bank dropdown is never empty.
_SA_BANKS_FALLBACK = [
    {'name': 'Absa Bank Limited, South Africa', 'code': '632005', 'slug': 'absa-za'},
    {'name': 'Access Bank South Africa', 'code': '410506', 'slug': 'access-bank-south-africa-za'},
    {'name': 'African Bank Limited', 'code': '430000', 'slug': 'african-bank-za'},
    {'name': 'African Business Bank', 'code': '584000', 'slug': 'grindrod-bank-za'},
    {'name': 'Albaraka Bank', 'code': '800000', 'slug': 'albaraka-za'},
    {'name': 'Bank of China', 'code': '686000', 'slug': 'bank-of-china-za'},
    {'name': 'Bank Zero', 'code': '888000', 'slug': 'bank-zero-za'},
    {'name': 'Bidvest Bank Limited', 'code': '462005', 'slug': 'bidvest-bank-za'},
    {'name': 'Capitec Bank Limited', 'code': '470010', 'slug': 'capitec-bank-za'},
    {'name': 'Capitec Business', 'code': '450105', 'slug': 'capitec-business-za'},
    {'name': 'CitiBank', 'code': '350005', 'slug': 'citibank-za'},
    {'name': 'Discovery Bank Limited', 'code': '679000', 'slug': 'discovery-bank-za'},
    {'name': 'Finbond EPE', 'code': '591000', 'slug': 'finbond-epe-za'},
    {'name': 'Finbond Mutual Bank', 'code': '589000', 'slug': 'finbond-mutual-bank-za'},
    {'name': 'First National Bank', 'code': '250655', 'slug': 'first-national-bank-za'},
    {'name': 'FirstRand Bank', 'code': '201419', 'slug': 'firstrand-bank-za'},
    {'name': 'GoTyme Bank', 'code': '678910', 'slug': 'tymebank-za'},
    {'name': 'HBZ Bank (Westville)', 'code': '570226', 'slug': 'hbz-bank-westville-za'},
    {'name': 'HSBC South Africa', 'code': '587000', 'slug': 'hsbc-za'},
    {'name': 'Investec Bank Ltd', 'code': '580105', 'slug': 'investec-bank-za'},
    {'name': 'JP Morgan South Africa', 'code': '432000', 'slug': 'jp-morgan-za'},
    {'name': 'Nedbank', 'code': '198765', 'slug': 'nedbank-za'},
    {'name': 'Olympus Mobile', 'code': '585001', 'slug': 'olympus-mobile-za'},
    {'name': 'OM Bank', 'code': '352000', 'slug': 'om-bank-za'},
    {'name': 'Rand Merchant Bank', 'code': '261251', 'slug': 'rand-merchant-bank-za'},
    {'name': 'RMB Private Bank', 'code': '222026', 'slug': 'rmb-private-bank-za'},
    {'name': 'SASFIN Bank', 'code': '683000', 'slug': 'sasfin-bank-za'},
    {'name': 'Société Générale South Africa', 'code': '351005', 'slug': 'societe-generale-za'},
    {'name': 'South African Bank of Athens', 'code': '410105', 'slug': 'bank-of-athens-za'},
    {'name': 'Standard Bank South Africa', 'code': '051001', 'slug': 'standard-bank-za'},
    {'name': 'Standard Chartered Bank', 'code': '730020', 'slug': 'standard-chartered-za'},
    {'name': 'Ubank Ltd', 'code': '431010', 'slug': 'ubank-ltd-za'},
    {'name': 'VBS Mutual Bank', 'code': '588000', 'slug': 'vbs-mutual-bank-za'},
]


class BankListView(APIView):
    unverified_actions = ('get',)
    """List banks supported by Paystack.

    The upstream list barely changes, but hitting Paystack on EVERY request
    made this endpoint as slow and unreliable as the network — connect
    timeouts left the vendor's bank dropdown silently empty. So:

      1. serve a cached list when we have a fresh one (fast path);
      2. otherwise call Paystack and cache the result;
      3. if Paystack is unreachable, fall back to the last known good list
         rather than returning nothing.

    Only a cold cache + unreachable Paystack produces an error now.
    """
    permission_classes = [permissions.IsAuthenticated]

    FRESH_TTL = 60 * 60 * 24          # 24h — the list is effectively static
    STALE_TTL = 60 * 60 * 24 * 30     # last-known-good kept for a month

    def get(self, request):
        from django.core.cache import cache

        country = (request.query_params.get('country')
                   or 'south africa').strip().lower()
        # Cache keys must not contain spaces (breaks memcached).
        slug = country.replace(' ', '-')
        fresh_key = f'paystack:banks:{slug}'
        stale_key = f'paystack:banks:lastgood:{slug}'

        cached = cache.get(fresh_key)
        if cached:
            return Response(cached)

        result = paystack_api.list_banks(country=country)
        if result.get('status'):
            banks = result.get('data', []) or []
            if banks:
                cache.set(fresh_key, banks, self.FRESH_TTL)
                cache.set(stale_key, banks, self.STALE_TTL)
            return Response(banks)

        # Paystack unreachable — better a slightly stale list than none.
        last_good = cache.get(stale_key)
        if last_good:
            logger.warning('Paystack bank list unavailable (%s); serving cached copy.',
                           result.get('message', 'unknown error'))
            return Response(last_good)

        # Cold cache AND Paystack down — serve the built-in SA list so the
        # vendor can still pick their bank (these codes are stable).
        if country in ('south africa', 'za', 'south-africa'):
            logger.warning('Paystack bank list unavailable (%s); serving built-in list.',
                           result.get('message'))
            cache.set(stale_key, _SA_BANKS_FALLBACK, self.STALE_TTL)
            return Response(_SA_BANKS_FALLBACK)

        logger.error('Paystack bank list unavailable and no cached copy: %s',
                     result.get('message'))
        return Response(
            {'detail': "We couldn't load the bank list just now. "
                       'Please check your connection and try again in a moment.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _is_south_african_bank(bank_code: str) -> bool:
    """Is this bank code a South African one?

    Checked against the cached Paystack ZA list, falling back to the
    built-in list so this still works when Paystack is unreachable.
    """
    code = str(bank_code or '').strip()
    if not code:
        return False
    try:
        from django.core.cache import cache
        cached = (cache.get('paystack:banks:south-africa')
                  or cache.get('paystack:banks:lastgood:south-africa'))
        if cached:
            return any(str(b.get('code')) == code for b in cached)
    except Exception:
        pass
    return any(str(b['code']) == code for b in _SA_BANKS_FALLBACK)


class ResolveAccountView(APIView):
    unverified_actions = ('post',)
    """Resolve a bank account number to verify the account name.

    IMPORTANT: Paystack's `/bank/resolve` only supports NGN, USD, GHS and
    KES — it rejects South African accounts with a raw
    "Please supply one of the following valid currencies" error. Rather
    than making a call that can never succeed (and showing the vendor that
    message), South African accounts short-circuit to a clear explanation:
    their account is confirmed by our team when the payout recipient is
    reviewed, which the marketplace flow already does.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = ResolveAccountSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if _is_south_african_bank(data['bank_code']):
            return Response({
                'auto_verified': False,
                'requires_manual_review': True,
                'detail': (
                    "South African bank accounts can't be checked instantly — "
                    "Paystack only auto-verifies NGN, USD, GHS and KES "
                    "accounts. Save your details and our team will confirm "
                    "them; payouts unlock once they're approved."
                ),
            })

        result = paystack_api.resolve_account_number(
            data['account_number'], data['bank_code'],
        )
        if not result.get('status'):
            message = result.get('message') or 'Could not resolve account.'
            # Never leak Paystack's currency-list error to a vendor.
            if 'valid currencies' in message.lower():
                message = (
                    "This account can't be checked instantly. Save your "
                    'details and our team will confirm them.'
                )
            return Response({'detail': message},
                            status=status.HTTP_400_BAD_REQUEST)
        payload = dict(result.get('data', {}) or {})
        payload['auto_verified'] = True
        return Response(payload)


# ═══════════════════════════════════════════════════════════════
# Paystack Webhook
# ═══════════════════════════════════════════════════════════════

class PaystackWebhookView(APIView):
    """
    Receive and process Paystack webhook events.
    This endpoint must be publicly accessible (no auth).
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        # Verify signature
        signature = request.headers.get('X-Paystack-Signature', '')
        from .paystack import PaystackAPI
        if not signature or not PaystackAPI.verify_webhook_signature(request.body, signature):
            logger.warning('Missing or invalid Paystack webhook signature')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get('event', '')
        event_data = payload.get('data', {})

        # Idempotency – use a composite key
        event_id = f"{event_type}_{event_data.get('id', event_data.get('reference', ''))}"

        webhook_event, created = PaystackWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'event_type': event_type,
                'raw_data': payload,
                'status': 'received',
            },
        )

        if not created and webhook_event.status in ('processed', 'ignored'):
            return Response({'status': 'already processed'})

        try:
            from django.db import transaction
            with transaction.atomic():
                webhook_event = PaystackWebhookEvent.objects.select_for_update().get(pk=webhook_event.pk)
                if webhook_event.status in ('processed', 'ignored'):
                    return Response({'status': 'already processed'})
                self._process_event(event_type, event_data, webhook_event)
                if webhook_event.status != 'ignored':
                    webhook_event.status = 'processed'
                webhook_event.processed_at = timezone.now()
                webhook_event.save(update_fields=['status', 'processed_at'])
        except Exception as exc:
            logger.exception('Webhook processing error: %s', exc)
            webhook_event.status = 'failed'
            webhook_event.processing_error = str(exc)
            webhook_event.save(update_fields=['status', 'processing_error'])
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)

    def _process_event(self, event_type, data, webhook_event):
        handler_map = {
            'charge.success': self._handle_charge_success,
            'transfer.success': self._handle_transfer_success,
            'transfer.failed': self._handle_transfer_failed,
            'refund.processed': self._handle_refund_processed,
            'refund.failed': self._handle_refund_failed,
            'subscription.create': self._handle_subscription_create,
            'subscription.disable': self._handle_subscription_disable,
            'subscription.not_renew': self._handle_subscription_not_renew,
            'invoice.create': self._handle_invoice_create,
            'invoice.payment_failed': self._handle_invoice_payment_failed,
            'charge.dispute.create': self._handle_dispute_create,
            'charge.dispute.remind': self._handle_dispute_remind,
            'charge.dispute.resolve': self._handle_dispute_resolve,
        }

        handler = handler_map.get(event_type)
        if handler:
            handler(data, webhook_event)
        else:
            webhook_event.status = 'ignored'
            webhook_event.save(update_fields=['status'])

    # ── Charge ───────────────────────────────────────────────

    def _handle_charge_success(self, data, webhook_event):
        """Handle successful charge – update transaction status."""
        reference = data.get('reference', '')
        try:
            txn = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            logger.warning('Webhook charge.success for unknown ref: %s', reference)
            return

        from subscriptions.billing import apply_subscription_payment
        apply_subscription_payment(txn, data)

        txn.status = 'success'
        txn.channel = data.get('channel', '')
        txn.gateway_response = data.get('gateway_response', '')
        txn.paystack_transaction_id = data.get('id')
        txn.paystack_fees = data.get('fees', 0) / 100
        txn.paystack_response = data

        auth = data.get('authorization', {})
        if auth:
            txn.authorization_code = auth.get('authorization_code', '')
            txn.card_type = auth.get('card_type', '')
            txn.last4 = auth.get('last4', '')
            txn.exp_month = auth.get('exp_month', '')
            txn.exp_year = auth.get('exp_year', '')
            txn.bank = auth.get('bank', '')

        customer = data.get('customer', {})
        if customer:
            txn.paystack_customer_code = customer.get('customer_code', '')

        if data.get('paid_at'):
            from django.utils.dateparse import parse_datetime
            txn.paid_at = parse_datetime(data['paid_at'])

        txn.save()
        webhook_event.transaction = txn
        webhook_event.save(update_fields=['transaction'])

        PaymentLog.objects.create(
            transaction=txn,
            log_type='transaction_success',
            message=f'Payment successful via webhook: {reference}',
            response_data=data,
        )

        # Auto-mark the linked order as paid when payment is fully successful
        _settle_order_payment(txn)

        # Apply repayment to the credit purchase if this was a credit_payment
        if txn.payment_intent == 'credit_payment' and txn.credit_purchase_id:
            self._apply_credit_repayment(txn)

        # Email a subscription receipt/invoice for paid vendor tiers.
        if txn.payment_intent == 'tier_payment' and txn.vendor_tier_subscription_id:
            try:
                from core.email import send_subscription_invoice_email
                send_subscription_invoice_email(txn.vendor_tier_subscription, txn)
            except Exception:
                logger.exception(
                    'subscription invoice failed for txn %s', txn.id)

        # Send confirmation email async
        from .tasks import send_payment_confirmation_email
        send_payment_confirmation_email.delay(str(txn.id))

    def _apply_credit_repayment(self, txn):
        """Record a CreditRepayment and update the purchase + account balances."""
        from decimal import Decimal
        from debit.models import CreditRepayment

        purchase = txn.credit_purchase
        if purchase is None:
            return

        amount = Decimal(str(txn.amount))
        # Penalty is paid first, then principal
        penalty_owed = purchase.outstanding_penalty
        penalty_portion = min(amount, penalty_owed)
        principal_portion = amount - penalty_portion

        if penalty_portion > 0 and principal_portion > 0:
            repayment_type = 'mixed'
        elif penalty_portion > 0:
            repayment_type = 'penalty'
        else:
            repayment_type = 'principal'

        CreditRepayment.objects.create(
            purchase=purchase,
            amount=amount,
            principal_portion=principal_portion,
            penalty_portion=penalty_portion,
            payment_method='paystack',
            repayment_type=repayment_type,
            reference=txn.reference,
            paystack_transaction_id=str(txn.id),
        )

        purchase.amount_paid = purchase.amount_paid + principal_portion
        purchase.penalty_paid = purchase.penalty_paid + penalty_portion
        update_fields = ['amount_paid', 'penalty_paid', 'updated_at']
        if purchase.is_fully_paid:
            purchase.status = 'paid'
            purchase.paid_at = timezone.now()
            update_fields += ['status', 'paid_at']
        purchase.save(update_fields=update_fields)

        account = purchase.credit_account
        account.current_balance = max(
            account.current_balance - principal_portion, Decimal('0.00'),
        )
        account.save(update_fields=['current_balance', 'updated_at'])

        # Lift suspension automatically if no overdue purchases remain
        if account.status == 'suspended':
            account.unsuspend()

    def _handle_transfer_success(self, data, webhook_event):
        logger.info('Transfer success: %s', data.get('reference'))

    def _handle_transfer_failed(self, data, webhook_event):
        logger.warning('Transfer failed: %s', data.get('reference'))

    # ── Refund ───────────────────────────────────────────────

    def _handle_refund_processed(self, data, webhook_event):
        ps_id = data.get('id')
        try:
            refund = Refund.objects.get(paystack_refund_id=ps_id)
        except Refund.DoesNotExist:
            return

        refund.status = 'processed'
        refund.processed_at = timezone.now()
        refund.paystack_response = data
        refund.save()

        # Update transaction status
        txn = refund.transaction
        total_refunded = sum(
            r.amount for r in txn.refunds.filter(status='processed')
        )
        if total_refunded >= txn.amount:
            txn.status = 'reversed'
            txn.save(update_fields=['status', 'updated_at'])

        PaymentLog.objects.create(
            transaction=txn,
            refund=refund,
            log_type='refund_processed',
            message=f'Refund processed via webhook: {ps_id}',
            response_data=data,
        )

        from .tasks import send_refund_notification_email
        send_refund_notification_email.delay(str(refund.id))

    def _handle_refund_failed(self, data, webhook_event):
        ps_id = data.get('id')
        try:
            refund = Refund.objects.get(paystack_refund_id=ps_id)
        except Refund.DoesNotExist:
            return

        refund.status = 'failed'
        refund.failure_reason = data.get('gateway_response', 'Refund failed')
        refund.paystack_response = data
        refund.save()

        PaymentLog.objects.create(
            transaction=refund.transaction,
            refund=refund,
            log_type='refund_failed',
            message=f'Refund failed via webhook: {ps_id}',
            response_data=data,
        )

    # ── Subscription ─────────────────────────────────────────

    def _handle_subscription_create(self, data, webhook_event):
        # Subscription creation is not proof of payment. New checkouts are
        # prepaid; stop legacy recurring mandates without granting benefits.
        from subscriptions.billing import queue_cancellation
        code = data.get('subscription_code') or ''
        if code:
            queue_cancellation(code, data.get('email_token') or '',
                               'Manual renewal policy: disable legacy recurring mandate')

    def _subscription_for_event(self, data):
        nested = data.get('subscription') or {}
        code = data.get('subscription_code') or (
            nested.get('subscription_code') if isinstance(nested, dict) else nested)
        if not code:
            return None
        from subscriptions.models import Subscription
        from tiers.models import VendorTierSubscription
        for model in (Subscription, VendorTierSubscription):
            sub = model.objects.filter(paystack_subscription_code=code).first()
            if sub:
                return sub
        return None

    def _handle_subscription_disable(self, data, webhook_event):
        from subscriptions.billing import expire_subscription
        sub = self._subscription_for_event(data)
        if sub:
            expire_subscription(sub, reason='Paystack subscription disabled', force=True)

    def _handle_subscription_not_renew(self, data, webhook_event):
        # Paystack sends this immediately on cancellation; already-paid time
        # remains usable until the stored end date.
        sub = self._subscription_for_event(data)
        if sub and sub.is_overdue:
            sub.expire_and_downgrade(reason='Paystack subscription will not renew')

    def _handle_invoice_create(self, data, webhook_event):
        sub = self._subscription_for_event(data)
        if sub and sub.is_overdue:
            sub.expire_and_downgrade(reason='Invoice for an expired subscription')

    def _handle_invoice_payment_failed(self, data, webhook_event):
        from subscriptions.billing import expire_subscription, queue_cancellation
        sub = self._subscription_for_event(data)
        if sub:
            expire_subscription(sub, reason='Subscription payment failed', force=True)
        else:
            # A replaced subscription can still have a live mandate remotely.
            nested = data.get('subscription') or {}
            code = nested.get('subscription_code') if isinstance(nested, dict) else nested
            if code:
                queue_cancellation(code, reason='Payment failed on a legacy subscription')

    # ── Dispute ──────────────────────────────────────────────

    def _handle_dispute_create(self, data, webhook_event):
        ps_id = data.get('id')
        if Dispute.objects.filter(paystack_dispute_id=ps_id).exists():
            return

        txn_ref = data.get('transaction', {}).get('reference', '')
        txn = Transaction.objects.filter(reference=txn_ref).first()
        if not txn:
            return

        Dispute.objects.create(
            paystack_dispute_id=ps_id,
            transaction=txn,
            user=txn.user,
            amount=data.get('amount', 0) / 100,
            currency=data.get('currency', 'ZAR'),
            status=data.get('status', 'pending'),
            category=data.get('category', 'general'),
            message=data.get('message', ''),
            due_at=data.get('due_at'),
            paystack_response=data,
        )

        PaymentLog.objects.create(
            transaction=txn,
            log_type='dispute_created',
            message=f'Dispute created via webhook: {ps_id}',
            response_data=data,
        )

    def _handle_dispute_remind(self, data, webhook_event):
        logger.info('Dispute reminder: %s', data.get('id'))

    def _handle_dispute_resolve(self, data, webhook_event):
        ps_id = data.get('id')
        try:
            dispute = Dispute.objects.get(paystack_dispute_id=ps_id)
        except Dispute.DoesNotExist:
            return

        dispute.status = data.get('status', 'resolved')
        dispute.resolution = data.get('resolution', '')
        dispute.resolved_at = timezone.now()
        dispute.paystack_response = data
        dispute.save()

        PaymentLog.objects.create(
            transaction=dispute.transaction,
            dispute=dispute,
            log_type='dispute_resolved',
            message=f'Dispute resolved via webhook: {ps_id}',
            response_data=data,
        )


# ═══════════════════════════════════════════════════════════════
# Vendor-Scoped Payment Views
# ═══════════════════════════════════════════════════════════════

def _resolve_vendor_payment(request, vendor_uuid):
    """
    Verify the authenticated user owns (or is admin for) the given vendor_uuid.
    Returns (vendor_profile, None) or (None, error Response).
    """
    from business.models import VendorProfile
    try:
        vp = VendorProfile.objects.get(id=vendor_uuid)
    except VendorProfile.DoesNotExist:
        return None, Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
    is_admin = (
        request.user.is_staff
        or hasattr(request.user, 'admin_profile')
        or getattr(request.user, 'user_type', '') == 'admin'
    )
    if not is_admin:
        user_vp = getattr(request.user, 'vendor_profile', None)
        if user_vp != vp:
            return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    return vp, None


class VendorPublicSubaccountView(generics.RetrieveAPIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/subaccount/
    Public — no JWT required. Returns the vendor's Paystack subaccount details.
    """
    serializer_class = PaystackSubaccountSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        from business.models import VendorProfile
        try:
            vp = VendorProfile.objects.get(id=self.kwargs['vendor_uuid'])
        except VendorProfile.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Vendor not found.')
        try:
            return PaystackSubaccount.objects.select_related('vendor').get(vendor=vp)
        except PaystackSubaccount.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('No subaccount found for this vendor.')


class VendorTransactionsView(generics.ListAPIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/transactions/
    JWT required. Returns transactions where Transaction.vendor matches the vendor.
    Supports ?status= and ?payment_intent= query filters.
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, err = _resolve_vendor_payment(self.request, self.kwargs['vendor_uuid'])
        if err:
            return Transaction.objects.none()
        qs = Transaction.objects.filter(vendor=vp).select_related(
            'order', 'user', 'vendor', 'subaccount', 'split',
        ).order_by('-created_at')
        txn_status = self.request.query_params.get('status')
        if txn_status:
            qs = qs.filter(status=txn_status)
        payment_intent = self.request.query_params.get('payment_intent')
        if payment_intent:
            qs = qs.filter(payment_intent=payment_intent)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor_payment(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class VendorTransactionDetailView(generics.RetrieveAPIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/transactions/<pk>/
    JWT required. Returns a single transaction belonging to the vendor.
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]

    def get_object(self):
        vp, err = _resolve_vendor_payment(self.request, self.kwargs['vendor_uuid'])
        if err:
            return None
        try:
            return Transaction.objects.select_related(
                'order', 'user', 'vendor', 'subaccount', 'split',
            ).get(pk=self.kwargs['pk'], vendor=vp)
        except Transaction.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Transaction not found.')

    def retrieve(self, request, *args, **kwargs):
        vp, err = _resolve_vendor_payment(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().retrieve(request, *args, **kwargs)


class VendorRefundsView(generics.ListAPIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/refunds/
    JWT required. Returns refunds for transactions where the vendor received funds.
    Supports ?status= query filter.
    """
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, err = _resolve_vendor_payment(self.request, self.kwargs['vendor_uuid'])
        if err:
            return Refund.objects.none()
        qs = Refund.objects.filter(
            Q(vendor=vp) | Q(transaction__vendor=vp)
        ).select_related(
            'transaction', 'user', 'order', 'restaurant_order', 'vendor',
            'approved_by',
        ).distinct().order_by('-created_at')
        refund_status = self.request.query_params.get('status')
        if refund_status:
            qs = qs.filter(status=refund_status)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor_payment(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class VendorTransactionChargesView(APIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/transactions/<pk>/charges/
    JWT required. Returns the Paystack charge breakdown for one of the
    vendor's transactions (Paystack fee, business share, vendor share).
    """
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]

    def get(self, request, vendor_uuid, pk):
        vp, err = _resolve_vendor_payment(request, vendor_uuid)
        if err:
            return err
        try:
            txn = Transaction.objects.select_related(
                'user', 'vendor', 'subaccount', 'split',
            ).get(pk=pk, vendor=vp)
        except Transaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        fresh = request.query_params.get('fresh') in ('1', 'true', 'yes')
        return Response(compute_charge_breakdown(txn, fresh=fresh))


class VendorChargesSummaryView(APIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/charges-summary/?from=YYYY-MM-DD&to=YYYY-MM-DD
    Aggregate charge totals for one vendor (Paystack fees, business share,
    and what the vendor itself received via subaccount payouts).
    """
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]

    def get(self, request, vendor_uuid):
        from decimal import Decimal
        from django.utils.dateparse import parse_date

        vp, err = _resolve_vendor_payment(request, vendor_uuid)
        if err:
            return err

        qs = Transaction.objects.filter(vendor=vp, status='success').select_related(
            'subaccount', 'split', 'user',
        )

        date_from = parse_date(request.query_params.get('from', '') or '')
        date_to = parse_date(request.query_params.get('to', '') or '')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        payment_intent = request.query_params.get('payment_intent')
        if payment_intent:
            qs = qs.filter(payment_intent=payment_intent)

        gross = Decimal('0.00')
        fees = Decimal('0.00')
        vendor_received = Decimal('0.00')
        count = 0

        for txn in qs.iterator():
            breakdown = compute_charge_breakdown(txn, fresh=False)
            gross += Decimal(breakdown['totals']['gross_amount'])
            fees += Decimal(breakdown['totals']['paystack_fee'])
            # Sum the lines that point to this vendor's subaccount
            for sub in breakdown['subaccounts']:
                if sub.get('vendor_id') == str(vp.id):
                    vendor_received += Decimal(sub['amount'])
            count += 1

        main_account_total = (gross - fees - vendor_received).quantize(Decimal('0.01'))

        return Response({
            'vendor_id': str(vp.id),
            'count': count,
            'filters': {
                'from': date_from.isoformat() if date_from else None,
                'to': date_to.isoformat() if date_to else None,
                'payment_intent': payment_intent,
            },
            'totals': {
                'gross_amount': str(gross.quantize(Decimal('0.01'))),
                'paystack_fee': str(fees.quantize(Decimal('0.01'))),
                'vendor_received': str(vendor_received.quantize(Decimal('0.01'))),
                'main_account_total': str(main_account_total),
            },
        })


class VendorDisputesView(generics.ListAPIView):
    """
    GET /api/payments/vendor/<vendor_uuid>/disputes/
    JWT required. Returns disputes on transactions where the vendor received funds.
    Supports ?status= query filter.
    """
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, err = _resolve_vendor_payment(self.request, self.kwargs['vendor_uuid'])
        if err:
            return Dispute.objects.none()
        qs = Dispute.objects.filter(
            Q(vendor=vp) | Q(transaction__vendor=vp)
        ).select_related(
            'transaction', 'user', 'order', 'restaurant_order', 'vendor',
        ).prefetch_related('transaction__refunds').distinct().order_by('-created_at')
        dispute_status = self.request.query_params.get('status')
        if dispute_status:
            qs = qs.filter(status=dispute_status)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor_payment(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)

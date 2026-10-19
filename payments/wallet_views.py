"""Wallet + payout REST endpoints.

Splits by audience:

    Vendor / Driver (the wallet owner):
        GET  /api/payments/marketplace/me/wallet/
        GET  /api/payments/marketplace/me/wallet/transactions/
        GET  /api/payments/marketplace/me/payouts/

    Admin (Super Admin or financial_access):
        GET  /api/payments/marketplace/admin/wallets/
        GET  /api/payments/marketplace/admin/wallets/<id>/
        POST /api/payments/marketplace/admin/wallets/<id>/adjust/    (credit/debit)
        POST /api/payments/marketplace/admin/wallets/<id>/freeze/
        POST /api/payments/marketplace/admin/wallets/<id>/unfreeze/

        GET  /api/payments/marketplace/admin/payouts/
        GET  /api/payments/marketplace/admin/payouts/<id>/
        POST /api/payments/marketplace/admin/payouts/initiate/       (manual payout)
        POST /api/payments/marketplace/admin/payouts/<id>/retry/

        GET  /api/payments/marketplace/admin/recipients/
        GET  /api/payments/marketplace/admin/recipients/<id>/

        GET  /api/payments/marketplace/admin/overview/               (dashboard stats)
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .paystack import paystack_api
from .wallet_models import PaystackRecipient, Payout, Wallet, WalletTransaction


# ─── Paystack error translation ───────────────────────────────────────────────
#
# Paystack returns terse messages that hide the *cause* — most commonly a
# KYC-tier restriction on the platform's own Paystack business profile.
# Map the well-known phrases to admin-actionable guidance so the dashboard
# never shows raw Paystack-ese.
_PAYSTACK_TRANSLATIONS = (
    (
        'third party payouts',
        "Your Paystack business is on the 'Starter' tier, which can only "
        "send transfers back to the business's own bank account. To pay "
        "vendors and drivers (third-party recipients) you must upgrade to "
        "'Registered Business' on the Paystack Dashboard "
        "(Settings -> Compliance) — upload CIPC / company docs, director ID, "
        "and proof of business. Once Paystack approves the upgrade, "
        "retry the payout.",
    ),
    (
        'balance is not sufficient',
        "Paystack settled-balance is too low to cover this transfer. "
        "Wait for customer payments to clear out of pending into available "
        "balance, or top up the Paystack account.",
    ),
    (
        'transfer recipient',
        "Paystack does not recognise this transfer recipient. The RCP "
        "code may have been deleted on the Paystack side — re-submit the "
        "recipient's bank details to mint a fresh one.",
    ),
    (
        'otp',
        "Paystack requires an OTP for this transfer. Disable the "
        "'OTP for transfers' option in Settings -> Preferences on the "
        "Paystack Dashboard, or finalise the transfer there directly.",
    ),
)


def _translate_paystack_error(raw: str) -> str:
    """Return an actionable message when we recognise the Paystack error."""
    needle = (raw or '').lower()
    for fragment, friendly in _PAYSTACK_TRANSLATIONS:
        if fragment in needle:
            return friendly
    return raw or 'Paystack rejected the transfer.'


def _refund_failed_payout(*, wallet, amount, payout, reason: str):
    """Refund a wallet via a proper reversal row when a payout fails.

    Two-step process:

      1. Skip if a reversal row already exists for this payout (defends
         against double-refund if the failure path runs twice).
      2. Otherwise create a `TYPE_REVERSAL` credit row referencing the
         payout so ``Recompute from ledger`` re-derives the wallet
         balance correctly and "Available balance" never reflects a
         failed payout.
    """
    if WalletTransaction.objects.filter(
        payout=payout, transaction_type=WalletTransaction.TYPE_REVERSAL,
    ).exists():
        return
    wallet.credit(
        amount,
        transaction_type=WalletTransaction.TYPE_REVERSAL,
        reference=payout.reference,
        description=reason[:255],
    )
    # Link the reversal row to the payout so the audit trail keeps
    # both sides of the trace.
    WalletTransaction.objects.filter(
        wallet=wallet, payout__isnull=True,
        transaction_type=WalletTransaction.TYPE_REVERSAL,
        reference=payout.reference,
    ).update(payout=payout)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _admin_profile(request):
    return getattr(request.user, 'admin_profile', None)


def _can_manage_payments(profile):
    if profile is None:
        return False
    if profile.is_super_admin:
        return True
    return bool(profile.has_permission('financial_access'))


def _serialise_wallet(w, *, include_owner=True):
    owner_info = None
    if include_owner:
        owner_info = _resolve_owner(w.owner_type, w.owner_id)
    return {
        'id': str(w.id),
        'owner_type': w.owner_type,
        'owner_id': w.owner_id,
        'owner': owner_info,
        'balance': str(w.balance),
        'is_frozen': w.is_frozen,
        'created_at': w.created_at.isoformat(),
        'updated_at': w.updated_at.isoformat(),
    }


def _serialise_transaction(t):
    return {
        'id': str(t.id),
        'wallet_id': str(t.wallet_id),
        'transaction_type': t.transaction_type,
        'credit': str(t.credit),
        'debit': str(t.debit),
        'reference': t.reference,
        'description': t.description,
        'status': t.status,
        'order_id': str(t.order_id) if t.order_id else None,
        'restaurant_order_id': str(t.restaurant_order_id) if t.restaurant_order_id else None,
        'payout_id': str(t.payout_id) if t.payout_id else None,
        'created_at': t.created_at.isoformat(),
        # `order_breakdown` is non-null whenever this ledger row is
        # tied to a real order — drives the per-transaction
        # "show calculation" affordance on the admin screen.
        'order_breakdown': _order_breakdown(t),
    }


# ─── Per-transaction breakdown ────────────────────────────────────────────────

def _money(value):
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal('0.01'))


def _fmt(value) -> str:
    """Two-decimal string for embedding inline in formulas."""
    return f'{_money(value):.2f}'


def _order_breakdown(t):
    """Compute the full per-order financial breakdown for a wallet
    transaction, when the transaction is linked to an order.

    Returns ``None`` for adjustments / payouts that have no order
    backing. Otherwise returns a dict with raw numbers + a
    ``formulas`` list of human-readable equations the admin screen
    renders verbatim under each transaction.
    """
    order = getattr(t, 'order', None)
    restaurant_order = getattr(t, 'restaurant_order', None)
    if order is None and restaurant_order is None:
        return None

    if order is not None:
        return _breakdown_for_retail_order(order, t)
    return _breakdown_for_restaurant_order(restaurant_order, t)


def _breakdown_for_retail_order(order, t):
    items_amount    = _money(order.subtotal)
    delivery_fee    = _money(order.shipping_cost)
    service_fee     = _money(order.service_fee)
    service_pct     = _money(getattr(order, 'service_fee_percent', 0))
    commission_pct  = _money(order.commission_percent)
    commission_amt  = _money(order.commission_amount)
    paystack_fee    = _money(order.paystack_fee)
    vendor_payout   = _money(order.vendor_payout)
    is_delivery     = (order.fulfillment_type or '').lower() == 'delivery'
    delivery_kept   = delivery_fee if is_delivery else Decimal('0.00')
    platform_rev    = service_fee + commission_amt - paystack_fee
    customer_paid   = _money(order.total_amount)
    vendor          = order.primary_vendor
    business_cat    = getattr(vendor, 'business_category', 'retail') if vendor else 'retail'

    return _assemble_breakdown(
        order_number=order.order_number,
        business_category=business_cat,
        fulfillment_type=order.fulfillment_type or '',
        is_delivery=is_delivery,
        items_amount=items_amount,
        delivery_fee=delivery_fee,
        delivery_kept=delivery_kept,
        service_fee=service_fee,
        service_pct=service_pct,
        commission_pct=commission_pct,
        commission_amount=commission_amt,
        paystack_fee=paystack_fee,
        vendor_payout=vendor_payout,
        platform_revenue=platform_rev,
        customer_paid=customer_paid,
        transaction_type=t.transaction_type,
    )


def _breakdown_for_restaurant_order(order, t):
    items_amount    = _money(order.subtotal)
    delivery_fee    = _money(getattr(order, 'delivery_fee', 0))
    service_fee     = _money(getattr(order, 'service_fee', 0))
    service_pct     = _money(getattr(order, 'service_fee_percent', 0))
    commission_pct  = _money(getattr(order, 'commission_percent', 0))
    commission_amt  = _money(getattr(order, 'commission_amount', 0))
    paystack_fee    = _money(getattr(order, 'paystack_fee', 0))
    vendor_payout   = _money(getattr(order, 'vendor_payout', 0))
    is_delivery     = (getattr(order, 'fulfillment_type', '') or '').lower() == 'delivery'
    delivery_kept   = delivery_fee if is_delivery else Decimal('0.00')
    platform_rev    = service_fee + commission_amt - paystack_fee
    customer_paid   = _money(getattr(order, 'total_amount', items_amount + delivery_fee + service_fee))

    return _assemble_breakdown(
        order_number=getattr(order, 'order_number', ''),
        business_category='restaurant',
        fulfillment_type=getattr(order, 'fulfillment_type', '') or '',
        is_delivery=is_delivery,
        items_amount=items_amount,
        delivery_fee=delivery_fee,
        delivery_kept=delivery_kept,
        service_fee=service_fee,
        service_pct=service_pct,
        commission_pct=commission_pct,
        commission_amount=commission_amt,
        paystack_fee=paystack_fee,
        vendor_payout=vendor_payout,
        platform_revenue=platform_rev,
        customer_paid=customer_paid,
        transaction_type=t.transaction_type,
    )


def _assemble_breakdown(
    *, order_number, business_category, fulfillment_type, is_delivery,
    items_amount, delivery_fee, delivery_kept, service_fee, service_pct,
    commission_pct, commission_amount, paystack_fee,
    vendor_payout, platform_revenue, customer_paid, transaction_type,
):
    """Build the breakdown dict shared by retail + restaurant orders."""
    pickup_note = '' if is_delivery else ' (pickup → 0)'
    formulas = [
        f"Customer paid = Items + Delivery + Service "
        f"= R{_fmt(items_amount)} + R{_fmt(delivery_fee)} + R{_fmt(service_fee)} "
        f"= R{_fmt(customer_paid)}",
        f"Commission = Items × Commission % "
        f"= R{_fmt(items_amount)} × {_fmt(commission_pct)}% "
        f"= R{_fmt(commission_amount)}",
        f"Vendor Payout = Items − Commission "
        f"= R{_fmt(items_amount)} − R{_fmt(commission_amount)} "
        f"= R{_fmt(vendor_payout)}",
        f"Driver Earnings = Delivery Fee{pickup_note} "
        f"= R{_fmt(delivery_kept)}",
        f"Platform Revenue = Service Fee + Commission − Paystack Fee "
        f"= R{_fmt(service_fee)} + R{_fmt(commission_amount)} − R{_fmt(paystack_fee)} "
        f"= R{_fmt(platform_revenue)}",
    ]
    notes = [
        "Commission is taken off the items amount only — never off the "
        "delivery or service fee.",
        "Vendor receives the items amount minus commission — the service "
        "fee and delivery fee never flow to the vendor.",
    ]
    if not is_delivery:
        notes.append(
            "Pickup orders: delivery fee is zero, no driver earnings line."
        )
    if paystack_fee == 0:
        notes.append(
            "Paystack fee is R0.00 here — either the fee has not posted "
            "yet (it arrives on the verify / webhook), or this row pre-dates "
            "Paystack fee tracking."
        )
    if transaction_type == WalletTransaction.TYPE_DELIVERY_ESCROW:
        notes.append(
            "This row is the delivery fee held in escrow on the platform "
            "ledger while we wait for a driver. It will move to the "
            "driver's wallet when one is assigned."
        )
    return {
        'order_number': order_number,
        'business_category': business_category,
        'fulfillment_type': fulfillment_type,
        'is_delivery': is_delivery,
        'items_amount': str(items_amount),
        'delivery_fee': str(delivery_fee),
        'delivery_kept': str(delivery_kept),
        'service_fee': str(service_fee),
        'service_fee_percent': str(service_pct),
        'commission_percent': str(commission_pct),
        'commission_amount': str(commission_amount),
        'paystack_fee': str(paystack_fee),
        'vendor_payout': str(vendor_payout),
        'driver_earnings': str(delivery_kept),
        'platform_revenue': str(platform_revenue),
        'customer_paid': str(customer_paid),
        'formulas': formulas,
        'notes': notes,
    }


def _serialise_payout(p):
    return {
        'id': str(p.id),
        'owner_type': p.owner_type,
        'owner_id': p.owner_id,
        'owner': _resolve_owner(p.owner_type, p.owner_id),
        'recipient_code': p.recipient.recipient_code if p.recipient_id else '',
        'recipient_id': str(p.recipient_id) if p.recipient_id else None,
        'amount': str(p.amount),
        'currency': p.currency,
        'reason': p.reason,
        'reference': p.reference,
        'transfer_code': p.transfer_code,
        'status': p.status,
        'failure_reason': p.failure_reason,
        'created_by_email': p.created_by.email if p.created_by_id else None,
        'created_at': p.created_at.isoformat(),
        'updated_at': p.updated_at.isoformat(),
        'completed_at': p.completed_at.isoformat() if p.completed_at else None,
    }


def _serialise_recipient(r):
    if r is None:
        return None
    return {
        'id': str(r.id),
        'owner_type': r.owner_type,
        'owner_id': r.owner_id,
        'owner': _resolve_owner(r.owner_type, r.owner_id),
        'business_name': r.business_name,
        'bank_code': r.bank_code,
        'bank_name': r.bank_name,
        'account_number': r.account_number,
        'submitted_account_name': r.submitted_account_name,
        'resolved_account_name': r.resolved_account_name,
        'recipient_code': r.recipient_code,
        'verification_status': r.verification_status,
        'bank_verified': r.bank_verified,
        'payout_enabled': r.payout_enabled,
        'archived_at': r.archived_at.isoformat() if r.archived_at else None,
        'notes': r.notes,
        'created_at': r.created_at.isoformat(),
        'updated_at': r.updated_at.isoformat(),
    }


def _resolve_owner(owner_type, owner_id):
    """Best-effort: return a small dict describing the wallet/payout owner."""
    if owner_type == Wallet.OWNER_PLATFORM:
        return {'label': 'Platform revenue ledger'}
    try:
        if owner_type in (Wallet.OWNER_VENDOR, PaystackRecipient.OWNER_VENDOR):
            from business.models import VendorProfile
            v = VendorProfile.objects.filter(id=owner_id).first()
            if v:
                return {
                    'id': str(v.id),
                    'label': v.trading_name or v.name or v.user.email,
                    'email': v.user.email,
                    'business_category': v.business_category,
                }
        if owner_type in (Wallet.OWNER_DRIVER, PaystackRecipient.OWNER_DRIVER):
            from delivery.models import DeliveryDriver
            d = DeliveryDriver.objects.filter(id=owner_id).first()
            if d:
                return {
                    'id': str(d.id),
                    'label': f'{d.user.first_name} {d.user.last_name}'.strip() or d.user.email,
                    'email': d.user.email,
                }
    except Exception:
        pass
    return {'id': owner_id, 'label': owner_id}


def _vendor_for(request):
    return getattr(request.user, 'vendor_profile', None)


def _driver_for(request):
    return getattr(request.user, 'driver_profile', None)


# ─── Owner-facing (vendor / driver) ───────────────────────────────────────────

class MyWalletView(APIView):
    """Returns the wallet for the calling vendor or driver."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet, _scope = _resolve_caller_wallet(request)
        if wallet is None:
            return Response(
                {'error': 'No vendor or driver profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(_serialise_wallet(wallet, include_owner=False))


class MyWalletTransactionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet, _scope = _resolve_caller_wallet(request)
        if wallet is None:
            return Response(
                {'error': 'No vendor or driver profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        limit = max(1, min(int(request.query_params.get('limit', 50)), 200))
        qs = (
            wallet.transactions
            .select_related('order', 'restaurant_order')
            .all()[:limit]
        )
        return Response({
            'wallet_balance': str(wallet.balance),
            'count': qs.count() if False else len(qs),
            'results': [_serialise_transaction(t) for t in qs],
        })


class MyPayoutsView(APIView):
    """Payouts for the calling vendor or driver."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        owner_type, owner_id = _caller_owner(request)
        if owner_type is None:
            return Response(
                {'error': 'No vendor or driver profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = Payout.objects.filter(
            owner_type=owner_type, owner_id=str(owner_id),
        ).select_related('recipient').order_by('-created_at')
        return Response({
            'count': qs.count(),
            'results': [_serialise_payout(p) for p in qs[:100]],
        })


def _resolve_caller_wallet(request):
    """Pick the wallet for whichever profile the caller has."""
    vendor = _vendor_for(request)
    if vendor:
        return Wallet.for_vendor(vendor), 'vendor'
    driver = _driver_for(request)
    if driver:
        return Wallet.for_driver(driver), 'driver'
    return None, None


def _caller_owner(request):
    vendor = _vendor_for(request)
    if vendor:
        return Wallet.OWNER_VENDOR, vendor.id
    driver = _driver_for(request)
    if driver:
        return Wallet.OWNER_DRIVER, driver.id
    return None, None


# ─── Admin: wallets ───────────────────────────────────────────────────────────

class AdminWalletListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        owner_type = request.query_params.get('owner_type')
        qs = Wallet.objects.all().order_by('-balance')
        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        # Aggregates for the overview card
        totals = Wallet.objects.aggregate(
            total_balance=Sum('balance'),
            count=Count('id'),
        )
        per_type = {
            row['owner_type']: row
            for row in Wallet.objects.values('owner_type')
            .annotate(total_balance=Sum('balance'), count=Count('id'))
        }
        return Response({
            'total_balance': str(totals['total_balance'] or Decimal('0.00')),
            'wallet_count': totals['count'] or 0,
            'per_type': {
                k: {'total_balance': str(v['total_balance'] or 0), 'count': v['count']}
                for k, v in per_type.items()
            },
            'results': [_serialise_wallet(w) for w in qs[:200]],
        })


class AdminWalletDetailView(APIView):
    """GET / DELETE for a single wallet.

    DELETE is only allowed on **non-platform** wallets with a zero
    balance. The platform revenue ledger is permanent. Passing
    `?force=1` archives a non-zero wallet by first zeroing the balance
    with an admin adjustment row — the audit trail (WalletTransaction)
    is preserved so the wallet can be reconstructed.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, wallet_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        txns = list(
            wallet.transactions
            .select_related('order', 'restaurant_order')
            .all()[:100]
        )
        # Surface the active recipient + any pending payouts on the
        # detail payload so the admin sheet can render a full overview
        # without an extra round trip.
        recipient = PaystackRecipient.objects.filter(
            owner_type=wallet.owner_type, owner_id=wallet.owner_id,
            archived_at__isnull=True,
        ).first()
        pending_payouts = Payout.objects.filter(
            owner_type=wallet.owner_type, owner_id=wallet.owner_id,
            status__in=[Payout.STATUS_PENDING, Payout.STATUS_PROCESSING],
        ).order_by('-created_at')
        return Response({
            'wallet': _serialise_wallet(wallet),
            'transactions': [_serialise_transaction(t) for t in txns],
            'recipient': _serialise_recipient(recipient),
            'pending_payouts': [_serialise_payout(p) for p in pending_payouts],
        })

    def delete(self, request, wallet_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if wallet.owner_type == Wallet.OWNER_PLATFORM:
            return Response(
                {'error': 'The platform revenue ledger cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Block deletion when payouts are mid-flight; the wallet has
        # already been debited so the transfer would orphan.
        if Payout.objects.filter(
            owner_type=wallet.owner_type, owner_id=wallet.owner_id,
            status__in=[Payout.STATUS_PENDING, Payout.STATUS_PROCESSING],
        ).exists():
            return Response(
                {'error': 'Wallet has in-flight payouts. Wait for them to settle.'},
                status=status.HTTP_409_CONFLICT,
            )
        force = str(request.query_params.get('force', '')).lower() in ('1', 'true', 'yes')
        if wallet.balance > 0 and not force:
            return Response(
                {'error': f'Wallet balance R{wallet.balance} is non-zero. '
                          'Pass ?force=1 to write-off and delete.'},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            if wallet.balance > 0:
                wallet.debit(
                    wallet.balance,
                    transaction_type=WalletTransaction.TYPE_ADJUSTMENT,
                    description=f'Wallet archived by {request.user.email} '
                                f'(write-off R{wallet.balance}).',
                )
            wallet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminWalletAdjustView(APIView):
    """Manual credit or debit by an admin — audit-trailed."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, wallet_id):
        profile = _admin_profile(request)
        if not _can_manage_payments(profile):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        action = (request.data.get('action') or '').lower()
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except Exception:
            return Response({'error': 'Invalid amount.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({'error': 'Amount must be positive.'},
                            status=status.HTTP_400_BAD_REQUEST)
        reference = request.data.get('reference', '')
        description = request.data.get('description', f'Manual {action} by {request.user.email}')
        try:
            if action == 'credit':
                wallet.credit(
                    amount,
                    transaction_type=WalletTransaction.TYPE_ADJUSTMENT,
                    reference=reference, description=description,
                )
            elif action == 'debit':
                wallet.debit(
                    amount,
                    transaction_type=WalletTransaction.TYPE_ADJUSTMENT,
                    reference=reference, description=description,
                )
            else:
                return Response(
                    {'error': "action must be 'credit' or 'debit'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        wallet.refresh_from_db()
        return Response(_serialise_wallet(wallet))


class AdminWalletRecomputeView(APIView):
    """Rewrite a wallet's `balance` from the sum of its ledger rows.

    The wallet table caches a running balance for read performance,
    but the WalletTransaction table is the source of truth. When
    pre-redesign settlements left a wallet out of sync (e.g. duplicate
    credits, a debit that overshot, manual SQL fixes), this endpoint
    rebases the cached balance to ``Σcredit − Σdebit`` across all
    success-status rows.

    Returns the wallet before + after along with the delta applied.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, wallet_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        totals = wallet.transactions.filter(
            status=WalletTransaction.STATUS_SUCCESS,
        ).aggregate(
            credits=Sum('credit'),
            debits=Sum('debit'),
        )
        derived = (totals['credits'] or Decimal('0.00')) - (totals['debits'] or Decimal('0.00'))
        derived = derived.quantize(Decimal('0.01'))
        previous = wallet.balance
        wallet.balance = derived
        wallet.save(update_fields=['balance', 'updated_at'])
        return Response({
            'wallet': _serialise_wallet(wallet),
            'previous_balance': str(previous),
            'derived_balance': str(derived),
            'delta': str(derived - previous),
        })


class AdminReleaseDriverEscrowView(APIView):
    """Sweep delivery-fee escrow rows into the assigned driver's wallet.

    Historically `settle_order` parked the delivery fee on the
    platform ledger tagged ``TYPE_DELIVERY_ESCROW`` when the driver
    wasn't yet assigned. The handover to `credit_driver_earning`
    happens automatically when the driver marks the job delivered,
    but legacy rows already on the platform ledger never got swept.

    This endpoint walks every escrow row whose linked order has a
    delivered DeliveryJob and releases the fee into the driver's
    wallet. Idempotent — `credit_driver_earning` skips rows that
    already produced a driver-earning entry.

    Returns ``{released_count, total_released, errors}``.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        from payments.settlement import credit_driver_earning
        from delivery.models import DeliveryJob

        platform = Wallet.platform_ledger()
        escrow_rows = platform.transactions.filter(
            transaction_type=WalletTransaction.TYPE_DELIVERY_ESCROW,
            credit__gt=0,  # only original parks, not later debits
        ).select_related('order', 'restaurant_order')

        released_count = 0
        total = Decimal('0.00')
        errors = []
        for row in escrow_rows:
            # Skip if already released (driver-earning row exists for
            # this reference).
            if WalletTransaction.objects.filter(
                reference=row.reference,
                transaction_type=WalletTransaction.TYPE_DRIVER_EARNING,
            ).exists():
                continue
            order = row.order
            restaurant_order = row.restaurant_order
            job = None
            if order is not None:
                job = DeliveryJob.objects.filter(
                    retail_order=order,
                ).select_related('driver').first()
            elif restaurant_order is not None:
                job = DeliveryJob.objects.filter(
                    restaurant_order=restaurant_order,
                ).select_related('driver').first()
            if job is None or job.driver_id is None:
                continue
            try:
                result = credit_driver_earning(
                    order, job.driver,
                    restaurant_order=restaurant_order,
                )
                if not result.get('skipped'):
                    released_count += 1
                    total += Decimal(str(result.get('driver_credit', 0)))
            except Exception as exc:
                errors.append({
                    'reference': row.reference,
                    'error': str(exc),
                })
        return Response({
            'released_count': released_count,
            'total_released': str(total),
            'errors': errors,
        })


class AdminWalletFreezeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, wallet_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        freeze = self.kwargs.get('action') != 'unfreeze'  # default freeze
        wallet.is_frozen = freeze
        wallet.save(update_fields=['is_frozen', 'updated_at'])
        return Response(_serialise_wallet(wallet))


# ─── Admin: payouts ───────────────────────────────────────────────────────────

class AdminPayoutListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        qs = Payout.objects.select_related('recipient').order_by('-created_at')
        owner_type = request.query_params.get('owner_type')
        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        # Aggregates for the dashboard. Failed payouts are EXCLUDED
        # from `total_amount` — the money never left the platform, so
        # counting it as "transferred" would overstate outflow. They
        # still get a standalone `failed_count` for visibility.
        totals = Payout.objects.aggregate(
            total_amount=Sum(
                'amount',
                filter=~Q(status=Payout.STATUS_FAILED),
            ),
            success_amount=Sum(
                'amount', filter=Q(status=Payout.STATUS_SUCCESS),
            ),
            pending_count=Count(
                'id',
                filter=Q(status__in=[
                    Payout.STATUS_PENDING, Payout.STATUS_PROCESSING,
                ]),
            ),
            failed_count=Count(
                'id', filter=Q(status=Payout.STATUS_FAILED),
            ),
        )
        return Response({
            'total_amount': str(totals['total_amount'] or Decimal('0.00')),
            'success_amount': str(totals['success_amount'] or Decimal('0.00')),
            'pending_count': totals['pending_count'] or 0,
            'failed_count': totals['failed_count'] or 0,
            'results': [_serialise_payout(p) for p in qs[:200]],
        })


class AdminPayoutDetailView(APIView):
    """GET / PATCH / DELETE a single payout.

    DELETE is only allowed for failed payouts (Paystack rejected) — a
    successful or in-flight transfer represents real money movement
    and stays on the audit trail forever.
    PATCH lets admins amend `reason` or `failure_reason` notes.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payout_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            p = Payout.objects.select_related('recipient').get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        ledger = [
            _serialise_transaction(t)
            for t in p.ledger_entries.select_related('order', 'restaurant_order').all()
        ]
        data = _serialise_payout(p)
        data['ledger_entries'] = ledger
        data['recipient'] = _serialise_recipient(p.recipient)
        return Response(data)

    def patch(self, request, payout_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            p = Payout.objects.select_related('recipient').get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        # Only the narrative fields are editable — amount / recipient /
        # status are immutable once the transfer leaves the system.
        editable = {'reason', 'failure_reason'}
        dirty = []
        for field in editable:
            if field in request.data:
                value = request.data.get(field) or ''
                setattr(p, field, str(value)[:1000])
                dirty.append(field)
        if not dirty:
            return Response({'error': 'No editable fields provided.'},
                            status=status.HTTP_400_BAD_REQUEST)
        dirty.append('updated_at')
        p.save(update_fields=dirty)
        return Response(_serialise_payout(p))

    def delete(self, request, payout_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            p = Payout.objects.get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if p.status != Payout.STATUS_FAILED:
            return Response(
                {'error': f'Only failed payouts can be deleted. '
                          f'This payout is "{p.status}".'},
                status=status.HTTP_409_CONFLICT,
            )
        # The original debit/refund ledger rows are kept (reference
        # column makes them recoverable) — we just nullify the FK so
        # the row stays as an audit breadcrumb pointing at nothing.
        WalletTransaction.objects.filter(payout=p).update(payout=None)
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminPayoutInitiateView(APIView):
    """Initiate a payout immediately for a single wallet.

    Body:
      {
        "wallet_id": "<uuid>",      // OR owner_type + owner_id
        "amount":    "<decimal>",   // defaults to full wallet balance
        "reason":    "Weekly settlement"
      }

    Performs the Paystack `/transfer` call inline; success/failure
    later updated via webhook (`transfer.success` / `transfer.failed`).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = _admin_profile(request)
        if not _can_manage_payments(profile):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        # Identify the wallet
        wallet = None
        if request.data.get('wallet_id'):
            wallet = Wallet.objects.filter(id=request.data['wallet_id']).first()
        elif request.data.get('owner_type') and request.data.get('owner_id'):
            wallet = Wallet.objects.filter(
                owner_type=request.data['owner_type'],
                owner_id=str(request.data['owner_id']),
            ).first()
        if wallet is None:
            return Response({'error': 'Wallet not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if wallet.owner_type == Wallet.OWNER_PLATFORM:
            return Response({'error': 'Cannot initiate transfers from the platform ledger.'},
                            status=status.HTTP_400_BAD_REQUEST)

        recipient = PaystackRecipient.objects.filter(
            owner_type=wallet.owner_type,
            owner_id=wallet.owner_id,
            archived_at__isnull=True,
            bank_verified=True,
            payout_enabled=True,
        ).first()
        if recipient is None or not recipient.recipient_code:
            return Response(
                {'error': 'No verified recipient on file for this wallet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(request.data.get('amount') or wallet.balance))
        except Exception:
            return Response({'error': 'Invalid amount.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({'error': 'Amount must be positive.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if amount > wallet.balance:
            return Response(
                {'error': f'Wallet balance R{wallet.balance} insufficient for R{amount}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if wallet.is_frozen:
            return Response({'error': 'Wallet is frozen.'},
                            status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason') or 'Marketplace settlement'
        reference = f'PAYOUT_{timezone.now().strftime("%Y%m%d%H%M%S")}_{wallet.id.hex[:8]}'

        with transaction.atomic():
            payout = Payout.objects.create(
                owner_type=wallet.owner_type,
                owner_id=wallet.owner_id,
                recipient=recipient,
                amount=amount,
                reason=reason,
                reference=reference,
                status=Payout.STATUS_PROCESSING,
                created_by=request.user,
            )
            # Debit the wallet up-front. If the Paystack call fails we
            # refund inline below.
            wallet.debit(
                amount,
                transaction_type=WalletTransaction.TYPE_PAYOUT,
                reference=reference, payout=payout,
                description=f'Payout via {recipient.recipient_code}',
            )

        # Outside the transaction — Paystack call is slow.
        try:
            result = paystack_api.initiate_transfer(
                source='balance',
                recipient=recipient.recipient_code,
                amount=int((amount * Decimal('100')).quantize(Decimal('1'))),
                reason=reason,
                reference=reference,
            )
        except Exception as exc:
            # Refund the wallet via a proper reversal row so the
            # ledger stays balanced (debit + reversal credit net to 0).
            # A failed payout must NOT linger on the wallet balance —
            # the money never left, so the balance must show as if the
            # payout was never raised.
            _refund_failed_payout(
                wallet=wallet, amount=amount, payout=payout,
                reason=f'Paystack request error: {exc}',
            )
            payout.mark_failed(f'Paystack request error: {exc}')
            return Response(
                {'error': f'Transfer initiation failed: {exc}',
                 'payout': _serialise_payout(payout)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not result.get('status'):
            # Refund + mark failed. Translate well-known Paystack error
            # phrases into actionable admin guidance — the raw message
            # ("You cannot initiate third party payouts as a starter
            # business") tells you nothing about how to unblock.
            raw_message = result.get('message', 'Paystack rejected the transfer.')
            friendly = _translate_paystack_error(raw_message)
            _refund_failed_payout(
                wallet=wallet, amount=amount, payout=payout,
                reason=f'Refund — {friendly}',
            )
            payout.mark_failed(friendly, response=result)
            return Response(
                {
                    'error': friendly,
                    'paystack_error': raw_message,
                    'payout': _serialise_payout(payout),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = result.get('data') or {}
        payout.transfer_code = data.get('transfer_code', '')
        payout.paystack_transfer_id = data.get('id')
        payout.paystack_response = result
        # Paystack may finalise sync (`success`) or async (webhook).
        ps_status = (data.get('status') or '').lower()
        if ps_status in ('success', 'successful'):
            payout.mark_success(
                transfer_code=payout.transfer_code,
                transfer_id=payout.paystack_transfer_id,
                response=result,
            )
        else:
            payout.status = Payout.STATUS_PROCESSING
            payout.save(update_fields=[
                'transfer_code', 'paystack_transfer_id', 'paystack_response',
                'status', 'updated_at',
            ])

        return Response(_serialise_payout(payout),
                        status=status.HTTP_201_CREATED)


class AdminPayoutRetryView(APIView):
    """Retry a failed payout. Equivalent to deleting + re-creating with
    the same amount, but preserves the audit row."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, payout_id):
        profile = _admin_profile(request)
        if not _can_manage_payments(profile):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            failed = Payout.objects.get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if failed.status != Payout.STATUS_FAILED:
            return Response({'error': 'Only failed payouts can be retried.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Just re-initiate using the same wallet + recipient + amount.
        request._full_data = {
            'owner_type': failed.owner_type,
            'owner_id': failed.owner_id,
            'amount': str(failed.amount),
            'reason': failed.reason,
        }
        return AdminPayoutInitiateView().post(request)


# ─── Admin: recipients ────────────────────────────────────────────────────────

class AdminRecipientListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        qs = PaystackRecipient.objects.all().order_by('-created_at')
        owner_type = request.query_params.get('owner_type')
        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        verification = request.query_params.get('verification_status')
        if verification:
            qs = qs.filter(verification_status=verification)
        return Response({
            'pending_review': qs.filter(
                verification_status=PaystackRecipient.VERIFICATION_MANUAL_REVIEW,
                archived_at__isnull=True,
            ).count(),
            'results': [_serialise_recipient(r) for r in qs[:200]],
        })


class AdminRecipientDetailView(APIView):
    """GET / PATCH / DELETE a single Paystack transfer recipient.

    DELETE archives the row (sets ``archived_at``) so the owner can
    onboard fresh bank details. Hard delete is blocked because past
    payouts FK to the recipient via PROTECT.
    PATCH lets admins amend `business_name`, `bank_name`, or `notes`.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, recipient_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            r = PaystackRecipient.objects.get(id=recipient_id)
        except PaystackRecipient.DoesNotExist:
            return Response({'error': 'Recipient not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        payouts = Payout.objects.filter(
            recipient=r,
        ).order_by('-created_at')[:25]
        data = _serialise_recipient(r)
        data['payouts'] = [_serialise_payout(p) for p in payouts]
        return Response(data)

    def patch(self, request, recipient_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            r = PaystackRecipient.objects.get(id=recipient_id)
        except PaystackRecipient.DoesNotExist:
            return Response({'error': 'Recipient not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        editable = {'business_name', 'bank_name', 'notes'}
        dirty = []
        for field in editable:
            if field in request.data:
                value = request.data.get(field) or ''
                setattr(r, field, str(value)[:255])
                dirty.append(field)
        # Admins can also flip payout_enabled on a verified row.
        if 'payout_enabled' in request.data:
            r.payout_enabled = bool(request.data.get('payout_enabled'))
            dirty.append('payout_enabled')
        if not dirty:
            return Response({'error': 'No editable fields provided.'},
                            status=status.HTTP_400_BAD_REQUEST)
        dirty.append('updated_at')
        r.save(update_fields=dirty)
        return Response(_serialise_recipient(r))

    def delete(self, request, recipient_id):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            r = PaystackRecipient.objects.get(id=recipient_id)
        except PaystackRecipient.DoesNotExist:
            return Response({'error': 'Recipient not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if r.archived_at is not None:
            return Response({'error': 'Recipient is already archived.'},
                            status=status.HTTP_409_CONFLICT)
        reason = (request.data.get('reason') if hasattr(request, 'data') else '') \
            or 'Archived by admin.'
        r.archive(reason=reason)
        return Response(_serialise_recipient(r))


# ─── Admin: overview ──────────────────────────────────────────────────────────

class AdminMarketplaceOverviewView(APIView):
    """One-shot dashboard payload — totals + recent activity."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _can_manage_payments(_admin_profile(request)):
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        wallet_totals = {
            row['owner_type']: row
            for row in Wallet.objects.values('owner_type')
            .annotate(total_balance=Sum('balance'), count=Count('id'))
        }

        # Failed payouts NEVER contribute to total/success amounts —
        # the money never left the platform, so counting them would
        # double up the available-balance picture. They're still
        # surfaced through `failed_count` so admins can see + clear
        # the queue.
        payout_totals = Payout.objects.aggregate(
            total_amount=Sum(
                'amount',
                filter=~Q(status=Payout.STATUS_FAILED),
            ),
            success_amount=Sum(
                'amount', filter=Q(status=Payout.STATUS_SUCCESS),
            ),
            success_count=Count(
                'id', filter=Q(status=Payout.STATUS_SUCCESS),
            ),
            failed_count=Count(
                'id', filter=Q(status=Payout.STATUS_FAILED),
            ),
            pending_count=Count(
                'id',
                filter=Q(status__in=[
                    Payout.STATUS_PENDING, Payout.STATUS_PROCESSING,
                ]),
            ),
        )

        recipient_totals = PaystackRecipient.objects.filter(
            archived_at__isnull=True
        ).aggregate(
            verified=Count('id', filter=Q(verification_status=PaystackRecipient.VERIFICATION_VERIFIED)),
            pending=Count('id', filter=Q(verification_status=PaystackRecipient.VERIFICATION_PENDING)),
            manual=Count('id', filter=Q(verification_status=PaystackRecipient.VERIFICATION_MANUAL_REVIEW)),
            failed=Count('id', filter=Q(verification_status=PaystackRecipient.VERIFICATION_FAILED)),
        )

        recent_payouts = (
            Payout.objects.select_related('recipient')
            .order_by('-created_at')[:10]
        )
        recent_recipients = (
            PaystackRecipient.objects.filter(archived_at__isnull=True)
            .order_by('-updated_at')[:10]
        )

        # ── Driver-side delivery commission revenue ────────────────
        # Mirrors how the merchant-side commission is exposed: the
        # marketplace screen renders these next to the other revenue
        # cards. Excludes disputed earnings so refunds/clawbacks don't
        # inflate platform revenue.
        from delivery.models import DriverEarning
        delivery_totals = DriverEarning.objects.exclude(
            status='disputed',
        ).aggregate(
            total_gross=Sum('gross_amount'),
            total_commission=Sum('platform_commission'),
            total_net=Sum('net_amount'),
            job_count=Count('id'),
        )

        return Response({
            'wallets': {
                k: {
                    'total_balance': str(v['total_balance'] or 0),
                    'count': v['count'],
                }
                for k, v in wallet_totals.items()
            },
            'payouts': {
                'total_amount': str(payout_totals['total_amount'] or 0),
                'success_amount': str(payout_totals['success_amount'] or 0),
                'success_count': payout_totals['success_count'] or 0,
                'failed_count': payout_totals['failed_count'] or 0,
                'pending_count': payout_totals['pending_count'] or 0,
            },
            'recipients': recipient_totals,
            'delivery_commission': {
                'total_gross':
                    str(delivery_totals['total_gross'] or 0),
                'total_commission':
                    str(delivery_totals['total_commission'] or 0),
                'total_net_to_drivers':
                    str(delivery_totals['total_net'] or 0),
                'job_count': delivery_totals['job_count'] or 0,
            },
            'recent_payouts': [_serialise_payout(p) for p in recent_payouts],
            'recent_recipients': [_serialise_recipient(r) for r in recent_recipients],
        })

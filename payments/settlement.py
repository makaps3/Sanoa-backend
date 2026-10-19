"""Order settlement engine — credits vendor / driver / platform wallets
the moment a customer payment lands.

Implements the formulas from ``docs/payments/Marketplace Payment Flow``:

    commission_fee   = order_amount × commission_percent
    vendor_payout    = order_amount − commission_fee
    driver_earnings  = delivery_fee   (0 for pickup)
    platform_revenue = service_fee + commission_fee − paystack_fee

The platform acts as merchant of record, so on payment success the
customer's money lands in the platform Paystack account. We then
credit internal wallets — actual bank transfers happen later via the
scheduled payout job.

Three invariants the engine guarantees:

  1. ``vendor_credit + driver_credit + platform_credit + paystack_fee
     == order_amount + delivery_kept + service_fee``  (no orphaned cents).
  2. When the order is a delivery but no driver has been assigned at
     settlement time, the delivery_fee is parked in the platform
     ledger tagged ``TYPE_DELIVERY_ESCROW``; ``credit_driver_earning``
     can transfer it to the driver when one is assigned.
  3. When Paystack returns the gateway fee *after* settlement
     (webhook timing), ``apply_paystack_fee`` debits the platform
     ledger by the delta so the wallet stays aligned with the spec.

`settle_order` is idempotent: it scans for prior `WalletTransaction`
rows tagged with the order reference and skips if found. This makes
it safe to call from both the synchronous payment-success path and
the webhook handler.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction

from .wallet_models import Wallet, WalletTransaction


_CENTS = Decimal('0.01')


def settle_order(order, *, driver=None) -> dict:
    """Credit internal wallets for a finalised retail order.

    Args:
        order: An `orders.Order` instance. The vendor is read from
            its primary vendor (single-vendor cart guarantee). The
            service_fee / commission_amount / vendor_payout fields
            must already have been computed by `Order.calculate_totals`.
        driver: Optional driver model — when supplied AND the order is
            a delivery, credits the driver's wallet with the delivery
            fee. When omitted, delivery_fee is escrowed on the platform
            ledger for later assignment.

    Returns:
        ``{'vendor_credit': D, 'driver_credit': D, 'platform_credit': D,
           'delivery_escrow': D, 'paystack_fee': D, 'skipped': bool}``
    """
    return _settle_generic(
        order=order,
        restaurant_order=None,
        vendor=order.primary_vendor,
        order_amount=order.subtotal,
        delivery_fee=order.shipping_cost,
        fulfillment_type=order.fulfillment_type,
        service_fee=order.service_fee,
        commission_amount=order.commission_amount,
        vendor_payout=order.vendor_payout,
        paystack_fee=order.paystack_fee,
        reference=f'ORDER_{order.order_number}',
        driver=driver,
    )


def settle_restaurant_order(order, *, driver=None) -> dict:
    """Same as `settle_order` but for restaurant orders."""
    return _settle_generic(
        order=None,
        restaurant_order=order,
        vendor=order.vendor,
        order_amount=order.subtotal,
        delivery_fee=order.delivery_fee,
        fulfillment_type=order.fulfillment_type,
        service_fee=order.service_fee,
        commission_amount=order.commission_amount,
        vendor_payout=order.vendor_payout,
        paystack_fee=getattr(order, 'paystack_fee', 0),
        reference=f'RST_{order.order_number}',
        driver=driver,
    )


def _settle_generic(
    *,
    order, restaurant_order,
    vendor,
    order_amount,
    delivery_fee,
    fulfillment_type: str,
    service_fee,
    commission_amount,
    vendor_payout,
    paystack_fee,
    reference: str,
    driver=None,
) -> dict:
    if vendor is None:
        return {'skipped': True, 'reason': 'no_vendor'}

    # Idempotency — if we've already settled this order, no-op.
    if WalletTransaction.objects.filter(
        reference=reference,
        transaction_type__in=[
            WalletTransaction.TYPE_ORDER_SETTLEMENT,
            WalletTransaction.TYPE_PLATFORM_REVENUE,
            WalletTransaction.TYPE_DRIVER_EARNING,
            WalletTransaction.TYPE_DELIVERY_ESCROW,
        ],
    ).exists():
        return {'skipped': True, 'reason': 'already_settled'}

    is_delivery = (fulfillment_type or '').lower() == 'delivery'
    delivery_kept = _money(delivery_fee) if is_delivery else Decimal('0.00')
    fee_money = _money(paystack_fee)
    # Spec: platform_revenue = service_fee + commission − paystack_fee.
    platform_credit = _money(service_fee) + _money(commission_amount) - fee_money

    with transaction.atomic():
        # 1. Vendor wallet ← order_amount − commission
        vendor_wallet = Wallet.for_vendor(vendor)
        vendor_wallet.credit(
            _money(vendor_payout),
            transaction_type=WalletTransaction.TYPE_ORDER_SETTLEMENT,
            reference=reference,
            order=order, restaurant_order=restaurant_order,
            description=f'Vendor payout for {reference}',
        )

        # 2. Driver wallet ← delivery_fee (when delivery + driver known);
        #    otherwise the delivery_fee is parked in the platform ledger
        #    tagged DELIVERY_ESCROW so the invariant
        #    (sum of credits == customer_paid − paystack_fee) holds.
        driver_credit = Decimal('0.00')
        delivery_escrow = Decimal('0.00')
        if delivery_kept > 0:
            if driver is not None:
                driver_wallet = Wallet.for_driver(driver)
                driver_wallet.credit(
                    delivery_kept,
                    transaction_type=WalletTransaction.TYPE_DRIVER_EARNING,
                    reference=reference,
                    order=order, restaurant_order=restaurant_order,
                    description=f'Driver earnings for {reference}',
                )
                driver_credit = delivery_kept
            else:
                Wallet.platform_ledger().credit(
                    delivery_kept,
                    transaction_type=WalletTransaction.TYPE_DELIVERY_ESCROW,
                    reference=reference,
                    order=order, restaurant_order=restaurant_order,
                    description=(
                        f'Delivery fee escrow for {reference} — '
                        'awaiting driver assignment.'
                    ),
                )
                delivery_escrow = delivery_kept

        # 3. Platform revenue ledger ← service_fee + commission − paystack_fee.
        #    Skip writing a zero row, but DO write a negative row when
        #    paystack_fee outstrips the platform's slice (small orders).
        if platform_credit != 0:
            platform_wallet = Wallet.platform_ledger()
            if platform_credit > 0:
                platform_wallet.credit(
                    platform_credit,
                    transaction_type=WalletTransaction.TYPE_PLATFORM_REVENUE,
                    reference=reference,
                    order=order, restaurant_order=restaurant_order,
                    description=f'Platform revenue for {reference} '
                                f'(service R{_money(service_fee)} + '
                                f'commission R{_money(commission_amount)} '
                                f'− Paystack fee R{fee_money}).',
                )
            else:
                platform_wallet.debit(
                    -platform_credit,
                    transaction_type=WalletTransaction.TYPE_PLATFORM_REVENUE,
                    reference=reference,
                    order=order, restaurant_order=restaurant_order,
                    description=f'Platform loss for {reference}: Paystack '
                                f'fee R{fee_money} exceeded service + '
                                f'commission.',
                )

    return {
        'skipped': False,
        'vendor_credit':    _money(vendor_payout),
        'driver_credit':    driver_credit,
        'platform_credit':  platform_credit,
        'delivery_escrow':  delivery_escrow,
        'paystack_fee':     fee_money,
        'order_amount':     _money(order_amount),
        'delivery_fee':     _money(delivery_fee),
    }


def credit_driver_earning(order, driver, *, restaurant_order=None) -> dict:
    """Release the delivery-fee escrow to the driver once assigned.

    Idempotent — checks for an existing driver-earning row for the
    same reference before crediting. Returns
    ``{'skipped': bool, 'driver_credit': D, 'reason': str}``.
    """
    reference = (
        f'RST_{restaurant_order.order_number}' if restaurant_order is not None
        else f'ORDER_{order.order_number}'
    )
    if WalletTransaction.objects.filter(
        reference=reference,
        transaction_type=WalletTransaction.TYPE_DRIVER_EARNING,
    ).exists():
        return {'skipped': True, 'driver_credit': Decimal('0.00'),
                'reason': 'already_credited'}
    escrow = WalletTransaction.objects.filter(
        reference=reference,
        transaction_type=WalletTransaction.TYPE_DELIVERY_ESCROW,
    ).first()
    if escrow is None:
        return {'skipped': True, 'driver_credit': Decimal('0.00'),
                'reason': 'no_escrow'}
    amount = _money(escrow.credit)
    if amount <= 0:
        return {'skipped': True, 'driver_credit': Decimal('0.00'),
                'reason': 'zero_escrow'}
    with transaction.atomic():
        Wallet.platform_ledger().debit(
            amount,
            transaction_type=WalletTransaction.TYPE_DELIVERY_ESCROW,
            reference=reference,
            order=order, restaurant_order=restaurant_order,
            description=f'Escrow release to driver for {reference}.',
        )
        Wallet.for_driver(driver).credit(
            amount,
            transaction_type=WalletTransaction.TYPE_DRIVER_EARNING,
            reference=reference,
            order=order, restaurant_order=restaurant_order,
            description=f'Driver earnings for {reference}.',
        )
    return {'skipped': False, 'driver_credit': amount, 'reason': 'released'}


def apply_paystack_fee(order, fee, *, restaurant_order=None) -> dict:
    """Apply the late-arriving Paystack fee to the platform ledger.

    When `settle_order` ran before Paystack returned the fee (the
    common case — webhook timing), the platform was credited with the
    full ``service_fee + commission``. Once the fee lands we debit the
    delta so the wallet matches the spec.

    Idempotent on ``(reference, transaction_type=PAYSTACK_FEE)``.
    """
    fee = _money(fee)
    if fee <= 0:
        return {'skipped': True, 'reason': 'zero_fee', 'fee': fee}
    reference = (
        f'RST_{restaurant_order.order_number}' if restaurant_order is not None
        else f'ORDER_{order.order_number}'
    )
    fee_ref = f'{reference}_PAYSTACK_FEE'
    if WalletTransaction.objects.filter(
        reference=fee_ref,
        transaction_type=WalletTransaction.TYPE_PAYSTACK_FEE,
    ).exists():
        return {'skipped': True, 'reason': 'already_applied', 'fee': fee}
    with transaction.atomic():
        Wallet.platform_ledger().debit(
            fee,
            transaction_type=WalletTransaction.TYPE_PAYSTACK_FEE,
            reference=fee_ref,
            order=order, restaurant_order=restaurant_order,
            description=f'Paystack gateway fee for {reference}.',
        )
    return {'skipped': False, 'fee': fee, 'reference': fee_ref}


def _money(value):
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_CENTS)


def reverse_settlement_for_refund(refund) -> dict:
    """Claw back wallet credits when a refund is paid out to a customer.

    Settlement credited the vendor its payout and the platform its
    revenue the moment the customer paid. A refund sends that money
    back out of the platform's Paystack balance, so those internal
    credits have to be undone — otherwise the vendor keeps money the
    platform has already returned, and the payout job pays it twice.

    The refund is apportioned by what each party actually received:

        share = party_credit / customer_paid

    so a partial refund claws back a proportional slice. Reversals may
    push a wallet negative (the vendor may already have been paid out);
    that debt is the honest position and nets off the next settlement.

    Idempotent — a second call for the same refund is a no-op.
    """
    order = getattr(refund, 'order', None)
    restaurant_order = getattr(refund, 'restaurant_order', None)
    if order is None and restaurant_order is None:
        txn = refund.transaction
        order = getattr(txn, 'order', None)
        restaurant_order = getattr(txn, 'restaurant_order', None)

    src = order if order is not None else restaurant_order
    if src is None:
        return {'skipped': True, 'reason': 'no order behind the refund'}

    reference = f'REFUND_{refund.id}'
    if WalletTransaction.objects.filter(reference=reference).exists():
        return {'skipped': True, 'reason': 'already reversed'}

    vendor = (
        getattr(refund, 'vendor', None)
        or getattr(src, 'primary_vendor', None)
        or getattr(src, 'vendor', None)
    )

    customer_paid = _money(getattr(src, 'total_amount', 0))
    vendor_payout = _money(getattr(src, 'vendor_payout', 0))
    commission = _money(getattr(src, 'commission_amount', 0))
    service_fee = _money(getattr(src, 'service_fee', 0))
    paystack_fee = _money(getattr(src, 'paystack_fee', 0))
    platform_revenue = commission + service_fee - paystack_fee
    refund_amount = _money(refund.amount)

    if customer_paid <= 0 or refund_amount <= 0:
        return {'skipped': True, 'reason': 'nothing to reverse'}

    # Cap at a full refund so rounding can never claw back more than
    # was credited in the first place.
    ratio = min(refund_amount / customer_paid, Decimal('1'))
    vendor_share = _money(vendor_payout * ratio)
    platform_share = _money(platform_revenue * ratio)

    result = {
        'skipped': False,
        'vendor_debit': Decimal('0.00'),
        'platform_debit': Decimal('0.00'),
    }

    with transaction.atomic():
        if vendor is not None and vendor_share > 0:
            wallet = Wallet.for_vendor(vendor)
            wallet.debit(
                vendor_share,
                transaction_type=WalletTransaction.TYPE_REVERSAL,
                reference=reference,
                order=order,
                restaurant_order=restaurant_order,
                description=f'Refund on {getattr(src, "order_number", "order")}',
                allow_overdraft=True,
            )
            result['vendor_debit'] = vendor_share

        if platform_share > 0:
            platform = Wallet.platform_ledger()
            platform.debit(
                platform_share,
                transaction_type=WalletTransaction.TYPE_REVERSAL,
                reference=reference,
                order=order,
                restaurant_order=restaurant_order,
                description=f'Refund on {getattr(src, "order_number", "order")}',
                allow_overdraft=True,
            )
            result['platform_debit'] = platform_share

    return result

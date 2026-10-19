"""Order financial split — single source of truth for the per-order
vendor / platform breakdown applied to both retail and restaurant
orders.

Per the marketplace payment-flow spec
(``docs/payments/Marketplace Payment Flow``):

    commission_fee   = order_amount × commission_percent
    vendor_payout    = order_amount − commission_fee
    driver_earnings  = delivery_fee  (0 for pickup)
    platform_revenue = service_fee + commission_fee − paystack_fee

Where ``order_amount`` is the **product subtotal (cart)** — NOT the
total the customer paid. The customer's gross payment is
``order_amount + delivery_fee + service_fee``; the commission is
calculated off the goods value only, never off delivery or service.

Commission / service-fee percentages come from the
``platform_admin.PlatformFee`` row matching the vendor's
``business_category`` (`retail` or `restaurant`).

The Paystack gateway fee IS deducted from the platform's slice at
settlement time. Paystack returns the fee asynchronously on the
verify / webhook payload, so the per-order calc accepts a
``paystack_fee`` arg that defaults to 0; ``Order.update_paystack_fee``
then applies the delta to the platform wallet once the real fee
lands.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple, Optional


_CENTS = Decimal('0.01')


def _money(value) -> Decimal:
    """Coerce any number/None into a 2-decimal Decimal."""
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


class OrderFinancials(NamedTuple):
    """Computed split for a single order."""
    service_fee: Decimal
    commission_amount: Decimal
    vendor_payout: Decimal
    driver_earnings: Decimal
    platform_payout: Decimal
    delivery_kept: Decimal


def lookup_platform_fee(vendor):
    """Return the active PlatformFee row matching the vendor's
    `business_category`, or None if no row is configured.
    """
    if vendor is None:
        return None
    from platform_admin.models import PlatformFee
    return PlatformFee.for_business_category(
        getattr(vendor, 'business_category', None)
    )


def vendor_tier_commission_discount(vendor) -> Decimal:
    """Return the per-tier commission discount (percentage points)
    granted to `vendor` by their active BusinessTier subscription, or
    0 when they have none / are on the free tier.
    """
    if vendor is None:
        return Decimal('0')
    sub = getattr(vendor, 'tier_subscription', None)
    if sub is None:
        return Decimal('0')
    # Only honour the discount while the subscription is still active.
    if not getattr(sub, 'is_active', False):
        return Decimal('0')
    tier = sub.tier
    return Decimal(str(getattr(tier, 'commission_discount', 0) or 0))


def compute_order_financials(
    *,
    order_amount,
    delivery_fee,
    fulfillment_type: str,
    service_fee=0,
    commission_percent=0,
    paystack_fee=0,
) -> OrderFinancials:
    """Pure-function compute of the per-order split.

    Inputs are arbitrary numeric types — coerced to Decimal internally
    so callers don't have to wrap their arguments. Returns a
    NamedTuple so callers can either unpack or refer to fields by
    name.

    Math, per the marketplace spec:

        commission_amount = order_amount × commission_percent / 100
        vendor_payout     = order_amount − commission_amount
        driver_earnings   = delivery_fee     (0 for pickup)
        platform_payout   = service_fee + commission_amount − paystack_fee

    The customer-paid gross is ``order_amount + delivery_fee +
    service_fee``; the sum of vendor + driver + platform shares
    therefore equals that gross minus the Paystack processing fee
    (which Paystack itself withholds, so the platform's slice
    absorbs it).
    """
    order_amount = _money(order_amount)
    delivery_fee = _money(delivery_fee)
    service_fee = _money(service_fee)
    commission_percent = _money(commission_percent)
    paystack_fee = _money(paystack_fee)

    delivery_kept = (
        delivery_fee if (fulfillment_type or '').lower() == 'delivery'
        else Decimal('0.00')
    )
    commission_amount = (order_amount * commission_percent / Decimal('100'))
    commission_amount = commission_amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    vendor_payout = order_amount - commission_amount
    driver_earnings = delivery_kept
    # Net platform revenue per the spec. Allowed to go negative when
    # a tiny order's Paystack fee exceeds service_fee + commission —
    # the platform still owes the vendor / driver in full, the fee is
    # just the platform's cost of accepting the payment.
    platform_payout = service_fee + commission_amount - paystack_fee
    return OrderFinancials(
        service_fee=service_fee,
        commission_amount=commission_amount,
        vendor_payout=_money(vendor_payout),
        driver_earnings=_money(driver_earnings),
        platform_payout=_money(platform_payout),
        delivery_kept=_money(delivery_kept),
    )


def derive_from_platform_fee(
    *,
    vendor,
    order_amount,
    delivery_fee,
    fulfillment_type: str,
    paystack_fee=0,
    service_fee: Optional[Decimal] = None,
) -> OrderFinancials:
    """Convenience wrapper: look up the vendor's PlatformFee row and
    apply the percentages.

    `service_fee` is optional — when omitted (the common case during
    order creation) it's computed as `order_amount × customer_service_fee_percent`.
    The created Order serializer accepts a client-supplied
    `service_fee` for parity with what was shown on the checkout
    summary; we honour that when present and fall back to the
    server-computed value otherwise.
    """
    fee_row = lookup_platform_fee(vendor)
    base_commission = (
        Decimal(str(fee_row.merchant_commission_percent))
        if fee_row else Decimal('0')
    )
    # Subtract the vendor's tier discount (capped so the effective
    # commission never goes below zero — a misconfigured tier should
    # never end up paying the vendor *more* than the order amount).
    discount = vendor_tier_commission_discount(vendor)
    commission_percent = max(base_commission - discount, Decimal('0'))
    if service_fee is None:
        if fee_row is not None:
            csf_pct = Decimal(str(fee_row.customer_service_fee_percent))
            service_fee = _money(_money(order_amount) * csf_pct / Decimal('100'))
        else:
            service_fee = Decimal('0.00')
    return compute_order_financials(
        order_amount=order_amount,
        delivery_fee=delivery_fee,
        fulfillment_type=fulfillment_type,
        service_fee=service_fee,
        commission_percent=commission_percent,
        paystack_fee=paystack_fee,
    )

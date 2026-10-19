"""
Discount engine.

Given a shopping cart, work out every discount that applies:

  1. Automatic promotions (vendor-owned for the cart's vendor + platform-wide).
     Each cart item is discounted by at most ONE promotion — the highest
     priority one that targets it. This prevents a single item being
     discounted several times over.

  2. A code coupon, if one is attached to the cart. The coupon applies on
     top of automatic promotions (standard "store promo + coupon" stacking),
     computed against the coupon's eligible subtotal.

  3. Stacking control: a promotion whose ``stackable_with_coupon`` is False
     is dropped from the automatic pass whenever a coupon is present.

The result is a plain dict (``CartPricing``) that both the cart-summary
endpoint and checkout consume. All money is 2dp ``Decimal`` in ZAR.
"""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import (
    AppliedCoupon,
    DiscountType,
    OwnerType,
    Promotion,
    money,
)

ZERO = Decimal('0.00')


def build_rule_analytics(rule):
    """Usage analytics for a single promotion or coupon.

    Returns a dict with an overall summary, a per-customer breakdown (who
    used it, how many times, total discount they received, and the order
    value it was applied to), and the most recent redemptions.
    """
    from collections import OrderedDict

    from .models import Coupon

    is_coupon = isinstance(rule, Coupon)
    redemptions = list(
        rule.redemptions.select_related('user', 'order')
        .order_by('-redeemed_at'))

    total_discount = ZERO
    total_order_value = ZERO   # goods subtotal the discount applied to
    total_paid = ZERO          # what customers actually paid
    per_user = OrderedDict()

    for r in redemptions:
        disc = money(r.discount_amount)
        order = r.order
        subtotal = money(getattr(order, 'subtotal', 0)) if order else ZERO
        paid = money(getattr(order, 'total_amount', 0)) if order else ZERO
        total_discount = money(total_discount + disc)
        total_order_value = money(total_order_value + subtotal)
        total_paid = money(total_paid + paid)

        u = r.user
        key = u.id if u else 0
        row = per_user.get(key)
        if row is None:
            row = {
                'user_id': u.id if u else None,
                'email': getattr(u, 'email', '') if u else '',
                'name': (f'{u.first_name} {u.last_name}'.strip()
                         if u else '') or (getattr(u, 'email', '') if u else ''),
                'uses': 0,
                'total_discount': ZERO,
                'total_spent': ZERO,
                'last_used': None,
            }
            per_user[key] = row
        row['uses'] += 1
        row['total_discount'] = money(row['total_discount'] + disc)
        row['total_spent'] = money(row['total_spent'] + paid)
        if row['last_used'] is None:
            row['last_used'] = r.redeemed_at  # list is newest-first

    users = sorted(
        per_user.values(), key=lambda x: x['total_discount'], reverse=True)
    n = len(redemptions)
    avg_discount = money(total_discount / n) if n else ZERO

    summary = {
        'redemptions': n,
        'unique_customers': len(per_user),
        'total_discount': total_discount,
        'total_order_value': total_order_value,
        'total_paid': total_paid,
        'average_discount': avg_discount,
    }
    if is_coupon:
        summary['max_uses'] = rule.max_uses
        summary['times_used'] = rule.times_used
        summary['uses_remaining'] = (
            None if rule.max_uses is None
            else max(0, rule.max_uses - rule.times_used))
    else:
        summary['usage_limit'] = rule.usage_limit
        summary['times_used'] = rule.times_used

    recent = [{
        'order_number': getattr(r.order, 'order_number', None),
        'customer': (getattr(r.user, 'email', '') if r.user else ''),
        'discount': money(r.discount_amount),
        'order_total': (money(getattr(r.order, 'total_amount', 0))
                        if r.order else ZERO),
        'redeemed_at': r.redeemed_at.isoformat() if r.redeemed_at else None,
    } for r in redemptions[:20]]

    return {'summary': summary, 'customers': users, 'recent': recent}


def build_overview(promotions_qs, coupons_qs):
    """Aggregate analytics across a set of promotions & coupons (a vendor's
    own, or every rule for admin). Powers the management dashboard header."""
    from django.db.models import Count, Sum

    from .models import CouponRedemption, PromotionRedemption

    now = timezone.now()

    def _live_count(qs):
        return sum(1 for r in qs if r.is_live(now))

    p_agg = (PromotionRedemption.objects
             .filter(promotion__in=promotions_qs)
             .aggregate(n=Count('id'), disc=Sum('discount_amount')))
    c_agg = (CouponRedemption.objects
             .filter(coupon__in=coupons_qs)
             .aggregate(n=Count('id'), disc=Sum('discount_amount')))

    total_redemptions = (p_agg['n'] or 0) + (c_agg['n'] or 0)
    total_discount = money((p_agg['disc'] or 0)) + money((c_agg['disc'] or 0))

    # Top performers by discount given. (Annotation names must not collide
    # with the 'redemptions' reverse relation.)
    top_promos = (promotions_qs
                  .annotate(redemption_count=Count('redemptions'),
                            discount_total=Sum('redemptions__discount_amount'))
                  .filter(redemption_count__gt=0)
                  .order_by('-discount_total')[:5])
    top_coupons = (coupons_qs
                   .annotate(redemption_count=Count('redemptions'),
                             discount_total=Sum('redemptions__discount_amount'))
                   .filter(redemption_count__gt=0)
                   .order_by('-discount_total')[:5])

    def _top_row(obj, label):
        return {
            'id': str(obj.id),
            'name': label,
            'redemptions': obj.redemption_count,
            'total_discount': money(obj.discount_total or 0),
        }

    return {
        'promotions': {
            'total': promotions_qs.count(),
            'active': _live_count(promotions_qs),
            'redemptions': p_agg['n'] or 0,
            'total_discount': money(p_agg['disc'] or 0),
        },
        'coupons': {
            'total': coupons_qs.count(),
            'active': _live_count(coupons_qs),
            'redemptions': c_agg['n'] or 0,
            'total_discount': money(c_agg['disc'] or 0),
        },
        'totals': {
            'redemptions': total_redemptions,
            'total_discount': total_discount,
        },
        'top_promotions': [_top_row(p, p.name) for p in top_promos],
        'top_coupons': [_top_row(c, c.code) for c in top_coupons],
    }


def _live_promotions_for(vendor_id, now):
    """Active, in-window promotions for this vendor + platform-wide ones."""
    qs = (Promotion.objects
          .filter(is_active=True, start_date__lte=now)
          .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
          .filter(Q(owner_type=OwnerType.PLATFORM) | Q(vendor_id=vendor_id))
          .prefetch_related('applicable_products', 'applicable_categories')
          .order_by('-priority', '-created_at'))
    # usage_limit is a Python-side check (times_used vs limit).
    return [p for p in qs if p.is_live(now)]


def _item_rows(cart):
    """Normalise cart items to (item, product, category_id, line_total)."""
    rows = []
    items = (cart.items
             .select_related('product', 'product__category', 'product_variant')
             .all())
    for it in items:
        product = it.product
        if product is None:
            continue
        rows.append({
            'item': it,
            'product': product,
            'category_id': getattr(product, 'category_id', None),
            'line_total': money(it.total_price),
        })
    return rows


def compute_cart_pricing(cart, user=None, coupon=None):
    """
    Price a cart. ``coupon`` overrides whatever is attached to the cart
    (used for validate/preview); pass it explicitly or leave None to use
    the cart's :class:`AppliedCoupon`.

    Returns a dict:
        {
          currency, subtotal,
          promotions: [{id, name, discount_type, discount, items:[item_ids]}],
          automatic_discount,
          coupon: {code, name, ...} | None,
          coupon_discount, coupon_error,
          free_shipping: bool,
          total_discount, total, total_savings
        }
    """
    now = timezone.now()
    rows = _item_rows(cart)
    subtotal = money(sum((r['line_total'] for r in rows), ZERO))

    result = {
        'currency': 'R',
        'subtotal': subtotal,
        'promotions': [],
        'automatic_discount': ZERO,
        'coupon': None,
        'coupon_discount': ZERO,
        'coupon_error': None,
        'free_shipping': False,
        'free_shipping_funder': None,
        'total_discount': ZERO,
        # How the monetary discount splits by who funds it. A vendor-funded
        # discount is absorbed by the vendor (commission is charged on the
        # discounted amount); a platform-funded discount comes out of the
        # platform's slice. These always sum to total_discount.
        'vendor_funded_discount': ZERO,
        'platform_funded_discount': ZERO,
        'total': subtotal,
        'total_savings': ZERO,
    }
    if not rows:
        return result

    # Resolve the coupon (explicit arg wins; else whatever is on the cart).
    if coupon is None:
        applied = (AppliedCoupon.objects
                   .filter(cart=cart).select_related('coupon').first())
        coupon = applied.coupon if applied else None
    has_coupon = coupon is not None

    # ── 1. automatic promotions ──────────────────────────────────────
    # Free-shipping promotions are orthogonal to per-item price discounts,
    # so they never "consume" an item — a store can run "free shipping"
    # AND "10% off" on the same product. Only monetary promotions compete
    # for an item (each item is discounted by at most one of them).
    promotions = [p for p in _live_promotions_for(cart.vendor_id, now)
                  if p.applies_to_user(user)]
    consumed = set()          # item ids already discounted by a promotion
    auto_discount = ZERO
    free_shipping = False
    applied_promos = []

    def _eligible_rows(rule, skip_consumed):
        out = []
        for r in rows:
            if skip_consumed and r['item'].id in consumed:
                continue
            if not rule.matches_item(r['product'], r['category_id']):
                continue
            out.append(r)
        return out

    def _meets_thresholds(rule, eligible):
        sub = money(sum((r['line_total'] for r in eligible), ZERO))
        if sub < money(rule.minimum_order_amount):
            return False
        min_qty = getattr(rule, 'minimum_quantity', 0)
        if min_qty:
            if sum(r['item'].quantity for r in eligible) < min_qty:
                return False
        return True

    monetary = [p for p in promotions if not p.is_free_shipping]
    shipping = [p for p in promotions if p.is_free_shipping]

    vendor_funded = ZERO
    platform_funded = ZERO
    free_shipping_funder = None

    for promo in monetary:
        if has_coupon and not promo.stackable_with_coupon:
            continue
        eligible = _eligible_rows(promo, skip_consumed=True)
        if not eligible or not _meets_thresholds(promo, eligible):
            continue
        eligible_subtotal = money(sum((r['line_total'] for r in eligible), ZERO))
        discount = promo.compute_discount(eligible_subtotal)
        if discount <= 0:
            continue
        for r in eligible:
            consumed.add(r['item'].id)
        auto_discount = money(auto_discount + discount)
        if promo.is_platform:
            platform_funded = money(platform_funded + discount)
        else:
            vendor_funded = money(vendor_funded + discount)
        applied_promos.append({
            'id': str(promo.id),
            'name': promo.name,
            'discount_type': promo.discount_type,
            'discount': discount,
            'free_shipping': False,
            'item_ids': [str(r['item'].id) for r in eligible],
        })

    for promo in shipping:
        if has_coupon and not promo.stackable_with_coupon:
            continue
        eligible = _eligible_rows(promo, skip_consumed=False)
        if not eligible or not _meets_thresholds(promo, eligible):
            continue
        free_shipping = True
        if free_shipping_funder is None:
            free_shipping_funder = 'platform' if promo.is_platform else 'vendor'
        applied_promos.append({
            'id': str(promo.id),
            'name': promo.name,
            'discount_type': promo.discount_type,
            'discount': ZERO,
            'free_shipping': True,
            'item_ids': [str(r['item'].id) for r in eligible],
        })

    result['promotions'] = applied_promos
    result['automatic_discount'] = auto_discount

    # ── 2. coupon ────────────────────────────────────────────────────
    coupon_discount = ZERO
    if has_coupon:
        ok, message = coupon.validate_for(
            user, subtotal, vendor_id=cart.vendor_id)
        if not ok:
            result['coupon_error'] = message
        else:
            eligible = [
                r for r in rows
                if coupon.matches_item(r['product'], r['category_id'])
            ]
            eligible_subtotal = money(
                sum((r['line_total'] for r in eligible), ZERO))
            if coupon.is_free_shipping:
                free_shipping = True
                coupon_discount = ZERO
                if free_shipping_funder is None:
                    free_shipping_funder = (
                        'platform' if coupon.is_platform else 'vendor')
            else:
                coupon_discount = coupon.compute_discount(eligible_subtotal)
                if coupon.is_platform:
                    platform_funded = money(platform_funded + coupon_discount)
                else:
                    vendor_funded = money(vendor_funded + coupon_discount)
            result['coupon'] = {
                'id': str(coupon.id),
                'code': coupon.code,
                'name': coupon.name,
                'discount_type': coupon.discount_type,
                'discount': coupon_discount,
                'free_shipping': coupon.is_free_shipping,
            }
    result['coupon_discount'] = coupon_discount

    # ── 3. totals ────────────────────────────────────────────────────
    total_discount = money(auto_discount + coupon_discount)
    if total_discount > subtotal:
        total_discount = subtotal

    # Reconcile the funded split against the (possibly capped) total so the
    # two buckets always sum to total_discount.
    raw_funded = money(vendor_funded + platform_funded)
    if raw_funded > 0 and total_discount != raw_funded:
        vendor_funded = money(vendor_funded * total_discount / raw_funded)
        platform_funded = money(total_discount - vendor_funded)

    result['free_shipping'] = free_shipping
    result['free_shipping_funder'] = free_shipping_funder
    result['total_discount'] = total_discount
    result['vendor_funded_discount'] = vendor_funded
    result['platform_funded_discount'] = platform_funded
    result['total'] = money(subtotal - total_discount)
    result['total_savings'] = total_discount
    return result


def apply_coupon_to_cart(cart, code, user):
    """
    Validate ``code`` against ``cart`` and attach it. Returns
    ``(pricing_dict, error_message)`` — on success ``error_message`` is None.
    """
    from .models import Coupon

    code = (code or '').strip().upper()
    if not code:
        return None, 'Enter a coupon code.'
    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return None, 'That coupon code is not valid.'

    rows = _item_rows(cart)
    subtotal = money(sum((r['line_total'] for r in rows), ZERO))
    ok, message = coupon.validate_for(user, subtotal, vendor_id=cart.vendor_id)
    if not ok:
        return None, message

    # A coupon that discounts nothing on this cart (e.g. targets products the
    # cart doesn't contain) is a poor experience — reject it clearly.
    preview = compute_cart_pricing(cart, user=user, coupon=coupon)
    if not coupon.is_free_shipping and preview['coupon_discount'] <= 0:
        return None, 'This coupon does not apply to the items in your cart.'

    AppliedCoupon.objects.update_or_create(
        cart=cart, defaults={'coupon': coupon})
    return compute_cart_pricing(cart, user=user), None


def remove_coupon_from_cart(cart):
    AppliedCoupon.objects.filter(cart=cart).delete()


def commit_cart_discounts(cart, order, user):
    """
    Called once an order is created from a cart. Records redemptions,
    bumps usage counters, and returns the total discount applied so the
    caller can stamp it on the order. Clears the cart's applied coupon.
    """
    pricing = compute_cart_pricing(cart, user=user)

    for p in pricing['promotions']:
        try:
            promo = Promotion.objects.get(id=p['id'])
        except Promotion.DoesNotExist:
            continue
        Promotion.objects.filter(pk=promo.pk).update(
            times_used=models_f_increment())
        PromotionRedemption = _promotion_redemption_model()
        PromotionRedemption.objects.create(
            promotion=promo, user=user, order=order,
            discount_amount=p['discount'])

    coupon_info = pricing.get('coupon')
    if coupon_info and pricing['coupon_discount'] >= 0 and \
            not pricing.get('coupon_error'):
        from .models import Coupon, CouponRedemption
        try:
            coupon = Coupon.objects.get(id=coupon_info['id'])
            Coupon.objects.filter(pk=coupon.pk).update(
                times_used=models_f_increment())
            CouponRedemption.objects.create(
                coupon=coupon, user=user, order=order,
                discount_amount=pricing['coupon_discount'])
        except Coupon.DoesNotExist:
            pass

    remove_coupon_from_cart(cart)
    return pricing


def models_f_increment():
    from django.db.models import F
    return F('times_used') + 1


def _promotion_redemption_model():
    from .models import PromotionRedemption
    return PromotionRedemption

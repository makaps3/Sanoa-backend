"""
Store operations helpers for the vendor's own profile:

  * Operating-hours (Mon–Sun) serialisation to/from the ``opening_hours``
    JSON field that already powers ``VendorProfile.is_open_now``.
  * Syncing the open-state fields down to the legacy Individual/Business
    profiles so the store-discovery feed stays accurate.
  * Live revenue / order / rating stats for the profile screen — computed
    from real orders instead of the cached counter fields.

The ``opening_hours`` JSON shape is ``{ "0": [{"open": "08:00",
"close": "17:00"}], ... }`` keyed by weekday (0=Mon .. 6=Sun). A missing
key or empty list means the store is closed that day. Keeping this exact
shape means ``business.models._is_open_now`` keeps working unchanged.
"""
from __future__ import annotations

import re
from decimal import Decimal

from django.db.models import Sum

WEEKDAYS = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]

_TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

# Order states that count as realised revenue (money in the vendor's pocket).
ACTUAL_ORDER_STATUSES = ('delivered', 'completed')


class HoursError(ValueError):
    """Raised when an operating-hours payload is malformed."""


# ---------------------------------------------------------------------------
# Hours serialisation
# ---------------------------------------------------------------------------
def serialize_hours(opening_hours):
    """Return a stable Mon→Sun list of day dicts for the API/UI.

    Each entry: ``{day, day_name, is_closed, open, close}``. Reads the first
    window of each weekday (single open→close per day in the UI).
    """
    opening_hours = opening_hours or {}
    days = []
    for idx, name in WEEKDAYS:
        windows = opening_hours.get(str(idx)) or []
        window = windows[0] if windows else None
        open_t = (window or {}).get('open') if window else None
        close_t = (window or {}).get('close') if window else None
        days.append({
            'day': idx,
            'day_name': name,
            'is_closed': not (open_t and close_t),
            'open': open_t,
            'close': close_t,
        })
    return days


def _clean_time(value, field):
    if value in (None, ''):
        return None
    value = str(value).strip()
    # Accept "8:00" / "08:00:00" too, normalise to HH:MM.
    if len(value) >= 5 and value[2] == ':':
        value = value[:5]
    elif re.match(r'^\d:\d{2}', value):
        value = '0' + value[:4]
    if not _TIME_RE.match(value):
        raise HoursError(f'"{field}" must be a valid 24h time in HH:MM format.')
    return value


def build_opening_hours(days):
    """Turn a list of day dicts (from the client) into the storage JSON.

    Accepts ``[{day, is_closed, open, close}, ...]``. Days marked closed —
    or missing both times — are simply left out of the JSON. Raises
    :class:`HoursError` on malformed input.
    """
    if not isinstance(days, list):
        raise HoursError('operating_hours must be a list of day objects.')
    result = {}
    seen = set()
    for entry in days:
        if not isinstance(entry, dict):
            raise HoursError('Each operating-hours entry must be an object.')
        try:
            day = int(entry.get('day'))
        except (TypeError, ValueError):
            raise HoursError('Each entry needs an integer "day" (0=Mon .. 6=Sun).')
        if day < 0 or day > 6:
            raise HoursError('"day" must be between 0 (Monday) and 6 (Sunday).')
        if day in seen:
            raise HoursError(f'Duplicate entry for day {day}.')
        seen.add(day)

        if entry.get('is_closed'):
            continue
        open_t = _clean_time(entry.get('open'), 'open')
        close_t = _clean_time(entry.get('close'), 'close')
        if not open_t or not close_t:
            # Treat "no times given" as closed for that day.
            continue
        if open_t >= close_t:
            raise HoursError(
                f'Closing time must be after opening time for {dict(WEEKDAYS)[day]}.'
            )
        result[str(day)] = [{'open': open_t, 'close': close_t}]
    return result


def set_day(opening_hours, day, *, is_closed=False, open_t=None, close_t=None):
    """Return a copy of ``opening_hours`` with a single ``day`` updated."""
    day = int(day)
    if day < 0 or day > 6:
        raise HoursError('"day" must be between 0 (Monday) and 6 (Sunday).')
    hours = dict(opening_hours or {})
    if is_closed:
        hours.pop(str(day), None)
        return hours
    open_t = _clean_time(open_t, 'open')
    close_t = _clean_time(close_t, 'close')
    if not open_t or not close_t:
        hours.pop(str(day), None)
        return hours
    if open_t >= close_t:
        raise HoursError('Closing time must be after opening time.')
    hours[str(day)] = [{'open': open_t, 'close': close_t}]
    return hours


# ---------------------------------------------------------------------------
# Legacy-profile sync (keeps the store-discovery feed in step)
# ---------------------------------------------------------------------------
def sync_open_state(vendor_profile):
    """Mirror ``opening_hours`` + ``is_temporarily_closed`` onto whichever
    legacy Individual/Business profile the same user owns, so the discovery
    feed's ``is_open_now`` matches what the vendor set on their profile."""
    user = getattr(vendor_profile, 'user', None)
    if user is None:
        return
    for attr in ('individual_vendor_profile', 'business_vendor_profile'):
        legacy = getattr(user, attr, None)
        if legacy is None:
            continue
        legacy.opening_hours = vendor_profile.opening_hours
        legacy.is_temporarily_closed = vendor_profile.is_temporarily_closed
        try:
            legacy.save(update_fields=['opening_hours', 'is_temporarily_closed'])
        except Exception:
            # Non-fatal: discovery accuracy is best-effort, never block the vendor.
            pass


# ---------------------------------------------------------------------------
# Live profile stats
# ---------------------------------------------------------------------------
def compute_vendor_stats(vendor_profile):
    """Real revenue / order / product / rating figures for the profile screen.

    Revenue is ``vendor_payout`` (items subtotal − commission) on realised
    orders only — delivery and service fees are not vendor revenue. Covers
    both retail (``orders``) and restaurant (``restaurant``) orders so the
    numbers are correct whichever kind of store this is.
    """
    revenue = Decimal('0.00')
    orders_total = 0
    orders_completed = 0
    orders_pending = 0
    products_count = 0

    # ── Retail orders ──────────────────────────────────────────────────────
    try:
        from orders.models import Order, OrderItem
        order_ids = (
            OrderItem.objects.filter(vendor=vendor_profile)
            .values_list('order_id', flat=True)
            .distinct()
        )
        r_orders = Order.objects.filter(id__in=order_ids)
        realised = r_orders.filter(
            status__in=ACTUAL_ORDER_STATUSES, payment_status='paid',
        )
        revenue += realised.aggregate(t=Sum('vendor_payout'))['t'] or Decimal('0.00')
        orders_total += r_orders.count()
        orders_completed += realised.count()
        orders_pending += r_orders.filter(status='pending').count()
    except Exception:
        pass

    # ── Restaurant orders ──────────────────────────────────────────────────
    try:
        from restaurant.models import RestaurantOrder
        rest = RestaurantOrder.objects.filter(vendor=vendor_profile)
        realised = rest.filter(payment_status='paid')
        revenue += realised.aggregate(t=Sum('vendor_payout'))['t'] or Decimal('0.00')
        orders_total += rest.count()
        orders_completed += realised.count()
        orders_pending += rest.filter(status='pending').count()
    except Exception:
        pass

    # ── Product catalogue size ─────────────────────────────────────────────
    try:
        from products.models import Product
        products_count = Product.objects.filter(vendor=vendor_profile).count()
    except Exception:
        pass

    return {
        'revenue': str(revenue.quantize(Decimal('0.01'))),
        'orders_total': orders_total,
        'orders_completed': orders_completed,
        'orders_pending': orders_pending,
        'orders_outstanding': max(orders_total - orders_completed, 0),
        'products_count': products_count,
        'average_rating': float(vendor_profile.average_rating or 0),
        'total_reviews': vendor_profile.total_reviews or 0,
    }

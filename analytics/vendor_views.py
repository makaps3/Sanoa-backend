"""
Vendor analytics views.
All views require ?vendor_id UUID in the URL path.
  - The authenticated vendor can only access their own UUID.
  - A platform admin can access any vendor UUID.
Supports ?period=today|week|month|year and ?from=YYYY-MM-DD&to=YYYY-MM-DD.
"""
import datetime
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.insights import (
    vendor_category_insights,
    vendor_customer_insights,
    vendor_negotiation_insights,
    vendor_order_insights,
    vendor_overview_insights,
    vendor_payment_insights,
    vendor_product_insights,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_vendor(request, vendor_id):
    """
    Look up VendorProfile by UUID and authorise the caller.
      - Platform admins may access any vendor.
      - Vendors may only access their own profile.
    Returns (vendor_profile, None) on success or (None, error_response) on failure.
    """
    from business.models import VendorProfile

    user = request.user
    is_admin = (
        user.is_staff
        or hasattr(user, 'admin_profile')
        or getattr(user, 'user_type', '') == 'admin'
    )

    try:
        vp = VendorProfile.objects.get(id=vendor_id)
    except VendorProfile.DoesNotExist:
        return None, Response(
            {'detail': 'Vendor not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not is_admin:
        user_vp = getattr(user, 'vendor_profile', None)
        if user_vp is None or str(user_vp.id) != str(vendor_id):
            return None, Response(
                {'detail': 'Forbidden.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    return vp, None


def _date_range(request):
    period = request.query_params.get('period', 'month')
    from_str = request.query_params.get('from')
    to_str = request.query_params.get('to')
    now = timezone.now()

    if from_str and to_str:
        try:
            start = datetime.datetime.fromisoformat(from_str).replace(
                tzinfo=datetime.timezone.utc)
            end = datetime.datetime.fromisoformat(to_str).replace(
                tzinfo=datetime.timezone.utc)
            return start, end
        except ValueError:
            pass

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = now - datetime.timedelta(days=7)
    elif period == 'year':
        start = now - datetime.timedelta(days=365)
    else:
        start = now - datetime.timedelta(days=30)
    return start, now


# ── Revenue-type filter ───────────────────────────────────────────────────────
# Used by every vendor analytics endpoint EXCEPT subscription/negotiation.
#   - "actual"    → only orders that are delivered/completed AND payment_status='paid'
#   - "projected" → every order in the window (the full potential pipeline,
#                   including ones that *will* eventually be delivered+paid)

ACTUAL_ORDER_STATUSES = ('delivered', 'completed')


def _revenue_type(request):
    """Return either ``'actual'`` or ``'projected'`` (default: actual)."""
    rt = (request.query_params.get('revenue_type') or '').strip().lower()
    return rt if rt in ('actual', 'projected') else 'actual'


def filter_orders_by_revenue_type(orders_qs, revenue_type):
    """
    Apply the actual/projected filter to a queryset of ``orders.Order``.
    ``projected`` is a no-op (every order counts toward the gross pipeline).
    """
    if revenue_type == 'actual':
        return orders_qs.filter(
            status__in=ACTUAL_ORDER_STATUSES,
            payment_status='paid',
        )
    return orders_qs


def restaurant_orders_for(vp, start=None, end=None):
    """The vendor's restaurant orders in a window.

    Restaurant checkouts live in `restaurant.RestaurantOrder`, a separate
    table from `orders.Order`. Analytics was written against the retail
    table only, so a restaurant vendor saw zeros everywhere. This returns
    the equivalent queryset — it carries the same `vendor_payout`,
    `status`, `payment_status` and `created_at` fields, so the shared
    revenue helpers work on it unchanged.
    """
    try:
        from restaurant.models import RestaurantOrder
    except Exception:
        return None
    qs = RestaurantOrder.objects.filter(vendor=vp)
    if start is not None:
        qs = qs.filter(created_at__gte=start)
    if end is not None:
        qs = qs.filter(created_at__lte=end)
    return qs


def vendor_orders_source(vp, retail_qs, start=None, end=None):
    """The order queryset that actually holds this vendor's sales.

    A store is either a retail storefront or a restaurant, and the two keep
    their orders in different tables. `RestaurantOrder` carries the same
    `status`, `vendor_payout`, `created_at` and `fulfillment_type` fields the
    analytics aggregates use, so returning it here makes every existing
    aggregation work unchanged — instead of reporting zeros.
    """
    if getattr(vp, 'business_category', '') == 'restaurant':
        rest = restaurant_orders_for(vp, start, end)
        if rest is not None:
            return rest
    return retail_qs


def vendor_order_items_source(vp, retail_items_qs, start=None, end=None):
    """Line-items for whichever order table this vendor sells through.

    `RestaurantOrderItem` mirrors `OrderItem`'s `product_id`, `product_name`,
    `quantity` and `total_price`, and reaches the vendor via `order__vendor`
    (it has no `vendor` column of its own), so the sales aggregations work on
    it unchanged. Without this, per-product and per-category revenue read
    zero for every restaurant.
    """
    if getattr(vp, 'business_category', '') != 'restaurant':
        return retail_items_qs
    try:
        from restaurant.models import RestaurantOrderItem
    except Exception:
        return retail_items_qs
    qs = RestaurantOrderItem.objects.filter(order__vendor=vp)
    if start is not None:
        qs = qs.filter(order__created_at__gte=start)
    if end is not None:
        qs = qs.filter(order__created_at__lte=end)
    return qs


def filter_order_items_by_revenue_type(items_qs, revenue_type):
    """Same idea but for ``OrderItem`` querysets — filters on ``order__*``."""
    if revenue_type == 'actual':
        return items_qs.filter(
            order__status__in=ACTUAL_ORDER_STATUSES,
            order__payment_status='paid',
        )
    return items_qs


# ── Overview ──────────────────────────────────────────────────────────────────

class VendorAnalyticsOverviewView(APIView):
    """
    Overview with both revenue views surfaced side-by-side:
      - ``actual``    → orders delivered + paid (money in pocket)
      - ``projected`` → EVERY order in the window (full potential, including
                        the ones already counted in actual)

    Both views are always returned so the UI can show the diff between
    pipeline and realised revenue. The optional ``?revenue_type=`` param only
    mirrors the chosen view into the legacy flat ``revenue.total`` keys.
    """
    permission_classes = [IsAuthenticated]

    def _compute_revenue(self, orders_qs):
        """Return (actual, projected) decimals for a given orders queryset.

        Vendor revenue is ``vendor_payout`` = items subtotal − commission.
        Delivery and service fees are NOT vendor revenue (they fund the
        driver and the platform), so they're excluded here — matching the
        per-order financial split in core/order_financials.py.
        """
        actual = (
            filter_orders_by_revenue_type(orders_qs, 'actual')
            .aggregate(total=Sum('vendor_payout'))['total']
            or Decimal('0.00')
        )
        projected = (
            orders_qs.aggregate(total=Sum('vendor_payout'))['total']
            or Decimal('0.00')
        )
        return actual, projected

    @staticmethod
    def _order_counts(orders, rest_orders, completed_count):
        """Order tallies across BOTH order tables.

        Restaurant orders are stored separately, so counting only the retail
        queryset reported zero for every restaurant vendor.
        """
        def tally(qs, **flt):
            return qs.filter(**flt).count() if qs is not None else 0

        total = orders.count() + tally(rest_orders)
        return {
            'total': total,                   # every order (projected)
            'completed': completed_count,     # delivered + paid (actual)
            'outstanding': total - completed_count,
            'cancelled': (orders.filter(status='cancelled').count()
                          + tally(rest_orders, status='cancelled')),
            'pending': (orders.filter(status='pending').count()
                        + tally(rest_orders, status='pending')),
        }

    @staticmethod
    def _growth(current, previous):
        if not previous:
            return None
        return round(float((current - previous) / previous * 100), 2)

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from orders.models import Order, OrderItem

        revenue_type = _revenue_type(request)
        start, end = _date_range(request)
        order_ids = (
            OrderItem.objects.filter(vendor=vp)
            .values_list('order_id', flat=True)
            .distinct()
        )
        orders = Order.objects.filter(
            id__in=order_ids, created_at__gte=start, created_at__lte=end,
        )

        actual_rev, projected_rev = self._compute_revenue(orders)

        # Restaurant checkouts live in their own table — without this a
        # restaurant vendor's dashboard reads zero across the board.
        rest_orders = restaurant_orders_for(vp, start, end)
        if rest_orders is not None and rest_orders.exists():
            r_actual, r_projected = self._compute_revenue(rest_orders)
            actual_rev += r_actual
            projected_rev += r_projected

        # Previous-period comparison (same window length, immediately preceding)
        period_len = end - start
        prev_orders = Order.objects.filter(
            id__in=order_ids,
            created_at__gte=start - period_len,
            created_at__lte=start,
        )
        prev_actual_rev, prev_projected_rev = self._compute_revenue(prev_orders)
        prev_rest = restaurant_orders_for(vp, start - period_len, start)
        if prev_rest is not None and prev_rest.exists():
            pr_actual, pr_projected = self._compute_revenue(prev_rest)
            prev_actual_rev += pr_actual
            prev_projected_rev += pr_projected

        try:
            perf = vp.performance_score
            ml_score = {'score': perf.score, 'tier': perf.tier, 'scored_at': perf.scored_at}
        except Exception:
            ml_score = None

        customer_ids = set(orders.values_list('user_id', flat=True))
        if rest_orders is not None:
            customer_ids |= set(rest_orders.values_list('user_id', flat=True))
        customer_ids.discard(None)
        unique_customers = len(customer_ids)

        # ── Difference between projected and actual ────────────────────────
        gap = (projected_rev or Decimal('0.00')) - (actual_rev or Decimal('0.00'))
        prev_gap = (prev_projected_rev or Decimal('0.00')) - (prev_actual_rev or Decimal('0.00'))
        # Conversion = actual / projected ⇒ how much of the pipeline has
        # materialised as realised revenue.
        if projected_rev and projected_rev > 0:
            conversion_pct = round(float(actual_rev / projected_rev * 100), 2)
        else:
            conversion_pct = None

        revenue_block = {
            'actual': {
                'total': actual_rev,
                'previous_period': prev_actual_rev,
                'growth_percent': self._growth(actual_rev, prev_actual_rev),
                'description': 'Revenue from orders that are delivered and paid.',
            },
            'projected': {
                'total': projected_rev,
                'previous_period': prev_projected_rev,
                'growth_percent': self._growth(projected_rev, prev_projected_rev),
                'description': 'Total value of every order placed in the period (full potential).',
            },
            'difference': {
                # gap = projected − actual; the amount still to convert
                'amount': gap,
                'previous_period': prev_gap,
                'growth_percent': self._growth(gap, prev_gap),
                # share of projected revenue that has *not* yet been realised
                'percent_of_projected': (
                    round(float(gap / projected_rev * 100), 2)
                    if projected_rev and projected_rev > 0 else None
                ),
                # share of projected revenue that *has* been realised
                'conversion_percent': conversion_pct,
                'description': 'Projected − Actual: revenue still to be realised from outstanding orders.',
            },
            'selected_type': revenue_type,
        }
        # Backwards-compatible flat keys mirror the selected revenue type.
        selected = revenue_block[revenue_type]
        revenue_block.update({
            'total': selected['total'],
            'previous_period': selected['previous_period'],
            'growth_percent': selected['growth_percent'],
        })

        completed_count = filter_orders_by_revenue_type(orders, 'actual').count()
        if rest_orders is not None:
            completed_count += filter_orders_by_revenue_type(rest_orders, 'actual').count()
        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'vendor_name': vp.trading_name or vp.name,
            'revenue': revenue_block,
            'orders': self._order_counts(orders, rest_orders, completed_count),
            'unique_customers': unique_customers,
            'performance_score': ml_score,
        }
        result['insights'] = vendor_overview_insights(result)
        return Response(result)


# ── Orders ────────────────────────────────────────────────────────────────────

class VendorOrderAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from orders.models import Order, OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        order_ids = (
            OrderItem.objects.filter(vendor=vp)
            .values_list('order_id', flat=True)
            .distinct()
        )
        orders = Order.objects.filter(
            id__in=order_ids,
            created_at__gte=start,
            created_at__lte=end,
        )
        # Restaurant stores keep orders in their own table.
        orders = vendor_orders_source(vp, orders, start, end)
        # When viewing "actual", restrict revenue aggregations to delivered+paid;
        # when viewing "projected", aggregate over every order in the window.
        revenue_orders = filter_orders_by_revenue_type(orders, revenue_type)

        # Vendor revenue = vendor_payout (items − commission). Delivery and
        # service fees are excluded — they never settle to the vendor.
        agg = revenue_orders.aggregate(
            total_revenue=Sum('vendor_payout'),
            avg_value=Avg('vendor_payout'),
        )

        # Zero-fill all 7 statuses so every status always appears in the
        # breakdown even when no orders with that status exist in the period.
        all_order_statuses = [
            'pending', 'processing', 'shipped',
            'delivered', 'cancelled', 'refunded', 'partially_refunded',
        ]
        _status_map = {
            s: {'status': s, 'count': 0, 'revenue': Decimal('0.00')}
            for s in all_order_statuses
        }
        for row in orders.values('status').annotate(
            count=Count('id'), revenue=Sum('vendor_payout')
        ):
            _status_map[row['status']] = {
                'status': row['status'],
                'count': row['count'],
                'revenue': row['revenue'] or Decimal('0.00'),
            }
        status_breakdown = sorted(
            _status_map.values(), key=lambda r: r['count'], reverse=True
        )

        fulfillment_split = list(
            orders.values('fulfillment_type').annotate(count=Count('id'))
        )

        # Daily breakdown follows the same revenue-type filter.
        daily = list(
            revenue_orders
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'), revenue=Sum('vendor_payout'))
            .order_by('day')
        )

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'vendor_name': vp.trading_name or vp.name,
            'revenue_type': revenue_type,
            'totals': {
                'total_orders': revenue_orders.count(),
                'total_revenue': agg['total_revenue'] or Decimal('0.00'),
                'avg_order_value': agg['avg_value'] or Decimal('0.00'),
                'pending':    orders.filter(status='pending').count(),
                'processing': orders.filter(status='processing').count(),
                'shipped':    orders.filter(status='shipped').count(),
                'completed':  orders.filter(status='delivered').count(),
                'cancelled':  orders.filter(status='cancelled').count(),
                'refunded':   orders.filter(
                    status__in=('refunded', 'partially_refunded')
                ).count(),
            },
            'status_breakdown': status_breakdown,
            'fulfillment_split': fulfillment_split,
            'daily_breakdown': daily,
        }
        result['insights'] = vendor_order_insights(result)
        return Response(result)


# ── Products ──────────────────────────────────────────────────────────────────

class VendorProductAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from products.models import Product
        from orders.models import OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        products = Product.objects.filter(vendor=vp)

        status_breakdown = products.values('status').annotate(count=Count('id'))

        # Top-selling / slow-moving respect the revenue-type filter. In actual
        # mode only delivered+paid orders count; in projected mode every order
        # counts toward potential sales.
        base_items = OrderItem.objects.filter(
            vendor=vp,
            order__created_at__gte=start,
            order__created_at__lte=end,
        )
        # Restaurants sell through their own line-item table.
        base_items = vendor_order_items_source(vp, base_items, start, end)
        scoped_items = filter_order_items_by_revenue_type(base_items, revenue_type)

        top_selling = (
            scoped_items
            .values('product_id', 'product_name')
            .annotate(
                units_sold=Sum('quantity'),
                revenue=Sum('total_price'),
                orders=Count('order__id', distinct=True),
            )
            .order_by('-revenue')[:20]
        )

        slow_moving_exclude = filter_order_items_by_revenue_type(
            vendor_order_items_source(
                vp,
                OrderItem.objects.filter(vendor=vp, order__created_at__gte=start),
                start, None,
            ),
            revenue_type,
        ).values_list('product_id', flat=True)
        slow_moving = (
            products.filter(status='active')
            .exclude(id__in=slow_moving_exclude)
            .values('id', 'name', 'price')[:20]
        )

        price_agg = products.filter(status='active').aggregate(avg=Avg('price'))

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'revenue_type': revenue_type,
            'totals': {
                'total_products': products.count(),
                'active': products.filter(status='active').count(),
                'avg_price': price_agg['avg'] or 0,
            },
            'status_breakdown': list(status_breakdown),
            'top_selling': list(top_selling),
            'slow_moving': list(slow_moving),
        }
        result['insights'] = vendor_product_insights(result)
        return Response(result)


# ── Categories ────────────────────────────────────────────────────────────────

class VendorCategoryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from products.models import Product
        from orders.models import OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        # ── Products per category (current snapshot, no time window) ─────────
        raw_products = (
            Product.objects.filter(vendor=vp)
            .values('category_id', 'category__name', 'category__slug')
            .annotate(
                total_products=Count('pk'),
                active_products=Count('pk', filter=Q(status='active')),
                avg_price=Avg('price'),
            )
            .order_by('-total_products')
        )

        products_per_category = [
            {
                'category_id': row['category_id'],
                'category_name': row['category__name'],
                'category_slug': row['category__slug'],
                'total_products': row['total_products'],
                'active_products': row['active_products'],
                'avg_price': row['avg_price'] or Decimal('0.00'),
            }
            for row in raw_products
        ]

        # ── Revenue per category (filtered by revenue_type) ───────────────
        category_items = filter_order_items_by_revenue_type(
            vendor_order_items_source(
                vp,
                OrderItem.objects.filter(
                    vendor=vp,
                    order__created_at__gte=start,
                    order__created_at__lte=end,
                ),
                start, end,
            ),
            revenue_type,
        )
        raw_revenue = (
            category_items
            .values('product__category_id', 'product__category__name')
            .annotate(
                revenue=Sum('total_price'),
                units_sold=Sum('quantity'),
                order_count=Count('order__id', distinct=True),
            )
            .order_by('-revenue')
        )

        revenue_per_category = [
            {
                'category_id': row['product__category_id'],
                'category_name': row['product__category__name'],
                'revenue': row['revenue'] or Decimal('0.00'),
                'units_sold': row['units_sold'] or 0,
                'order_count': row['order_count'] or 0,
            }
            for row in raw_revenue
        ]

        top_category_name = revenue_per_category[0]['category_name'] if revenue_per_category else None

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'vendor_name': vp.trading_name or vp.name,
            'revenue_type': revenue_type,
            'totals': {
                'total_categories_with_products': len(products_per_category),
                'total_active_categories': sum(
                    1 for c in products_per_category if (c['active_products'] or 0) > 0
                ),
                'total_categories_with_revenue': len(revenue_per_category),
            },
            'products_per_category': products_per_category,
            'revenue_per_category': revenue_per_category,
            'top_category': top_category_name,
        }
        result['insights'] = vendor_category_insights(result)
        return Response(result)


# ── Customers ─────────────────────────────────────────────────────────────────

class VendorCustomerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from orders.models import Order, OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        order_ids = (
            OrderItem.objects.filter(vendor=vp)
            .values_list('order_id', flat=True)
            .distinct()
        )
        orders = Order.objects.filter(
            id__in=order_ids, created_at__gte=start, created_at__lte=end
        )
        # Restaurant stores keep orders in their own table.
        orders = vendor_orders_source(vp, orders, start, end)
        # Customer metrics derived from spend should respect the revenue-type
        # filter — projected uses every order, actual only delivered+paid.
        revenue_orders = filter_orders_by_revenue_type(orders, revenue_type)

        unique_customers = revenue_orders.values('user_id').distinct().count()

        # "Spend" here is the revenue this customer generates for the vendor
        # (vendor_payout = items − commission), not the gross the customer paid
        # — so the vendor's customer value never includes delivery/service fees.
        repeat = (
            revenue_orders.values('user__email', 'user_id')
            .annotate(order_count=Count('id'), total_spend=Sum('vendor_payout'))
            .filter(order_count__gt=1)
            .order_by('-total_spend')[:20]
        )

        all_order_ids = (
            OrderItem.objects.filter(vendor=vp)
            .values_list('order_id', flat=True)
        )
        new_cust_ids = set()
        for user_id in revenue_orders.values_list('user_id', flat=True).distinct():
            first_order = (
                Order.objects.filter(id__in=all_order_ids, user_id=user_id)
                .order_by('created_at')
                .first()
            )
            if first_order and first_order.created_at >= start:
                new_cust_ids.add(user_id)

        avg_ltv = (
            revenue_orders
            .values('user_id')
            .annotate(spend=Sum('vendor_payout'))
            .aggregate(avg=Avg('spend'))
        )

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'vendor_name': vp.trading_name or vp.name,
            'revenue_type': revenue_type,
            'totals': {
                'unique_customers': unique_customers,
                'new_customers': len(new_cust_ids),
                'repeat_customers': repeat.count(),
                'avg_customer_lifetime_value': avg_ltv['avg'] or 0,
            },
            'top_repeat_customers': list(repeat),
        }
        result['insights'] = vendor_customer_insights(result)
        return Response(result)


# ── Negotiations ──────────────────────────────────────────────────────────────

class VendorNegotiationAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from negotiations.models import NegotiationRoom, NegotiationOffer

        start, end = _date_range(request)
        rooms = NegotiationRoom.objects.filter(
            vendor=vp, created_at__gte=start, created_at__lte=end
        )

        total = rooms.count()
        agreed = rooms.filter(status='agreed').count()
        agreement_rate = agreed / total * 100 if total else 0

        status_breakdown = rooms.values('status').annotate(count=Count('id'))
        mode_breakdown = rooms.values('mode').annotate(count=Count('id'))

        agreed_revenue = rooms.filter(status='agreed').aggregate(
            total=Sum('agreed_price')
        )

        avg_rounds = (
            NegotiationOffer.objects.filter(room__in=rooms.filter(status='agreed'))
            .values('room_id')
            .annotate(rounds=Count('id'))
            .aggregate(avg=Avg('rounds'))
        )

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'totals': {
                'total': total,
                'agreed': agreed,
                'expired': rooms.filter(status='expired').count(),
                'open': rooms.filter(status='open').count(),
                'agreement_rate_percent': round(agreement_rate, 2),
            },
            'agreed_revenue': agreed_revenue['total'] or 0,
            'avg_rounds_to_agreement': avg_rounds['avg'] or 0,
            'status_breakdown': list(status_breakdown),
            'mode_breakdown': list(mode_breakdown),
        }
        result['insights'] = vendor_negotiation_insights(result)
        return Response(result)


# ── Payments ──────────────────────────────────────────────────────────────────

class VendorPaymentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from payments.models import Transaction, Refund

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        txns = Transaction.objects.filter(
            vendor=vp, created_at__gte=start, created_at__lte=end
        )

        # actual    → only successful transactions (money in hand)
        # projected → every transaction (potential / pipeline)
        if revenue_type == 'actual':
            revenue_txns = txns.filter(status='success')
        else:
            revenue_txns = txns

        # Vendor revenue per transaction = the linked order's vendor_payout
        # (items − commission). The amount the customer actually paid
        # (`amount`) includes delivery + service fees that never settle to the
        # vendor, so it's only surfaced separately as `gross_customer_paid`.
        # A transaction links to EITHER a retail order or a restaurant one,
        # so read the payout/commission from whichever is set — summing only
        # `order__*` reported zero revenue for every restaurant vendor.
        payout = Coalesce('order__vendor_payout',
                          'restaurant_order__vendor_payout')
        commission = Coalesce('order__commission_amount',
                              'restaurant_order__commission_amount')
        agg = revenue_txns.aggregate(
            total=Sum(payout),
            commission=Sum(commission),
            gross=Sum('amount'),
            count=Count('id'),
        )
        total_txns = txns.count()
        success_rate = (
            txns.filter(status='success').count() / total_txns * 100
            if total_txns else 0
        )

        status_breakdown = txns.values('status').annotate(
            count=Count('id'), total=Sum(payout)
        )
        channel_breakdown = revenue_txns.values('channel').annotate(
            count=Count('id'), total=Sum(payout),
        )

        refunds = Refund.objects.filter(
            transaction__vendor=vp,
            created_at__gte=start,
            created_at__lte=end,
        )
        refund_agg = refunds.filter(status='processed').aggregate(
            total=Sum('amount'), count=Count('id')
        )

        # Commission Sanoa kept from these orders (already excluded from the
        # vendor's revenue). Surfaced for transparency, not deducted again.
        commission_total = agg['commission'] or Decimal('0')
        vendor_revenue = agg['total'] or Decimal('0')

        result = {
            'period': {'start': start, 'end': end},
            'vendor_id': str(vp.id),
            'vendor_name': vp.trading_name or vp.name,
            'revenue_type': revenue_type,
            'transactions': {
                'total': total_txns,
                'successful': txns.filter(status='success').count(),
                'counted': agg['count'] or 0,  # txns included in the totals
                'success_rate_percent': round(success_rate, 2),
                # Vendor revenue = items − commission. The vendor receives this
                # in full; no further fees are deducted from their payout.
                'total_revenue': vendor_revenue,
                'net_revenue': vendor_revenue,
                'commission': commission_total,
                'gross_customer_paid': agg['gross'] or Decimal('0'),
            },
            'refunds': {
                'count': refund_agg['count'] or 0,
                'total_amount': refund_agg['total'] or 0,
            },
            'by_status': list(status_breakdown),
            'by_channel': list(channel_breakdown),
        }
        result['insights'] = vendor_payment_insights(result)
        return Response(result)


# ── Subscription / Tier ───────────────────────────────────────────────────────

class VendorSubscriptionAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        vp, err = _resolve_vendor(request, vendor_id)
        if err:
            return err

        from tiers.models import VendorTierSubscription

        try:
            sub = VendorTierSubscription.objects.select_related('tier').get(vendor=vp)
        except VendorTierSubscription.DoesNotExist:
            return Response({
                'vendor_id': str(vp.id),
                'subscription': None,
                'tier': None,
                'insights': ['ℹ️ This vendor has no active tier subscription.'],
            })

        if sub.is_overdue:
            sub.expire_and_downgrade()
        if not sub.is_active:
            return Response({
                'vendor_id': str(vp.id),
                'subscription': {'id': str(sub.pk), 'status': sub.status,
                                 'is_active': False, 'current_period_end': sub.current_period_end},
                'tier': None,
                'insights': ['Your subscription is inactive. Subscribe again to restore paid benefits.'],
            })
        tier = sub.tier
        now = timezone.now()

        days_remaining = None
        if sub.current_period_end:
            delta = sub.current_period_end - now
            days_remaining = max(0, delta.days)

        # The discount the vendor's tier shaves off the platform's
        # merchant commission on each settled order. Surfaced to the
        # vendor's "How much am I saving?" widget.
        commission_saving = Decimal(str(
            getattr(tier, 'commission_discount', 0) or 0
        ))

        # How many products the vendor has vs their limit
        try:
            from products.models import Product
            active_products = Product.objects.filter(vendor=vp, status='active').count()
        except Exception:
            active_products = 0

        product_limit = tier.max_products
        product_usage_percent = (
            round(active_products / product_limit * 100, 1)
            if product_limit > 0 else None  # None = unlimited
        )

        result = {
            'vendor_id': str(vp.id),
            'subscription': {
                'id': str(sub.id),
                'status': sub.status,
                'started_at': sub.started_at,
                'current_period_start': sub.current_period_start,
                'current_period_end': sub.current_period_end,
                'cancelled_at': sub.cancelled_at,
                'days_remaining': days_remaining,
                'is_active': sub.is_active,
            },
            'tier': {
                'id': str(tier.id),
                'name': tier.name,
                'slug': tier.slug,
                'tier_level': tier.tier_level,
                'price': tier.price,
                'commission_rate': tier.commission_rate,
                'commission_discount': tier.commission_discount,
                'commission_saving_vs_default': commission_saving,
                'max_products': tier.max_products,
                'negotiation_enabled': tier.negotiation_enabled,
                'max_markup_percent': tier.max_markup_percent,
                'max_discount_percent': tier.max_discount_percent,
                'featured_listings': tier.featured_listings,
                'search_priority_boost': tier.search_priority_boost,
                'trial_days': tier.trial_days,
                'features': tier.features,
            },
            'product_usage': {
                'active_products': active_products,
                'limit': product_limit if product_limit > 0 else 'unlimited',
                'usage_percent': product_usage_percent,
            },
        }

        # Insights
        notes = []
        if sub.status == 'past_due':
            notes.append('🔴 Your subscription is past due. Update your payment method to avoid losing tier benefits.')
        elif sub.status == 'cancelled':
            notes.append(f'⚠️ Your {tier.name} subscription was cancelled. You will revert to the free tier at period end.')
        elif days_remaining is not None and days_remaining <= 7 and sub.status == 'active':
            notes.append(f'⏳ Your {tier.name} subscription renews in {days_remaining} day(s).')

        if commission_saving > 0:
            notes.append(f'💰 You save {commission_saving:.1f}% commission on every sale vs the default 12% rate.')

        if product_usage_percent is not None and product_usage_percent >= 80:
            notes.append(f'📦 You are using {product_usage_percent}% of your product limit ({active_products}/{product_limit}). Consider upgrading to list more products.')

        if not tier.negotiation_enabled:
            notes.append('💡 Upgrade to a higher tier to unlock the price negotiation engine and increase conversions.')

        result['insights'] = notes
        return Response(result)

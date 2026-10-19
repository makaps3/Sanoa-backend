"""
Platform-admin analytics views.
All views require platform admin authentication.
Supports ?period=today|week|month|year and ?from=YYYY-MM-DD&to=YYYY-MM-DD.
"""
import datetime
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.insights import (
    platform_overview_insights,
    customer_analytics_insights,
    order_analytics_insights,
    payment_analytics_insights,
    negotiation_analytics_insights,
    debit_analytics_insights,
    delivery_analytics_insights,
    driver_analytics_insights,
    payout_analytics_insights,
    subscription_analytics_insights,
)


def _require_admin(request):
    user = request.user
    return (
        user.is_staff
        or hasattr(user, 'admin_profile')
        or getattr(user, 'user_type', '') == 'admin'
    )


def _date_range(request):
    """Return (start, end) datetimes from query params."""
    period = request.query_params.get('period', 'month')
    from_str = request.query_params.get('from')
    to_str = request.query_params.get('to')
    now = timezone.now()

    if from_str and to_str:
        try:
            start = datetime.datetime.fromisoformat(from_str).replace(tzinfo=datetime.timezone.utc)
            end = datetime.datetime.fromisoformat(to_str).replace(tzinfo=datetime.timezone.utc)
            return start, end
        except ValueError:
            pass

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = now - datetime.timedelta(days=7)
    elif period == 'year':
        start = now - datetime.timedelta(days=365)
    else:  # month (default)
        start = now - datetime.timedelta(days=30)

    return start, now


# ── Revenue-type filter (shared with vendor analytics) ────────────────────────
# Applies to all admin endpoints EXCEPT negotiation, debit, deliveries,
# drivers, payouts and subscriptions — those don't have order-revenue semantics.
#
#   actual    → orders delivered/completed AND payment_status='paid'
#   projected → every order in the window (full potential pipeline)

ACTUAL_ORDER_STATUSES = ('delivered', 'completed')


def _revenue_type(request):
    """Return ``'actual'`` (default) or ``'projected'``."""
    rt = (request.query_params.get('revenue_type') or '').strip().lower()
    return rt if rt in ('actual', 'projected') else 'actual'


def _filter_orders_by_revenue_type(orders_qs, revenue_type):
    if revenue_type == 'actual':
        return orders_qs.filter(
            status__in=ACTUAL_ORDER_STATUSES,
            payment_status='paid',
        )
    return orders_qs


def _filter_order_items_by_revenue_type(items_qs, revenue_type):
    if revenue_type == 'actual':
        return items_qs.filter(
            order__status__in=ACTUAL_ORDER_STATUSES,
            order__payment_status='paid',
        )
    return items_qs


def _compute_admin_revenue_views(orders_qs):
    """
    Returns (actual_total, projected_total) for an orders queryset.
      actual    = delivered/completed + paid
      projected = every order in the window
    """
    actual = (
        _filter_orders_by_revenue_type(orders_qs, 'actual')
        .aggregate(total=Sum('total_amount'))['total']
        or Decimal('0.00')
    )
    projected = (
        orders_qs.aggregate(total=Sum('total_amount'))['total']
        or Decimal('0.00')
    )
    return actual, projected


def _growth(current, previous):
    if not previous:
        return None
    return round(float((current - previous) / previous * 100), 2)


# ── Overview ─────────────────────────────────────────────────────────────────

class AdminAnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from accounts.models import User
        from orders.models import Order
        from payments.models import Transaction
        from delivery.models import DeliveryJob
        from analytics.models import DailyPlatformSnapshot

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        # Revenue is now derived from Orders so actual/projected semantics
        # align with vendor analytics.
        orders = Order.objects.filter(created_at__gte=start, created_at__lte=end)
        actual_rev, projected_rev = _compute_admin_revenue_views(orders)

        # Previous period
        period_len = (end - start)
        prev_orders = Order.objects.filter(
            created_at__gte=start - period_len, created_at__lte=start,
        )
        prev_actual_rev, prev_projected_rev = _compute_admin_revenue_views(prev_orders)

        # Transactions are still surfaced for the txn snapshot.
        txns = Transaction.objects.filter(created_at__gte=start, created_at__lte=end, status='success')
        txn_revenue = txns.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Difference block — gap and conversion between projected and actual.
        gap = (projected_rev or Decimal('0.00')) - (actual_rev or Decimal('0.00'))
        prev_gap = (prev_projected_rev or Decimal('0.00')) - (prev_actual_rev or Decimal('0.00'))
        conversion_pct = (
            round(float(actual_rev / projected_rev * 100), 2)
            if projected_rev and projected_rev > 0 else None
        )

        revenue_block = {
            'actual': {
                'total': actual_rev,
                'previous_period': prev_actual_rev,
                'growth_percent': _growth(actual_rev, prev_actual_rev),
                'description': 'Revenue from orders that are delivered and paid.',
            },
            'projected': {
                'total': projected_rev,
                'previous_period': prev_projected_rev,
                'growth_percent': _growth(projected_rev, prev_projected_rev),
                'description': 'Total value of every order placed in the period (full potential).',
            },
            'difference': {
                'amount': gap,
                'previous_period': prev_gap,
                'growth_percent': _growth(gap, prev_gap),
                'percent_of_projected': (
                    round(float(gap / projected_rev * 100), 2)
                    if projected_rev and projected_rev > 0 else None
                ),
                'conversion_percent': conversion_pct,
                'description': 'Projected − Actual: revenue still to be realised from outstanding orders.',
            },
            'selected_type': revenue_type,
        }
        selected = revenue_block[revenue_type]
        revenue_block.update({
            'total': selected['total'],
            'previous_period': selected['previous_period'],
            'growth_percent': selected['growth_percent'],
        })

        # Last 7 daily snapshots for sparkline
        snapshots = list(
            DailyPlatformSnapshot.objects.order_by('-date')[:7].values(
                'date', 'total_revenue', 'total_orders', 'total_transactions',
                'new_customers', 'completed_deliveries',
            )
        )

        completed_count = _filter_orders_by_revenue_type(orders, 'actual').count()
        result = {
            'period': {'start': start, 'end': end},
            'revenue': revenue_block,
            'orders': {
                'total': orders.count(),
                'completed': completed_count,
                'outstanding': orders.count() - completed_count,
                'cancelled': orders.filter(status='cancelled').count(),
            },
            'users': {
                'total_customers': User.objects.filter(user_type='customer').count(),
                'total_vendors': User.objects.filter(user_type='vendor').count(),
                'total_drivers': User.objects.filter(user_type='driver').count(),
                'new_customers': User.objects.filter(user_type='customer', date_joined__gte=start).count(),
                'new_vendors': User.objects.filter(user_type='vendor', date_joined__gte=start).count(),
            },
            'transactions': {
                'total': txns.count(),
                'total_value': txn_revenue,
            },
            'deliveries': {
                'total': DeliveryJob.objects.filter(created_at__gte=start).count(),
                'completed': DeliveryJob.objects.filter(created_at__gte=start, status='delivered').count(),
            },
            'daily_snapshots': snapshots,
        }
        result['insights'] = platform_overview_insights(result)
        return Response(result)


# ── Customers ─────────────────────────────────────────────────────────────────

class AdminCustomerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from accounts.models import User, CustomerProfile
        from orders.models import Order
        from analytics.models import CustomerChurnScore

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        customers = User.objects.filter(user_type='customer')
        new_customers = customers.filter(date_joined__gte=start, date_joined__lte=end).count()

        # Churn risk distribution (from ML scores)
        churn_dist = CustomerChurnScore.objects.values('risk_segment').annotate(count=Count('id'))
        churn_map = {row['risk_segment']: row['count'] for row in churn_dist}

        # Top spenders / spend aggregates honour the revenue-type filter:
        # actual = delivered+paid only; projected = every order in the window.
        spend_orders = _filter_orders_by_revenue_type(
            Order.objects.filter(created_at__gte=start, created_at__lte=end),
            revenue_type,
        )
        top_spenders = (
            spend_orders
            .values('user__email', 'user__id')
            .annotate(total_spend=Sum('total_amount'), order_count=Count('id'))
            .order_by('-total_spend')[:10]
        )

        spend_agg = spend_orders.aggregate(
            total=Sum('total_amount'), avg=Avg('total_amount'),
        )

        # Suspension/verification stats
        suspended = customers.filter(is_suspended=True).count()
        verified = customers.filter(is_verified=True).count()

        # Loyalty distribution
        loyalty_agg = CustomerProfile.objects.aggregate(
            total_points=Sum('loyalty_points'),
            avg_points=Avg('loyalty_points'),
        )

        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'totals': {
                'total_customers': customers.count(),
                'new_customers': new_customers,
                'suspended': suspended,
                'verified': verified,
            },
            'churn_risk': {
                'low': churn_map.get('low', 0),
                'medium': churn_map.get('medium', 0),
                'high': churn_map.get('high', 0),
                'note': 'Computed weekly via Scikit-learn rule-based model',
            },
            'spending': {
                'total': spend_agg['total'] or 0,
                'average_order_value': spend_agg['avg'] or 0,
            },
            'loyalty': {
                'total_points_issued': loyalty_agg['total_points'] or 0,
                'avg_points_per_customer': loyalty_agg['avg_points'] or 0,
            },
            'top_spenders': list(top_spenders),
        }
        result['insights'] = customer_analytics_insights(result)
        return Response(result)


# ── Orders ────────────────────────────────────────────────────────────────────

class AdminOrderAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from orders.models import Order, OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        orders = Order.objects.filter(created_at__gte=start, created_at__lte=end)
        # Revenue aggregations follow actual/projected:
        # actual = delivered+paid only; projected = every order.
        revenue_orders = _filter_orders_by_revenue_type(orders, revenue_type)

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
            count=Count('id'), revenue=Sum('total_amount')
        ):
            _status_map[row['status']] = {
                'status': row['status'],
                'count': row['count'],
                'revenue': row['revenue'] or Decimal('0.00'),
            }
        status_breakdown = sorted(
            _status_map.values(), key=lambda r: r['count'], reverse=True
        )

        payment_status_breakdown = list(
            orders.values('payment_status').annotate(count=Count('id'))
        )

        fulfillment_split = list(
            orders.values('fulfillment_type').annotate(count=Count('id'))
        )

        agg = revenue_orders.aggregate(
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
        )

        # Top vendors: revenue tied to the same revenue-type filter.
        top_vendor_items = _filter_order_items_by_revenue_type(
            OrderItem.objects.filter(
                order__created_at__gte=start, order__created_at__lte=end,
            ),
            revenue_type,
        )
        top_vendors = (
            top_vendor_items
            .values('vendor__id', 'vendor__name', 'vendor__trading_name')
            .annotate(order_count=Count('order_id', distinct=True), revenue=Sum('total_price'))
            .order_by('-revenue')[:10]
        )

        # Daily trend uses the same scoped set so the chart matches headline numbers.
        daily = list(
            revenue_orders
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'), revenue=Sum('total_amount'))
            .order_by('day')
        )

        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'totals': {
                'total_orders': revenue_orders.count(),
                'total_revenue': agg['total_revenue'] or Decimal('0.00'),
                'avg_order_value': agg['avg_order_value'] or Decimal('0.00'),
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
            'payment_status_breakdown': payment_status_breakdown,
            'fulfillment_split': fulfillment_split,
            'top_vendors_by_revenue': list(top_vendors),
            'daily_breakdown': daily,
        }
        result['insights'] = order_analytics_insights(result)
        return Response(result)


# ── Payments / Transactions ───────────────────────────────────────────────────

class AdminPaymentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from payments.models import Transaction, Refund, Dispute, PaystackSubaccount

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        txns = Transaction.objects.filter(created_at__gte=start, created_at__lte=end)

        # actual    → only successful transactions (money in hand)
        # projected → every transaction (full potential)
        revenue_txns = (
            txns.filter(status='success') if revenue_type == 'actual' else txns
        )

        status_breakdown = txns.values('status').annotate(count=Count('id'), total=Sum('amount'))
        channel_breakdown = revenue_txns.values('channel').annotate(
            count=Count('id'), total=Sum('amount'),
        )
        intent_breakdown = txns.values('payment_intent').annotate(
            count=Count('id'), total=Sum('amount'),
        )

        agg = revenue_txns.aggregate(
            total_revenue=Sum('amount'),
            total_fees=Sum('paystack_fees'),
            txn_count=Count('id'),
        )

        refunds = Refund.objects.filter(created_at__gte=start, created_at__lte=end)
        refund_agg = refunds.filter(status='processed').aggregate(
            total=Sum('amount'), count=Count('id'),
        )

        disputes = Dispute.objects.filter(created_at__gte=start, created_at__lte=end)
        dispute_agg = disputes.aggregate(total=Sum('amount'), count=Count('id'))

        total_txns = txns.count()
        success_rate = (
            txns.filter(status='success').count() / total_txns * 100
            if total_txns else 0
        )

        platform_fee_total = agg['total_fees'] or Decimal('0')
        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'transactions': {
                'total': total_txns,
                'successful': txns.filter(status='success').count(),
                'counted': agg['txn_count'] or 0,
                'success_rate_percent': round(success_rate, 2),
                'total_revenue': agg['total_revenue'] or 0,
                'platform_fee': platform_fee_total,
                'net_revenue': (agg['total_revenue'] or Decimal('0')) - platform_fee_total,
            },
            'refunds': {
                'count': refund_agg['count'] or 0,
                'total_amount': refund_agg['total'] or 0,
            },
            'disputes': {
                'count': dispute_agg['count'] or 0,
                'total_amount': dispute_agg['total'] or 0,
            },
            'by_status': list(status_breakdown),
            'by_channel': list(channel_breakdown),
            'by_intent': list(intent_breakdown),
        }
        result['insights'] = payment_analytics_insights(result)
        return Response(result)


# ── Products ──────────────────────────────────────────────────────────────────

class AdminProductAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from products.models import Product
        from orders.models import OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        products = Product.objects.all()
        status_breakdown = products.values('status').annotate(count=Count('id'))

        # Top selling honours the revenue-type filter.
        top_selling_items = _filter_order_items_by_revenue_type(
            OrderItem.objects.filter(
                order__created_at__gte=start, order__created_at__lte=end,
            ),
            revenue_type,
        )
        top_selling = (
            top_selling_items
            .values('product_id', 'product_name', 'product__vendor__name')
            .annotate(
                units_sold=Sum('quantity'),
                revenue=Sum('total_price'),
                order_count=Count('order_id', distinct=True),
            )
            .order_by('-revenue')[:20]
        )

        price_agg = products.filter(status='active').aggregate(
            avg_price=Avg('price'), min_price=Sum('price'),
        )

        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'totals': {
                'total_products': products.count(),
                'active': products.filter(status='active').count(),
                'inactive': products.filter(status='inactive').count(),
                'avg_price': price_agg['avg_price'] or 0,
            },
            'status_breakdown': list(status_breakdown),
            'top_selling': list(top_selling),
        }
        result['insights'] = []
        return Response(result)


# ── Categories ────────────────────────────────────────────────────────────────

class AdminCategoryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from products.models import Category, Product
        from orders.models import OrderItem

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)

        categories = Category.objects.all()

        # Products per category (snapshot — unchanged by revenue type)
        cat_products = (
            Product.objects.filter(status='active')
            .values('category__id', 'category__name')
            .annotate(product_count=Count('id'), avg_price=Avg('price'))
            .order_by('-product_count')
        )

        # Revenue per category — filtered by actual/projected.
        cat_items = _filter_order_items_by_revenue_type(
            OrderItem.objects.filter(
                order__created_at__gte=start, order__created_at__lte=end,
            ),
            revenue_type,
        )
        cat_revenue = (
            cat_items
            .values('product__category__id', 'product__category__name')
            .annotate(revenue=Sum('total_price'), orders=Count('order_id', distinct=True))
            .order_by('-revenue')[:20]
        )

        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'totals': {
                'total_categories': categories.count(),
                'system_categories': categories.filter(is_system=True).count(),
                'custom_categories': categories.filter(is_system=False).count(),
                'active': categories.filter(is_active=True).count(),
            },
            'products_per_category': list(cat_products),
            'revenue_per_category': list(cat_revenue),
        }
        result['insights'] = []
        return Response(result)


# ── Negotiations ──────────────────────────────────────────────────────────────

class AdminNegotiationAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from negotiations.models import NegotiationRoom, NegotiationOffer

        start, end = _date_range(request)
        rooms = NegotiationRoom.objects.filter(created_at__gte=start, created_at__lte=end)

        status_breakdown = rooms.values('status').annotate(count=Count('id'))
        mode_breakdown = rooms.values('mode').annotate(count=Count('id'))

        total = rooms.count()
        agreed = rooms.filter(status='agreed').count()
        agreement_rate = agreed / total * 100 if total else 0

        # Avg rounds to agreement
        avg_rounds = NegotiationOffer.objects.filter(
            room__in=rooms.filter(status='agreed'),
        ).values('room_id').annotate(rounds=Count('id')).aggregate(avg=Avg('rounds'))

        # Revenue from agreed negotiations
        agreed_revenue = rooms.filter(
            status='agreed', agreed_price__isnull=False,
        ).aggregate(total=Sum('agreed_price'))

        # AI vs manual agreement rate
        ai_total = rooms.filter(mode='ai').count()
        ai_agreed = rooms.filter(mode='ai', status='agreed').count()
        manual_total = rooms.filter(mode='manual').count()
        manual_agreed = rooms.filter(mode='manual', status='agreed').count()

        result = {
            'period': {'start': start, 'end': end},
            'totals': {
                'total_negotiations': total,
                'agreed': agreed,
                'expired': rooms.filter(status='expired').count(),
                'cancelled': rooms.filter(status='cancelled').count(),
                'open': rooms.filter(status='open').count(),
                'agreement_rate_percent': round(agreement_rate, 2),
            },
            'avg_rounds_to_agreement': avg_rounds['avg'] or 0,
            'agreed_price_total': agreed_revenue['total'] or 0,
            'mode_breakdown': list(mode_breakdown),
            'status_breakdown': list(status_breakdown),
            'ai_performance': {
                'total': ai_total,
                'agreed': ai_agreed,
                'agreement_rate_percent': round(ai_agreed / ai_total * 100, 2) if ai_total else 0,
            },
            'manual_performance': {
                'total': manual_total,
                'agreed': manual_agreed,
                'agreement_rate_percent': round(manual_agreed / manual_total * 100, 2) if manual_total else 0,
            },
        }
        result['insights'] = negotiation_analytics_insights(result)
        return Response(result)


# ── Debit / Credit ────────────────────────────────────────────────────────────

class AdminDebitAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from debit.models import CreditAccount, CreditPurchase, CreditRepayment

        start, end = _date_range(request)

        accounts = CreditAccount.objects.all()
        status_breakdown = accounts.values('status').annotate(count=Count('id'))

        agg = accounts.aggregate(
            total_balance=Sum('current_balance'),
            total_penalties=Sum('total_penalties'),
            total_limit=Sum('credit_limit'),
        )

        purchases = CreditPurchase.objects.filter(created_at__gte=start, created_at__lte=end)
        purchase_agg = purchases.aggregate(
            total_issued=Sum('remaining_amount'),
            total_amount=Sum('total_amount'),
            count=Count('id'),
        )

        repayments = CreditRepayment.objects.filter(created_at__gte=start, created_at__lte=end)
        repayment_agg = repayments.aggregate(
            total=Sum('amount'), count=Count('id'),
        )

        overdue_count = sum(1 for p in CreditPurchase.objects.filter(
            status__in=('active', 'defaulted')
        ) if p.is_overdue)

        purchase_status = purchases.values('status').annotate(count=Count('id'))

        result = {
            'period': {'start': start, 'end': end},
            'accounts': {
                'total': accounts.count(),
                'active': accounts.filter(status='active').count(),
                'suspended': accounts.filter(status='suspended').count(),
                'closed': accounts.filter(status='closed').count(),
                'status_breakdown': list(status_breakdown),
            },
            'balances': {
                'total_credit_limit': agg['total_limit'] or 0,
                'total_outstanding_balance': agg['total_balance'] or 0,
                'total_penalties': agg['total_penalties'] or 0,
            },
            'purchases': {
                'count': purchase_agg['count'] or 0,
                'total_credit_issued': purchase_agg['total_issued'] or 0,
                'total_purchase_value': purchase_agg['total_amount'] or 0,
                'overdue_count': overdue_count,
                'status_breakdown': list(purchase_status),
            },
            'repayments': {
                'count': repayment_agg['count'] or 0,
                'total_repaid': repayment_agg['total'] or 0,
            },
        }
        result['insights'] = debit_analytics_insights(result)
        return Response(result)


# ── Deliveries ────────────────────────────────────────────────────────────────

class AdminDeliveryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DeliveryJob, DriverRating, DeliveryFare
        import numpy as np

        start, end = _date_range(request)
        jobs = DeliveryJob.objects.filter(created_at__gte=start, created_at__lte=end)

        status_breakdown = jobs.values('status').annotate(count=Count('id'))
        total = jobs.count()
        completed = jobs.filter(status='delivered').count()
        failed = jobs.filter(status__in=('cancelled', 'failed')).count()
        completion_rate = completed / total * 100 if total else 0

        agg = jobs.aggregate(
            avg_distance=Avg('distance_km'),
            total_fare=Sum('fare_amount'),
            avg_fare=Avg('fare_amount'),
        )

        # Avg delivery time in minutes
        delivery_times = []
        for job in jobs.filter(status='delivered', accepted_at__isnull=False, delivered_at__isnull=False):
            delta = (job.delivered_at - job.accepted_at).total_seconds() / 60
            if 0 < delta < 480:
                delivery_times.append(delta)
        avg_delivery_time = round(float(np.mean(delivery_times)), 2) if delivery_times else None

        ratings = DriverRating.objects.filter(created_at__gte=start, created_at__lte=end)
        rating_agg = ratings.aggregate(avg=Avg('rating'), count=Count('id'))

        result = {
            'period': {'start': start, 'end': end},
            'totals': {
                'total_deliveries': total,
                'completed': completed,
                'failed': failed,
                'pending': jobs.filter(status='pending').count(),
                'in_transit': jobs.filter(status='in_transit').count(),
                'completion_rate_percent': round(completion_rate, 2),
            },
            'performance': {
                'avg_distance_km': agg['avg_distance'] or 0,
                'total_fare_collected': agg['total_fare'] or 0,
                'avg_fare': agg['avg_fare'] or 0,
                'avg_delivery_time_mins': avg_delivery_time,
            },
            'ratings': {
                'avg_driver_rating': rating_agg['avg'] or 0,
                'total_ratings': rating_agg['count'],
            },
            'status_breakdown': list(status_breakdown),
        }
        result['insights'] = delivery_analytics_insights(result)
        return Response(result)


# ── Drivers ───────────────────────────────────────────────────────────────────

class AdminDriverAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DeliveryDriver, DeliveryJob
        from analytics.models import DriverPerformanceScore

        start, end = _date_range(request)
        drivers = DeliveryDriver.objects.all()

        verification_breakdown = drivers.values(
            'background_check_status'
        ).annotate(count=Count('id'))

        vehicle_breakdown = drivers.values('vehicle_type').annotate(count=Count('id'))

        agg = drivers.aggregate(avg_rating=Avg('average_rating'))

        # ML score distribution
        score_dist = DriverPerformanceScore.objects.values('grade').annotate(count=Count('id'))

        # Flagged for payout anomaly
        anomaly_count = DriverPerformanceScore.objects.filter(payout_anomaly=True).count()

        # Top 10 drivers
        top_drivers = (
            DriverPerformanceScore.objects.select_related('driver__user')
            .order_by('-score')[:10]
            .values('driver__user__email', 'score', 'grade', 'total_deliveries', 'avg_rating', 'completion_rate')
        )

        result = {
            'period': {'start': start, 'end': end},
            'totals': {
                'total_drivers': drivers.count(),
                'available': drivers.filter(is_available=True).count(),
                'approved': drivers.filter(background_check_status='approved').count(),
                'pending_verification': drivers.filter(background_check_status='pending').count(),
                'avg_rating': agg['avg_rating'] or 0,
            },
            'ml_performance': {
                'grade_distribution': list(score_dist),
                'payout_anomaly_flagged': anomaly_count,
                'note': 'Computed weekly via Scikit-learn composite scoring',
            },
            'top_drivers': list(top_drivers),
            'vehicle_breakdown': list(vehicle_breakdown),
            'verification_breakdown': list(verification_breakdown),
        }
        result['insights'] = driver_analytics_insights(result)
        return Response(result)


# ── Driver Payouts ────────────────────────────────────────────────────────────

class AdminPayoutAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from delivery.models import DriverPayout, DriverEarning

        start, end = _date_range(request)
        payouts = DriverPayout.objects.filter(created_at__gte=start, created_at__lte=end)

        agg = payouts.aggregate(
            total_gross=Sum('total_gross'),
            total_commission=Sum('total_commission'),
            total_net=Sum('total_net'),
            count=Count('id'),
        )

        status_breakdown = payouts.values('status').annotate(count=Count('id'), total=Sum('total_net'))

        earnings = DriverEarning.objects.filter(created_at__gte=start, created_at__lte=end)
        earning_agg = earnings.aggregate(
            total_gross=Sum('gross_amount'),
            total_commission=Sum('platform_commission'),
            total_net=Sum('net_amount'),
        )

        # Top earning drivers
        top_earners = (
            earnings.values('driver__user__email')
            .annotate(total=Sum('net_amount'), jobs=Count('id'))
            .order_by('-total')[:10]
        )

        result = {
            'period': {'start': start, 'end': end},
            'payouts': {
                'count': agg['count'] or 0,
                'total_gross': agg['total_gross'] or 0,
                'total_commission': agg['total_commission'] or 0,
                'total_net_paid': agg['total_net'] or 0,
                'pending': payouts.filter(status='pending').aggregate(total=Sum('total_net'))['total'] or 0,
            },
            'earnings': {
                'total_gross': earning_agg['total_gross'] or 0,
                'platform_commission': earning_agg['total_commission'] or 0,
                'driver_net': earning_agg['total_net'] or 0,
            },
            'status_breakdown': list(status_breakdown),
            'top_earners': list(top_earners),
        }
        result['insights'] = payout_analytics_insights(result)
        return Response(result)


# ── Subaccounts ───────────────────────────────────────────────────────────────

class AdminSubaccountAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from payments.models import PaystackSubaccount, Transaction

        start, end = _date_range(request)
        revenue_type = _revenue_type(request)
        subaccounts = PaystackSubaccount.objects.all()

        # actual    → only successful txns route to subaccounts
        # projected → every txn (success/pending/failed) attached to a subaccount
        sub_txns = Transaction.objects.filter(
            created_at__gte=start, created_at__lte=end,
            subaccount__isnull=False,
        )
        if revenue_type == 'actual':
            sub_txns = sub_txns.filter(status='success')

        subaccount_revenue = (
            sub_txns
            .values('subaccount__id', 'subaccount__business_name', 'subaccount__subaccount_code')
            .annotate(
                revenue=Sum('amount'),
                txn_count=Count('id'),
                fees=Sum('paystack_fees'),
            )
            .order_by('-revenue')[:20]
        )

        result = {
            'period': {'start': start, 'end': end},
            'revenue_type': revenue_type,
            'totals': {
                'total_subaccounts': subaccounts.count(),
                'active': subaccounts.filter(is_active=True).count(),
                'inactive': subaccounts.filter(is_active=False).count(),
            },
            'revenue_per_subaccount': list(subaccount_revenue),
        }
        result['insights'] = []
        return Response(result)


# ── Subscriptions ─────────────────────────────────────────────────────────────

class AdminSubscriptionAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        from subscriptions.models import Plan, Subscription
        from tiers.models import BusinessTier, VendorTierSubscription

        start, end = _date_range(request)

        # ── Customer subscriptions ────────────────────────────────────────────
        all_subs = Subscription.objects.all()
        new_subs = all_subs.filter(started_at__gte=start, started_at__lte=end)
        cancelled_subs = all_subs.filter(cancelled_at__gte=start, cancelled_at__lte=end)

        customer_status_breakdown = list(
            all_subs.values('status').annotate(count=Count('id'))
        )

        # Revenue: sum plan prices for subscriptions started in the period
        customer_revenue = sum(
            s.plan.price for s in new_subs.select_related('plan')
        )

        # Plan breakdown — active/trialing subscribers per plan
        plan_breakdown = list(
            all_subs.filter(status__in=('active', 'trialing'))
            .values('plan__id', 'plan__name', 'plan__slug',
                    'plan__plan_tier', 'plan__price', 'plan__billing_cycle')
            .annotate(subscriber_count=Count('id'))
            .order_by('-subscriber_count')
        )

        # Plans catalogue
        plans_catalogue = list(
            Plan.objects.filter(is_active=True).values(
                'id', 'name', 'slug', 'plan_tier', 'price', 'billing_cycle',
                'credit_limit', 'trial_days',
            ).order_by('sort_order', 'price')
        )

        # MRR estimate for customer plans
        customer_mrr = Decimal('0.00')
        for s in all_subs.filter(status='active').select_related('plan'):
            if s.plan.billing_cycle == 'yearly':
                customer_mrr += s.plan.price / 12
            else:
                customer_mrr += s.plan.price

        # ── Vendor tier subscriptions ─────────────────────────────────────────
        all_tier_subs = VendorTierSubscription.objects.all()
        new_tier_subs = all_tier_subs.filter(started_at__gte=start, started_at__lte=end)
        cancelled_tier_subs = all_tier_subs.filter(cancelled_at__gte=start, cancelled_at__lte=end)

        vendor_status_breakdown = list(
            all_tier_subs.values('status').annotate(count=Count('id'))
        )

        # Revenue from vendor tier subscriptions started in period
        vendor_revenue = sum(
            ts.tier.price for ts in new_tier_subs.select_related('tier')
        )

        # Tier breakdown — active vendors per tier
        tier_breakdown = list(
            all_tier_subs.filter(status__in=('active', 'trialing'))
            .values('tier__id', 'tier__name', 'tier__slug',
                    'tier__tier_level', 'tier__price', 'tier__commission_rate')
            .annotate(vendor_count=Count('id'))
            .order_by('-tier__tier_level')
        )

        # Tiers catalogue
        tiers_catalogue = list(
            BusinessTier.objects.filter(is_active=True).values(
                'id', 'name', 'slug', 'tier_level', 'price', 'commission_rate',
                'max_products', 'negotiation_enabled', 'trial_days',
            ).order_by('sort_order', 'tier_level')
        )

        # MRR from vendor tiers (all monthly; no yearly billing cycle on tiers)
        vendor_mrr = sum(
            ts.tier.price
            for ts in all_tier_subs.filter(status='active').select_related('tier')
        )

        # ── Combined ─────────────────────────────────────────────────────────
        combined_mrr = customer_mrr + vendor_mrr
        combined_revenue = (customer_revenue or Decimal('0')) + (vendor_revenue or Decimal('0'))

        result = {
            'period': {'start': start, 'end': end},
            'customer_subscriptions': {
                'total': all_subs.count(),
                'active': all_subs.filter(status='active').count(),
                'trialing': all_subs.filter(status='trialing').count(),
                'cancelled': all_subs.filter(status='cancelled').count(),
                'expired': all_subs.filter(status='expired').count(),
                'past_due': all_subs.filter(status='past_due').count(),
                'new_this_period': new_subs.count(),
                'cancellations_this_period': cancelled_subs.count(),
                'revenue_this_period': customer_revenue or Decimal('0'),
                'estimated_mrr': round(customer_mrr, 2),
                'status_breakdown': customer_status_breakdown,
                'plan_breakdown': plan_breakdown,
                'plans_catalogue': plans_catalogue,
            },
            'vendor_tier_subscriptions': {
                'total': all_tier_subs.count(),
                'active': all_tier_subs.filter(status='active').count(),
                'trialing': all_tier_subs.filter(status='trialing').count(),
                'cancelled': all_tier_subs.filter(status='cancelled').count(),
                'expired': all_tier_subs.filter(status='expired').count(),
                'past_due': all_tier_subs.filter(status='past_due').count(),
                'new_this_period': new_tier_subs.count(),
                'cancellations_this_period': cancelled_tier_subs.count(),
                'revenue_this_period': vendor_revenue or Decimal('0'),
                'estimated_mrr': round(vendor_mrr, 2),
                'status_breakdown': vendor_status_breakdown,
                'tier_breakdown': tier_breakdown,
                'tiers_catalogue': tiers_catalogue,
            },
            'combined': {
                'total_paying_subscribers': (
                    all_subs.filter(status='active').count() +
                    all_tier_subs.filter(status='active').count()
                ),
                'combined_mrr': round(combined_mrr, 2),
                'combined_revenue_this_period': combined_revenue,
                'new_this_period': new_subs.count() + new_tier_subs.count(),
                'cancellations_this_period': (
                    cancelled_subs.count() + cancelled_tier_subs.count()
                ),
            },
        }
        result['insights'] = subscription_analytics_insights(result)
        return Response(result)

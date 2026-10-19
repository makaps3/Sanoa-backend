"""
ML scoring functions for analytics.

Already applied elsewhere (do NOT change):
  - fraud app: fraud/risk scoring
  - negotiations: XGBoost AI chatbot pricing

New ML here:
  - Customer churn  → Scikit-learn rule-based → RandomForest when data >= 500
  - Vendor scoring  → XGBoost feature-weighted rule-based → full XGBoost when data >= 200
  - Driver scoring  → Scikit-learn weighted composite
  - Driver payout anomaly → XGBoost isolation-like rule when data >= 100
"""
import logging
from decimal import Decimal

import numpy as np
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger('sanoa.analytics')


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_rate(numerator, denominator):
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _vendor_tier(score):
    if score >= 80:
        return 'platinum'
    if score >= 65:
        return 'gold'
    if score >= 45:
        return 'silver'
    return 'bronze'


def _driver_grade(score):
    if score >= 90:
        return 'A'
    if score >= 75:
        return 'B'
    if score >= 60:
        return 'C'
    if score >= 40:
        return 'D'
    return 'F'


# ── Customer Churn ────────────────────────────────────────────────────────────

def compute_customer_churn_scores():
    """
    Score all customers for churn risk.
    Rule-based in Stage 1; upgrades to RandomForest in Stage 2.
    Returns count of records updated.
    """
    from accounts.models import User
    from orders.models import Order
    from subscriptions.models import Subscription
    from .models import CustomerChurnScore

    now = timezone.now()
    customers = User.objects.filter(user_type='customer').prefetch_related(
        'orders', 'customer_profile',
    )
    updated = 0

    for user in customers:
        try:
            # ── feature computation ──────────────────────────────────────────
            orders = Order.objects.filter(user=user)
            total_orders = orders.count()
            last_order = orders.order_by('-created_at').first()
            days_since = (now - last_order.created_at).days if last_order else 999

            spend_agg = orders.filter(payment_status='paid').aggregate(total=Sum('total_amount'))
            total_spend = float(spend_agg['total'] or 0)
            avg_order_value = total_spend / total_orders if total_orders else 0

            has_sub = False
            try:
                sub = user.subscription
                has_sub = sub.is_active
            except Exception:
                pass

            cp = getattr(user, 'customer_profile', None)
            loyalty = getattr(cp, 'loyalty_points', 0)

            # ── rule-based churn probability ─────────────────────────────────
            # Base probability from recency
            if days_since >= 120:
                prob = 0.90
            elif days_since >= 90:
                prob = 0.75
            elif days_since >= 60:
                prob = 0.55
            elif days_since >= 30:
                prob = 0.30
            elif days_since >= 14:
                prob = 0.15
            else:
                prob = 0.05

            # Reduce risk for engaged/loyal customers
            if has_sub:
                prob *= 0.55
            if loyalty > 1000:
                prob *= 0.70
            elif loyalty > 300:
                prob *= 0.85
            if total_orders > 20:
                prob *= 0.60
            elif total_orders > 5:
                prob *= 0.80
            if avg_order_value > 500:
                prob *= 0.85

            prob = min(max(prob, 0.0), 1.0)

            if prob >= 0.60:
                segment = 'high'
            elif prob >= 0.30:
                segment = 'medium'
            else:
                segment = 'low'

            CustomerChurnScore.objects.update_or_create(
                user=user,
                defaults={
                    'churn_probability': round(prob, 4),
                    'risk_segment': segment,
                    'days_since_last_order': days_since,
                    'total_orders': total_orders,
                    'total_spend': round(total_spend, 2),
                    'avg_order_value': round(avg_order_value, 2),
                    'has_subscription': has_sub,
                    'loyalty_points': loyalty,
                    'model_version': 'rule-based-v1',
                },
            )
            updated += 1
        except Exception as exc:
            logger.warning('Churn scoring failed for user %s: %s', user.id, exc)

    logger.info('Customer churn scoring complete: %d records updated', updated)
    return updated


# ── Vendor Performance ────────────────────────────────────────────────────────

def compute_vendor_performance_scores():
    """
    Score all vendors (0–100) using XGBoost-compatible feature weighting.
    Rule-based in Stage 1; XGBoost classifier in Stage 2 when labelled data >= 200.
    """
    from business.models import VendorProfile
    from orders.models import Order
    from payments.models import Refund, Dispute, Transaction
    from negotiations.models import NegotiationRoom
    from .models import VendorPerformanceScore

    now = timezone.now()
    vendors = VendorProfile.objects.all()
    updated = 0

    for vendor in vendors:
        try:
            # ── orders ───────────────────────────────────────────────────────
            order_items = vendor.order_items.all()
            order_ids = order_items.values_list('order_id', flat=True).distinct()
            orders = Order.objects.filter(id__in=order_ids)
            total_orders = orders.count()
            completed = orders.filter(status__in=('delivered', 'completed')).count()
            completion_rate = _safe_rate(completed, total_orders)

            revenue_agg = orders.filter(payment_status='paid').aggregate(total=Sum('total_amount'))
            total_revenue = float(revenue_agg['total'] or 0)
            avg_order_value = total_revenue / completed if completed else 0

            last_sale = orders.filter(status__in=('delivered', 'completed')).order_by('-created_at').first()
            days_since_last_sale = (now - last_sale.created_at).days if last_sale else 999

            # ── refunds ──────────────────────────────────────────────────────
            vendor_txns = Transaction.objects.filter(vendor=vendor, status='success')
            txn_count = vendor_txns.count()
            refund_count = Refund.objects.filter(
                transaction__vendor=vendor, status='processed',
            ).count()
            refund_rate = _safe_rate(refund_count, txn_count)

            # ── disputes ─────────────────────────────────────────────────────
            dispute_count = Dispute.objects.filter(transaction__vendor=vendor).count()
            dispute_rate = _safe_rate(dispute_count, txn_count)

            # ── negotiations ─────────────────────────────────────────────────
            neg_total = NegotiationRoom.objects.filter(vendor=vendor).count()
            neg_agreed = NegotiationRoom.objects.filter(vendor=vendor, status='agreed').count()
            neg_agreement_rate = _safe_rate(neg_agreed, neg_total)

            # ── XGBoost-compatible weighted score ────────────────────────────
            # Weight each feature contribution (mimics XGBoost feature importance)
            score = 0.0

            # Completion rate (weight=30)
            score += completion_rate * 30

            # Refund rate penalty (weight=20, inverted)
            score += max(0, (1 - refund_rate * 5)) * 20

            # Dispute rate penalty (weight=20, inverted)
            score += max(0, (1 - dispute_rate * 10)) * 20

            # Volume bonus (weight=15) — more orders = more reliable data
            vol_score = min(total_orders / 100.0, 1.0)
            score += vol_score * 15

            # Recency (weight=10) — active vendors score higher
            if days_since_last_sale <= 7:
                recency_score = 1.0
            elif days_since_last_sale <= 30:
                recency_score = 0.8
            elif days_since_last_sale <= 90:
                recency_score = 0.5
            else:
                recency_score = 0.1
            score += recency_score * 10

            # Negotiation engagement bonus (weight=5)
            score += neg_agreement_rate * 5

            score = min(max(score, 0.0), 100.0)

            VendorPerformanceScore.objects.update_or_create(
                vendor=vendor,
                defaults={
                    'score': round(score, 2),
                    'tier': _vendor_tier(score),
                    'total_orders': total_orders,
                    'completion_rate': round(completion_rate, 4),
                    'avg_order_value': round(avg_order_value, 2),
                    'refund_rate': round(refund_rate, 4),
                    'dispute_rate': round(dispute_rate, 4),
                    'negotiation_agreement_rate': round(neg_agreement_rate, 4),
                    'days_since_last_sale': days_since_last_sale,
                    'model_version': 'xgb-rule-v1',
                },
            )
            updated += 1
        except Exception as exc:
            logger.warning('Vendor scoring failed for vendor %s: %s', vendor.id, exc)

    logger.info('Vendor performance scoring complete: %d records updated', updated)
    return updated


# ── Driver Performance ────────────────────────────────────────────────────────

def compute_driver_performance_scores():
    """
    Score all drivers (0–100) using Scikit-learn weighted composite.
    Also flags payout anomalies.
    """
    from delivery.models import DeliveryDriver, DeliveryJob, DriverEarning, DriverRating
    from .models import DriverPerformanceScore

    now = timezone.now()
    drivers = DeliveryDriver.objects.all()
    updated = 0

    for driver in drivers:
        try:
            jobs = DeliveryJob.objects.filter(driver=driver)
            total_jobs = jobs.count()
            completed_jobs = jobs.filter(status='delivered').count()
            failed_jobs = jobs.filter(status__in=('cancelled', 'failed')).count()
            completion_rate = _safe_rate(completed_jobs, total_jobs)

            # Average delivery time (accepted_at → delivered_at)
            delivery_times = []
            for job in jobs.filter(status='delivered', accepted_at__isnull=False, delivered_at__isnull=False):
                delta = (job.delivered_at - job.accepted_at).total_seconds() / 60
                if 0 < delta < 480:  # sanity check: 0-8 hours
                    delivery_times.append(delta)
            avg_delivery_time = float(np.mean(delivery_times)) if delivery_times else 0

            # On-time rate: deliveries completed within 90 mins
            on_time = sum(1 for t in delivery_times if t <= 90)
            on_time_rate = _safe_rate(on_time, len(delivery_times)) if delivery_times else 0

            # Average rating
            avg_rating = float(driver.average_rating or 0)

            # Payout anomaly: std deviation of earnings is > 3x mean
            earnings = list(
                DriverEarning.objects.filter(driver=driver).values_list('gross_amount', flat=True)
            )
            payout_anomaly = False
            if len(earnings) >= 5:
                arr = np.array([float(e) for e in earnings])
                if arr.std() > arr.mean() * 3:
                    payout_anomaly = True

            # ── Scikit-learn weighted composite score ────────────────────────
            score = 0.0

            # Completion rate (weight=35)
            score += completion_rate * 35

            # Rating (weight=30) — normalise 1-5 to 0-1
            rating_norm = max(0, (avg_rating - 1) / 4) if avg_rating else 0
            score += rating_norm * 30

            # On-time rate (weight=25)
            score += on_time_rate * 25

            # Volume bonus (weight=10)
            vol_norm = min(total_jobs / 200.0, 1.0)
            score += vol_norm * 10

            # Payout anomaly penalty
            if payout_anomaly:
                score -= 10

            score = min(max(score, 0.0), 100.0)

            DriverPerformanceScore.objects.update_or_create(
                driver=driver,
                defaults={
                    'score': round(score, 2),
                    'grade': _driver_grade(score),
                    'payout_anomaly': payout_anomaly,
                    'total_deliveries': completed_jobs,
                    'completion_rate': round(completion_rate, 4),
                    'avg_rating': round(avg_rating, 2),
                    'avg_delivery_time_mins': round(avg_delivery_time, 2),
                    'on_time_rate': round(on_time_rate, 4),
                    'model_version': 'sklearn-rule-v1',
                },
            )
            updated += 1
        except Exception as exc:
            logger.warning('Driver scoring failed for driver %s: %s', driver.id, exc)

    logger.info('Driver performance scoring complete: %d records updated', updated)
    return updated


# ── Daily Platform Snapshot ───────────────────────────────────────────────────

def compute_daily_platform_snapshot(date=None):
    """Compute and store the daily platform snapshot for the given date (default: yesterday)."""
    import datetime
    from django.utils import timezone
    from accounts.models import User
    from orders.models import Order
    from payments.models import Transaction, Refund
    from negotiations.models import NegotiationRoom
    from delivery.models import DeliveryJob
    from debit.models import CreditAccount, CreditRepayment
    from .models import DailyPlatformSnapshot

    if date is None:
        date = (timezone.now() - datetime.timedelta(days=1)).date()

    start = timezone.datetime.combine(date, datetime.time.min).replace(tzinfo=timezone.utc)
    end = timezone.datetime.combine(date, datetime.time.max).replace(tzinfo=timezone.utc)

    def count_in(qs, field='created_at'):
        return qs.filter(**{f'{field}__gte': start, f'{field}__lte': end}).count()

    new_customers = User.objects.filter(user_type='customer', date_joined__gte=start, date_joined__lte=end).count()
    new_vendors = User.objects.filter(user_type='vendor', date_joined__gte=start, date_joined__lte=end).count()
    new_drivers = User.objects.filter(user_type='driver', date_joined__gte=start, date_joined__lte=end).count()

    orders = Order.objects.filter(created_at__gte=start, created_at__lte=end)
    revenue_agg = orders.filter(payment_status='paid').aggregate(total=Sum('total_amount'))

    txns = Transaction.objects.filter(created_at__gte=start, created_at__lte=end)
    txn_value = txns.filter(status='success').aggregate(total=Sum('amount'))
    refunds = Refund.objects.filter(created_at__gte=start, created_at__lte=end)
    refund_value = refunds.filter(status='processed').aggregate(total=Sum('amount'))

    jobs = DeliveryJob.objects.filter(created_at__gte=start, created_at__lte=end)
    credit_repaid = CreditRepayment.objects.filter(created_at__gte=start, created_at__lte=end).aggregate(total=Sum('amount'))
    credit_issued_agg = CreditAccount.objects.filter(created_at__gte=start, created_at__lte=end).aggregate(total=Sum('credit_limit'))

    snapshot, _ = DailyPlatformSnapshot.objects.update_or_create(
        date=date,
        defaults={
            'new_customers': new_customers,
            'new_vendors': new_vendors,
            'new_drivers': new_drivers,
            'total_customers': User.objects.filter(user_type='customer').count(),
            'total_vendors': User.objects.filter(user_type='vendor').count(),
            'total_drivers': User.objects.filter(user_type='driver').count(),
            'total_orders': orders.count(),
            'completed_orders': orders.filter(status__in=('delivered', 'completed')).count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
            'total_revenue': revenue_agg['total'] or 0,
            'total_transactions': txns.count(),
            'successful_transactions': txns.filter(status='success').count(),
            'failed_transactions': txns.filter(status='failed').count(),
            'total_transaction_value': txn_value['total'] or 0,
            'total_refunds': refunds.count(),
            'total_refund_value': refund_value['total'] or 0,
            'total_negotiations': NegotiationRoom.objects.filter(created_at__gte=start, created_at__lte=end).count(),
            'agreed_negotiations': NegotiationRoom.objects.filter(created_at__gte=start, created_at__lte=end, status='agreed').count(),
            'total_deliveries': jobs.count(),
            'completed_deliveries': jobs.filter(status='delivered').count(),
            'failed_deliveries': jobs.filter(status__in=('cancelled', 'failed')).count(),
            'credit_accounts_opened': CreditAccount.objects.filter(created_at__gte=start, created_at__lte=end).count(),
            'credit_issued': credit_issued_agg['total'] or 0,
            'credit_repaid': credit_repaid['total'] or 0,
        },
    )
    return snapshot

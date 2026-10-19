"""
Feature extraction for XGBoost fraud scoring.

Each extractor returns a plain dict; ml_models.py converts it to a numpy array
with a fixed column order so the trained model sees the same feature layout.
"""
import logging
from datetime import timedelta

from django.db.models import Avg, Sum
from django.utils import timezone

logger = logging.getLogger('sanoa.fraud')

# Column order MUST match what the models were trained on — do not reorder.
USER_FEATURE_NAMES = [
    'account_age_days',
    'is_verified',
    'has_profile_pic',
    'order_count_total',
    'order_count_7d',
    'order_count_24h',
    'total_order_value',
    'avg_order_value',
    'refund_count',
    'refund_rate',
    'dispute_count',
    'failed_payment_count',
    'credit_suspended',
    'unique_address_count',
]

VENDOR_FEATURE_NAMES = [
    'vendor_age_days',
    'is_verified',
    'total_orders',
    'refund_rate',
    'dispute_rate',
    'avg_order_value',
    'revenue_30d',
    'unique_buyer_count',
]


def extract_user_features(user) -> dict:
    """Return a fraud-signal feature dict for a user account."""
    from orders.models import Order
    from payments.models import Transaction, Refund, Dispute

    now = timezone.now()
    orders_qs = Order.objects.filter(user=user)

    order_count_total = orders_qs.count()
    order_count_7d    = orders_qs.filter(created_at__gte=now - timedelta(days=7)).count()
    order_count_24h   = orders_qs.filter(created_at__gte=now - timedelta(hours=24)).count()

    agg = orders_qs.aggregate(total=Sum('total_amount'), avg=Avg('total_amount'))
    total_order_value = float(agg['total'] or 0)
    avg_order_value   = float(agg['avg']   or 0)

    refund_count = Refund.objects.filter(user=user).count()
    refund_rate  = refund_count / max(order_count_total, 1)

    dispute_count        = Dispute.objects.filter(user=user).count()
    failed_payment_count = Transaction.objects.filter(user=user, status='failed').count()

    credit_suspended = 0
    try:
        credit_suspended = 1 if user.debit_account.status == 'suspended' else 0
    except Exception:
        pass

    has_profile_pic = 0
    try:
        has_profile_pic = 1 if user.customerprofile.avatar else 0
    except Exception:
        pass

    unique_addresses  = orders_qs.values('shipping_address').distinct().count()
    account_age_days  = (now - user.date_joined).total_seconds() / 86400

    return {
        'account_age_days':     account_age_days,
        'is_verified':          1 if user.is_verified else 0,
        'has_profile_pic':      has_profile_pic,
        'order_count_total':    order_count_total,
        'order_count_7d':       order_count_7d,
        'order_count_24h':      order_count_24h,
        'total_order_value':    total_order_value,
        'avg_order_value':      avg_order_value,
        'refund_count':         refund_count,
        'refund_rate':          refund_rate,
        'dispute_count':        dispute_count,
        'failed_payment_count': failed_payment_count,
        'credit_suspended':     credit_suspended,
        'unique_address_count': unique_addresses,
    }


def extract_vendor_features(vendor) -> dict:
    """Return a fraud-signal feature dict for a vendor profile."""
    from orders.models import Order
    from payments.models import Refund, Dispute

    now = timezone.now()

    vendor_age_days = (now - vendor.created_at).total_seconds() / 86400

    orders_qs   = Order.objects.filter(items__vendor=vendor).distinct()
    total_orders = orders_qs.count()

    agg = orders_qs.aggregate(avg=Avg('total_amount'))
    avg_order_value = float(agg['avg'] or 0)

    revenue_30d = float(
        orders_qs.filter(created_at__gte=now - timedelta(days=30))
        .aggregate(total=Sum('total_amount'))['total'] or 0
    )

    refund_count  = (
        Refund.objects
        .filter(transaction__order__items__vendor=vendor)
        .distinct().count()
    )
    dispute_count = (
        Dispute.objects
        .filter(transaction__order__items__vendor=vendor)
        .distinct().count()
    )

    refund_rate   = refund_count  / max(total_orders, 1)
    dispute_rate  = dispute_count / max(total_orders, 1)
    unique_buyers = orders_qs.values('user').distinct().count()

    return {
        'vendor_age_days':   vendor_age_days,
        'is_verified':       1 if vendor.verification_status == 'verified' else 0,
        'total_orders':      total_orders,
        'refund_rate':       refund_rate,
        'dispute_rate':      dispute_rate,
        'avg_order_value':   avg_order_value,
        'revenue_30d':       revenue_30d,
        'unique_buyer_count': unique_buyers,
    }


def features_to_array(feature_dict: dict, feature_names: list):
    import numpy as np
    return np.array([feature_dict[k] for k in feature_names], dtype=float)

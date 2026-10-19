"""
XGBoost-powered fraud classifiers.

Two separate binary classifiers:
  - user model:   predicts P(user is fraudulent)
  - vendor model: predicts P(vendor is fraudulent)

Both return a fraud probability 0–1, scaled to 0–100 for the scoring engine.
If no trained models exist they bootstrap on synthetic data the first time, exactly
like the negotiations engine.

One module-level singleton per model keeps them loaded once per worker process.
"""
import logging
from pathlib import Path

import joblib
import numpy as np

from .features import USER_FEATURE_NAMES, VENDOR_FEATURE_NAMES, features_to_array

logger = logging.getLogger('sanoa.fraud')

MODEL_DIR = Path(__file__).parent / 'ml_models'

_user_clf    = None
_vendor_clf  = None


# ---------------------------------------------------------------------------
# Getters (lazy load from disk)
# ---------------------------------------------------------------------------

def get_user_clf():
    global _user_clf
    path = MODEL_DIR / 'user_fraud.joblib'
    if _user_clf is None and path.exists():
        _user_clf = joblib.load(path)
    return _user_clf


def get_vendor_clf():
    global _vendor_clf
    path = MODEL_DIR / 'vendor_fraud.joblib'
    if _vendor_clf is None and path.exists():
        _vendor_clf = joblib.load(path)
    return _vendor_clf


# ---------------------------------------------------------------------------
# Synthetic bootstrap datasets
# ---------------------------------------------------------------------------

def _synthetic_user_data(n: int = 800):
    """
    Produce labeled (X, y) training data for the user classifier.
    y=0 → normal, y=1 → fraudulent.
    Features follow USER_FEATURE_NAMES order.
    """
    rng = np.random.default_rng(42)
    n_fraud  = n // 4
    n_normal = n - n_fraud

    # Normal users
    normal = np.column_stack([
        rng.uniform(30, 1200, n_normal),                        # account_age_days
        rng.choice([0, 1], n_normal, p=[0.10, 0.90]),           # is_verified
        rng.choice([0, 1], n_normal, p=[0.25, 0.75]),           # has_profile_pic
        rng.integers(0, 25,  n_normal),                         # order_count_total
        rng.integers(0, 4,   n_normal),                         # order_count_7d
        rng.integers(0, 2,   n_normal),                         # order_count_24h
        rng.uniform(0, 4000, n_normal),                         # total_order_value
        rng.uniform(80, 600, n_normal),                         # avg_order_value
        rng.integers(0, 2,   n_normal),                         # refund_count
        rng.uniform(0, 0.12, n_normal),                         # refund_rate
        rng.integers(0, 1,   n_normal),                         # dispute_count
        rng.integers(0, 2,   n_normal),                         # failed_payment_count
        rng.choice([0, 1], n_normal, p=[0.96, 0.04]),           # credit_suspended
        rng.integers(1, 4,   n_normal),                         # unique_address_count
    ])

    # Fraudulent users — four archetypes mixed together
    fraud_parts = []

    # 1. Fake accounts: brand-new, unverified, burst of orders
    n1 = n_fraud // 4
    fraud_parts.append(np.column_stack([
        rng.uniform(0,   5, n1),
        np.zeros(n1),                                           # not verified
        np.zeros(n1),                                           # no pic
        rng.integers(8,  40, n1),
        rng.integers(6,  20, n1),
        rng.integers(5,  15, n1),
        rng.uniform(3000, 30000, n1),
        rng.uniform(500, 3000,   n1),
        rng.integers(0, 2, n1),
        rng.uniform(0, 0.15, n1),
        rng.integers(0, 2, n1),
        rng.integers(0, 3, n1),
        np.zeros(n1),
        rng.integers(3, 12, n1),
    ]))

    # 2. Refund abusers: high refund rate
    n2 = n_fraud // 4
    fraud_parts.append(np.column_stack([
        rng.uniform(30, 500, n2),
        rng.choice([0, 1], n2, p=[0.4, 0.6]),
        rng.choice([0, 1], n2, p=[0.4, 0.6]),
        rng.integers(10, 40, n2),
        rng.integers(0,  5,  n2),
        rng.integers(0,  2,  n2),
        rng.uniform(1000, 10000, n2),
        rng.uniform(100,  500,   n2),
        rng.integers(5,  20, n2),
        rng.uniform(0.5, 1.0, n2),                             # high refund rate
        rng.integers(0,  3,   n2),
        rng.integers(0,  4,   n2),
        rng.choice([0, 1], n2, p=[0.6, 0.4]),
        rng.integers(2,  8,  n2),
    ]))

    # 3. Dispute pattern: many disputes, failed payments
    n3 = n_fraud // 4
    fraud_parts.append(np.column_stack([
        rng.uniform(10, 300, n3),
        rng.choice([0, 1], n3, p=[0.5, 0.5]),
        rng.choice([0, 1], n3, p=[0.5, 0.5]),
        rng.integers(5,  30, n3),
        rng.integers(0,  4,  n3),
        rng.integers(0,  3,  n3),
        rng.uniform(500, 8000, n3),
        rng.uniform(100, 800,  n3),
        rng.integers(1,  5,    n3),
        rng.uniform(0.1, 0.4,  n3),
        rng.integers(3,  10,   n3),                            # high disputes
        rng.integers(6,  20,   n3),                            # many failures
        rng.choice([0, 1], n3, p=[0.4, 0.6]),
        rng.integers(2,  8,    n3),
    ]))

    # 4. Credit abusers: suspended credit + continue ordering
    n4 = n_fraud - n1 - n2 - n3
    fraud_parts.append(np.column_stack([
        rng.uniform(60, 600, n4),
        rng.choice([0, 1], n4, p=[0.3, 0.7]),
        rng.choice([0, 1], n4, p=[0.3, 0.7]),
        rng.integers(10, 50, n4),
        rng.integers(2,  10, n4),
        rng.integers(1,  5,  n4),
        rng.uniform(2000, 20000, n4),
        rng.uniform(300,  2000,  n4),
        rng.integers(2,  8,   n4),
        rng.uniform(0.2, 0.6, n4),
        rng.integers(1,  5,   n4),
        rng.integers(3,  10,  n4),
        np.ones(n4),                                           # all suspended
        rng.integers(2,  8,   n4),
    ]))

    fraud = np.vstack(fraud_parts)

    X = np.vstack([normal, fraud])
    y = np.concatenate([np.zeros(n_normal), np.ones(n_fraud)])
    return X, y


def _synthetic_vendor_data(n: int = 400):
    """Produce labeled (X, y) training data for the vendor classifier."""
    rng = np.random.default_rng(42)
    n_fraud  = n // 4
    n_normal = n - n_fraud

    normal = np.column_stack([
        rng.uniform(30, 1000, n_normal),                        # vendor_age_days
        rng.choice([0, 1], n_normal, p=[0.20, 0.80]),           # is_verified
        rng.integers(5,  200,  n_normal),                       # total_orders
        rng.uniform(0,   0.05, n_normal),                       # refund_rate
        rng.uniform(0,   0.02, n_normal),                       # dispute_rate
        rng.uniform(100, 2000, n_normal),                       # avg_order_value
        rng.uniform(500, 80000, n_normal),                      # revenue_30d
        rng.integers(3,  100,   n_normal),                      # unique_buyer_count
    ])

    fraud_parts = []

    # 1. Suspicious vendor: new + volume surge
    n1 = n_fraud // 3
    fraud_parts.append(np.column_stack([
        rng.uniform(0,  10, n1),
        np.zeros(n1),
        rng.integers(30, 200, n1),
        rng.uniform(0.1, 0.4, n1),
        rng.uniform(0.1, 0.3, n1),
        rng.uniform(10,  100, n1),
        rng.uniform(50000, 500000, n1),
        rng.integers(1, 5, n1),
    ]))

    # 2. Dispute heavy (chargeback fraud)
    n2 = n_fraud // 3
    fraud_parts.append(np.column_stack([
        rng.uniform(10, 300, n2),
        rng.choice([0, 1], n2, p=[0.6, 0.4]),
        rng.integers(20, 300, n2),
        rng.uniform(0.15, 0.5, n2),
        rng.uniform(0.15, 0.4, n2),
        rng.uniform(50,   500, n2),
        rng.uniform(5000, 100000, n2),
        rng.integers(1,   8, n2),
    ]))

    # 3. Unverified + high activity
    n3 = n_fraud - n1 - n2
    fraud_parts.append(np.column_stack([
        rng.uniform(5,  200, n3),
        np.zeros(n3),
        rng.integers(20, 150, n3),
        rng.uniform(0.1, 0.3, n3),
        rng.uniform(0.05, 0.2, n3),
        rng.uniform(50,   800, n3),
        rng.uniform(5000, 80000, n3),
        rng.integers(2,   20, n3),
    ]))

    fraud = np.vstack(fraud_parts)
    X = np.vstack([normal, fraud])
    y = np.concatenate([np.zeros(n_normal), np.ones(n_fraud)])
    return X, y


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_all_models():
    """Train or retrain XGBoost classifiers. Saves to disk, updates singletons."""
    from xgboost import XGBClassifier

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for name, synth_fn, real_fn, feature_names, path_key in [
        ('user',   _synthetic_user_data,   _load_real_user_data,   USER_FEATURE_NAMES,   'user_fraud.joblib'),
        ('vendor', _synthetic_vendor_data, _load_real_vendor_data, VENDOR_FEATURE_NAMES, 'vendor_fraud.joblib'),
    ]:
        real = real_fn(feature_names)
        if real is not None and len(real[0]) >= (50 if name == 'user' else 20):
            X, y = real
            logger.info("Training %s fraud model on %d real samples", name, len(X))
        else:
            X, y = synth_fn()
            logger.info("Bootstrapping %s fraud model on %d synthetic samples", name, len(X))

        clf = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=3,       # upweight minority fraud class
            eval_metric='logloss',
            random_state=42,
            n_jobs=-1,
        )
        clf.fit(X, y)
        path = MODEL_DIR / path_key
        joblib.dump(clf, path)
        logger.info("%s fraud model saved to %s", name.capitalize(), path)

    # Invalidate in-process cache so the new models are used immediately
    global _user_clf, _vendor_clf
    _user_clf   = joblib.load(MODEL_DIR / 'user_fraud.joblib')
    _vendor_clf = joblib.load(MODEL_DIR / 'vendor_fraud.joblib')


def _load_real_user_data(feature_names):
    """Pull real user feature vectors for retraining.  Returns (X, y) or None."""
    try:
        from django.contrib.auth import get_user_model
        from .features import extract_user_features
        from .models import FraudProfile

        User = get_user_model()
        rows, labels = [], []

        # Labelled examples come from admin-reviewed profiles
        for profile in FraudProfile.objects.filter(
            user__isnull=False, is_reviewed=True
        ).select_related('user'):
            try:
                feat = extract_user_features(profile.user)
                rows.append(features_to_array(feat, feature_names))
                labels.append(1 if profile.review_outcome == 'confirmed' else 0)
            except Exception:
                continue

        if len(rows) < 50:
            return None
        return np.array(rows), np.array(labels)
    except Exception as exc:
        logger.warning("Could not load real user training data: %s", exc)
        return None


def _load_real_vendor_data(feature_names):
    """Pull real vendor feature vectors for retraining. Returns (X, y) or None."""
    try:
        from django.apps import apps
        from .features import extract_vendor_features
        from .models import FraudProfile

        VendorProfile = apps.get_model('business', 'VendorProfile')
        rows, labels = [], []

        for profile in FraudProfile.objects.filter(
            vendor__isnull=False, is_reviewed=True
        ).select_related('vendor'):
            try:
                feat = extract_vendor_features(profile.vendor)
                rows.append(features_to_array(feat, feature_names))
                labels.append(1 if profile.review_outcome == 'confirmed' else 0)
            except Exception:
                continue

        if len(rows) < 20:
            return None
        return np.array(rows), np.array(labels)
    except Exception as exc:
        logger.warning("Could not load real vendor training data: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_user_vector(feature_dict: dict) -> float:
    """
    Return a fraud risk score 0–100 for the given user feature dict.
    Higher = more likely fraudulent.
    """
    clf = get_user_clf()
    if clf is None:
        return 0.0
    vec = features_to_array(feature_dict, USER_FEATURE_NAMES).reshape(1, -1)
    prob = float(clf.predict_proba(vec)[0][1])   # P(fraud)
    return round(prob * 100, 2)


def score_vendor_vector(feature_dict: dict) -> float:
    """Return a fraud risk score 0–100 for the given vendor feature dict."""
    clf = get_vendor_clf()
    if clf is None:
        return 0.0
    vec = features_to_array(feature_dict, VENDOR_FEATURE_NAMES).reshape(1, -1)
    prob = float(clf.predict_proba(vec)[0][1])
    return round(prob * 100, 2)

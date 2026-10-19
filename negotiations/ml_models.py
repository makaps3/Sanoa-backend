"""
XGBoost models for the Negotiation AI engine.

Two models:
  1. Acceptance Classifier  — labels 0=reject, 1=counter, 2=accept
  2. Counter-offer Regressor — predicts optimal counter_price / original_price

Cold start: trains on synthetic data that encodes the core negotiation rules.
As real NegotiationOffer records accumulate (>=50), retrain_from_history()
improves accuracy with real deal data.
"""
import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger('sanoa.negotiations')

MODEL_DIR = Path(__file__).resolve().parent / 'trained_models'
MODEL_DIR.mkdir(exist_ok=True)

ACCEPTANCE_MODEL_PATH = MODEL_DIR / 'acceptance_classifier.pkl'
COUNTER_MODEL_PATH = MODEL_DIR / 'counter_offer_regressor.pkl'


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_offer_features(offer_ratio, demand_score, vendor_margin,
                           round_number, time_elapsed_ratio):
    """
    7-feature vector for a single negotiation event.

    offer_ratio        : offered_price / original_price
    demand_score       : product demand signal 0-1
    vendor_margin      : max_discount_percent / 100
    round_number       : how many offers have been exchanged so far
    time_elapsed_ratio : hours_since_room_created / 24
    """
    slack = max(0.0, vendor_margin - (1.0 - offer_ratio))
    return np.array([
        offer_ratio,
        demand_score,
        vendor_margin,
        min(float(round_number), 10.0),
        min(float(time_elapsed_ratio), 1.0),
        offer_ratio * demand_score,
        slack,
    ], dtype=float)


# ---------------------------------------------------------------------------
# Synthetic data (cold-start bootstrap)
# ---------------------------------------------------------------------------

def _generate_synthetic_acceptance_data(n_samples=2000):
    rng = np.random.default_rng(42)
    X, y = [], []
    for _ in range(n_samples):
        offer_ratio = rng.uniform(0.50, 1.05)
        demand_score = rng.uniform(0.0, 1.0)
        vendor_margin = rng.uniform(0.05, 0.20)
        round_n = int(rng.integers(1, 7))
        time_elapsed = float(rng.uniform(0.0, 1.0))

        X.append(extract_offer_features(
            offer_ratio, demand_score, vendor_margin, round_n, time_elapsed
        ))

        min_acceptable = 1.0 - vendor_margin
        if offer_ratio >= min_acceptable + 0.03:
            label = 2   # accept
        elif offer_ratio >= min_acceptable - 0.04:
            label = 1   # counter
        else:
            label = 0   # reject

        if rng.random() < 0.05:     # 5 % noise
            label = int(rng.choice([0, 1, 2]))
        y.append(label)

    return np.array(X), np.array(y)


def _generate_synthetic_counter_data(n_samples=2000):
    rng = np.random.default_rng(123)
    X, y = [], []
    for _ in range(n_samples):
        offer_ratio = rng.uniform(0.65, 0.97)
        demand_score = rng.uniform(0.0, 1.0)
        vendor_margin = rng.uniform(0.05, 0.20)
        round_n = int(rng.integers(1, 7))
        time_elapsed = float(rng.uniform(0.0, 1.0))

        X.append(extract_offer_features(
            offer_ratio, demand_score, vendor_margin, round_n, time_elapsed
        ))

        min_acceptable = 1.0 - vendor_margin
        counter_ratio = (offer_ratio + min_acceptable) / 2.0
        counter_ratio += demand_score * 0.015
        counter_ratio = min(1.0, max(offer_ratio + 0.01, counter_ratio))
        y.append(counter_ratio)

    return np.array(X), np.array(y)


# ---------------------------------------------------------------------------
# Model persistence
# ---------------------------------------------------------------------------

def _load(path):
    if path.exists():
        with open(path, 'rb') as f:
            return pickle.load(f)
    return None


def _save(model, path):
    with open(path, 'wb') as f:
        pickle.dump(model, f)


def get_acceptance_model():
    return _load(ACCEPTANCE_MODEL_PATH)


def get_counter_model():
    return _load(COUNTER_MODEL_PATH)


def clear_model_cache():
    for p in [ACCEPTANCE_MODEL_PATH, COUNTER_MODEL_PATH]:
        if p.exists():
            p.unlink()
    logger.info("Model cache cleared")


# ---------------------------------------------------------------------------
# Model builders (XGBoost with scikit-learn fallback)
# ---------------------------------------------------------------------------

def _build_classifier():
    try:
        import xgboost as xgb
        return xgb.XGBClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric='mlogloss',
            random_state=42, n_jobs=-1,
        )
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        logger.warning("xgboost not installed — using GradientBoostingClassifier")
        return GradientBoostingClassifier(n_estimators=150, max_depth=4, random_state=42)


def _build_regressor():
    try:
        import xgboost as xgb
        return xgb.XGBRegressor(
            n_estimators=150, max_depth=4, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1,
        )
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor
        logger.warning("xgboost not installed — using GradientBoostingRegressor")
        return GradientBoostingRegressor(n_estimators=150, max_depth=4, random_state=42)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_all_models():
    """Train both models on synthetic data.  Returns {name: cv_score}."""
    from sklearn.model_selection import cross_val_score

    logger.info("Training acceptance classifier …")
    X_acc, y_acc = _generate_synthetic_acceptance_data()
    clf = _build_classifier()
    clf.fit(X_acc, y_acc)
    _save(clf, ACCEPTANCE_MODEL_PATH)
    acc_score = float(cross_val_score(clf, X_acc, y_acc, cv=3, scoring='accuracy').mean())

    logger.info("Training counter-offer regressor …")
    X_ctr, y_ctr = _generate_synthetic_counter_data()
    reg = _build_regressor()
    reg.fit(X_ctr, y_ctr)
    _save(reg, COUNTER_MODEL_PATH)
    ctr_score = float(cross_val_score(reg, X_ctr, y_ctr, cv=3, scoring='r2').mean())

    logger.info(
        f"Models trained — acceptance acc: {acc_score:.3f}, counter R2: {ctr_score:.3f}"
    )
    return {'acceptance_classifier': acc_score, 'counter_regressor': ctr_score}


def retrain_from_history():
    """
    Retrain using real NegotiationOffer data.
    Returns number of offers used, or None if insufficient data.
    """
    from negotiations.models import NegotiationOffer

    offers = list(
        NegotiationOffer.objects.filter(
            status__in=['accepted', 'rejected', 'countered']
        ).select_related('room', 'room__product', 'room__vendor')
    )

    if len(offers) < 50:
        logger.info(f"Only {len(offers)} resolved offers — need >=50 to retrain")
        return None

    X_acc, y_acc, X_ctr, y_ctr = [], [], [], []

    for offer in offers:
        room = offer.room
        orig = float(offer.original_price)
        if orig == 0:
            continue

        offer_ratio = float(offer.offered_price) / orig
        sales = getattr(room.product, 'sales_count', 0) or 0
        demand_score = min(1.0, sales / 100)
        policy = getattr(room.vendor, 'price_policy', None)
        vendor_margin = float(policy.max_discount_percent) / 100 if policy else 0.10
        hours = (offer.created_at - room.created_at).total_seconds() / 3600
        time_elapsed = min(1.0, hours / 24)

        feat = extract_offer_features(
            offer_ratio, demand_score, vendor_margin, offer.round_number, time_elapsed
        )
        X_acc.append(feat)
        label = 2 if offer.status == 'accepted' else 1 if offer.status == 'countered' else 0
        y_acc.append(label)

        if offer.status == 'countered' and offer.counter_offer_price:
            X_ctr.append(feat)
            y_ctr.append(float(offer.counter_offer_price) / orig)

    clf = _build_classifier()
    clf.fit(np.array(X_acc), np.array(y_acc))
    _save(clf, ACCEPTANCE_MODEL_PATH)

    if len(X_ctr) >= 20:
        reg = _build_regressor()
        reg.fit(np.array(X_ctr), np.array(y_ctr))
        _save(reg, COUNTER_MODEL_PATH)

    logger.info(f"Models retrained from {len(offers)} real offers")
    return len(offers)

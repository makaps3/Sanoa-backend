"""
Fraud scoring engine.

Combines deterministic rule checks with an XGBoost probability score.
Rules catch well-known fraud patterns with certainty; XGBoost catches
novel combinations the rules don't cover.

Final score formula:
    final = min(100, rule_score + xgb_score * 0.35)

A purely rule-driven fraud (e.g. 50% refund rate) scores high even if the
model hasn't seen that pattern before.  A purely ML-detected anomaly
contributes up to 35 extra points as a soft signal.
"""
import logging

from django.utils import timezone

from .features import extract_user_features, extract_vendor_features
from .ml_models import (
    get_user_clf,
    get_vendor_clf,
    score_user_vector,
    score_vendor_vector,
    train_all_models,
)

logger = logging.getLogger('sanoa.fraud')

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------
# Each rule is a dict with:
#   id          – maps to FRAUD_EVENT_TYPES in models.py
#   check(f)    – lambda that returns True when the rule fires
#   score       – points added to rule_score (capped at 100)
#   severity    – 'low' | 'medium' | 'high' | 'critical'
#   description – format string, receives feature dict as kwargs

USER_RULES = [
    {
        'id': 'new_account_surge',
        'check': lambda f: f['account_age_days'] < 7 and f['order_count_total'] >= 5,
        'score': 30,
        'severity': 'high',
        'description': 'New account ({account_age_days:.0f}d old) placed {order_count_total} orders',
    },
    {
        'id': 'rapid_orders',
        'check': lambda f: f['order_count_24h'] >= 8,
        'score': 35,
        'severity': 'high',
        'description': '{order_count_24h} orders in the last 24 hours',
    },
    {
        'id': 'high_refund_rate',
        'check': lambda f: f['refund_rate'] >= 0.5 and f['refund_count'] >= 3,
        'score': 45,
        'severity': 'critical',
        'description': (
            'Refund rate {refund_rate:.0%} across {refund_count} refunds — '
            'possible refund abuse'
        ),
    },
    {
        'id': 'refund_abuse',
        'check': lambda f: f['refund_count'] >= 6,
        'score': 25,
        'severity': 'high',
        'description': '{refund_count} total refund requests on this account',
    },
    {
        'id': 'dispute_pattern',
        'check': lambda f: f['dispute_count'] >= 3,
        'score': 35,
        'severity': 'high',
        'description': '{dispute_count} payment disputes on record',
    },
    {
        'id': 'payment_failure_spike',
        'check': lambda f: f['failed_payment_count'] >= 8,
        'score': 20,
        'severity': 'medium',
        'description': '{failed_payment_count} failed payment attempts',
    },
    {
        'id': 'credit_abuse',
        'check': lambda f: f['credit_suspended'] == 1,
        'score': 20,
        'severity': 'medium',
        'description': 'Credit/BNPL account is currently suspended for non-payment',
    },
    {
        'id': 'unverified_high_value',
        'check': lambda f: f['is_verified'] == 0 and f['total_order_value'] >= 5000,
        'score': 25,
        'severity': 'medium',
        'description': (
            'Unverified account with R{total_order_value:.0f} total order value'
        ),
    },
]

VENDOR_RULES = [
    {
        'id': 'suspicious_vendor',
        'check': lambda f: f['dispute_rate'] >= 0.15,
        'score': 50,
        'severity': 'critical',
        'description': (
            'Dispute rate {dispute_rate:.0%} — well above the 2% platform average'
        ),
    },
    {
        'id': 'high_refund_rate',
        'check': lambda f: f['refund_rate'] >= 0.20,
        'score': 35,
        'severity': 'high',
        'description': (
            'Refund rate {refund_rate:.0%} suggests product quality or fulfilment issues'
        ),
    },
    {
        'id': 'new_vendor_surge',
        'check': lambda f: f['vendor_age_days'] < 14 and f['total_orders'] >= 30,
        'score': 35,
        'severity': 'high',
        'description': (
            'New vendor ({vendor_age_days:.0f}d old) already has {total_orders} orders'
        ),
    },
    {
        'id': 'unverified_active',
        'check': lambda f: f['is_verified'] == 0 and f['total_orders'] >= 20,
        'score': 20,
        'severity': 'medium',
        'description': 'Unverified vendor is processing {total_orders} orders',
    },
]


# ---------------------------------------------------------------------------
# Shared rule runner
# ---------------------------------------------------------------------------

def _apply_rules(features: dict, rules: list, profile, entity_type: str, entity_id: str) -> int:
    """
    Fire matching rules, emit FraudEvents (max one per rule per day),
    return total rule score (capped at 100).
    """
    from .models import FraudEvent

    rule_score = 0
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for rule in rules:
        try:
            fired = rule['check'](features)
        except Exception:
            continue
        if not fired:
            continue

        rule_score += rule['score']

        description = rule['description'].format(**features)

        already_today = FraudEvent.objects.filter(
            profile=profile,
            event_type=rule['id'],
            created_at__gte=today_start,
        ).exists()

        if not already_today:
            FraudEvent.objects.create(
                profile=profile,
                event_type=rule['id'],
                severity=rule['severity'],
                description=description,
                entity_type=entity_type,
                entity_id=str(entity_id),
                metadata={k: (float(v) if hasattr(v, '__float__') else v)
                          for k, v in features.items()},
            )

    return min(rule_score, 100)


# ---------------------------------------------------------------------------
# Public scoring API
# ---------------------------------------------------------------------------

def score_user(user, save: bool = True):
    """
    Compute and persist the fraud risk score for a user.
    Returns the updated FraudProfile instance.
    """
    from .models import FraudProfile, FraudEvent

    profile, _ = FraudProfile.objects.get_or_create(user=user)

    if get_user_clf() is None:
        logger.info("No user fraud model found — bootstrapping on synthetic data …")
        train_all_models()

    features = extract_user_features(user)

    rule_score = _apply_rules(features, USER_RULES, profile, 'user', str(user.id))
    xgb_score  = score_user_vector(features)

    # XGBoost catches patterns rules miss; rules are authoritative when they fire
    final_score = min(100.0, rule_score + xgb_score * 0.35)

    # Emit an ML-only event when XGBoost is confident but no rules fired
    if xgb_score >= 70 and rule_score < 10:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if not FraudEvent.objects.filter(
            profile=profile, event_type='ml_anomaly', created_at__gte=today_start
        ).exists():
            FraudEvent.objects.create(
                profile=profile,
                event_type='ml_anomaly',
                severity='medium',
                description=f'XGBoost fraud probability: {xgb_score:.1f}/100',
                entity_type='user',
                entity_id=str(user.id),
                metadata={'xgb_score': xgb_score, 'rule_score': rule_score},
                ml_score=xgb_score,
            )

    profile.risk_score    = final_score
    profile.score_features = {k: (float(v) if hasattr(v, '__float__') else v)
                               for k, v in features.items()}
    profile.last_scored_at = timezone.now()
    profile.apply_risk_level()

    if save:
        profile.save()

    logger.debug(
        "User %s scored — rules=%s xgb=%s final=%.1f level=%s",
        user.email, rule_score, xgb_score, final_score, profile.risk_level,
    )
    return profile


def score_vendor(vendor, save: bool = True):
    """
    Compute and persist the fraud risk score for a vendor.
    Returns the updated FraudProfile instance.
    """
    from .models import FraudProfile, FraudEvent

    profile, _ = FraudProfile.objects.get_or_create(vendor=vendor)

    if get_vendor_clf() is None:
        logger.info("No vendor fraud model found — bootstrapping on synthetic data …")
        train_all_models()

    features = extract_vendor_features(vendor)

    rule_score = _apply_rules(features, VENDOR_RULES, profile, 'vendor', str(vendor.id))
    xgb_score  = score_vendor_vector(features)

    final_score = min(100.0, rule_score + xgb_score * 0.35)

    if xgb_score >= 70 and rule_score < 10:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if not FraudEvent.objects.filter(
            profile=profile, event_type='ml_anomaly', created_at__gte=today_start
        ).exists():
            FraudEvent.objects.create(
                profile=profile,
                event_type='ml_anomaly',
                severity='medium',
                description=f'XGBoost fraud probability: {xgb_score:.1f}/100',
                entity_type='vendor',
                entity_id=str(vendor.id),
                metadata={'xgb_score': xgb_score, 'rule_score': rule_score},
                ml_score=xgb_score,
            )

    profile.risk_score     = final_score
    profile.score_features = {k: (float(v) if hasattr(v, '__float__') else v)
                               for k, v in features.items()}
    profile.last_scored_at  = timezone.now()
    profile.apply_risk_level()

    if save:
        profile.save()

    logger.debug(
        "Vendor %s scored — rules=%s xgb=%s final=%.1f level=%s",
        vendor.name, rule_score, xgb_score, final_score, profile.risk_level,
    )
    return profile

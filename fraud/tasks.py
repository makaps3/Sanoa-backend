"""
Celery tasks for periodic fraud rescoring and XGBoost model retraining.
"""
import logging

from celery import shared_task

logger = logging.getLogger('sanoa.fraud')


@shared_task(name='fraud.rescore_all_users')
def rescore_all_users():
    """Daily: rescore every active customer-type user."""
    from django.contrib.auth import get_user_model
    from .engine import score_user

    User = get_user_model()
    count, errors = 0, 0
    for user in User.objects.filter(user_type='customer', is_active=True).iterator():
        try:
            score_user(user)
            count += 1
        except Exception as exc:
            logger.warning("Failed to score user %s: %s", user.id, exc)
            errors += 1

    logger.info("Fraud user rescore complete: %d scored, %d errors", count, errors)
    return {'scored': count, 'errors': errors}


@shared_task(name='fraud.rescore_all_vendors')
def rescore_all_vendors():
    """Daily: rescore all active vendors."""
    from django.apps import apps
    from .engine import score_vendor

    VendorProfile = apps.get_model('business', 'VendorProfile')
    count, errors = 0, 0
    for vendor in VendorProfile.objects.filter(store_active=True).iterator():
        try:
            score_vendor(vendor)
            count += 1
        except Exception as exc:
            logger.warning("Failed to score vendor %s: %s", vendor.id, exc)
            errors += 1

    logger.info("Fraud vendor rescore complete: %d scored, %d errors", count, errors)
    return {'scored': count, 'errors': errors}


@shared_task(name='fraud.retrain_models')
def retrain_fraud_models():
    """Weekly: retrain XGBoost models.  Falls back to synthetic data if not enough real labels."""
    from .ml_models import train_all_models
    try:
        train_all_models()
        logger.info("Fraud XGBoost models retrained successfully")
        return {'status': 'ok'}
    except Exception as exc:
        logger.exception("Fraud model retraining failed: %s", exc)
        return {'status': 'error', 'detail': str(exc)}

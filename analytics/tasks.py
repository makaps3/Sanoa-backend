"""
Celery tasks for automated analytics computation.
All tasks are registered in CELERY_BEAT_SCHEDULE in project_config/base.py.
"""
import logging
from celery import shared_task

logger = logging.getLogger('sanoa.analytics')


@shared_task(name='analytics.score_customer_churn', bind=True, max_retries=3)
def score_customer_churn(self):
    """Weekly: compute churn risk scores for all customers."""
    try:
        from .ml_scoring import compute_customer_churn_scores
        count = compute_customer_churn_scores()
        return {'status': 'ok', 'updated': count}
    except Exception as exc:
        logger.error('score_customer_churn failed: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='analytics.score_vendor_performance', bind=True, max_retries=3)
def score_vendor_performance(self):
    """Weekly: compute performance scores for all vendors."""
    try:
        from .ml_scoring import compute_vendor_performance_scores
        count = compute_vendor_performance_scores()
        return {'status': 'ok', 'updated': count}
    except Exception as exc:
        logger.error('score_vendor_performance failed: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='analytics.score_driver_performance', bind=True, max_retries=3)
def score_driver_performance(self):
    """Weekly: compute performance scores for all drivers."""
    try:
        from .ml_scoring import compute_driver_performance_scores
        count = compute_driver_performance_scores()
        return {'status': 'ok', 'updated': count}
    except Exception as exc:
        logger.error('score_driver_performance failed: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='analytics.compute_daily_snapshot', bind=True, max_retries=3)
def compute_daily_snapshot(self):
    """Daily (02:00 UTC): compute previous day's platform snapshot."""
    try:
        from .ml_scoring import compute_daily_platform_snapshot
        snapshot = compute_daily_platform_snapshot()
        return {'status': 'ok', 'date': str(snapshot.date)}
    except Exception as exc:
        logger.error('compute_daily_snapshot failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='analytics.run_all_scoring')
def run_all_scoring():
    """Trigger all ML scoring tasks (used for manual re-score)."""
    score_customer_churn.delay()
    score_vendor_performance.delay()
    score_driver_performance.delay()
    compute_daily_snapshot.delay()
    return {'status': 'triggered'}

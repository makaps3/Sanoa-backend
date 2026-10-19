"""
Django signals that trigger real-time fraud scoring.

Each handler fires a background thread so the request/consumer that triggered
the save is not blocked while the XGBoost model runs.
"""
import logging
import threading
from django.db import transaction, close_old_connections

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('sanoa.fraud')


def _score_user_bg(user_id):
    """Run score_user in a daemon thread so the caller is never blocked."""
    def _run():
        try:
            from django.contrib.auth import get_user_model
            from .engine import score_user
            user = get_user_model().objects.get(id=user_id)
            score_user(user)
        except Exception as exc:
            logger.exception("Background fraud scoring failed for user %s: %s", user_id, exc)
        finally:
            close_old_connections()

    transaction.on_commit(lambda: threading.Thread(target=_run, daemon=True).start())


def _score_vendor_bg(vendor_id):
    def _run():
        try:
            from django.apps import apps
            from .engine import score_vendor
            VendorProfile = apps.get_model('business', 'VendorProfile')
            vendor = VendorProfile.objects.get(id=vendor_id)
            score_vendor(vendor)
        except Exception as exc:
            logger.exception("Background fraud scoring failed for vendor %s: %s", vendor_id, exc)
        finally:
            close_old_connections()

    transaction.on_commit(lambda: threading.Thread(target=_run, daemon=True).start())


# ── Buyers ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='orders.Order')
def on_order_created(sender, instance, created, **kwargs):
    """Score buyer whenever a new order is placed."""
    if created and instance.user_id:
        _score_user_bg(instance.user_id)


@receiver(post_save, sender='payments.Refund')
def on_refund_requested(sender, instance, created, **kwargs):
    """Score buyer whenever a refund is requested."""
    if created and instance.user_id:
        _score_user_bg(instance.user_id)


@receiver(post_save, sender='payments.Transaction')
def on_transaction_saved(sender, instance, created, **kwargs):
    """Re-score buyer on payment failure (indicates potential card testing)."""
    if created and instance.status == 'failed' and instance.user_id:
        _score_user_bg(instance.user_id)


# ── Vendors ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='business.VendorProfile')
def on_vendor_saved(sender, instance, created, **kwargs):
    """Score vendor on creation or any profile update."""
    _score_vendor_bg(instance.id)

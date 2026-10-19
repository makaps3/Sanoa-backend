"""
Celery tasks for negotiation lifecycle management.

Recommended beat schedule (add to your Celery config):

    'expire-negotiations': {
        'task': 'negotiations.tasks.expire_old_negotiations',
        'schedule': crontab(minute=0),       # every hour
    },
    'retrain-negotiation-models': {
        'task': 'negotiations.tasks.retrain_negotiation_models',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # weekly Mon 3 AM
    },
"""
import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('sanoa.negotiations')


@shared_task
def expire_old_negotiations():
    """
    Expire agreed rooms whose 24-hour checkout window has passed, and expire
    any pending offers past their individual expiry.
    Sends a WebSocket 'expired' event to each affected room group.
    """
    from .models import NegotiationRoom, NegotiationOffer
    from channels.layers import get_channel_layer

    now = timezone.now()
    channel_layer = get_channel_layer()

    # Two flavours of timed-out rooms:
    #   - status='agreed'         → buyer never checked out within 24h.
    #   - status='pending_vendor' → vendor didn't confirm AI's accept in 24h.
    expired_rooms = NegotiationRoom.objects.filter(
        status__in=['agreed', 'pending_vendor'], offer_expires_at__lt=now,
    )
    room_ids = list(expired_rooms.values_list('id', flat=True))
    room_count = expired_rooms.update(status='expired')

    for room_id in room_ids:
        try:
            async_to_sync(channel_layer.group_send)(
                f"negotiation_{room_id}",
                {'type': 'chat.expired'},
            )
        except Exception as exc:
            logger.warning(f"WS expiry notify failed for room {room_id}: {exc}")

    offer_count = NegotiationOffer.objects.filter(
        status='pending', expires_at__lt=now,
    ).update(status='expired')

    logger.info(f"Expired {room_count} rooms, {offer_count} pending offers")
    return {'expired_rooms': room_count, 'expired_offers': offer_count}


@shared_task
def retrain_negotiation_models():
    """Retrain XGBoost models from accumulated NegotiationOffer data."""
    from .ml_models import retrain_from_history

    result = retrain_from_history()
    if result:
        logger.info(f"Negotiation models retrained on {result} offers")
        return {'retrained': True, 'offers_used': result}

    logger.info("Not enough data to retrain negotiation models")
    return {'retrained': False}

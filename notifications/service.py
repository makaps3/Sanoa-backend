"""
Core notification service.

notify()       — create a Notification record + push via WebSocket.
notify_admins() — same but targets every admin user.
"""
import logging

from django.contrib.auth import get_user_model

from .models import Notification, NotificationPreference

logger = logging.getLogger('sanoa.notifications')


def notify(
    recipient,
    notification_type: str,
    title: str,
    body: str,
    category: str = 'account',
    actor=None,
    data: dict = None,
):
    """
    Create a Notification for `recipient` and push it to their WebSocket group.

    recipient — User instance or user PK.
    actor     — User instance who triggered the action (None for system events).
    data      — arbitrary JSON-serialisable dict (e.g. order_id, amount).
    """
    User = get_user_model()

    if not isinstance(recipient, User):
        try:
            recipient = User.objects.get(pk=recipient)
        except User.DoesNotExist:
            logger.warning('notify(): recipient %s not found', recipient)
            return None

    # Respect preferences (get_or_create so first-time users are handled gracefully)
    prefs, _ = NotificationPreference.objects.get_or_create(user=recipient)
    if not prefs.is_enabled(category):
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        category=category,
        title=title,
        body=body,
        data=data or {},
    )

    _push_ws(recipient.pk, notification)
    return notification


def notify_admins(
    notification_type: str,
    title: str,
    body: str,
    category: str = 'admin',
    actor=None,
    data: dict = None,
):
    """Send a notification to every active admin user."""
    User = get_user_model()
    admins = User.objects.filter(user_type='admin', is_active=True)
    for admin in admins:
        notify(
            recipient=admin,
            notification_type=notification_type,
            title=title,
            body=body,
            category=category,
            actor=actor,
            data=data,
        )


def _push_ws(user_id, notification: Notification):
    """Push serialised notification payload to the user's WebSocket group."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        payload = {
            'id': str(notification.id),
            'type': notification.notification_type,
            'category': notification.category,
            'title': notification.title,
            'body': notification.body,
            'data': notification.data,
            'is_read': False,
            'created_at': notification.created_at.isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            f'notifications_{user_id}',
            {'type': 'notification.push', 'notification': payload},
        )
    except Exception as exc:
        # WebSocket push is best-effort; the DB record is already saved.
        logger.warning('WS push failed for user %s: %s', user_id, exc)

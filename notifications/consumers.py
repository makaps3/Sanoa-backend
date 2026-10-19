"""
WebSocket consumer for real-time notifications.

Frontend connects to:  ws://<host>/ws/notifications/?token=<JWT>

Authentication follows the same pattern used by NegotiationConsumer:
the JWT access token is read from the ?token= query parameter and
validated with rest_framework_simplejwt.  The scope user (AnonymousUser
set by AuthMiddlewareStack) is intentionally ignored — JWT is the only
supported auth mechanism here.
"""
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger('sanoa.notifications')


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)
            return

        self.user_id = user.pk
        self.group_name = f'notifications_{self.user_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug('Notification WS connected: user=%s', self.user_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get('action')
        if action == 'mark_read':
            await self._mark_read(data.get('id'))
        elif action == 'mark_all_read':
            await self._mark_all_read()

    async def notification_push(self, event):
        """Called by channel layer when service._push_ws() sends a group message."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification'],
        }))

    # ── Authentication ───────────────────────────────────────────────

    @database_sync_to_async
    def _authenticate(self):
        """
        Decode the JWT from ?token=<value> in the WebSocket query string.
        Returns a User instance on success, None on failure.
        Mirrors the pattern in NegotiationConsumer._authenticate().
        """
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        qs = self.scope.get('query_string', b'').decode()
        params = {
            k: v
            for k, v in (p.split('=', 1) for p in qs.split('&') if '=' in p)
        }
        token_str = params.get('token')
        if not token_str:
            logger.debug('Notification WS: no token in query string')
            return None
        try:
            User = get_user_model()
            payload = AccessToken(token_str)
            return User.objects.get(id=payload['user_id'])
        except Exception as exc:
            logger.debug('Notification WS auth failed: %s', exc)
            return None

    # ── Actions ──────────────────────────────────────────────────────

    @database_sync_to_async
    def _mark_read(self, notification_id):
        from .models import Notification
        from django.utils import timezone

        if not notification_id:
            return
        Notification.objects.filter(
            id=notification_id, recipient_id=self.user_id, is_read=False,
        ).update(is_read=True, read_at=timezone.now())

    @database_sync_to_async
    def _mark_all_read(self):
        from .models import Notification
        from django.utils import timezone

        Notification.objects.filter(
            recipient_id=self.user_id, is_read=False,
        ).update(is_read=True, read_at=timezone.now())

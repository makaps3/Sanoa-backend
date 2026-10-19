"""
WebSocket consumer for the chat room.

Connection URL:
    ws://<host>/ws/chat/<conversation_uuid>/?token=<JWT_access_token>

Server → client events:
    {"type": "history",       "messages": [...]}
    {"type": "message",       "message": {...}}
    {"type": "read",          "role": "customer|driver", "read_at": "..."}
    {"type": "typing",        "role": "customer|driver"}
    {"type": "error",         "message": "..."}

Client → server events:
    {"type": "typing"}
    {"type": "read"}              # mark this side read up to now

Sending messages is done via REST (POST /messages/) so a single code
path validates input and persists. The consumer fan-outs the result.
"""
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message
from .serializers import MessageSerializer

log = logging.getLogger('sanoa.chat')


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conv_id = self.scope['url_route']['kwargs']['conv_id']
        self.group_name = f'chat_{self.conv_id}'
        self.user = self.scope.get('user') if self.scope else None
        if not (self.user and self.user.is_authenticated):
            await self.close(code=4001)
            return

        conv, role = await self._load_conv(self.conv_id, self.user)
        if conv is None:
            await self.close(code=4004)
            return
        self.conv = conv
        self.role = role

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self._history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'conversation_id': str(conv.id),
            'status': conv.status,
            'role': role,
            'messages': history,
        }))

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._error('Malformed payload.')
            return
        kind = data.get('type')
        if kind == 'typing':
            if self.role in ('customer', 'driver'):
                await self.channel_layer.group_send(
                    self.group_name,
                    {'type': 'chat.typing', 'role': self.role},
                )
            return
        if kind == 'read':
            await self._mark_read()
            return
        # Sending text goes through REST — keeping ws read-mostly.
        await self._error(f'Unsupported type: {kind!r}')

    # ── group event handlers ─────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def chat_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'role': event['role'],
            'read_at': event['read_at'],
        }))

    async def chat_typing(self, event):
        # Don't echo a user their own typing event.
        if event['role'] == self.role and self.role in ('customer', 'driver'):
            return
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'role': event['role'],
        }))

    # ── helpers ──────────────────────────────────────────────────

    async def _error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error', 'message': message,
        }))

    @database_sync_to_async
    def _load_conv(self, conv_id, user):
        try:
            conv = (Conversation.objects
                    .select_related('customer', 'driver', 'delivery_job')
                    .get(id=conv_id))
        except Conversation.DoesNotExist:
            return None, None
        role = conv.role_for(user)
        if role is None:
            return None, None
        return conv, role

    @database_sync_to_async
    def _history(self):
        qs = (self.conv.messages
              .filter(is_deleted=False)
              .select_related('sender')
              .order_by('-created_at')[:50])
        return MessageSerializer(list(reversed(qs)), many=True).data

    @database_sync_to_async
    def _mark_read(self):
        if self.role not in ('customer', 'driver'):
            return
        now = timezone.now()
        if self.role == 'customer':
            self.conv.customer_read_at = now
            self.conv.save(update_fields=['customer_read_at'])
        else:
            self.conv.driver_read_at = now
            self.conv.save(update_fields=['driver_read_at'])
        from asgiref.sync import async_to_sync
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {'type': 'chat.read', 'role': self.role,
             'read_at': now.isoformat()},
        )

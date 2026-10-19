"""
WebSocket consumers for support tickets.

TicketConsumer — the chat room:
    ws://<host>/ws/tickets/<ticket_uuid>/?token=<JWT>

    Server → client:
        {"type": "history", "ticket_id": ..., "status": ..., "role": ..., "messages": [...]}
        {"type": "message", "message": {...}}
        {"type": "read",    "role": ..., "read_at": ...}
        {"type": "typing",  "role": ...}
        {"type": "status",  "status": ...}
        {"type": "error",   "message": ...}

    Client → server:
        {"type": "typing"}
        {"type": "read"}

TicketAlertConsumer — urgent-ticket alert channel for vendors/admins:
    ws://<host>/ws/tickets/alerts/?token=<JWT>

    Server → client:
        {"type": "ticket_alert",         "alert": {...}}
        {"type": "ticket_alert_dismiss", "ticket_id": ...}

Sending messages goes through REST so one code path validates and
persists; the consumers only fan out.
"""
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Ticket
from .serializers import TicketMessageSerializer
from .ws_broadcast import ADMIN_ALERT_GROUP, vendor_alert_group

log = logging.getLogger('sanoa.tickets')


class TicketConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.group_name = f'ticket_{self.ticket_id}'
        self.user = self.scope.get('user') if self.scope else None
        if not (self.user and self.user.is_authenticated):
            await self.close(code=4001)
            return

        ticket, role = await self._load_ticket(self.ticket_id, self.user)
        if ticket is None:
            await self.close(code=4004)
            return
        self.ticket = ticket
        self.role = role

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self._history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'ticket_id': str(ticket.id),
            'status': ticket.status,
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
        if kind == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return
        if kind == 'typing':
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'ticket.typing', 'role': self.role},
            )
            return
        if kind == 'read':
            await self._mark_read()
            return
        await self._error(f'Unsupported type: {kind!r}')

    # ── group event handlers ─────────────────────────────────────

    async def ticket_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message', 'message': event['message'],
        }))

    async def ticket_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'role': event['role'],
            'read_at': event['read_at'],
        }))

    async def ticket_typing(self, event):
        if event['role'] == self.role:
            return
        await self.send(text_data=json.dumps({
            'type': 'typing', 'role': event['role'],
        }))

    async def ticket_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status', 'status': event['status'],
        }))

    # ── helpers ──────────────────────────────────────────────────

    async def _error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error', 'message': message,
        }))

    @database_sync_to_async
    def _load_ticket(self, ticket_id, user):
        try:
            ticket = (Ticket.objects
                      .select_related('customer', 'vendor', 'vendor__user')
                      .get(id=ticket_id))
        except (Ticket.DoesNotExist, ValueError):
            return None, None
        role = ticket.role_for(user)
        if role is None:
            return None, None
        return ticket, role

    @database_sync_to_async
    def _history(self):
        qs = (self.ticket.messages
              .filter(is_deleted=False)
              .select_related('sender')
              .order_by('-created_at')[:50])
        return TicketMessageSerializer(list(reversed(qs)), many=True).data

    @database_sync_to_async
    def _mark_read(self):
        field = self.ticket.read_marker_field(self.role)
        if field is None:
            return
        now = timezone.now()
        setattr(self.ticket, field, now)
        self.ticket.save(update_fields=[field])
        from asgiref.sync import async_to_sync
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {'type': 'ticket.read', 'role': self.role,
             'read_at': now.isoformat()},
        )


class TicketAlertConsumer(AsyncWebsocketConsumer):
    """Per-role alert channel. Admins join a shared group; vendors join
    their own vendor group. Customers have no alert channel."""

    async def connect(self):
        self.user = self.scope.get('user') if self.scope else None
        if not (self.user and self.user.is_authenticated):
            await self.close(code=4001)
            return

        self.groups_joined = await self._resolve_groups(self.user)
        if not self.groups_joined:
            await self.close(code=4003)
            return

        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, 'groups_joined', []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    # ── group event handlers ─────────────────────────────────────

    async def ticket_alert(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ticket_alert', 'alert': event['alert'],
        }))

    async def ticket_alert_dismiss(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ticket_alert_dismiss',
            'ticket_id': event['ticket_id'],
        }))

    # ── helpers ──────────────────────────────────────────────────

    @database_sync_to_async
    def _resolve_groups(self, user):
        groups = []
        if user.is_staff or user.is_superuser or \
                hasattr(user, 'admin_profile'):
            groups.append(ADMIN_ALERT_GROUP)
        vendor_id = None
        vp = getattr(user, 'vendor_profile', None)
        if vp is not None:
            vendor_id = vp.id
        else:
            emp = getattr(user, 'vendor_employment', None)
            if emp is not None and emp.is_active:
                vendor_id = emp.vendor_id
        if vendor_id is not None:
            groups.append(vendor_alert_group(vendor_id))
        return groups

"""
WebSocket consumers for the retail orders app.

Channels:
  ws/orders/vendor/  — vendor real-time queue + new-order alerts (retail)

Events pushed:
  { type: "new_order",       order_id, order_number, status, ... }
  { type: "status_changed",  order_id, order_number, status, ... }

The push helpers in `orders/views.py` send to the
``vendor_orders_<vendor_id>`` group whenever a retail order is created or
transitions through a status. The consumer simply forwards each payload to
the connected vendor client.
"""
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json


class VendorOrdersConsumer(AsyncWebsocketConsumer):
    """Vendors connect to receive retail order events in real time."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.vendor_id = await self._get_vendor_id(user)
        if not self.vendor_id:
            await self.close(code=4003)
            return

        self.group_name = f"vendor_orders_{self.vendor_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Read-only consumer — vendor app doesn't send messages over this socket.
        pass

    async def new_order(self, event):
        await self.send(text_data=json.dumps(event))

    async def status_changed(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _get_vendor_id(self, user):
        if user.is_staff:
            return 'admin'
        if getattr(user, 'user_type', None) != 'vendor':
            return None
        from business.models import VendorProfile
        try:
            vp = VendorProfile.objects.get(user=user)
            return str(vp.id)
        except VendorProfile.DoesNotExist:
            return None

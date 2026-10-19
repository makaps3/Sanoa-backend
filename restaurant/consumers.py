"""
WebSocket consumers for the restaurant app.

Channels:
  ws/restaurant/orders/<order_id>/tracking/  — customer real-time order tracking
  ws/restaurant/kitchen/                     — vendor kitchen real-time new orders
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class CustomerOrderTrackingConsumer(AsyncWebsocketConsumer):
    """
    Customers connect to track a specific order.
    Group name: restaurant_order_<order_id>

    Events pushed:
      { type: "order_update", event_type, message, metadata, order_status, created_at }
    """

    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.group_name = f"restaurant_order_{self.order_id}"

        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify the order belongs to this user (or user is staff/vendor)
        allowed = await self._check_access(user)
        if not allowed:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current tracking snapshot on connect
        events = await self._get_tracking_events()
        await self.send(text_data=json.dumps({'type': 'snapshot', 'events': events}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass  # read-only consumer

    async def order_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _check_access(self, user):
        from .models import RestaurantOrder
        try:
            order = RestaurantOrder.objects.get(id=self.order_id)
        except RestaurantOrder.DoesNotExist:
            return False
        if user.is_staff:
            return True
        if order.user_id == user.id:
            return True
        # Vendor of the order
        if getattr(user, 'user_type', None) == 'vendor':
            from business.models import VendorProfile
            try:
                vp = VendorProfile.objects.get(user=user)
                return order.vendor_id == vp.id
            except VendorProfile.DoesNotExist:
                pass
        return False

    @database_sync_to_async
    def _get_tracking_events(self):
        from .models import RestaurantOrderTrackingEvent
        events = RestaurantOrderTrackingEvent.objects.filter(
            order_id=self.order_id
        ).order_by('created_at').values(
            'event_type', 'message', 'metadata', 'created_at',
        )
        result = []
        for e in events:
            result.append({
                'event_type': e['event_type'],
                'message': e['message'],
                'metadata': e['metadata'],
                'created_at': e['created_at'].isoformat(),
            })
        return result


class VendorKitchenConsumer(AsyncWebsocketConsumer):
    """
    Vendors connect to receive new restaurant orders in real time.
    Group name: kitchen_vendor_<vendor_id>

    Events pushed:
      { type: "new_order", order_id, order_number, fulfillment_type, table_number, items_count }
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.vendor_id = await self._get_vendor_id(user)
        if not self.vendor_id:
            await self.close(code=4003)
            return

        self.group_name = f"kitchen_vendor_{self.vendor_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass  # read-only consumer

    async def new_order(self, event):
        await self.send(text_data=json.dumps(event))

    async def status_changed(self, event):
        """Forward queue status transitions to the connected vendor client."""
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

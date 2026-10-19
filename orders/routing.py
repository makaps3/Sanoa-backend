"""WebSocket routing for the orders (retail) app."""
from django.urls import re_path
from .consumers import VendorOrdersConsumer

websocket_urlpatterns = [
    re_path(r'^ws/orders/vendor/$', VendorOrdersConsumer.as_asgi()),
]

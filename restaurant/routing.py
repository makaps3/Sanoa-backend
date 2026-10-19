from django.urls import re_path
from .consumers import CustomerOrderTrackingConsumer, VendorKitchenConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/restaurant/orders/(?P<order_id>[0-9a-f-]+)/tracking/$',
        CustomerOrderTrackingConsumer.as_asgi(),
    ),
    re_path(
        r'^ws/restaurant/kitchen/$',
        VendorKitchenConsumer.as_asgi(),
    ),
]

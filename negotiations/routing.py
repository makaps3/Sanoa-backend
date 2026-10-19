from django.urls import re_path
from .consumers import NegotiationConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/negotiations/(?P<room_id>[0-9a-f-]+)/$',
        NegotiationConsumer.as_asgi(),
    ),
]

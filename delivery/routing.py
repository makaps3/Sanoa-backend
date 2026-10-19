from django.urls import re_path
from .consumers import DeliveryTrackingConsumer, DriverJobConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/delivery/driver/jobs/$',
        DriverJobConsumer.as_asgi(),
    ),
    re_path(
        r'^ws/delivery/track/(?P<job_id>[0-9a-f-]+)/$',
        DeliveryTrackingConsumer.as_asgi(),
    ),
]

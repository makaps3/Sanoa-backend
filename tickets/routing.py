from django.urls import re_path

from .consumers import TicketAlertConsumer, TicketConsumer

websocket_urlpatterns = [
    re_path(r'^ws/tickets/alerts/$', TicketAlertConsumer.as_asgi()),
    re_path(r'^ws/tickets/(?P<ticket_id>[0-9a-f-]+)/$',
            TicketConsumer.as_asgi()),
]

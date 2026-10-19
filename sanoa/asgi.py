import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sanoa.settings')

# Initialise Django before importing anything that touches models/settings.
django_asgi_app = get_asgi_application()

from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from core.ws_auth import JWTAuthMiddlewareStack

import chat.routing
import delivery.routing
import negotiations.routing
import notifications.routing
import orders.routing
import restaurant.routing
import tickets.routing

websocket_router = JWTAuthMiddlewareStack(
    URLRouter(
        restaurant.routing.websocket_urlpatterns
        + orders.routing.websocket_urlpatterns
        + delivery.routing.websocket_urlpatterns
        + negotiations.routing.websocket_urlpatterns
        + notifications.routing.websocket_urlpatterns
        + chat.routing.websocket_urlpatterns
        + tickets.routing.websocket_urlpatterns
    )
)

# In DEBUG we skip Origin validation so Flutter mobile/emulator/LAN clients
# (which send unpredictable Origin headers — null, http://10.0.2.2, file://,
# random LAN IPs) can connect. In production the validator stays on to
# prevent cross-site WebSocket hijacking.
if settings.DEBUG:
    websocket_app = websocket_router
else:
    websocket_app = AllowedHostsOriginValidator(websocket_router)

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': websocket_app,
})

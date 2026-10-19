from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        # Wire signal handlers (auto-create conversation when a
        # DeliveryJob gets a driver assigned).
        from . import signals  # noqa: F401

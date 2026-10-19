"""
Bridge from synchronous REST views to the WebSocket layer.

We push events into the conversation's channel-layer group so connected
clients (customer, driver, admin observer) receive realtime updates.
Importing this module is safe even when channels isn't configured —
the helpers no-op gracefully so unit tests don't need a channel layer.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _group_for(conv):
    return f'chat_{conv.id}'


def _send(conv, event):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(_group_for(conv), event)


def broadcast_message(conv, message_payload):
    """Notify both participants + any admin observer of a new message."""
    _send(conv, {'type': 'chat.message', 'message': message_payload})


def broadcast_read_marker(conv, role, when):
    _send(conv, {
        'type': 'chat.read',
        'role': role,
        'read_at': when.isoformat(),
    })

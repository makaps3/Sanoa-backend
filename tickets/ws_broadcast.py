"""
Bridge from synchronous REST views to the WebSocket layer.

Two kinds of groups:
  * ticket_<ticket_id>            — the chat room (customer, vendor, admin)
  * ticket_alerts_admin           — every connected platform admin
  * ticket_alerts_vendor_<vp_id>  — the vendor's devices

Helpers no-op gracefully when the channel layer is unavailable so
unit tests don't need Redis / an event loop.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .serializers import ticket_alert_payload

ADMIN_ALERT_GROUP = 'ticket_alerts_admin'


def vendor_alert_group(vendor_id):
    return f'ticket_alerts_vendor_{vendor_id}'


def _send(group, event):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group, event)


def _room(ticket):
    return f'ticket_{ticket.id}'


# ── chat room events ──────────────────────────────────────────────

def broadcast_message(ticket, message_payload):
    _send(_room(ticket), {
        'type': 'ticket.message', 'message': message_payload,
    })


def broadcast_read_marker(ticket, role, when):
    _send(_room(ticket), {
        'type': 'ticket.read', 'role': role, 'read_at': when.isoformat(),
    })


def broadcast_status(ticket):
    _send(_room(ticket), {
        'type': 'ticket.status', 'status': ticket.status,
    })


# ── urgent alert events ───────────────────────────────────────────

def _alert_groups(ticket):
    groups = [ADMIN_ALERT_GROUP]
    if ticket.target_type == ticket.TARGET_VENDOR and ticket.vendor_id:
        groups.append(vendor_alert_group(ticket.vendor_id))
    return groups


def push_urgent_alert(ticket):
    payload = ticket_alert_payload(ticket)
    for group in _alert_groups(ticket):
        _send(group, {'type': 'ticket.alert', 'alert': payload})


def dismiss_urgent_alert(ticket):
    """Someone responded — stop ringing on every device."""
    for group in _alert_groups(ticket):
        _send(group, {
            'type': 'ticket.alert.dismiss', 'ticket_id': str(ticket.id),
        })

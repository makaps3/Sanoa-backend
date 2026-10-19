"""Serializers for the support-ticket REST surface."""
from rest_framework import serializers

from .models import Ticket, TicketMessage


def _user_brief(user):
    if user is None:
        return None
    return {
        'id': user.id,
        'email': user.email,
        'full_name': f'{user.first_name} {user.last_name}'.strip()
            or user.email,
        'user_type': user.user_type,
    }


def _vendor_brief(vendor):
    if vendor is None:
        return None
    return {
        'id': str(vendor.id),
        'name': vendor.name,
        'business_category': vendor.business_category,
    }


class TicketMessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = TicketMessage
        fields = [
            'id', 'kind', 'body', 'sender', 'sender_role',
            'is_deleted', 'created_at',
        ]
        read_only_fields = fields

    def get_sender(self, obj):
        return _user_brief(obj.sender)


class TicketSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'target_type', 'category', 'urgency', 'subject',
            'status', 'customer', 'vendor',
            'last_message_at', 'last_message_preview',
            'first_response_at', 'role', 'unread_count',
            'created_at', 'closed_at',
        ]
        read_only_fields = fields

    def get_customer(self, obj):
        return _user_brief(obj.customer)

    def get_vendor(self, obj):
        return _vendor_brief(obj.vendor)

    def get_role(self, obj):
        request = self.context.get('request')
        if request is None:
            return None
        return obj.role_for(request.user)

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request is None:
            return 0
        return obj.unread_count_for(request.user)


def ticket_alert_payload(ticket):
    """Compact payload pushed over the alert WebSocket groups."""
    return {
        'ticket_id': str(ticket.id),
        'target_type': ticket.target_type,
        'category': ticket.category,
        'urgency': ticket.urgency,
        'subject': ticket.subject,
        'preview': ticket.last_message_preview,
        'customer': _user_brief(ticket.customer),
        'vendor': _vendor_brief(ticket.vendor),
        'created_at': ticket.created_at.isoformat(),
    }

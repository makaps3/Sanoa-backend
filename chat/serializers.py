"""Serializers for the chat REST surface."""
from rest_framework import serializers

from .models import Conversation, Message


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


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'kind', 'body',
            'latitude', 'longitude',
            'sender', 'sender_role',
            'is_deleted', 'created_at',
        ]
        read_only_fields = fields

    def get_sender(self, obj):
        return _user_brief(obj.sender)

    def get_sender_role(self, obj):
        if obj.sender is None:
            return 'system'
        conv = obj.conversation
        if obj.sender_id == conv.customer_id:
            return 'customer'
        if obj.sender_id == conv.driver_id:
            return 'driver'
        return 'admin'


class ConversationSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    driver = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'status',
            'customer', 'driver', 'delivery',
            'last_message_at', 'last_message_preview',
            'role', 'unread_count',
            'created_at', 'closed_at',
        ]
        read_only_fields = fields

    def get_customer(self, obj):
        return _user_brief(obj.customer)

    def get_driver(self, obj):
        return _user_brief(obj.driver)

    def get_delivery(self, obj):
        job = obj.delivery_job
        return {
            'id': job.id,
            'status': job.status,
            'retail_order_id': str(job.retail_order_id)
                if job.retail_order_id else None,
            'restaurant_order_id': str(job.restaurant_order_id)
                if job.restaurant_order_id else None,
        }

    def get_role(self, obj):
        user = self.context['request'].user
        return obj.role_for(user)

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.unread_count_for(user)

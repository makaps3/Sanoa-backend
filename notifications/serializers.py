from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'category',
            'title', 'body', 'data',
            'actor', 'actor_name',
            'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.email
        return None


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'order_notifications',
            'payment_notifications',
            'subscription_notifications',
            'credit_notifications',
            'negotiation_notifications',
            'delivery_notifications',
            'social_notifications',
            'fraud_notifications',
            'account_notifications',
            'admin_notifications',
            'in_app_enabled',
            'push_enabled',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

"""
Serializers for the audit trail API.
"""
from rest_framework import serializers
from audit.models import AuditLog, LoginAttempt


class AuditLogSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_display', 'user_email',
            'ip_address', 'user_agent',
            'category', 'action', 'status', 'description',
            'target_model', 'target_id', 'target_repr',
            'changes', 'extra_data',
            'request_method', 'request_path',
            'response_status_code', 'request_duration_ms',
            'timestamp',
        ]
        read_only_fields = fields

    def get_user_display(self, obj):
        if obj.user:
            return obj.user.email
        return obj.user_email or 'system'


class AuditLogSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_email', 'category', 'action',
            'status', 'description', 'target_model',
            'target_id', 'timestamp',
        ]
        read_only_fields = fields


class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'email', 'ip_address', 'user_agent',
            'status', 'failure_reason', 'timestamp',
        ]
        read_only_fields = fields


class AuditStatsSerializer(serializers.Serializer):
    """Serializer for audit statistics."""
    total_events = serializers.IntegerField()
    events_today = serializers.IntegerField()
    failed_logins_today = serializers.IntegerField()
    events_by_category = serializers.DictField()
    events_by_status = serializers.DictField()
    top_users = serializers.ListField()

from rest_framework import serializers

from .models import FraudEvent, FraudProfile


class FraudEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudEvent
        fields = [
            'id', 'event_type', 'severity', 'description',
            'entity_type', 'entity_id', 'metadata', 'ml_score',
            'is_false_positive', 'is_resolved', 'resolved_at', 'created_at',
        ]
        read_only_fields = fields


class FraudProfileSerializer(serializers.ModelSerializer):
    events     = FraudEventSerializer(many=True, read_only=True)
    user_email = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = FraudProfile
        fields = [
            'id', 'user', 'vendor', 'user_email', 'vendor_name',
            'risk_score', 'risk_level', 'is_flagged', 'auto_flagged_at',
            'total_orders', 'total_order_value',
            'refund_count', 'dispute_count', 'failed_payment_count',
            'is_reviewed', 'review_outcome', 'review_notes', 'reviewed_at',
            'last_scored_at', 'score_features', 'events',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'risk_score', 'risk_level', 'is_flagged', 'auto_flagged_at',
            'last_scored_at', 'score_features', 'events',
            'total_orders', 'total_order_value',
            'refund_count', 'dispute_count', 'failed_payment_count',
            'created_at', 'updated_at',
        ]

    def get_user_email(self, obj):
        return obj.user.email if obj.user_id else None

    def get_vendor_name(self, obj):
        return obj.vendor.name if obj.vendor_id else None


class FraudProfileSummarySerializer(serializers.ModelSerializer):
    """Lightweight — used for the buyer's own risk transparency endpoint."""
    class Meta:
        model = FraudProfile
        fields = [
            'id', 'risk_score', 'risk_level', 'is_flagged',
            'refund_count', 'dispute_count', 'last_scored_at',
        ]
        read_only_fields = fields


class ReviewSerializer(serializers.ModelSerializer):
    """Admin reviewing a flagged profile."""
    class Meta:
        model = FraudProfile
        fields = ['is_reviewed', 'review_outcome', 'review_notes']

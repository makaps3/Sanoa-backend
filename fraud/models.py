"""
Fraud detection models.

FraudProfile  — one per user OR per vendor; tracks running risk score and review state.
FraudEvent    — individual fraud signal (one rule violation or ML anomaly = one event).
"""
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()

RISK_LEVELS = [
    ('low',      'Low'),
    ('medium',   'Medium'),
    ('high',     'High'),
    ('critical', 'Critical'),
]

FRAUD_EVENT_TYPES = [
    ('rapid_orders',          'Rapid Order Velocity'),
    ('high_refund_rate',      'High Refund Rate'),
    ('refund_abuse',          'Refund Abuse'),
    ('dispute_pattern',       'Dispute Pattern'),
    ('new_account_surge',     'New Account Order Surge'),
    ('suspicious_vendor',     'Suspicious Vendor Activity'),
    ('new_vendor_surge',      'New Vendor Order Surge'),
    ('ml_anomaly',            'ML Anomaly Detected'),
    ('credit_abuse',          'Credit/BNPL Abuse'),
    ('payment_failure_spike', 'Payment Failure Spike'),
    ('unverified_high_value', 'Unverified High-Value Transaction'),
    ('unverified_active',     'Unverified Vendor with High Activity'),
]

ENTITY_TYPES = [
    ('user',        'User'),
    ('vendor',      'Vendor'),
    ('order',       'Order'),
    ('transaction', 'Transaction'),
    ('refund',      'Refund'),
]


class FraudProfile(models.Model):
    """Aggregated fraud risk profile — one row per user OR per vendor."""

    # Exactly one of user / vendor is non-null (enforced by CheckConstraint)
    user = models.OneToOneField(
        User, null=True, blank=True,
        on_delete=models.CASCADE, related_name='fraud_profile',
    )
    vendor = models.OneToOneField(
        'business.VendorProfile', null=True, blank=True,
        on_delete=models.CASCADE, related_name='fraud_profile',
    )

    # Risk score 0–100; higher = more suspicious
    risk_score = models.FloatField(default=0.0)
    risk_level  = models.CharField(max_length=10, choices=RISK_LEVELS, default='low')

    # Running aggregate stats kept in sync by signals/tasks
    total_orders        = models.PositiveIntegerField(default=0)
    total_order_value   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    refund_count        = models.PositiveIntegerField(default=0)
    dispute_count       = models.PositiveIntegerField(default=0)
    failed_payment_count = models.PositiveIntegerField(default=0)

    # Flag state
    is_flagged      = models.BooleanField(default=False)
    auto_flagged_at = models.DateTimeField(null=True, blank=True)

    # Admin review
    is_reviewed     = models.BooleanField(default=False)
    reviewed_by     = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reviewed_fraud_profiles',
    )
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    review_outcome  = models.CharField(
        max_length=20,
        choices=[
            ('cleared',    'Cleared'),
            ('confirmed',  'Confirmed Fraud'),
            ('monitoring', 'Under Monitoring'),
        ],
        blank=True,
    )
    review_notes = models.TextField(blank=True)

    last_scored_at = models.DateTimeField(null=True, blank=True)
    score_features = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, vendor__isnull=True)
                    | models.Q(user__isnull=True, vendor__isnull=False)
                ),
                name='fraud_profile_user_xor_vendor',
            )
        ]

    def __str__(self):
        subject = f"user:{self.user_id}" if self.user_id else f"vendor:{self.vendor_id}"
        return f"FraudProfile({subject}, {self.risk_level}, score={self.risk_score:.1f})"

    def apply_risk_level(self):
        """Derive risk_level from risk_score and auto-flag if high/critical."""
        if self.risk_score >= 75:
            self.risk_level = 'critical'
        elif self.risk_score >= 50:
            self.risk_level = 'high'
        elif self.risk_score >= 25:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'low'

        if self.risk_level in ('high', 'critical') and not self.is_flagged:
            self.is_flagged = True
            self.auto_flagged_at = timezone.now()


class FraudEvent(models.Model):
    """One fraud signal — a single rule violation or ML anomaly detection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    profile     = models.ForeignKey(FraudProfile, on_delete=models.CASCADE, related_name='events')
    event_type  = models.CharField(max_length=30, choices=FRAUD_EVENT_TYPES)
    severity    = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    description = models.TextField()

    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id   = models.CharField(max_length=100)

    metadata = models.JSONField(default=dict)
    ml_score = models.FloatField(null=True, blank=True)

    is_false_positive = models.BooleanField(default=False)
    is_resolved  = models.BooleanField(default=False)
    resolved_by  = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='resolved_fraud_events',
    )
    resolved_at  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} [{self.severity}] — {self.entity_type}:{self.entity_id}"

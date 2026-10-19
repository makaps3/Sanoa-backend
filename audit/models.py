"""
Audit trail models for tracking all actions across the application.

Captures:
- API request/response activity
- Model create, update, delete operations
- User authentication events (login, logout, failed attempts)
- Admin actions
- Business events (orders, payments, vendor approvals, etc.)
"""
import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Central audit trail recording all actions in the application.
    Every significant event is captured here for compliance and debugging.
    """

    # Action categories
    CATEGORY_CHOICES = [
        ('auth', 'Authentication'),
        ('user', 'User Management'),
        ('product', 'Product'),
        ('order', 'Order'),
        ('payment', 'Payment'),
        ('inventory', 'Inventory'),
        ('vendor', 'Vendor'),
        ('admin', 'Admin'),
        ('system', 'System'),
        ('api', 'API Request'),
        ('debit', 'Buy Now Pay Later'),
        ('subscription', 'Subscription'),
        ('negotiation', 'Negotiation'),
        ('tier', 'Business Tier'),
        ('otp', 'OTP Verification'),
    ]

    # Action types
    ACTION_CHOICES = [
        # CRUD
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('soft_delete', 'Soft Delete'),
        ('restore', 'Restore'),
        # Auth
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('login_failed', 'Login Failed'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('token_refresh', 'Token Refresh'),
        # Business
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
        ('refund', 'Refund'),
        ('status_change', 'Status Change'),
        ('export', 'Export'),
        ('import', 'Import'),
        # System
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('api_request', 'API Request'),
    ]

    # Severity / outcome
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    user_email = models.EmailField(
        blank=True,
        default='',
        help_text='Snapshot of user email at time of action',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    # What
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success', db_index=True)
    description = models.TextField(help_text='Human-readable description of what happened')

    # Which object
    target_model = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text='App label and model name, e.g. orders.Order',
    )
    target_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        db_index=True,
        help_text='Primary key of the affected object',
    )
    target_repr = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='String representation of the affected object',
    )

    # Change details
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text='JSON diff of field changes: {"field": {"old": ..., "new": ...}}',
    )
    extra_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Additional context data (request body, query params, etc.)',
    )

    # Request context (for API actions)
    request_method = models.CharField(max_length=10, blank=True, default='')
    request_path = models.CharField(max_length=500, blank=True, default='')
    response_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    request_duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Request duration in milliseconds',
    )

    # When
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['category', 'action']),
            models.Index(fields=['target_model', 'target_id']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['-timestamp', 'category']),
            models.Index(fields=['status', '-timestamp']),
        ]

    def __str__(self):
        user_str = self.user_email or 'system'
        return f"[{self.timestamp}] {user_str} {self.action} {self.target_model} ({self.status})"


class LoginAttempt(models.Model):
    """
    Dedicated table for tracking login attempts - useful for
    security monitoring and brute-force detection.
    """

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    failure_reason = models.CharField(max_length=100, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        indexes = [
            models.Index(fields=['email', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['status', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.email} - {self.status} at {self.timestamp}"

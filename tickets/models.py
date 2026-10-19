"""
Support tickets — chat-style threads from a customer to either a
specific vendor (product / order / delivery issues …) or to the
platform admins (app issues, suggestions …).

Design mirrors the `chat` app:
  * A Ticket is the room header; TicketMessages are append-only.
  * Read markers are per side (customer / vendor / admin) — three
    stamps beat an N×M receipt table.
  * Vendor-targeted tickets are visible to the vendor AND platform
    admins (either may respond); platform tickets are admin-only.
  * High/urgent tickets fan out a realtime alert to the responsible
    parties until the first response lands (`first_response_at`).
"""
import uuid

from django.conf import settings
from django.db import models


class Ticket(models.Model):

    TARGET_VENDOR = 'vendor'
    TARGET_PLATFORM = 'platform'
    TARGET_CHOICES = [
        (TARGET_VENDOR, 'Vendor'),
        (TARGET_PLATFORM, 'Platform'),
    ]

    CATEGORY_CHOICES = [
        ('product', 'Product'),
        ('order', 'Order'),
        ('payment', 'Payment'),
        ('delivery', 'Delivery'),
        ('account', 'Account'),
        ('app_issue', 'App Issue'),
        ('suggestion', 'Suggestion'),
        ('other', 'Other'),
    ]

    URGENCY_LOW = 'low'
    URGENCY_NORMAL = 'normal'
    URGENCY_HIGH = 'high'
    URGENCY_URGENT = 'urgent'
    URGENCY_CHOICES = [
        (URGENCY_LOW, 'Low'),
        (URGENCY_NORMAL, 'Normal'),
        (URGENCY_HIGH, 'High'),
        (URGENCY_URGENT, 'Urgent'),
    ]
    # Urgencies that trigger the realtime pop-up + ringtone alert.
    ALERT_URGENCIES = (URGENCY_HIGH, URGENCY_URGENT)

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                          editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets',
    )
    target_type = models.CharField(max_length=10, choices=TARGET_CHOICES)
    vendor = models.ForeignKey(
        'business.VendorProfile',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='support_tickets',
        help_text='Set when target_type is vendor.',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    urgency = models.CharField(
        max_length=10, choices=URGENCY_CHOICES, default=URGENCY_NORMAL,
    )
    subject = models.CharField(max_length=200)
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # Stamped on the first vendor/admin reply — dismisses the alert.
    first_response_at = models.DateTimeField(null=True, blank=True)

    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=140, blank=True)

    customer_read_at = models.DateTimeField(null=True, blank=True)
    vendor_read_at = models.DateTimeField(null=True, blank=True)
    admin_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['-last_message_at']),
            models.Index(fields=['customer', '-last_message_at']),
            models.Index(fields=['vendor', '-last_message_at']),
            models.Index(fields=['target_type', 'status']),
        ]

    def __str__(self):
        return f'Ticket<{self.id}> {self.target_type}/{self.category}'

    @property
    def needs_alert(self):
        return (
            self.urgency in self.ALERT_URGENCIES
            and self.first_response_at is None
            and self.status in (self.STATUS_OPEN, self.STATUS_IN_PROGRESS)
        )

    def role_for(self, user):
        """Return 'customer' | 'vendor' | 'admin' | None."""
        if self.customer_id == user.id:
            return 'customer'
        if user.is_staff or user.is_superuser or \
                hasattr(user, 'admin_profile'):
            return 'admin'
        if self.target_type == self.TARGET_VENDOR and self.vendor_id:
            if self.vendor.user_id == user.id:
                return 'vendor'
            emp = getattr(user, 'vendor_employment', None)
            if emp is not None and emp.vendor_id == self.vendor_id \
                    and emp.is_active:
                return 'vendor'
        return None

    def read_marker_field(self, role):
        return {
            'customer': 'customer_read_at',
            'vendor': 'vendor_read_at',
            'admin': 'admin_read_at',
        }.get(role)

    def unread_count_for(self, user):
        role = self.role_for(user)
        field = self.read_marker_field(role)
        if field is None:
            return 0
        marker = getattr(self, field)
        qs = self.messages.filter(is_deleted=False).exclude(sender=user)
        if marker is not None:
            qs = qs.filter(created_at__gt=marker)
        return qs.count()


class TicketMessage(models.Model):

    KIND_TEXT = 'text'
    KIND_SYSTEM = 'system'
    KIND_CHOICES = [
        (KIND_TEXT, 'Text'),
        (KIND_SYSTEM, 'System'),
    ]

    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('admin', 'Admin'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                          editable=False)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ticket_messages',
    )
    # Stored at write time so role survives vendor/admin churn.
    sender_role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default='system',
    )
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, default=KIND_TEXT,
    )
    body = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]

    def __str__(self):
        return f'TicketMsg<{self.id}> {self.sender_role}'

"""
Real-time chat between the customer and the delivery driver of a
single DeliveryJob, with platform-admin read-only oversight.

Design:
  * One Conversation per DeliveryJob (1:1) — so the chat room is
    naturally scoped to a single delivery and dies when the delivery
    is closed.
  * Messages are append-only; deleting is soft (`is_deleted` flag)
    so the audit trail stays intact for moderation.
  * `read_at` is tracked per side (customer / driver) rather than
    per message — two markers are enough for a 1:1 chat and avoid
    an N×M read-receipt table.
"""
import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """One chat room per delivery job."""

    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                         editable=False)
    delivery_job = models.OneToOneField(
        'delivery.DeliveryJob',
        on_delete=models.CASCADE,
        related_name='conversation',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_chats',
        limit_choices_to={'user_type': 'customer'},
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='driver_chats',
        limit_choices_to={'user_type': 'driver'},
    )
    status = models.CharField(
        max_length=8, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=140, blank=True)
    customer_read_at = models.DateTimeField(null=True, blank=True)
    driver_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['-last_message_at']),
            models.Index(fields=['customer', '-last_message_at']),
            models.Index(fields=['driver', '-last_message_at']),
        ]

    def __str__(self):
        return f'Chat<{self.id}> job={self.delivery_job_id}'

    def role_for(self, user):
        """Return 'customer' | 'driver' | 'admin' | None."""
        if self.customer_id == user.id:
            return 'customer'
        if self.driver_id == user.id:
            return 'driver'
        if user.is_staff or user.is_superuser or \
                hasattr(user, 'admin_profile'):
            return 'admin'
        return None

    def unread_count_for(self, user):
        marker = (
            self.customer_read_at if self.customer_id == user.id else
            self.driver_read_at if self.driver_id == user.id else
            None
        )
        qs = self.messages.filter(is_deleted=False).exclude(sender=user)
        if marker is not None:
            qs = qs.filter(created_at__gt=marker)
        return qs.count()


class Message(models.Model):
    """A single chat message — text, system, or location."""

    KIND_TEXT = 'text'
    KIND_SYSTEM = 'system'
    KIND_LOCATION = 'location'
    KIND_CHOICES = [
        (KIND_TEXT, 'Text'),
        (KIND_SYSTEM, 'System'),
        (KIND_LOCATION, 'Location'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                         editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chat_messages',
    )
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, default=KIND_TEXT,
    )
    body = models.TextField(blank=True)
    # For KIND_LOCATION — sender shares a single pin.
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f'Msg<{self.id}> {self.kind}'

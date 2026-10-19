import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPCode(models.Model):
    """Model to store OTP codes for user verification, password reset, and login."""

    PURPOSE_CHOICES = [
        ('verification', 'Account Verification'),
        ('password_reset', 'Password Reset'),
        ('login', 'Login'),
    ]

    MAX_ATTEMPTS = 3

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='otp_codes',
    )
    code = models.CharField(max_length=6, help_text="6-digit numeric OTP code")
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='verification')
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0, help_text="Number of failed verification attempts")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP Code'
        verbose_name_plural = 'OTP Codes'

    def __str__(self):
        return f"OTP {self.code} for {self.user.email} ({self.purpose})"

    @property
    def is_expired(self):
        """Check if the OTP has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if the OTP is still valid (not used, not expired, attempts < max)."""
        return not self.is_used and not self.is_expired and self.attempts < self.MAX_ATTEMPTS

    @staticmethod
    def generate_code():
        """Generate a random 6-digit numeric OTP code."""
        return str(secrets.randbelow(900000) + 100000)

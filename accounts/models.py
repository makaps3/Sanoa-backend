import hashlib
import secrets

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from PIL import Image


class User(AbstractUser):
    """Custom User model extending AbstractUser"""

    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('employee', 'Employee'),
        ('driver', 'Driver'),
        ('admin', 'Admin'),
    ]

    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='customer')
    is_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)

    # Suspension (credit default enforcement)
    is_suspended = models.BooleanField(
        default=False,
        help_text='Suspended users are blocked from using the platform except for making payments.',
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(
        blank=True,
        help_text='Reason for suspension (e.g. overdue credit payment).',
    )

    # Subscription trial usage — once True the customer no longer
    # qualifies for the 14-day free trial when (re-)subscribing. Set
    # the first time a trial subscription is created. Survives the
    # Subscription wipe-and-replace inside SubscriptionCreateSerializer
    # so we always know whether this user has already burned their
    # one-shot trial.
    had_trial = models.BooleanField(
        default=False,
        help_text=(
            'True after the customer has consumed their one-time 14-day '
            'subscription trial. Future re-subscribes skip the trial.'
        ),
    )

    # Forced password change. Flipped True when an account is
    # provisioned with a temporary password (e.g. a vendor manager
    # creating an employee). The login response surfaces this flag
    # so the client can route the user through a "set new password"
    # screen before any other action. Cleared by the change-password
    # endpoint.
    must_change_password = models.BooleanField(
        default=False,
        help_text=(
            'When True the next login forces a password change '
            'before the user can use the rest of the app. Set by '
            'flows that mint a temporary password.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.email} ({self.user_type})"


class CustomerProfile(models.Model):
    """Extended profile for customers"""

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    avatar = models.ImageField(upload_to='avatars/customers/', null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)

    # Interest categories (selected during registration)
    interest_categories = models.ManyToManyField(
        'products.Category', blank=True, related_name='interested_customers',
        help_text="Categories the customer is interested in"
    )

    # Customer location (for distance-based recommendations)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Customer latitude for proximity-based store discovery"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Customer longitude for proximity-based store discovery"
    )

    # Preferences
    preferred_language = models.CharField(max_length=10, default='en')
    newsletter_subscription = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)

    # Loyalty program
    loyalty_points = models.PositiveIntegerField(default=0)
    member_since = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Customer Profile'
        verbose_name_plural = 'Customer Profiles'

    def __str__(self):
        return f"{self.user.email} - Customer Profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar:
            img = Image.open(self.avatar.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.avatar.path)


# =============================================================================
# API Token
# =============================================================================

class APIToken(models.Model):
    """
    API token for authenticating requests to private endpoints.
    Each token is linked to a user account. Users can create multiple tokens
    with different names/scopes. The raw token is shown only once at creation;
    only the hash and a display prefix are stored for lookup.
    """

    SCOPE_CHOICES = [
        ('full', 'Full Access'),
        ('read', 'Read Only'),
        ('products', 'Products Management'),
        ('orders', 'Orders Management'),
        ('inventory', 'Inventory Management'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    name = models.CharField(max_length=100, help_text="A label to identify this token")

    # Token storage
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    prefix = models.CharField(
        max_length=8, editable=False,
        help_text="First 8 chars of the token for identification"
    )

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='full')
    is_active = models.BooleanField(default=True)

    # Expiry
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Leave blank for a non-expiring token"
    )

    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    total_requests = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API Token'
        verbose_name_plural = 'API Tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.prefix}...) - {self.user.email}"

    @staticmethod
    def generate_token():
        """Generate a secure random token and return (raw_token, token_hash, prefix)."""
        raw_token = f"snoa_{secrets.token_hex(32)}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        prefix = raw_token[:8]
        return raw_token, token_hash, prefix

    @staticmethod
    def hash_token(raw_token):
        """Hash a raw token for lookup."""
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    def record_usage(self, ip_address=None):
        """Update usage stats on each authenticated request."""
        self.last_used_at = timezone.now()
        self.last_used_ip = ip_address
        self.total_requests = models.F('total_requests') + 1
        self.save(update_fields=['last_used_at', 'last_used_ip', 'total_requests'])

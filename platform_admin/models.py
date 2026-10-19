"""
Platform Admin models.

Registration flow:
  1. POST /api/accounts/register/      (user_type='admin')
  2. POST /api/otp/verify/             (verify email OTP)
  3. POST /api/platform-admin/profile/ (create AdminProfile)

Employee flow:
  Super Admin sends invitation → AdminInvitation created →
  invitee registers account (user_type='admin') → verifies OTP →
  POST /api/platform-admin/invitations/<token>/accept/ →
  AdminProfile auto-created and linked to invitation.
"""
import secrets
import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

AUTH_USER_MODEL = settings.AUTH_USER_MODEL

ROLE_CHOICES = [
    ('super_admin',   'Super Admin'),
    ('ops_admin',     'Operations Admin'),
    ('support_admin', 'Support Admin'),
    ('finance_admin', 'Finance Admin'),
]

DEPARTMENT_CHOICES = [
    ('operations',  'Operations'),
    ('support',     'Support'),
    ('finance',     'Finance'),
    ('technology',  'Technology'),
    ('management',  'Management'),
]

# Default permission sets per role.
# Super Admin can override individual keys on any profile.
ROLE_PERMISSIONS = {
    'super_admin': {
        'manage_admins':        True,
        'manage_drivers':       True,
        'manage_vendors':       True,
        'manage_customers':     True,
        'manage_orders':        True,
        'manage_payments':      True,
        'manage_refunds':       True,
        'manage_disputes':      True,
        'manage_subscriptions': True,
        'manage_inventory':     True,
        'manage_delivery':      True,
        'manage_notifications': True,
        'view_analytics':       True,
        'system_configuration': True,
        'manage_support':       True,
        'view_audit_logs':      True,
        'financial_access':     True,
        'security_management':  True,
    },
    'ops_admin': {
        'manage_admins':        False,
        'manage_drivers':       True,
        'manage_vendors':       False,
        'manage_customers':     False,
        'manage_orders':        True,
        'manage_payments':      False,
        'manage_refunds':       False,
        'manage_disputes':      False,
        'manage_subscriptions': False,
        'manage_inventory':     True,
        'manage_delivery':      True,
        'manage_notifications': True,
        'view_analytics':       True,
        'system_configuration': False,
        'manage_support':       False,
        'view_audit_logs':      True,
        'financial_access':     False,
        'security_management':  False,
    },
    'support_admin': {
        'manage_admins':        False,
        'manage_drivers':       False,
        'manage_vendors':       False,
        'manage_customers':     True,
        'manage_orders':        True,
        'manage_payments':      False,
        'manage_refunds':       True,
        'manage_disputes':      True,
        'manage_subscriptions': False,
        'manage_inventory':     False,
        'manage_delivery':      False,
        'manage_notifications': True,
        'view_analytics':       False,
        'system_configuration': False,
        'manage_support':       True,
        'view_audit_logs':      True,
        'financial_access':     False,
        'security_management':  False,
    },
    'finance_admin': {
        'manage_admins':        False,
        'manage_drivers':       False,
        'manage_vendors':       False,
        'manage_customers':     False,
        'manage_orders':        False,
        'manage_payments':      True,
        'manage_refunds':       True,
        'manage_disputes':      True,
        'manage_subscriptions': True,
        'manage_inventory':     False,
        'manage_delivery':      False,
        'manage_notifications': False,
        'view_analytics':       True,
        'system_configuration': False,
        'manage_support':       False,
        'view_audit_logs':      True,
        'financial_access':     True,
        'security_management':  False,
    },
}


class AdminProfile(models.Model):
    STATUS_CHOICES = [
        ('active',    'Active'),
        ('suspended', 'Suspended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='admin_profile',
        limit_choices_to={'user_type': 'admin'},
    )

    # Basic info
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department    = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    role_title    = models.CharField(max_length=100, blank=True)
    work_email    = models.EmailField(unique=True)
    profile_photo = models.ImageField(upload_to='admin/photos/', null=True, blank=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Employee hierarchy
    invited_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='team_members',
    )

    # Fine-grained permissions — seeded from ROLE_PERMISSIONS on create.
    # Super Admin can override individual keys afterwards.
    permissions = models.JSONField(default=dict)

    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admin Profile'
        verbose_name_plural = 'Admin Profiles'
        ordering = ['role', 'user__email']

    def __str__(self):
        return f"{self.user.email} [{self.get_role_display()}]"

    @property
    def is_super_admin(self):
        return self.status == 'active' and self.role == 'super_admin'

    def has_permission(self, key: str) -> bool:
        if self.status != 'active':
            return False
        if self.is_super_admin:
            return True
        return bool(self.permissions.get(key, False))

    def seed_permissions(self):
        self.permissions = ROLE_PERMISSIONS.get(self.role, {}).copy()

    def record_login(self):
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])


class AdminInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('expired',  'Expired'),
        ('revoked',  'Revoked'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invited_by  = models.ForeignKey(
        AdminProfile, on_delete=models.CASCADE, related_name='sent_invitations',
    )
    email       = models.EmailField()
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department  = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    token       = models.CharField(max_length=64, unique=True, editable=False)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at  = models.DateTimeField()
    accepted_by = models.OneToOneField(
        AdminProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accepted_invitation',
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Admin Invitation'
        verbose_name_plural = 'Admin Invitations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite → {self.email} [{self.role}] ({self.status})"

    @property
    def is_valid(self):
        return self.status == 'pending' and timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)


# ── Platform Fee Schedule ────────────────────────────────────────────────────
#
# One row per business type. Two ranges per row — what we charge the
# customer (service fee on top of the order subtotal) and what we keep
# from the merchant (commission cut of the merchant payout). The ranges
# are inclusive bounds the ops team can quote to merchants during
# onboarding and to customers during checkout; the actual numeric value
# used at payment time still lives on the vendor's individual contract
# fields. Editing happens through the platform admin UI, not the Django
# admin alone.

class PlatformFee(models.Model):
    # Aligned with business.VendorProfile.business_category so the same
    # vocabulary works for both vendor onboarding and customer
    # checkout. Grocery is rolled into `retail` per the platform spec.
    BUSINESS_TYPE_RETAIL     = 'retail'
    BUSINESS_TYPE_RESTAURANT = 'restaurant'
    BUSINESS_TYPE_CHOICES = [
        (BUSINESS_TYPE_RETAIL,     'E-commerce / Retail (incl. grocery)'),
        (BUSINESS_TYPE_RESTAURANT, 'Restaurant delivery'),
    ]

    _percent_validators = [MinValueValidator(0), MaxValueValidator(100)]
    # The delivery commission is a small platform cut off the driver's
    # gross fare — capped tight on purpose so drivers always keep
    # the bulk of what they earned on the road.
    _delivery_fee_validators = [MinValueValidator(0), MaxValueValidator(5)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_type = models.CharField(
        max_length=32, choices=BUSINESS_TYPE_CHOICES, unique=True,
        help_text='The category this fee schedule applies to. One row per type.',
    )

    customer_service_fee_min = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        help_text='Lower bound of the customer-side service fee (percent of order subtotal).',
    )
    customer_service_fee_max = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        help_text='Upper bound of the customer-side service fee (percent of order subtotal).',
    )
    # Single applied value the checkout endpoint adds to the order.
    # Falls anywhere inside [min, max] — defaults to the midpoint when
    # left blank on first save (see `save`).
    customer_service_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        default=0,
        help_text='Actual percent added to customer orders at checkout.',
    )

    merchant_commission_min = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        help_text='Lower bound of the merchant commission Sanoa keeps (percent of merchant payout).',
    )
    merchant_commission_max = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        help_text='Upper bound of the merchant commission Sanoa keeps (percent of merchant payout).',
    )
    # Single applied value pushed into Paystack as the subaccount's
    # `percentage_charge`. Paystack's gateway fee is absorbed by the
    # platform out of this commission, so this number is the true
    # cut Sanoa keeps before settling the merchant.
    merchant_commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=_percent_validators,
        default=0,
        help_text='Actual percentage_charge pushed to Paystack subaccounts.',
    )

    # ── Driver-side delivery commission (0 – 5 %) ───────────────────
    # Capped low because the driver does the actual transport work —
    # the platform's cut here covers ops/dispatch overhead only.
    delivery_fee_min = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=_delivery_fee_validators, default=0,
        help_text='Lower bound of the platform delivery commission '
                  '(percent of driver gross fare).',
    )
    delivery_fee_max = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=_delivery_fee_validators, default=0,
        help_text='Upper bound of the platform delivery commission '
                  '(percent of driver gross fare).',
    )
    delivery_fee_percent = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=_delivery_fee_validators, default=0,
        help_text='Actual delivery commission deducted from the '
                  'driver gross fare on each completed job.',
    )

    notes = models.TextField(
        blank=True,
        help_text='Optional context for ops — exceptions, promo windows, etc.',
    )
    is_active = models.BooleanField(default=True)

    updated_by = models.ForeignKey(
        AdminProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform Fee'
        verbose_name_plural = 'Platform Fees'
        ordering = ['business_type']

    def __str__(self):
        label = dict(self.BUSINESS_TYPE_CHOICES).get(self.business_type, self.business_type)
        return f"{label} — customer {self.customer_service_fee_min}–{self.customer_service_fee_max}%, merchant {self.merchant_commission_min}–{self.merchant_commission_max}%"

    @property
    def customer_service_fee_range(self):
        return f'{self.customer_service_fee_min}%-{self.customer_service_fee_max}%'

    @property
    def merchant_commission_range(self):
        return f'{self.merchant_commission_min}%-{self.merchant_commission_max}%'

    @property
    def delivery_fee_range(self):
        return f'{self.delivery_fee_min}%-{self.delivery_fee_max}%'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.customer_service_fee_min > self.customer_service_fee_max:
            raise ValidationError({
                'customer_service_fee_min':
                    'Lower bound must be ≤ upper bound.',
            })
        if self.merchant_commission_min > self.merchant_commission_max:
            raise ValidationError({
                'merchant_commission_min':
                    'Lower bound must be ≤ upper bound.',
            })
        if not (
            self.customer_service_fee_min
            <= self.customer_service_fee_percent
            <= self.customer_service_fee_max
        ):
            raise ValidationError({
                'customer_service_fee_percent':
                    'Applied fee must sit inside [min, max].',
            })
        if not (
            self.merchant_commission_min
            <= self.merchant_commission_percent
            <= self.merchant_commission_max
        ):
            raise ValidationError({
                'merchant_commission_percent':
                    'Applied commission must sit inside [min, max].',
            })
        if self.delivery_fee_min > self.delivery_fee_max:
            raise ValidationError({
                'delivery_fee_min':
                    'Lower bound must be ≤ upper bound.',
            })
        if not (
            self.delivery_fee_min
            <= self.delivery_fee_percent
            <= self.delivery_fee_max
        ):
            raise ValidationError({
                'delivery_fee_percent':
                    'Applied delivery commission must sit inside '
                    '[min, max].',
            })

    def save(self, *args, **kwargs):
        # Default the applied % to the *minimum* of the advertised
        # range — the platform always quotes the friendly low end of
        # the band until ops explicitly bumps it.
        if not self.customer_service_fee_percent and self.customer_service_fee_min is not None:
            self.customer_service_fee_percent = self.customer_service_fee_min
        if not self.merchant_commission_percent and self.merchant_commission_min is not None:
            self.merchant_commission_percent = self.merchant_commission_min
        if not self.delivery_fee_percent and self.delivery_fee_min is not None:
            self.delivery_fee_percent = self.delivery_fee_min
        super().save(*args, **kwargs)

    @classmethod
    def for_business_category(cls, business_category):
        """Return the active fee row for a vendor's `business_category`.

        Vendor business_category is the same vocabulary as
        `BUSINESS_TYPE_CHOICES` (`retail` or `restaurant`), so the
        lookup is a straight equality match. Returns None when no
        active row exists — callers fall back to zero charges.
        """
        if not business_category:
            return None
        return cls.objects.filter(
            business_type=business_category, is_active=True,
        ).first()

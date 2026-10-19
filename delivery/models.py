from core.private_documents import private_document_storage
from django.utils import timezone
"""
Models for the Delivery app.

Contains:
- FareRate         — admin-configurable base fare / per-km / max-distance per business category
- DeliveryDriver   — profile for users with user_type='driver'
- DeliveryFare     — a calculated delivery quote between customer address and vendor
- DriverShift      — online / offline sessions with GPS at start/end
- DeliveryJob      — full delivery lifecycle attached to a retail or restaurant order
- DriverLocationPing — GPS snapshots taken while a job is active
- DriverEarning    — per-job earnings record
- DriverPayout     — aggregate payout batch for a driver
- DriverRating     — customer rating of a driver after delivery
"""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

AUTH_USER_MODEL = settings.AUTH_USER_MODEL

BUSINESS_CATEGORY_CHOICES = [
    ('retail', 'Groceries'),
    ('restaurant', 'Fast Food'),
]


class FareRate(models.Model):
    business_category = models.CharField(
        max_length=20, choices=BUSINESS_CATEGORY_CHOICES, unique=True,
    )
    base_fare = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('20.00'),
    )
    per_km_rate = models.DecimalField(max_digits=6, decimal_places=2)
    max_distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'delivery_farerate'
        verbose_name = 'Fare Rate'
        verbose_name_plural = 'Fare Rates'

    def __str__(self):
        return f"{self.business_category} — base R{self.base_fare} + R{self.per_km_rate}/km"

    def calculate(self, distance_km: Decimal) -> Decimal:
        return (self.base_fare + (self.per_km_rate * distance_km)).quantize(Decimal('0.01'))


class DeliveryDriver(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('bicycle', 'Bicycle'),
        ('motorbike', 'Motorbike'),
        ('car', 'Car'),
        ('van', 'Van'),
        ('truck', 'Truck'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='driver_profile',
        limit_choices_to={'user_type': 'driver'},
    )

    # ── Personal info ─────────────────────────────────────────
    profile_photo = models.ImageField(
        upload_to='drivers/photos/', null=True, blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, blank=True,
    )
    national_id_document = models.FileField(storage=private_document_storage, 
        upload_to='drivers/id_docs/', null=True, blank=True,
        help_text='National ID or passport scan',
    )
    residential_address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # ── Vehicle info ──────────────────────────────────────────
    vehicle_type = models.CharField(
        max_length=20, choices=VEHICLE_TYPE_CHOICES, default='motorbike',
    )
    vehicle_brand = models.CharField(max_length=100, blank=True)
    vehicle_model = models.CharField(max_length=100, blank=True)
    vehicle_registration = models.CharField(max_length=20, blank=True)
    vehicle_color = models.CharField(max_length=50, blank=True)
    vehicle_photo_front = models.ImageField(
        upload_to='drivers/vehicles/', null=True, blank=True,
    )
    vehicle_photo_side = models.ImageField(
        upload_to='drivers/vehicles/', null=True, blank=True,
    )
    vehicle_photo_rear = models.ImageField(
        upload_to='drivers/vehicles/', null=True, blank=True,
    )
    insurance_document = models.FileField(storage=private_document_storage, 
        upload_to='drivers/insurance/', null=True, blank=True,
    )
    vehicle_license_expiry = models.DateField(null=True, blank=True)

    # ── Verification & compliance ─────────────────────────────
    driver_license_document = models.FileField(storage=private_document_storage, 
        upload_to='drivers/licenses/', null=True, blank=True,
    )
    license_number = models.CharField(max_length=50, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    background_check_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending',
    )
    identity_verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending',
    )
    training_completed = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    # Free-text notes the admin records on the driver during vetting —
    # usually a list of missing documents the driver should re-upload
    # before the application can be approved.
    vetting_notes = models.TextField(
        blank=True,
        help_text='Admin notes about missing documents / re-submission '
                  'requirements visible to the driver.',
    )

    # ── Operational ───────────────────────────────────────────
    is_available = models.BooleanField(
        default=False,
        help_text='True when driver is online and accepting requests.',
    )
    current_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    current_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    total_deliveries = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('0.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'delivery_deliverydriver'
        verbose_name = 'Delivery Driver'
        verbose_name_plural = 'Delivery Drivers'

    def __str__(self):
        return f"{self.user.email} ({self.vehicle_type})"

    # ── Verification gate ────────────────────────────────────────────
    # Both review stages must pass before a driver can accept work.
    @property
    def is_verified(self) -> bool:
        """True when the driver is cleared to go online and accept jobs."""
        return (
            self.identity_verification_status == 'approved'
            and self.background_check_status == 'approved'
            and self.terms_accepted
            and self.license_expiry_date is not None
            and self.license_expiry_date >= timezone.localdate()
            and (self.vehicle_license_expiry is None or self.vehicle_license_expiry >= timezone.localdate())
            and self.user.is_active and self.user.is_verified and not self.user.is_suspended
        )

    @property
    def verification_status(self) -> str:
        """Single overall status for the UI, derived from the identity queue
        (the queue the driver actively submits to). One of
        pending / under_review / approved / rejected."""
        if self.background_check_status == 'rejected':
            return 'rejected'
        if self.identity_verification_status == 'approved' and self.background_check_status != 'approved':
            return 'under_review'
        return self.identity_verification_status


class DeliveryFare(models.Model):
    """Delivery fare quote — calculated before an order is placed."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='delivery_fares',
        limit_choices_to={'user_type': 'customer'},
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='delivery_fares',
    )
    address = models.ForeignKey(
        'orders.ShippingAddress', on_delete=models.PROTECT,
        related_name='delivery_fares',
    )
    driver = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_deliveries',
        limit_choices_to={'user_type': 'driver'},
    )
    business_category = models.CharField(max_length=20, choices=BUSINESS_CATEGORY_CHOICES)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    base_fare = models.DecimalField(max_digits=8, decimal_places=2)
    per_km_rate = models.DecimalField(max_digits=6, decimal_places=2)
    fare_amount = models.DecimalField(max_digits=8, decimal_places=2)

    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    decline_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'delivery_deliveryfare'
        verbose_name = 'Delivery Fare'
        verbose_name_plural = 'Delivery Fares'
        ordering = ['-created_at']

    def __str__(self):
        return f"Fare {self.id} — {self.distance_km}km — R{self.fare_amount}"


# ─────────────────────────────────────────────
#  Driver shift (online / offline tracking)
# ─────────────────────────────────────────────

class DriverShift(models.Model):
    """Records a driver going online and (eventually) offline."""

    driver = models.ForeignKey(
        DeliveryDriver, on_delete=models.CASCADE, related_name='shifts',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    start_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    start_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    end_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    end_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    class Meta:
        verbose_name = 'Driver Shift'
        verbose_name_plural = 'Driver Shifts'
        ordering = ['-started_at']

    def __str__(self):
        status = 'active' if self.is_active else f"ended {self.ended_at}"
        return f"{self.driver.user.email} shift — {status}"


# ─────────────────────────────────────────────
#  Delivery job (full lifecycle)
# ─────────────────────────────────────────────

class DeliveryJob(models.Model):
    """
    Full delivery lifecycle for a retail or restaurant order.
    Linked to at most one of retail_order or restaurant_order.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('driver_at_vendor', 'Driver at Vendor'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    fare = models.OneToOneField(
        DeliveryFare, on_delete=models.PROTECT,
        related_name='job', null=True, blank=True,
    )
    retail_order = models.OneToOneField(
        'orders.Order', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_job',
    )
    restaurant_order = models.OneToOneField(
        'restaurant.RestaurantOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='delivery_job',
    )

    driver = models.ForeignKey(
        DeliveryDriver, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jobs',
    )
    customer = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='delivery_jobs',
        limit_choices_to={'user_type': 'customer'},
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='delivery_jobs',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    fare_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))

    delivery_notes = models.TextField(blank=True)
    proof_of_delivery_image = models.ImageField(
        upload_to='delivery/proof/', null=True, blank=True,
    )

    # Drivers who have explicitly declined this job — excluded from re-dispatch
    declined_by = models.ManyToManyField(
        'DeliveryDriver',
        blank=True,
        related_name='declined_jobs',
        help_text='Drivers who declined this job offer.',
    )

    # 4-digit drop-off PIN.
    #
    # Generated automatically the first time the job is saved (see
    # `save()` below). The customer sees this in the tracking screen
    # from the moment the order is placed and reads it to the driver
    # at drop-off. The driver-side `delivered` endpoint demands the
    # PIN match before flipping the job to `delivered` — closes the
    # "driver claims delivery without actually handing over the
    # package" hole.
    delivery_pin = models.CharField(
        max_length=4, blank=True,
        help_text='Auto-generated 4-digit PIN the customer reads to the driver at drop-off.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    driver_at_vendor_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Delivery Job'
        verbose_name_plural = 'Delivery Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['driver', 'status']),
        ]

    def __str__(self):
        return f"Job {self.id} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.delivery_pin:
            import secrets
            # `secrets.randbelow` is cryptographically secure — safe to
            # use even though the PIN is short. Leading zeros are kept
            # (`f"{n:04d}"`) so e.g. 0473 stays four characters wide.
            self.delivery_pin = f"{secrets.randbelow(10000):04d}"
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
#  GPS pings (only stored while job is active)
# ─────────────────────────────────────────────

class DriverLocationPing(models.Model):
    """GPS ping from driver during an active DeliveryJob."""

    job = models.ForeignKey(DeliveryJob, on_delete=models.CASCADE, related_name='location_pings')
    driver = models.ForeignKey(DeliveryDriver, on_delete=models.CASCADE, related_name='location_pings')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.FloatField(null=True, blank=True)
    speed_kmh = models.FloatField(null=True, blank=True)
    heading_degrees = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Driver Location Ping'
        verbose_name_plural = 'Driver Location Pings'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['job', 'timestamp']),
        ]

    def __str__(self):
        return f"Ping job={self.job_id} lat={self.latitude} lon={self.longitude}"


# ─────────────────────────────────────────────
#  Earnings
# ─────────────────────────────────────────────

class DriverPayout(models.Model):
    """Aggregate payout batch for a driver over a period."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    driver = models.ForeignKey(DeliveryDriver, on_delete=models.CASCADE, related_name='payouts')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    total_gross = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_commission = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_net = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Driver Payout'
        verbose_name_plural = 'Driver Payouts'
        ordering = ['-period_end']

    def __str__(self):
        return f"Payout {self.driver.user.email} R{self.total_net} [{self.status}]"


class DriverEarning(models.Model):
    """Per-completed-job earnings record."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('disputed', 'Disputed'),
    ]

    driver = models.ForeignKey(DeliveryDriver, on_delete=models.CASCADE, related_name='earnings')
    job = models.OneToOneField(DeliveryJob, on_delete=models.CASCADE, related_name='earning')
    payout = models.ForeignKey(
        DriverPayout, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='earnings',
    )

    gross_amount = models.DecimalField(max_digits=8, decimal_places=2)
    platform_commission = models.DecimalField(max_digits=8, decimal_places=2)
    net_amount = models.DecimalField(max_digits=8, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Driver Earning'
        verbose_name_plural = 'Driver Earnings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Earning job={self.job_id} gross=R{self.gross_amount} net=R{self.net_amount}"


# ─────────────────────────────────────────────
#  Ratings
# ─────────────────────────────────────────────

class DriverRating(models.Model):
    """Customer rating of a driver after a completed delivery."""

    job = models.OneToOneField(DeliveryJob, on_delete=models.CASCADE, related_name='rating')
    customer = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='driver_ratings_given',
        limit_choices_to={'user_type': 'customer'},
    )
    driver = models.ForeignKey(DeliveryDriver, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Driver Rating'
        verbose_name_plural = 'Driver Ratings'

    def __str__(self):
        return f"{self.driver.user.email} rated {self.rating}/5 by {self.customer.email}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recompute driver's average rating
        driver = self.driver
        ratings = DriverRating.objects.filter(driver=driver).values_list('rating', flat=True)
        if ratings:
            driver.average_rating = Decimal(str(sum(ratings) / len(ratings))).quantize(Decimal('0.01'))
            driver.save(update_fields=['average_rating'])

from core.document_validation import DocumentValidationMixin
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import (
    DeliveryDriver, DeliveryFare, FareRate,
    DriverShift, DeliveryJob, DriverLocationPing,
    DriverEarning, DriverPayout, DriverRating,
)


class FareRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FareRate
        fields = [
            'id', 'business_category', 'base_fare', 'per_km_rate',
            'max_distance_km', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DeliveryDriverSerializer(serializers.ModelSerializer):
    """Full read serializer — returned on GET /api/delivery/driver/profile/"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    # Verification gate + admin notes so the driver app can show the review
    # status and any re-submission requirements without a second request.
    is_verified = serializers.BooleanField(read_only=True)
    verification_status = serializers.CharField(read_only=True)

    class Meta:
        model = DeliveryDriver
        fields = [
            'id', 'user', 'user_email', 'full_name',
            # Personal info
            'profile_photo', 'date_of_birth', 'gender',
            'national_id_document',
            'residential_address',
            'emergency_contact_name', 'emergency_contact_phone',
            # Vehicle
            'vehicle_type', 'vehicle_brand', 'vehicle_model',
            'vehicle_registration', 'vehicle_color',
            'vehicle_photo_front', 'vehicle_photo_side', 'vehicle_photo_rear',
            'insurance_document', 'vehicle_license_expiry',
            # Verification
            'driver_license_document', 'license_number', 'license_expiry_date',
            'background_check_status', 'identity_verification_status',
            'is_verified', 'verification_status', 'vetting_notes',
            'training_completed', 'terms_accepted', 'terms_accepted_at',
            # Operational
            'is_available', 'current_latitude', 'current_longitude',
            'total_deliveries', 'average_rating',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user',
            'background_check_status', 'identity_verification_status',
            'is_verified', 'verification_status', 'vetting_notes',
            'training_completed', 'terms_accepted_at',
            'is_available', 'current_latitude', 'current_longitude',
            'total_deliveries', 'average_rating',
            'created_at', 'updated_at',
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


class DeliveryDriverCreateSerializer(DocumentValidationMixin, serializers.ModelSerializer):
    """Create driver profile — POST /api/delivery/driver/profile/"""

    class Meta:
        model = DeliveryDriver
        fields = [
            # Personal info
            'profile_photo', 'date_of_birth', 'gender',
            'national_id_document',
            'residential_address',
            'emergency_contact_name', 'emergency_contact_phone',
            # Vehicle
            'vehicle_type', 'vehicle_brand', 'vehicle_model',
            'vehicle_registration', 'vehicle_color',
            'vehicle_photo_front', 'vehicle_photo_side', 'vehicle_photo_rear',
            'insurance_document', 'vehicle_license_expiry',
            # Verification docs
            'driver_license_document', 'license_number', 'license_expiry_date',
            'terms_accepted',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        if user.user_type != 'driver':
            raise serializers.ValidationError('Only users with driver account type can create a driver profile.')
        if DeliveryDriver.objects.filter(user=user).exists():
            raise serializers.ValidationError('You already have a driver profile.')
        if not attrs.get('terms_accepted'):
            raise serializers.ValidationError({'terms_accepted': 'Accept the terms to continue.'})
        return attrs

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError('You must accept the terms and conditions.')
        return value

    def create(self, validated_data):
        from django.utils import timezone
        validated_data['terms_accepted_at'] = timezone.now()
        return super().create(validated_data)


class DeliveryDriverUpdateSerializer(DocumentValidationMixin, serializers.ModelSerializer):
    """Update driver profile — PUT/PATCH /api/delivery/driver/profile/"""

    class Meta:
        model = DeliveryDriver
        fields = [
            # Personal info
            'profile_photo', 'date_of_birth', 'gender',
            'national_id_document',
            'residential_address',
            'emergency_contact_name', 'emergency_contact_phone',
            # Vehicle
            'vehicle_type', 'vehicle_brand', 'vehicle_model',
            'vehicle_registration', 'vehicle_color',
            'vehicle_photo_front', 'vehicle_photo_side', 'vehicle_photo_rear',
            'insurance_document', 'vehicle_license_expiry',
            # Verification docs
            'driver_license_document', 'license_number', 'license_expiry_date',
            # Terms — a driver may still need to accept during vetting.
            'terms_accepted',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field in ('license_expiry_date', 'vehicle_license_expiry'):
            if attrs.get(field) and attrs[field] < timezone.localdate():
                raise serializers.ValidationError({field: 'Choose a current, unexpired licence.'})
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = DeliveryDriver.objects.select_for_update().get(pk=instance.pk)
        evidence = {'national_id_document', 'driver_license_document', 'license_number',
                    'license_expiry_date', 'vehicle_registration', 'insurance_document',
                    'vehicle_license_expiry', 'vehicle_photo_front', 'terms_accepted'}
        if any(key in evidence and value != getattr(instance, key) for key, value in validated_data.items()):
            instance.identity_verification_status = 'pending'
            instance.is_available = False
        # Stamp the acceptance time the first time terms are accepted.
        if validated_data.get('terms_accepted') and not instance.terms_accepted:
            from django.utils import timezone
            instance.terms_accepted_at = timezone.now()
        return super().update(instance, validated_data)


class DeliveryFareSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    driver_email = serializers.CharField(source='driver.email', read_only=True, default=None)

    class Meta:
        model = DeliveryFare
        fields = [
            'id', 'customer', 'customer_email', 'vendor', 'vendor_email',
            'driver', 'driver_email', 'address',
            'business_category', 'distance_km',
            'base_fare', 'per_km_rate', 'fare_amount',
            'pickup_latitude', 'pickup_longitude',
            'dropoff_latitude', 'dropoff_longitude',
            'status', 'decline_reason',
            'created_at', 'updated_at', 'accepted_at', 'completed_at',
        ]
        read_only_fields = fields


class CalculateFareSerializer(serializers.Serializer):
    address_id = serializers.UUIDField()
    vendor_id = serializers.UUIDField()
    business_category = serializers.ChoiceField(choices=['retail', 'restaurant'])


class DeclineRequestSerializer(serializers.Serializer):
    decline_reason = serializers.CharField(required=False, allow_blank=True, default='')


# ── Driver shift ──────────────────────────────────────────────

class DriverShiftSerializer(serializers.ModelSerializer):
    driver_email = serializers.CharField(source='driver.user.email', read_only=True)
    vehicle_type = serializers.CharField(source='driver.vehicle_type', read_only=True)

    class Meta:
        model = DriverShift
        fields = [
            'id', 'driver', 'driver_email', 'vehicle_type',
            'started_at', 'ended_at', 'is_active',
            'start_latitude', 'start_longitude',
            'end_latitude', 'end_longitude',
        ]
        read_only_fields = ['id', 'driver', 'driver_email', 'vehicle_type', 'started_at', 'ended_at', 'is_active']


# ── Delivery job ─────────────────────────────────────────────

class DeliveryJobSerializer(serializers.ModelSerializer):
    driver_email = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryJob
        fields = [
            'id', 'fare', 'retail_order', 'restaurant_order',
            'driver', 'driver_email', 'customer', 'customer_email',
            'vendor', 'vendor_name',
            'status',
            'pickup_latitude', 'pickup_longitude',
            'dropoff_latitude', 'dropoff_longitude',
            'distance_km', 'fare_amount',
            'delivery_notes', 'proof_of_delivery_image',
            'created_at', 'updated_at',
            'accepted_at', 'driver_at_vendor_at', 'picked_up_at',
            'delivered_at', 'cancelled_at',
        ]
        read_only_fields = [
            'id', 'customer', 'vendor', 'distance_km', 'fare_amount',
            'created_at', 'updated_at',
            'accepted_at', 'driver_at_vendor_at', 'picked_up_at',
            'delivered_at', 'cancelled_at',
        ]

    def get_driver_email(self, obj):
        if obj.driver:
            return obj.driver.user.email
        return None

    def get_vendor_name(self, obj):
        return obj.vendor.trading_name or obj.vendor.name or None


# ── GPS ping ─────────────────────────────────────────────────

class DriverLocationPingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLocationPing
        fields = [
            'id', 'job', 'latitude', 'longitude',
            'accuracy_meters', 'speed_kmh', 'heading_degrees', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class GPSUpdateSerializer(serializers.Serializer):
    """
    Input payload for the driver GPS update endpoint.

    Accepts both long-form names (latitude/longitude) and short aliases
    (lat/lng or lat/lon) so Flutter and other clients don't need to rename
    their device-sensor fields.

    Precision is stored to 6 d.p. (≈ 11 cm accuracy).  We use 12 d.p.
    as the input ceiling so that device sensors that report extra digits
    (e.g. 9 d.p.) don't get rejected by a max_digits constraint.
    """
    # Primary field names
    latitude  = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)

    # Short-form aliases accepted from Flutter / mobile SDKs
    lat = serializers.DecimalField(max_digits=12, decimal_places=6, required=False, write_only=True)
    lng = serializers.DecimalField(max_digits=12, decimal_places=6, required=False, write_only=True)
    lon = serializers.DecimalField(max_digits=12, decimal_places=6, required=False, write_only=True)

    accuracy_meters  = serializers.FloatField(required=False, allow_null=True)
    speed_kmh        = serializers.FloatField(required=False, allow_null=True)
    heading_degrees  = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        # Resolve latitude: prefer explicit 'latitude', fall back to 'lat'
        lat = attrs.get('latitude') or attrs.get('lat')
        lon = attrs.get('longitude') or attrs.get('lng') or attrs.get('lon')

        if lat is None:
            raise serializers.ValidationError(
                {'latitude': 'This field is required. Send as "latitude" (or "lat").'}
            )
        if lon is None:
            raise serializers.ValidationError(
                {'longitude': 'This field is required. Send as "longitude" (or "lng"/"lon").'}
            )

        attrs['latitude']  = lat
        attrs['longitude'] = lon
        return attrs


# ── Earnings ─────────────────────────────────────────────────

class DriverEarningSerializer(serializers.ModelSerializer):
    job_status = serializers.CharField(source='job.status', read_only=True)

    class Meta:
        model = DriverEarning
        fields = [
            'id', 'driver', 'job', 'job_status', 'payout',
            'gross_amount', 'platform_commission', 'net_amount',
            'status', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class DriverPayoutSerializer(serializers.ModelSerializer):
    earnings_count = serializers.SerializerMethodField()

    class Meta:
        model = DriverPayout
        fields = [
            'id', 'driver', 'period_start', 'period_end',
            'total_gross', 'total_commission', 'total_net',
            'status', 'payment_reference', 'paid_at',
            'earnings_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_earnings_count(self, obj):
        return obj.earnings.count()


# ── Rating ───────────────────────────────────────────────────

class DriverRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverRating
        fields = [
            'id', 'job', 'customer', 'driver',
            'rating', 'comment', 'created_at',
        ]
        read_only_fields = ['id', 'customer', 'driver', 'created_at']

    def validate_job(self, job):
        if job.status != 'delivered':
            raise serializers.ValidationError('Can only rate a completed (delivered) job.')
        if hasattr(job, 'rating'):
            raise serializers.ValidationError('This job has already been rated.')
        return job

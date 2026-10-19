import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from orders.models import ShippingAddress
from .models import (
    DeliveryDriver, DeliveryFare, DeliveryJob,
    DriverEarning, DriverLocationPing, DriverPayout,
    DriverShift, FareRate,
)
logger = logging.getLogger('sanoa.delivery')

from .serializers import (
    CalculateFareSerializer,
    DeclineRequestSerializer,
    DeliveryDriverSerializer,
    DeliveryDriverCreateSerializer,
    DeliveryDriverUpdateSerializer,
    DeliveryFareSerializer,
    DeliveryJobSerializer,
    DriverEarningSerializer,
    DriverLocationPingSerializer,
    DriverPayoutSerializer,
    DriverRatingSerializer,
    DriverShiftSerializer,
    FareRateSerializer,
    GPSUpdateSerializer,
)
from .services import (
    haversine_km,
    resolve_vendor_coords,
    estimate_minutes,
    get_order_details,
    build_trip_info,
    dispatch_job_to_nearby_drivers,
    DISPATCH_RADIUS_KM,
)

User = get_user_model()

# Fallback used only when no active PlatformFee row exists for the job's
# business category. Set to zero so a misconfigured environment never
# silently overcharges a driver — admins can set a real rate in the
# Platform Fees screen.
DELIVERY_FEE_FALLBACK = Decimal('0.00')


def _delivery_commission_rate_for(job) -> Decimal:
    """Resolve the active delivery commission % for *job* and return
    it as a Decimal fraction (e.g. 3.5 % → Decimal('0.035'))."""
    try:
        from platform_admin.models import PlatformFee
        category = getattr(job.fare, 'business_category', None) \
            if getattr(job, 'fare_id', None) else None
        if category:
            row = PlatformFee.for_business_category(category)
            if row is not None:
                return (row.delivery_fee_percent or Decimal('0')) \
                    / Decimal('100')
    except Exception:
        # Never block delivery flow because of a settings lookup.
        logger.exception('delivery commission lookup failed')
    return DELIVERY_FEE_FALLBACK


# ─────────────────────────────────────────────────────────────────
# Internal broadcast helpers
# ─────────────────────────────────────────────────────────────────

def _broadcast_job_update(job, event_type, extra=None):
    """Push a job-status update to the customer tracking channel (and driver)."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        payload = {
            'type': 'job_update',
            'event_type': event_type,
            'job_id': str(job.id),
            'status': job.status,
            **(extra or {}),
        }
        # Broadcast to the shared tracking channel (customer + driver both listen here)
        async_to_sync(channel_layer.group_send)(
            f"delivery_job_{job.id}", payload
        )
    except Exception:
        pass


def _broadcast_location(job, driver, lat, lon, speed_kmh=None, heading=None):
    """
    Push a location_update to the tracking channel.
    Includes computed ETA from driver's current position to next waypoint.
    All coordinates are sent as floats so Flutter can parse them directly.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()

        vehicle = driver.vehicle_type or 'motorbike'

        # Determine next target coords based on job status
        if job.status in ('accepted', 'driver_at_vendor'):
            target_lat, target_lon = job.pickup_latitude, job.pickup_longitude
            target_label = 'pickup'
        else:
            target_lat, target_lon = job.dropoff_latitude, job.dropoff_longitude
            target_label = 'dropoff'

        remaining_km   = haversine_km(lat, lon, target_lat, target_lon)
        remaining_min  = estimate_minutes(remaining_km, vehicle)

        async_to_sync(channel_layer.group_send)(
            f"delivery_job_{job.id}",
            {
                'type':            'location_update',
                'job_id':          str(job.id),
                'latitude':        float(lat),
                'longitude':       float(lon),
                'speed_kmh':       float(speed_kmh) if speed_kmh is not None else None,
                'heading_degrees': float(heading)   if heading   is not None else None,
                'next_target':     target_label,
                'remaining_km':    float(remaining_km),
                'eta_minutes':     remaining_min,
            },
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# Fare rates (read-only, public)
# ─────────────────────────────────────────────────────────────────

class FareRateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FareRate.objects.filter(is_active=True)
    serializer_class = FareRateSerializer
    permission_classes = [IsAuthenticated]


# ─────────────────────────────────────────────────────────────────
# Calculate & create delivery fare (customer)
# ─────────────────────────────────────────────────────────────────

class CalculateFareView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'customer':
            return Response(
                {'error': 'Only customers can calculate delivery fares.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CalculateFareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            address = ShippingAddress.objects.get(id=data['address_id'], user=request.user)
        except ShippingAddress.DoesNotExist:
            return Response({'error': 'Shipping address not found.'}, status=status.HTTP_404_NOT_FOUND)

        if address.latitude is None or address.longitude is None:
            return Response({'error': 'Address does not have coordinates set.'}, status=status.HTTP_400_BAD_REQUEST)

        from business.models import VendorProfile
        try:
            vendor = VendorProfile.objects.select_related('user').get(id=data['vendor_id'])
        except VendorProfile.DoesNotExist:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

        vendor_lat, vendor_lon = resolve_vendor_coords(vendor)
        if vendor_lat is None or vendor_lon is None:
            return Response({'error': 'Vendor does not have coordinates set.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rate = FareRate.objects.get(business_category=data['business_category'], is_active=True)
        except FareRate.DoesNotExist:
            return Response({'error': 'No active fare rate for this business category.'}, status=status.HTTP_400_BAD_REQUEST)

        distance_km = haversine_km(vendor_lat, vendor_lon, address.latitude, address.longitude)
        if distance_km > rate.max_distance_km:
            return Response({
                'error': f'Distance {distance_km}km exceeds max {rate.max_distance_km}km.',
                'distance_km': str(distance_km),
                'max_distance_km': str(rate.max_distance_km),
            }, status=status.HTTP_400_BAD_REQUEST)

        fare = DeliveryFare.objects.create(
            customer=request.user,
            vendor=vendor,
            address=address,
            business_category=data['business_category'],
            distance_km=distance_km,
            base_fare=rate.base_fare,
            per_km_rate=rate.per_km_rate,
            fare_amount=rate.calculate(distance_km),
            pickup_latitude=vendor_lat,
            pickup_longitude=vendor_lon,
            dropoff_latitude=address.latitude,
            dropoff_longitude=address.longitude,
        )
        return Response(DeliveryFareSerializer(fare).data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────
# Driver profile
# ─────────────────────────────────────────────────────────────────

class DriverProfileView(APIView):
    unverified_actions = ('get', 'post', 'patch', 'put')
    """
    GET   /api/delivery/driver/profile/ — retrieve own driver profile
    POST  /api/delivery/driver/profile/ — create driver profile
    PUT   /api/delivery/driver/profile/ — full update
    PATCH /api/delivery/driver/profile/ — partial update
    Content-Type: multipart/form-data (supports file/image uploads)
    """
    permission_classes = [IsAuthenticated]

    def _require_driver(self, request):
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get(self, request):
        err = self._require_driver(request)
        if err:
            return err
        try:
            driver = DeliveryDriver.objects.get(user=request.user)
        except DeliveryDriver.DoesNotExist:
            return Response({'detail': 'Driver profile not found. Create one first.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DeliveryDriverSerializer(driver).data)

    def post(self, request):
        err = self._require_driver(request)
        if err:
            return err
        serializer = DeliveryDriverCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(DeliveryDriverSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        err = self._require_driver(request)
        if err:
            return err
        try:
            driver = DeliveryDriver.objects.get(user=request.user)
        except DeliveryDriver.DoesNotExist:
            return Response({'detail': 'Driver profile not found. Create one first.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DeliveryDriverUpdateSerializer(driver, data=request.data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DeliveryDriverSerializer(serializer.instance).data)


# ─────────────────────────────────────────────────────────────────
# Driver shift (go online / offline)
# ─────────────────────────────────────────────────────────────────

class DriverShiftViewSet(viewsets.GenericViewSet):
    serializer_class = DriverShiftSerializer
    permission_classes = [IsAuthenticated]

    def _require_driver(self, request):
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def list(self, request):
        err = self._require_driver(request)
        if err:
            return err
        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)
        qs = DriverShift.objects.filter(driver=driver).order_by('-started_at')
        return Response(DriverShiftSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='go-online')
    def go_online(self, request):
        err = self._require_driver(request)
        if err:
            return err
        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)

        # Verification gate — an unapproved driver cannot go online.
        if not driver.is_verified:
            return Response(
                {
                    'error': 'Your account is not verified yet. Complete your '
                             'documents and wait for approval before going online.',
                    'code': 'not_verified',
                    'verification_status': driver.verification_status,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Auto-close any stale active shifts (app crash, force-quit, etc.)
        DriverShift.objects.filter(driver=driver, is_active=True).update(
            is_active=False, ended_at=timezone.now()
        )

        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        shift = DriverShift.objects.create(
            driver=driver,
            start_latitude=lat,
            start_longitude=lon,
        )
        driver.is_available = True
        if lat and lon:
            driver.current_latitude = lat
            driver.current_longitude = lon
        driver.save(update_fields=['is_available', 'current_latitude', 'current_longitude', 'updated_at'])
        return Response(DriverShiftSerializer(shift).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='go-offline')
    def go_offline(self, request):
        err = self._require_driver(request)
        if err:
            return err
        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)

        active_shift = DriverShift.objects.filter(driver=driver, is_active=True).first()
        if not active_shift:
            return Response({'error': 'Not currently online.'}, status=status.HTTP_400_BAD_REQUEST)

        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        active_shift.ended_at = timezone.now()
        active_shift.is_active = False
        active_shift.end_latitude = lat
        active_shift.end_longitude = lon
        active_shift.save()

        driver.is_available = False
        driver.save(update_fields=['is_available', 'updated_at'])
        return Response(DriverShiftSerializer(active_shift).data)

    @action(detail=False, methods=['get'], url_path='current')
    def current_shift(self, request):
        err = self._require_driver(request)
        if err:
            return err
        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)
        shift = DriverShift.objects.filter(driver=driver, is_active=True).first()
        if not shift:
            return Response({'online': False, 'shift': None})
        return Response({'online': True, 'shift': DriverShiftSerializer(shift).data})


# ─────────────────────────────────────────────────────────────────
# GPS updates
# ─────────────────────────────────────────────────────────────────

class DriverLocationView(APIView):
    """
    POST /api/delivery/driver/location/
    Driver sends their current GPS coordinates.
    - Always updates DeliveryDriver.current_latitude/longitude.
    - If driver has an active job, stores a DriverLocationPing and broadcasts
      a location_update (with remaining distance + ETA) to the tracking channel.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can update location.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = GPSUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)
        driver.current_latitude  = data['latitude']
        driver.current_longitude = data['longitude']
        driver.save(update_fields=['current_latitude', 'current_longitude', 'updated_at'])

        # Store ping + broadcast if there's an active job
        active_job = DeliveryJob.objects.filter(
            driver=driver,
            status__in=['accepted', 'driver_at_vendor', 'picked_up', 'in_transit'],
        ).first()

        ping_data = None
        if active_job:
            ping = DriverLocationPing.objects.create(
                job=active_job,
                driver=driver,
                latitude=data['latitude'],
                longitude=data['longitude'],
                accuracy_meters=data.get('accuracy_meters'),
                speed_kmh=data.get('speed_kmh'),
                heading_degrees=data.get('heading_degrees'),
            )
            ping_data = DriverLocationPingSerializer(ping).data

            _broadcast_location(
                active_job, driver,
                data['latitude'], data['longitude'],
                speed_kmh=data.get('speed_kmh'),
                heading=data.get('heading_degrees'),
            )

        return Response({
            'updated': True,
            'current_latitude':  str(driver.current_latitude),
            'current_longitude': str(driver.current_longitude),
            'active_job': str(active_job.id) if active_job else None,
            'ping': ping_data,
        })


# ─────────────────────────────────────────────────────────────────
# Delivery jobs
# ─────────────────────────────────────────────────────────────────

class DeliveryJobViewSet(viewsets.GenericViewSet):
    serializer_class = DeliveryJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        qs = DeliveryJob.objects.select_related('driver__user', 'customer', 'vendor')
        if user.user_type == 'driver':
            driver, _ = DeliveryDriver.objects.get_or_create(user=user)
            return qs.filter(driver=driver)
        if user.user_type == 'customer':
            return qs.filter(customer=user)
        if user.is_staff:
            return qs
        return qs.none()

    def list(self, request):
        """
        - Drivers: see all jobs assigned to them.
        - Customers: see their own jobs.
        - Admin: all jobs.
        """
        return Response(DeliveryJobSerializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None):
        """Full details for a single job — the base fields plus the trip
        (route/distance/ETA) and the order summary (items, total, notes).

        Scoped through ``get_queryset`` so a driver can only open their own
        jobs, a customer their own, and admins any."""
        try:
            job = self.get_queryset().get(pk=pk)
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        data = DeliveryJobSerializer(job).data
        if job.driver:
            try:
                data['trip'] = build_trip_info(job.driver, job)
            except Exception:
                data['trip'] = None
        try:
            data['order'] = get_order_details(job)
        except Exception:
            data['order'] = None

        # On-demand address fallback: if a stop has no stored text address
        # (e.g. a vendor that only geocoded its coordinates), reverse-geocode
        # it here so the driver sees a readable address rather than lat/lng.
        trip = data.get('trip')
        if trip:
            from core.geocoding import reverse_geocode
            for key in ('pickup', 'dropoff'):
                stop = trip.get(key) or {}
                if not stop.get('address'):
                    addr = reverse_geocode(stop.get('latitude'), stop.get('longitude'))
                    if addr:
                        stop['address'] = addr
        return Response(data)

    # ── Available jobs (with 20 km radius filter) ──────────────────

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """
        Drivers: list pending unassigned jobs within 20 km of current location.

        Each job in the response is enriched with:
          driver_to_pickup_km     — distance from driver to vendor
          driver_to_pickup_minutes— ETA driver → vendor
          pickup_to_dropoff_km    — stored trip distance (vendor → customer)
          pickup_to_dropoff_minutes — ETA vendor → customer
          order                   — compact order summary
        """
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can see available jobs.'}, status=status.HTTP_403_FORBIDDEN)

        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)

        if not driver.current_latitude or not driver.current_longitude:
            return Response(
                {'error': 'Update your location first to see nearby jobs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vehicle = driver.vehicle_type or 'motorbike'

        # All pending unassigned jobs the driver has NOT already declined
        pending = (
            DeliveryJob.objects.filter(status='pending', driver__isnull=True)
            .exclude(declined_by=driver)
            .select_related('vendor', 'customer', 'retail_order', 'restaurant_order')
            .prefetch_related('retail_order__items', 'restaurant_order__items')
        )

        results = []
        for job in pending:
            d = haversine_km(
                driver.current_latitude, driver.current_longitude,
                job.pickup_latitude, job.pickup_longitude,
            )
            if d > DISPATCH_RADIUS_KM:
                continue

            base = DeliveryJobSerializer(job).data
            base.update({
                'driver_to_pickup_km':      str(d),
                'driver_to_pickup_minutes': estimate_minutes(d, vehicle),
                'pickup_to_dropoff_km':     str(job.distance_km),
                'pickup_to_dropoff_minutes': estimate_minutes(job.distance_km, vehicle),
                'order':                    get_order_details(job),
            })
            results.append((float(d), base))

        # Sort closest first
        results.sort(key=lambda x: x[0])
        return Response([r[1] for r in results])

    # ── Accept ────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept a pending job.

        Response includes the full serialized job plus a `trip` block:
          trip.driver_location       — driver's current GPS
          trip.pickup                — vendor coords + distance/ETA from driver
          trip.dropoff               — customer coords + distance/ETA from vendor
          trip.total_distance_km     — full round-trip distance
          trip.total_eta_minutes     — combined ETA
          trip.current_speed_kmh     — driver's last reported speed
        """
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can accept jobs.'}, status=status.HTTP_403_FORBIDDEN)

        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)

        # Verification gate — an unapproved driver cannot accept jobs.
        if not driver.is_verified:
            return Response(
                {
                    'error': 'Your account is not verified yet. Complete your '
                             'documents and wait for approval before accepting jobs.',
                    'code': 'not_verified',
                    'verification_status': driver.verification_status,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check driver is not already on an active job
        busy = DeliveryJob.objects.filter(
            driver=driver,
            status__in=['accepted', 'driver_at_vendor', 'picked_up', 'in_transit'],
        ).exists()
        if busy:
            return Response(
                {'error': 'You already have an active job in progress.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                job = DeliveryJob.objects.select_for_update().get(
                    pk=pk, status='pending', driver__isnull=True,
                )
            except DeliveryJob.DoesNotExist:
                return Response({'error': 'Job not available.'}, status=status.HTTP_404_NOT_FOUND)

            job.driver     = driver
            job.status     = 'accepted'
            job.accepted_at = timezone.now()
            job.save(update_fields=['driver', 'status', 'accepted_at', 'updated_at'])

        trip = build_trip_info(driver, job)

        _broadcast_job_update(job, 'driver_accepted', {
            'driver_name':     request.user.get_full_name() or request.user.email,
            'driver_latitude':  trip['driver_location']['latitude'],
            'driver_longitude': trip['driver_location']['longitude'],
            'eta_minutes':      trip['pickup']['eta_minutes'],
        })

        return Response({
            **DeliveryJobSerializer(job).data,
            'trip': trip,
        })

    # ── Decline ───────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """
        Decline a pending job.

        Records the decline so this driver is never re-offered the same job,
        then re-dispatches to other nearby available drivers.
        """
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can decline jobs.'}, status=status.HTTP_403_FORBIDDEN)

        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)

        try:
            job = DeliveryJob.objects.get(pk=pk)
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        if job.status != 'pending':
            return Response(
                {'error': f'Job is {job.status} — cannot decline.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DeclineRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Record the decline
        job.declined_by.add(driver)

        # Re-dispatch to other nearby drivers
        dispatch_job_to_nearby_drivers(job)

        return Response({
            'status':   'declined',
            'job_id':   str(job.id),
            'driver_id': str(driver.id),
            'reason':   serializer.validated_data.get('decline_reason', ''),
        })

    # ── Status transitions ────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='arrived-at-vendor')
    def arrived_at_vendor(self, request, pk=None):
        job = self._get_driver_job(request, pk)
        if isinstance(job, Response):
            return job
        if job.status != 'accepted':
            return Response({'error': 'Job must be accepted first.'}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'driver_at_vendor'
        job.driver_at_vendor_at = timezone.now()
        job.save(update_fields=['status', 'driver_at_vendor_at', 'updated_at'])

        driver = job.driver
        trip = build_trip_info(driver, job)
        _broadcast_job_update(job, 'driver_at_vendor', {
            'message': 'Driver has arrived at the vendor.',
            'driver_to_dropoff_km':      trip['dropoff']['distance_from_pickup_km'],
            'driver_to_dropoff_minutes': trip['dropoff']['eta_minutes'],
        })
        return Response({**DeliveryJobSerializer(job).data, 'trip': trip})

    @action(detail=True, methods=['post'], url_path='picked-up')
    def picked_up(self, request, pk=None):
        job = self._get_driver_job(request, pk)
        if isinstance(job, Response):
            return job
        if job.status not in ('accepted', 'driver_at_vendor'):
            return Response({'error': 'Cannot confirm pickup from current state.'}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'picked_up'
        job.picked_up_at = timezone.now()
        job.save(update_fields=['status', 'picked_up_at', 'updated_at'])

        driver = job.driver
        trip = build_trip_info(driver, job)
        _broadcast_job_update(job, 'picked_up', {
            'message':              'Driver has picked up your order.',
            'eta_minutes':          trip['dropoff']['eta_minutes'],
            'distance_to_drop_km':  trip['dropoff']['distance_from_pickup_km'],
        })
        return Response({**DeliveryJobSerializer(job).data, 'trip': trip})

    @action(detail=True, methods=['post'], url_path='in-transit')
    def in_transit(self, request, pk=None):
        """Mark the job as in transit (driving to customer)."""
        job = self._get_driver_job(request, pk)
        if isinstance(job, Response):
            return job
        if job.status != 'picked_up':
            return Response({'error': 'Job must be in picked_up state first.'}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'in_transit'
        job.save(update_fields=['status', 'updated_at'])

        driver = job.driver
        trip = build_trip_info(driver, job)
        _broadcast_job_update(job, 'in_transit', {
            'message':             'Order is on its way to you.',
            'eta_minutes':         trip['dropoff']['eta_minutes'],
            'distance_to_drop_km': trip['dropoff']['distance_from_pickup_km'],
            'current_speed_kmh':   trip['current_speed_kmh'],
        })
        return Response({**DeliveryJobSerializer(job).data, 'trip': trip})

    @action(detail=True, methods=['post'])
    def delivered(self, request, pk=None):
        """Confirm hand-over with the customer's 4-digit drop-off PIN.

        The driver asks the customer for their PIN at drop-off and
        submits it as ``{"pin": "1234"}``. If it doesn't match the
        job's `delivery_pin`, we reject and the parcel does NOT change
        hands — closes the "driver self-confirms delivery without
        actually handing the package over" hole.

        Returns 400 with a clear message for each failure mode so the
        driver app can surface the right copy:

          • `pin_required`    — PIN missing in the request body
          • `pin_invalid`     — wrong format (not 4 digits)
          • `pin_mismatch`    — doesn't match what the customer sees
        """
        job = self._get_driver_job(request, pk)
        if isinstance(job, Response):
            return job
        if job.status not in ('picked_up', 'in_transit'):
            return Response(
                {'error': 'Cannot confirm delivery from current state.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── PIN gate ──────────────────────────────────────────────
        raw_pin = (request.data.get('pin') or '').strip()
        if not raw_pin:
            return Response(
                {
                    'error': 'Ask the customer for their 4-digit delivery PIN before '
                             'handing over the parcel.',
                    'code': 'pin_required',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_pin) != 4 or not raw_pin.isdigit():
            return Response(
                {
                    'error': 'The PIN must be exactly 4 digits.',
                    'code': 'pin_invalid',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if raw_pin != (job.delivery_pin or ''):
            return Response(
                {
                    'error': 'That PIN doesn\'t match the customer\'s. '
                             'Ask them to read it again from their tracking screen.',
                    'code': 'pin_mismatch',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        job.status = 'delivered'
        job.delivered_at = now
        job.save(update_fields=['status', 'delivered_at', 'updated_at'])

        # Propagate 'delivered' status back to the originating order
        try:
            if job.retail_order_id:
                job.retail_order.status = 'delivered'
                job.retail_order.delivered_at = now
                job.retail_order.save(update_fields=['status', 'delivered_at', 'updated_at'])
            elif job.restaurant_order_id:
                ro = job.restaurant_order
                ro.status = 'delivered'
                ro.delivered_at = now
                ro.save(update_fields=['status', 'delivered_at', 'updated_at'])
                from restaurant.models import RestaurantOrderTrackingEvent
                RestaurantOrderTrackingEvent.objects.create(
                    order=ro,
                    event_type='delivered',
                    message='Your order has been delivered!',
                )
        except Exception:
            pass  # Never block delivery confirmation due to order update failure

        # Record earnings. The platform commission is the per-category
        # delivery fee % maintained in PlatformFee (0 – 5 %); falls
        # back to zero when no active row exists for the category, so
        # a misconfigured environment never silently overcharges a
        # driver.
        gross      = job.fare_amount
        rate       = _delivery_commission_rate_for(job)
        commission = (gross * rate).quantize(Decimal('0.01'))
        net        = gross - commission
        DriverEarning.objects.create(
            driver=job.driver,
            job=job,
            gross_amount=gross,
            platform_commission=commission,
            net_amount=net,
        )
        job.driver.total_deliveries += 1
        job.driver.save(update_fields=['total_deliveries'])

        # Release the delivery-fee escrow into the driver's wallet.
        #
        # `settle_order` is called when the customer pays — at that
        # point the driver usually isn't assigned yet, so the fee is
        # parked on the platform ledger tagged `TYPE_DELIVERY_ESCROW`.
        # This is the moment we know which driver to credit: move the
        # escrow into their wallet. Idempotent — re-running this on a
        # job that's already been settled (e.g. a status flip + re-flip)
        # no-ops.
        try:
            from payments.settlement import credit_driver_earning
            if job.retail_order_id:
                credit_driver_earning(job.retail_order, job.driver)
            elif job.restaurant_order_id:
                credit_driver_earning(
                    None, job.driver,
                    restaurant_order=job.restaurant_order,
                )
        except Exception as exc:
            # Don't block delivery confirmation if the wallet update
            # fails — admins can recompute / release escrow from the
            # marketplace screen.
            logger.warning(
                'credit_driver_earning failed for job %s: %s',
                job.pk, exc,
            )

        _broadcast_job_update(job, 'delivered', {
            'message':   'Your order has been delivered!',
            'fare':      str(gross),
        })
        return Response(DeliveryJobSerializer(job).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        try:
            job = DeliveryJob.objects.get(pk=pk)
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner  = (job.customer == user)
        is_driver = (job.driver and job.driver.user == user)
        if not (is_owner or is_driver or user.is_staff):
            return Response({'error': 'Not authorised.'}, status=status.HTTP_403_FORBIDDEN)

        if job.status in ('delivered', 'cancelled', 'failed'):
            return Response({'error': f'Cannot cancel a {job.status} job.'}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'cancelled'
        job.cancelled_at = timezone.now()
        job.save(update_fields=['status', 'cancelled_at', 'updated_at'])
        _broadcast_job_update(job, 'cancelled', {'message': 'Delivery was cancelled.'})
        return Response(DeliveryJobSerializer(job).data)

    # ── GPS ping history ──────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def pings(self, request, pk=None):
        """Customer or admin: GPS ping history for a job."""
        try:
            job = DeliveryJob.objects.get(pk=pk)
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not (job.customer == request.user or request.user.is_staff):
            return Response({'error': 'Not authorised.'}, status=status.HTTP_403_FORBIDDEN)
        pings = job.location_pings.order_by('timestamp')
        return Response(DriverLocationPingSerializer(pings, many=True).data)

    # ── Helpers ───────────────────────────────────────────────────

    def _get_driver_job(self, request, pk):
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can update job status.'}, status=status.HTTP_403_FORBIDDEN)
        driver, _ = DeliveryDriver.objects.get_or_create(user=request.user)
        try:
            return DeliveryJob.objects.select_related('driver').get(pk=pk, driver=driver)
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found or not assigned to you.'}, status=status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────
# Legacy driver request viewset (accept / decline on DeliveryFare)
# ─────────────────────────────────────────────────────────────────

class DriverRequestViewSet(viewsets.GenericViewSet):
    serializer_class = DeliveryFareSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeliveryFare.objects.all()

    def _require_driver(self, request):
        if request.user.user_type != 'driver':
            return Response({'error': 'Only drivers can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def list(self, request):
        err = self._require_driver(request)
        if err:
            return err
        qs = DeliveryFare.objects.filter(status='pending', driver__isnull=True)
        return Response(DeliveryFareSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        err = self._require_driver(request)
        if err:
            return err
        try:
            fare = DeliveryFare.objects.get(pk=pk)
        except DeliveryFare.DoesNotExist:
            return Response({'error': 'Delivery request not found.'}, status=status.HTTP_404_NOT_FOUND)
        if fare.status != 'pending':
            return Response({'error': f'Delivery request is already {fare.status}.'}, status=status.HTTP_400_BAD_REQUEST)
        fare.driver = request.user
        fare.status = 'accepted'
        fare.accepted_at = timezone.now()
        fare.save(update_fields=['driver', 'status', 'accepted_at', 'updated_at'])
        return Response(DeliveryFareSerializer(fare).data)

    @action(detail=True, methods=['post'], url_path='decline')
    def decline(self, request, pk=None):
        err = self._require_driver(request)
        if err:
            return err
        try:
            fare = DeliveryFare.objects.get(pk=pk)
        except DeliveryFare.DoesNotExist:
            return Response({'error': 'Delivery request not found.'}, status=status.HTTP_404_NOT_FOUND)
        if fare.status != 'pending':
            return Response({'error': f'Delivery request is already {fare.status}.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = DeclineRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fare.status = 'declined'
        fare.decline_reason = serializer.validated_data.get('decline_reason', '')
        fare.save(update_fields=['status', 'decline_reason', 'updated_at'])
        return Response(DeliveryFareSerializer(fare).data)


# ─────────────────────────────────────────────────────────────────
# Earnings
# ─────────────────────────────────────────────────────────────────

class DriverEarningViewSet(viewsets.GenericViewSet):
    serializer_class = DriverEarningSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def _get_driver(self, user):
        if user.user_type != 'driver':
            return None, Response({'error': 'Only drivers can access earnings.'}, status=status.HTTP_403_FORBIDDEN)
        driver, _ = DeliveryDriver.objects.get_or_create(user=user)
        return driver, None

    def list(self, request):
        driver, err = self._get_driver(request.user)
        if err:
            return err
        qs = DriverEarning.objects.filter(driver=driver).select_related('job').order_by('-created_at')
        return Response(DriverEarningSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        """Full details for a single earning — the fee breakdown plus the
        job it came from (with its order summary) so the driver can see
        exactly what they were paid for."""
        driver, err = self._get_driver(request.user)
        if err:
            return err
        try:
            earning = (DriverEarning.objects
                       .select_related('job', 'job__vendor')
                       .get(pk=pk, driver=driver))
        except DriverEarning.DoesNotExist:
            return Response({'error': 'Earning not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        data = DriverEarningSerializer(earning).data
        job = earning.job
        if job:
            job_data = DeliveryJobSerializer(job).data
            try:
                job_data['order'] = get_order_details(job)
            except Exception:
                job_data['order'] = None
            data['job'] = job_data
        return Response(data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        driver, err = self._get_driver(request.user)
        if err:
            return err
        totals = DriverEarning.objects.filter(driver=driver).aggregate(
            total_gross=Sum('gross_amount'),
            total_commission=Sum('platform_commission'),
            total_net=Sum('net_amount'),
        )
        pending = DriverEarning.objects.filter(driver=driver, status='pending').aggregate(
            pending_net=Sum('net_amount'),
        )
        return Response({
            'total_gross':       totals['total_gross']   or Decimal('0.00'),
            'total_commission':  totals['total_commission'] or Decimal('0.00'),
            'total_net':         totals['total_net']     or Decimal('0.00'),
            'pending_net':       pending['pending_net']  or Decimal('0.00'),
            'total_deliveries':  driver.total_deliveries,
        })


# ─────────────────────────────────────────────────────────────────
# Payouts
# ─────────────────────────────────────────────────────────────────

class DriverPayoutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DriverPayoutSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        if user.user_type != 'driver':
            return DriverPayout.objects.none()
        driver, _ = DeliveryDriver.objects.get_or_create(user=user)
        return DriverPayout.objects.filter(driver=driver).order_by('-period_end')


# ─────────────────────────────────────────────────────────────────
# Customer: rate a driver
# ─────────────────────────────────────────────────────────────────

class RateDriverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        if request.user.user_type != 'customer':
            return Response({'error': 'Only customers can rate drivers.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            job = DeliveryJob.objects.select_related('driver').get(
                pk=job_id, customer=request.user,
            )
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DriverRatingSerializer(data={**request.data, 'job': job.id})
        serializer.is_valid(raise_exception=True)
        rating = serializer.save(customer=request.user, driver=job.driver)
        return Response(DriverRatingSerializer(rating).data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────
# Customer: live-track a delivery job (REST fallback)
# ─────────────────────────────────────────────────────────────────

class TrackDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = (
                DeliveryJob.objects
                .select_related(
                    'driver__user', 'vendor',
                    'retail_order', 'restaurant_order',
                )
                .get(pk=job_id, customer=request.user)
            )
        except DeliveryJob.DoesNotExist:
            return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        driver_location = None
        trip_info = None
        driver_info = None
        if job.driver:
            driver_location = {
                'latitude':  str(job.driver.current_latitude  or ''),
                'longitude': str(job.driver.current_longitude or ''),
            }
            trip_info = build_trip_info(job.driver, job)
            driver_info = _public_driver_info(job.driver, request)

        last_ping = job.location_pings.order_by('-timestamp').first()
        return Response({
            'job':                     DeliveryJobSerializer(job).data,
            'driver_current_location': driver_location,
            'last_ping':               DriverLocationPingSerializer(last_ping).data if last_ping else None,
            'trip':                    trip_info,
            # Public-facing driver card for the customer tracking screen.
            'driver_info':             driver_info,
            # Item-level order summary so the customer sees what's coming.
            'order_summary':           get_order_details(job),
            # Pickup-side label data — used to draw the vendor card above
            # the pickup marker on the customer map.
            'vendor_info':             _public_vendor_info(job.vendor),
            # Dropoff-side label data — customer name shown above the
            # dropoff marker. Falls back to the order's customer name when
            # the auth user doesn't have a populated first/last name.
            'customer_info':          _public_customer_info(job, request.user),
            # 4-digit drop-off PIN — only included for the customer.
            # The driver-side `DeliveryJobSerializer` deliberately
            # leaves this off so the driver can't "shoulder-surf" it
            # from their own UI.
            'delivery_pin':           job.delivery_pin,
        })


def _public_vendor_info(vendor):
    """Compact, customer-safe view of the pickup vendor."""
    if vendor is None:
        return None
    display = vendor.trading_name or vendor.name or ''
    return {
        'name':           display,
        'average_rating': str(getattr(vendor, 'average_rating', '0.00') or '0.00'),
    }


def _public_customer_info(job, user):
    """Display name for the dropoff card."""
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    name = ' '.join(p for p in (first, last) if p).strip()
    if not name:
        order = job.retail_order or job.restaurant_order
        if order is not None:
            name = (getattr(order, 'shipping_full_name', '') or '').strip()
    if not name:
        name = (getattr(user, 'email', '') or '').split('@', 1)[0]
    return {'name': name or 'Customer'}


def _public_driver_info(driver, request):
    """Customer-safe slice of the driver's profile for the tracking sheet.

    Returns name (not email), profile photo URL, vehicle make/model/colour
    and registration, average rating and total deliveries. Excludes
    sensitive fields (IDs, licence docs, address).
    """
    user = driver.user
    first = (getattr(user, 'first_name', '') or '').strip()
    last = (getattr(user, 'last_name', '') or '').strip()
    full_name = ' '.join(p for p in (first, last) if p).strip()
    if not full_name:
        full_name = (user.email or '').split('@', 1)[0]
    photo_url = None
    if driver.profile_photo:
        try:
            url = driver.profile_photo.url
            photo_url = request.build_absolute_uri(url) if request else url
        except (ValueError, AttributeError):
            photo_url = None
    vehicle_parts = [
        driver.vehicle_color,
        driver.vehicle_brand,
        driver.vehicle_model,
    ]
    vehicle_display = ' '.join(p for p in vehicle_parts if p).strip()
    return {
        'full_name':         full_name,
        'profile_photo':     photo_url,
        'vehicle_type':      driver.vehicle_type,
        'vehicle_brand':     driver.vehicle_brand or '',
        'vehicle_model':     driver.vehicle_model or '',
        'vehicle_color':     driver.vehicle_color or '',
        'vehicle_registration': driver.vehicle_registration or '',
        'vehicle_display':   vehicle_display,
        'average_rating':    str(driver.average_rating),
        'total_deliveries':  driver.total_deliveries,
    }

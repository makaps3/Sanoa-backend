"""
Delivery service helpers.

  haversine_km(lat1, lon1, lat2, lon2)     — great-circle distance
  resolve_vendor_coords(vendor_profile)     — vendor lat/lon
  estimate_minutes(distance_km)             — ETA estimate in minutes
  get_order_details(job)                    — compact order summary for drivers
  build_trip_info(driver, job)              — full pickup→dropoff trip payload
  dispatch_job_to_nearby_drivers(job)       — WS broadcast to nearby drivers
"""
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

# Average city driving speed used for all ETA estimates.
# Overridden per vehicle type in estimate_minutes().
_DEFAULT_SPEED_KMH = 30


# ─────────────────────────────────────────────────────────────────
# Distance
# ─────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    """Great-circle distance between two (lat, lon) points in kilometres."""
    lat1, lon1, lat2, lon2 = map(
        lambda v: radians(float(v)), [lat1, lon1, lat2, lon2]
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371.0088 * c
    return Decimal(str(round(km, 2)))


def resolve_vendor_coords(vendor_profile):
    """
    Return (lat, lon) for a VendorProfile.

    Resolution order (first match wins):
      1. VendorProfile.latitude / longitude        — set during onboarding
      2. business.Address rows linked to the VP    — saved via AddressViewSet
      3. Legacy IndividualVendorProfile coords
      4. Legacy BusinessVendorProfile coords
    """
    if vendor_profile is None:
        return None, None

    # 1. VendorProfile own coords
    if vendor_profile.latitude and vendor_profile.longitude:
        return vendor_profile.latitude, vendor_profile.longitude

    # 2. Explicit Address rows (business.Address linked to this VendorProfile)
    try:
        addr = (
            vendor_profile.addresses
            .filter(latitude__isnull=False, longitude__isnull=False)
            .order_by('-is_default', '-created_at')
            .first()
        )
        if addr is not None:
            return addr.latitude, addr.longitude
    except Exception:
        pass

    # 3 & 4. Legacy profiles
    user = getattr(vendor_profile, 'user', None)
    if user is not None:
        for rel in ('business_vendor_profile', 'individual_vendor_profile'):
            legacy = getattr(user, rel, None)
            if legacy and legacy.latitude and legacy.longitude:
                return legacy.latitude, legacy.longitude

    return None, None


# ─────────────────────────────────────────────────────────────────
# ETA
# ─────────────────────────────────────────────────────────────────

def estimate_minutes(distance_km, vehicle_type: str = 'motorbike') -> int:
    """
    Estimate travel time in minutes.

    Uses conservative city-traffic speeds per vehicle type:
      bicycle  → 15 km/h
      motorbike→ 30 km/h  (default)
      car      → 25 km/h
      van/truck→ 20 km/h
    """
    speed_map = {
        'bicycle':  15,
        'motorbike': 30,
        'car':       25,
        'van':       20,
        'truck':     20,
    }
    speed = speed_map.get(vehicle_type, _DEFAULT_SPEED_KMH)
    dist  = float(distance_km) if distance_km else 0.0
    if dist <= 0:
        return 0
    return max(1, round(dist / speed * 60))


# ─────────────────────────────────────────────────────────────────
# Delivery fee calculation (reusable — called at order creation)
# ─────────────────────────────────────────────────────────────────

def compute_delivery_fare(vendor_profile, shipping_address, business_category: str) -> Decimal:
    """
    Calculate the delivery fare between a vendor and a customer shipping address
    using the same FareRate logic as POST /api/delivery/calculate-fare/.

    Returns the fare as a Decimal, or Decimal('0.00') when:
      - shipping_address is None or has no coordinates
      - vendor has no coordinates
      - no active FareRate exists for the business_category
      - distance exceeds the rate's max_distance_km

    Never raises — order creation is never blocked by a missing fare rate.
    """
    from .models import FareRate

    try:
        if shipping_address is None:
            return Decimal('0.00')

        dropoff_lat = getattr(shipping_address, 'latitude', None)
        dropoff_lon = getattr(shipping_address, 'longitude', None)
        if dropoff_lat is None or dropoff_lon is None:
            return Decimal('0.00')

        pickup_lat, pickup_lon = resolve_vendor_coords(vendor_profile)
        if pickup_lat is None or pickup_lon is None:
            return Decimal('0.00')

        try:
            rate = FareRate.objects.get(business_category=business_category, is_active=True)
        except FareRate.DoesNotExist:
            return Decimal('0.00')

        distance_km = haversine_km(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
        if distance_km > rate.max_distance_km:
            return Decimal('0.00')

        return rate.calculate(distance_km)

    except Exception:
        return Decimal('0.00')


# ─────────────────────────────────────────────────────────────────
# Order summary for driver job card
# ─────────────────────────────────────────────────────────────────

def get_order_details(job) -> dict:
    """
    Return a compact order summary that a driver can see when reviewing a job
    offer before accepting — and once accepted, the same payload powers the
    minimised "items en route" bottom sheet on the driver map.

    Includes:
      * ``items``      — first 8 line items (name, qty, variant, instructions)
      * ``items_extra``— how many lines were truncated (cap is 8)
      * ``item_count`` — full line count for the summary chip
      * customer + total + delivery notes
    """
    details = {
        'order_number':  None,
        'order_type':    None,   # 'retail' | 'restaurant'
        'item_count':    0,
        'items':         [],
        'items_extra':   0,
        'order_total':   None,
        'customer_name': None,
        'delivery_notes': job.delivery_notes or '',
    }

    if job.customer:
        name = f"{job.customer.first_name} {job.customer.last_name}".strip()
        details['customer_name'] = name or job.customer.email

    order = job.retail_order or job.restaurant_order
    if not order:
        return details

    details['order_number'] = getattr(order, 'order_number', str(order.id))
    details['order_type']   = 'retail' if job.retail_order else 'restaurant'
    details['order_total']  = str(getattr(order, 'total_amount', '') or '')

    if not hasattr(order, 'items'):
        return details

    total_lines = order.items.count()
    details['item_count'] = total_lines

    # Both restaurant and retail OrderItem rows expose the same shape:
    # product_name, variant_name, quantity, special_instructions.
    line_iter = order.items.all()[:8]
    items = []
    for it in line_iter:
        items.append({
            'name': getattr(it, 'product_name', '') or '',
            'variant': getattr(it, 'variant_name', '') or '',
            'quantity': getattr(it, 'quantity', 1) or 1,
            'special_instructions':
                getattr(it, 'special_instructions', '') or '',
        })
    details['items'] = items
    details['items_extra'] = max(0, total_lines - len(items))

    return details


# ─────────────────────────────────────────────────────────────────
# Full trip info payload
# ─────────────────────────────────────────────────────────────────

def _join_address(*parts) -> str | None:
    """Join non-empty address parts into a single readable line."""
    clean = [str(p).strip() for p in parts if p and str(p).strip()]
    return ', '.join(clean) or None


def vendor_pickup_address(vendor) -> str | None:
    """Full readable pickup address from the vendor profile."""
    if vendor is None:
        return None
    return _join_address(
        getattr(vendor, 'street_address', ''),
        getattr(vendor, 'city', ''),
        getattr(vendor, 'province', ''),
        getattr(vendor, 'postal_code', ''),
    )


def order_dropoff_address(job) -> str | None:
    """Full readable drop-off address from the order's shipping snapshot
    (both retail and restaurant orders carry the same field names)."""
    order = job.retail_order or job.restaurant_order
    if order is None:
        return None
    return _join_address(
        getattr(order, 'shipping_street_address', ''),
        getattr(order, 'shipping_apartment_number', ''),
        getattr(order, 'shipping_city', ''),
        getattr(order, 'shipping_state_province', ''),
        getattr(order, 'shipping_postal_code', ''),
    )


def build_trip_info(driver, job) -> dict:
    """
    Build the complete trip payload returned to a driver after accepting a job.

    Contains:
      driver_location  — driver's current GPS
      pickup           — vendor location + address + distance / ETA from driver
      dropoff          — customer location + address + distance / ETA from vendor
      totals           — combined distance & ETA for the full round trip
      current_speed_kmh — latest reported speed (from most-recent ping)
    """
    from .models import DriverLocationPing

    vehicle = getattr(driver, 'vehicle_type', 'motorbike') or 'motorbike'

    # ── Driver → pickup ───────────────────────────────────────────
    driver_to_pickup_km = Decimal('0.00')
    if (driver.current_latitude and driver.current_longitude
            and job.pickup_latitude and job.pickup_longitude):
        driver_to_pickup_km = haversine_km(
            driver.current_latitude, driver.current_longitude,
            job.pickup_latitude, job.pickup_longitude,
        )
    driver_to_pickup_min = estimate_minutes(driver_to_pickup_km, vehicle)

    # ── Pickup → dropoff ──────────────────────────────────────────
    pickup_to_dropoff_km  = job.distance_km or Decimal('0.00')
    pickup_to_dropoff_min = estimate_minutes(pickup_to_dropoff_km, vehicle)

    # ── Latest reported speed ─────────────────────────────────────
    last_ping = (
        DriverLocationPing.objects.filter(driver=driver)
        .order_by('-timestamp')
        .values('speed_kmh')
        .first()
    )
    current_speed = last_ping['speed_kmh'] if last_ping else None

    def _f(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return {
        'driver_location': {
            'latitude':  _f(driver.current_latitude),
            'longitude': _f(driver.current_longitude),
        },
        'pickup': {
            'latitude':                _f(job.pickup_latitude),
            'longitude':               _f(job.pickup_longitude),
            'address':                 vendor_pickup_address(job.vendor),
            'name':                    (job.vendor.trading_name or job.vendor.name) if job.vendor else None,
            'distance_from_driver_km': str(driver_to_pickup_km),
            'eta_minutes':             driver_to_pickup_min,
        },
        'dropoff': {
            'latitude':                _f(job.dropoff_latitude),
            'longitude':               _f(job.dropoff_longitude),
            'address':                 order_dropoff_address(job),
            'distance_from_pickup_km': str(pickup_to_dropoff_km),
            'eta_minutes':             pickup_to_dropoff_min,
        },
        'total_distance_km':  str(driver_to_pickup_km + pickup_to_dropoff_km),
        'total_eta_minutes':  driver_to_pickup_min + pickup_to_dropoff_min,
        'current_speed_kmh':  _f(current_speed),
    }


# ─────────────────────────────────────────────────────────────────
# Auto-create DeliveryJob when vendor confirms a delivery order
# ─────────────────────────────────────────────────────────────────

def create_delivery_job_for_order(order, business_category: str):
    """
    Create a DeliveryJob for a confirmed delivery order.

    Called from both retail and restaurant update_status views when the
    vendor sets status → 'confirmed' and fulfillment_type == 'delivery'.

    The post_save signal on DeliveryJob fires automatically after creation
    and calls dispatch_job_to_nearby_drivers(), so no separate dispatch
    call is needed here.

    Idempotent — returns None if a job already exists. Never raises.
    """
    import logging
    logger = logging.getLogger('sanoa.delivery')

    from .models import DeliveryJob

    try:
        # Idempotency guard
        if business_category == 'retail':
            if DeliveryJob.objects.filter(retail_order=order).exists():
                return None
        else:
            if DeliveryJob.objects.filter(restaurant_order=order).exists():
                return None

        # Resolve vendor.
        # Retail Order has no vendor FK — vendor lives on OrderItem.
        # RestaurantOrder has a direct vendor FK.
        if business_category == 'retail':
            first_item = order.items.select_related('vendor').first()
            if first_item is None:
                logger.warning('DeliveryJob skipped: order %s has no items', order)
                return None
            vendor = first_item.vendor
        else:
            vendor = getattr(order, 'vendor', None)

        if vendor is None:
            logger.warning('DeliveryJob skipped: could not resolve vendor for order %s', order)
            return None

        # Customer dropoff coords from the shipping address
        shipping_address = getattr(order, 'shipping_address', None)
        if shipping_address is None:
            logger.warning('DeliveryJob skipped: no shipping_address on order %s', order)
            return None
        dropoff_lat = getattr(shipping_address, 'latitude', None)
        dropoff_lon = getattr(shipping_address, 'longitude', None)
        if dropoff_lat is None or dropoff_lon is None:
            logger.warning(
                'DeliveryJob skipped: shipping_address %s has no coordinates (order %s)',
                getattr(shipping_address, 'id', '?'), order,
            )
            return None

        # Vendor pickup coords
        pickup_lat, pickup_lon = resolve_vendor_coords(vendor)
        if pickup_lat is None or pickup_lon is None:
            logger.warning(
                'DeliveryJob skipped: vendor %s has no coordinates (order %s)',
                vendor.id, order,
            )
            return None

        distance_km = haversine_km(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)

        if business_category == 'retail':
            fare_amount = getattr(order, 'shipping_cost', Decimal('0.00')) or Decimal('0.00')
        else:
            fare_amount = getattr(order, 'delivery_fee', Decimal('0.00')) or Decimal('0.00')

        kwargs = {
            'customer': order.user,
            'vendor': vendor,
            'status': 'pending',
            'pickup_latitude': pickup_lat,
            'pickup_longitude': pickup_lon,
            'dropoff_latitude': dropoff_lat,
            'dropoff_longitude': dropoff_lon,
            'distance_km': distance_km,
            'fare_amount': fare_amount,
            'delivery_notes': getattr(order, 'order_notes', '') or '',
        }
        if business_category == 'retail':
            kwargs['retail_order'] = order
        else:
            kwargs['restaurant_order'] = order

        job = DeliveryJob.objects.create(**kwargs)
        logger.info(
            'DeliveryJob %s created for %s order %s (%.2f km, fare R%s)',
            job.id, business_category, order, distance_km, fare_amount,
        )
        return job

    except Exception as exc:
        logger.exception('DeliveryJob creation failed for order %s: %s', order, exc)
        return None


# ─────────────────────────────────────────────────────────────────
# Job dispatch — push new job to all nearby online drivers
# ─────────────────────────────────────────────────────────────────

DISPATCH_RADIUS_KM = 20   # maximum radius for job offers


def dispatch_job_to_nearby_drivers(job, radius_km: float = DISPATCH_RADIUS_KM) -> int:
    """
    Push a `new_job` WebSocket event to every available driver within
    `radius_km` of the pickup location who has not already declined this job.

    Returns the number of drivers notified.
    Called synchronously from views / signals; handles channel_layer internally.
    """
    from .models import DeliveryDriver

    if not (job.pickup_latitude and job.pickup_longitude):
        return 0

    # Drivers who already declined — exclude them
    declined_ids = set(job.declined_by.values_list('id', flat=True))

    candidates = DeliveryDriver.objects.filter(
        is_available=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False,
    ).exclude(id__in=declined_ids).select_related('user')

    order_details = get_order_details(job)

    notified = 0
    nearby_payload_cache: dict[int, dict] = {}

    for driver in candidates:
        d = haversine_km(
            driver.current_latitude, driver.current_longitude,
            job.pickup_latitude, job.pickup_longitude,
        )
        if d > radius_km:
            continue

        vehicle = driver.vehicle_type or 'motorbike'
        nearby_payload_cache[driver.id] = {
            'type':                      'new_job',
            'job_id':                    str(job.id),
            'status':                    job.status,
            'fare_amount':               str(job.fare_amount),
            # Vendor (pickup)
            'pickup_latitude':           str(job.pickup_latitude),
            'pickup_longitude':          str(job.pickup_longitude),
            # Customer (dropoff)
            'dropoff_latitude':          str(job.dropoff_latitude),
            'dropoff_longitude':         str(job.dropoff_longitude),
            # Segment: pickup → dropoff
            'pickup_to_dropoff_km':      str(job.distance_km),
            'pickup_to_dropoff_minutes': estimate_minutes(job.distance_km, vehicle),
            # Segment: driver → pickup
            'driver_to_pickup_km':       str(d),
            'driver_to_pickup_minutes':  estimate_minutes(d, vehicle),
            # Order summary
            'order':                     order_details,
        }
        notified += 1

    if not notified:
        return 0

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return 0

        for driver_id, payload in nearby_payload_cache.items():
            async_to_sync(channel_layer.group_send)(
                f"driver_jobs_{driver_id}", payload
            )
    except Exception:
        pass

    return notified

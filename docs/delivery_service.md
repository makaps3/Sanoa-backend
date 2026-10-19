# Delivery Service — Flutter / Dart

Base URL: `/api/delivery/`
WebSocket base: `wss://api.sanoa.co.za/`

All REST endpoints require `Authorization: Bearer <token>`.
`user_type` restrictions are enforced per endpoint.

---

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [WebSocket Channels](#websocket-channels)
3. [Dart Models](#dart-models)
4. [Dart Service](#dart-service)
5. [Error Responses](#error-responses)
6. [Delivery Lifecycle Flow](#delivery-lifecycle-flow)

---

## Endpoint Reference

### Fare Rates

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/fare-rates/` | Any | List all active fare rates |
| `GET` | `/api/delivery/fare-rates/{id}/` | Any | Single fare rate |

### Calculate & Quote Fare

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `POST` | `/api/delivery/calculate-fare/` | `customer` | Calculate delivery cost + create quote |

### Driver Profile

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/driver/profile/` | `driver` | Get own driver profile |
| `POST` | `/api/delivery/driver/profile/` | `driver` | Create driver profile |
| `PUT` | `/api/delivery/driver/profile/` | `driver` | Full update |
| `PATCH` | `/api/delivery/driver/profile/` | `driver` | Partial update |

> See **`driver_profile_service.md`** for full field reference and multipart upload details.

### Driver Shift (Online / Offline)

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/driver/shifts/` | `driver` | Shift history |
| `POST` | `/api/delivery/driver/shifts/go-online/` | `driver` | Go online (start shift) |
| `POST` | `/api/delivery/driver/shifts/go-offline/` | `driver` | Go offline (end shift) |
| `GET` | `/api/delivery/driver/shifts/current/` | `driver` | Current active shift |

### GPS Location Update

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `POST` | `/api/delivery/driver/location/` | `driver` | Push current GPS position |

### Delivery Jobs

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/jobs/` | driver / customer / admin | List jobs for caller |
| `GET` | `/api/delivery/jobs/available/` | `driver` | Pending jobs within 20 km |
| `POST` | `/api/delivery/jobs/{id}/accept/` | `driver` | Accept a pending job |
| `POST` | `/api/delivery/jobs/{id}/decline/` | `driver` | Decline a job |
| `POST` | `/api/delivery/jobs/{id}/arrived-at-vendor/` | `driver` | Mark arrived at pickup |
| `POST` | `/api/delivery/jobs/{id}/picked-up/` | `driver` | Mark order collected |
| `POST` | `/api/delivery/jobs/{id}/in-transit/` | `driver` | Mark in transit to customer |
| `POST` | `/api/delivery/jobs/{id}/delivered/` | `driver` | Mark delivered |
| `POST` | `/api/delivery/jobs/{id}/cancel/` | customer / driver / admin | Cancel job |
| `GET` | `/api/delivery/jobs/{id}/pings/` | customer / admin | GPS ping history |

### Customer — Track & Rate

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/track/{job_id}/` | `customer` | Live tracking snapshot (REST fallback) |
| `POST` | `/api/delivery/track/{job_id}/rate/` | `customer` | Rate the driver after delivery |

### Earnings & Payouts

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/driver/earnings/` | `driver` | All earning records |
| `GET` | `/api/delivery/driver/earnings/summary/` | `driver` | Aggregate totals |
| `GET` | `/api/delivery/driver/payouts/` | `driver` | Payout batch history |
| `GET` | `/api/delivery/driver/payouts/{id}/` | `driver` | Single payout detail |

### Driver Analytics

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/delivery/driver/analytics/overview/` | `driver` | Totals, avg rating, deliveries |
| `GET` | `/api/delivery/driver/analytics/earnings/` | `driver` | Earnings over time |
| `GET` | `/api/delivery/driver/analytics/performance/` | `driver` | Speed, distance, completion rate |

---

## Request Body Reference

### `POST /api/delivery/calculate-fare/`

```json
{
  "vendor_id": 12,
  "address_id": 7,
  "business_category": "retail"
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `vendor_id` | Integer | ✅ | VendorProfile ID |
| `address_id` | Integer | ✅ | Customer's ShippingAddress ID |
| `business_category` | String | ✅ | `retail` \| `restaurant` |

---

### `POST /api/delivery/driver/shifts/go-online/`

```json
{
  "latitude": -26.2041,
  "longitude": 28.0473
}
```

Both fields are optional but recommended to seed the driver's initial position.

---

### `POST /api/delivery/driver/location/`

```json
{
  "latitude": -26.2041,
  "longitude": 28.0473,
  "accuracy_meters": 5.0,
  "speed_kmh": 28.5,
  "heading_degrees": 142.0
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `latitude` | Decimal | ✅ | WGS-84 |
| `longitude` | Decimal | ✅ | WGS-84 |
| `accuracy_meters` | Float | — | GPS accuracy |
| `speed_kmh` | Float | — | From device sensor |
| `heading_degrees` | Float | — | 0–360, north = 0 |

---

### `POST /api/delivery/jobs/{id}/decline/`

```json
{
  "decline_reason": "Too far from current location"
}
```

`decline_reason` is optional.

---

### `POST /api/delivery/track/{job_id}/rate/`

```json
{
  "rating": 5,
  "comment": "Fast and professional"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `rating` | Integer | ✅ | 1–5 |
| `comment` | String | — | Optional feedback |

---

## Response Examples

### `GET /api/delivery/jobs/available/` — Driver

Returns jobs sorted by distance (closest first).

```json
[
  {
    "id": "a1b2c3d4-...",
    "status": "pending",
    "fare_amount": "45.00",
    "pickup_latitude": "-26.2041",
    "pickup_longitude": "28.0473",
    "dropoff_latitude": "-26.1900",
    "dropoff_longitude": "28.0310",
    "distance_km": "3.20",
    "delivery_notes": "Leave at the gate",
    "created_at": "2026-05-26T08:00:00Z",
    "driver_to_pickup_km": "1.45",
    "driver_to_pickup_minutes": 3,
    "pickup_to_dropoff_km": "3.20",
    "pickup_to_dropoff_minutes": 6,
    "order": {
      "order_number": "ORD-001",
      "order_type": "retail",
      "item_count": 3,
      "order_total": "320.00",
      "customer_name": "Thandi Mokoena",
      "delivery_notes": "Leave at the gate"
    }
  }
]
```

---

### `POST /api/delivery/jobs/{id}/accept/` — Driver

```json
{
  "id": "a1b2c3d4-...",
  "status": "accepted",
  "fare_amount": "45.00",
  "pickup_latitude": "-26.2041",
  "pickup_longitude": "28.0473",
  "dropoff_latitude": "-26.1900",
  "dropoff_longitude": "28.0310",
  "accepted_at": "2026-05-26T08:05:00Z",
  "trip": {
    "driver_location": {
      "latitude": "-26.2150",
      "longitude": "28.0400"
    },
    "pickup": {
      "latitude": "-26.2041",
      "longitude": "28.0473",
      "distance_from_driver_km": "1.45",
      "eta_minutes": 3
    },
    "dropoff": {
      "latitude": "-26.1900",
      "longitude": "28.0310",
      "distance_from_pickup_km": "3.20",
      "eta_minutes": 6
    },
    "total_distance_km": "4.65",
    "total_eta_minutes": 9,
    "current_speed_kmh": 28.5
  }
}
```

The `trip` block is returned by `accept`, `arrived-at-vendor`, `picked-up`, and `in-transit`.

---

### `POST /api/delivery/driver/location/` — GPS update response

```json
{
  "updated": true,
  "current_latitude": "-26.2041",
  "current_longitude": "28.0473",
  "active_job": "a1b2c3d4-...",
  "ping": {
    "id": 99,
    "job": "a1b2c3d4-...",
    "latitude": "-26.2041",
    "longitude": "28.0473",
    "accuracy_meters": 5.0,
    "speed_kmh": 28.5,
    "heading_degrees": 142.0,
    "timestamp": "2026-05-26T08:10:00Z"
  }
}
```

---

### `GET /api/delivery/driver/earnings/summary/`

```json
{
  "total_gross": "1540.00",
  "total_commission": "308.00",
  "total_net": "1232.00",
  "pending_net": "45.00",
  "total_deliveries": 34
}
```

---

### `GET /api/delivery/track/{job_id}/` — Customer REST fallback

```json
{
  "job": { "...full job object..." },
  "driver_current_location": {
    "latitude": "-26.2041",
    "longitude": "28.0473"
  },
  "last_ping": {
    "id": 99,
    "latitude": "-26.2041",
    "longitude": "28.0473",
    "speed_kmh": 28.5,
    "heading_degrees": 142.0,
    "timestamp": "2026-05-26T08:10:00Z"
  },
  "trip": {
    "driver_location": { "latitude": "-26.2041", "longitude": "28.0473" },
    "pickup": { "latitude": "-26.2041", "longitude": "28.0473", "distance_from_driver_km": "0.00", "eta_minutes": 0 },
    "dropoff": { "latitude": "-26.1900", "longitude": "28.0310", "distance_from_pickup_km": "3.20", "eta_minutes": 6 },
    "total_distance_km": "3.20",
    "total_eta_minutes": 6,
    "current_speed_kmh": 28.5
  }
}
```

---

## WebSocket Channels

### Channel 1 — Driver job offers

```
wss://api.sanoa.co.za/ws/delivery/driver/jobs/
```

- **Who connects:** `driver` users
- **Auth:** JWT via query param or cookie
- **Group:** `driver_jobs_{driver_id}`
- **Read-only:** server → client only

#### On Connect — `pending_jobs` snapshot

Immediately after connect, the server sends queued pending jobs within 20 km:

```json
{
  "type": "pending_jobs",
  "jobs": [
    {
      "job_id": "a1b2c3d4-...",
      "status": "pending",
      "fare_amount": "45.00",
      "pickup_latitude": "-26.2041",
      "pickup_longitude": "28.0473",
      "dropoff_latitude": "-26.1900",
      "dropoff_longitude": "28.0310",
      "pickup_to_dropoff_km": "3.20",
      "pickup_to_dropoff_minutes": 6,
      "driver_to_pickup_km": "1.45",
      "driver_to_pickup_minutes": 3,
      "order": {
        "order_number": "ORD-001",
        "order_type": "retail",
        "item_count": 3,
        "order_total": "320.00",
        "customer_name": "Thandi Mokoena",
        "delivery_notes": ""
      }
    }
  ]
}
```

#### Event — `new_job`

Pushed when a new job is dispatched to nearby available drivers:

```json
{
  "type": "new_job",
  "job_id": "a1b2c3d4-...",
  "status": "pending",
  "fare_amount": "45.00",
  "pickup_latitude": "-26.2041",
  "pickup_longitude": "28.0473",
  "dropoff_latitude": "-26.1900",
  "dropoff_longitude": "28.0310",
  "pickup_to_dropoff_km": "3.20",
  "pickup_to_dropoff_minutes": 6,
  "driver_to_pickup_km": "1.45",
  "driver_to_pickup_minutes": 3,
  "order": {
    "order_number": "ORD-001",
    "order_type": "retail",
    "item_count": 3,
    "order_total": "320.00",
    "customer_name": "Thandi Mokoena",
    "delivery_notes": ""
  }
}
```

---

### Channel 2 — Customer / Driver live tracking

```
wss://api.sanoa.co.za/ws/delivery/track/{job_id}/
```

- **Who connects:** customer who owns the job, assigned driver, or admin
- **Auth:** JWT via query param or cookie
- **Group:** `delivery_job_{job_id}`
- **Read-only:** server → client only

#### On Connect — `snapshot`

```json
{
  "type": "snapshot",
  "job_id": "a1b2c3d4-...",
  "status": "in_transit",
  "driver_latitude": "-26.2041",
  "driver_longitude": "28.0473",
  "pickup_latitude": "-26.2041",
  "pickup_longitude": "28.0473",
  "dropoff_latitude": "-26.1900",
  "dropoff_longitude": "28.0310",
  "trip": {
    "driver_location": { "latitude": "-26.2041", "longitude": "28.0473" },
    "pickup": { "latitude": "-26.2041", "longitude": "28.0473", "distance_from_driver_km": "0.00", "eta_minutes": 0 },
    "dropoff": { "latitude": "-26.1900", "longitude": "28.0310", "distance_from_pickup_km": "3.20", "eta_minutes": 6 },
    "total_distance_km": "3.20",
    "total_eta_minutes": 6,
    "current_speed_kmh": 28.5
  }
}
```

#### Event — `location_update`

Fired each time the driver calls `POST /api/delivery/driver/location/`:

```json
{
  "type": "location_update",
  "job_id": "a1b2c3d4-...",
  "latitude": "-26.2000",
  "longitude": "28.0390",
  "speed_kmh": 30.2,
  "heading_degrees": 142.0,
  "next_target": "dropoff",
  "remaining_km": "1.85",
  "eta_minutes": 4
}
```

`next_target` is `"pickup"` when the driver is heading to the vendor, `"dropoff"` once the order is collected.

#### Event — `job_update`

Fired on status changes:

```json
{
  "type": "job_update",
  "event_type": "driver_accepted",
  "job_id": "a1b2c3d4-...",
  "status": "accepted",
  "driver_name": "Sipho Nkosi",
  "driver_latitude": "-26.2150",
  "driver_longitude": "28.0400",
  "eta_minutes": 3
}
```

| `event_type` | Triggered by |
|--------------|-------------|
| `driver_accepted` | Driver accepts job |
| `driver_at_vendor` | Driver marks arrived at vendor |
| `picked_up` | Driver marks order collected |
| `in_transit` | Driver marks in transit |
| `delivered` | Driver marks delivered |
| `cancelled` | Customer, driver, or admin cancels |

---

## Dart Models

```dart
// ─────────────────────────────────────────────
// Shared sub-models
// ─────────────────────────────────────────────

class DeliveryCoords {
  final double? latitude;
  final double? longitude;

  const DeliveryCoords({this.latitude, this.longitude});

  factory DeliveryCoords.fromJson(Map<String, dynamic> json) => DeliveryCoords(
        latitude:  json['latitude']  != null ? double.tryParse(json['latitude'].toString())  : null,
        longitude: json['longitude'] != null ? double.tryParse(json['longitude'].toString()) : null,
      );
}

class TripSegment {
  final double? latitude;
  final double? longitude;
  final double? distanceKm;
  final int? etaMinutes;

  const TripSegment({
    this.latitude,
    this.longitude,
    this.distanceKm,
    this.etaMinutes,
  });

  factory TripSegment.fromJson(Map<String, dynamic> json) => TripSegment(
        latitude:    double.tryParse((json['latitude'] ?? '').toString()),
        longitude:   double.tryParse((json['longitude'] ?? '').toString()),
        distanceKm:  double.tryParse(
          (json['distance_from_driver_km'] ?? json['distance_from_pickup_km'] ?? '0').toString(),
        ),
        etaMinutes:  json['eta_minutes'] as int?,
      );
}

class TripInfo {
  final DeliveryCoords driverLocation;
  final TripSegment pickup;
  final TripSegment dropoff;
  final double totalDistanceKm;
  final int totalEtaMinutes;
  final double? currentSpeedKmh;

  const TripInfo({
    required this.driverLocation,
    required this.pickup,
    required this.dropoff,
    required this.totalDistanceKm,
    required this.totalEtaMinutes,
    this.currentSpeedKmh,
  });

  factory TripInfo.fromJson(Map<String, dynamic> json) => TripInfo(
        driverLocation: DeliveryCoords.fromJson(
          json['driver_location'] as Map<String, dynamic>? ?? {},
        ),
        pickup:  TripSegment.fromJson(json['pickup']  as Map<String, dynamic>? ?? {}),
        dropoff: TripSegment.fromJson(json['dropoff'] as Map<String, dynamic>? ?? {}),
        totalDistanceKm: double.tryParse(json['total_distance_km'].toString()) ?? 0.0,
        totalEtaMinutes: json['total_eta_minutes'] as int? ?? 0,
        currentSpeedKmh: json['current_speed_kmh'] != null
            ? (json['current_speed_kmh'] as num).toDouble()
            : null,
      );
}

class OrderSummary {
  final String? orderNumber;
  final String? orderType;   // 'retail' | 'restaurant'
  final int itemCount;
  final String? orderTotal;
  final String? customerName;
  final String deliveryNotes;

  const OrderSummary({
    this.orderNumber,
    this.orderType,
    this.itemCount = 0,
    this.orderTotal,
    this.customerName,
    this.deliveryNotes = '',
  });

  factory OrderSummary.fromJson(Map<String, dynamic> json) => OrderSummary(
        orderNumber:   json['order_number'] as String?,
        orderType:     json['order_type']   as String?,
        itemCount:     json['item_count']   as int? ?? 0,
        orderTotal:    json['order_total']  as String?,
        customerName:  json['customer_name'] as String?,
        deliveryNotes: json['delivery_notes'] as String? ?? '',
      );
}

// ─────────────────────────────────────────────
// FareRate
// ─────────────────────────────────────────────

class FareRate {
  final int id;
  final String businessCategory;
  final double baseFare;
  final double perKmRate;
  final double maxDistanceKm;
  final bool isActive;
  final String createdAt;
  final String updatedAt;

  const FareRate({
    required this.id,
    required this.businessCategory,
    required this.baseFare,
    required this.perKmRate,
    required this.maxDistanceKm,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory FareRate.fromJson(Map<String, dynamic> json) => FareRate(
        id:               json['id'] as int,
        businessCategory: json['business_category'] as String,
        baseFare:         double.tryParse(json['base_fare'].toString()) ?? 0,
        perKmRate:        double.tryParse(json['per_km_rate'].toString()) ?? 0,
        maxDistanceKm:    double.tryParse(json['max_distance_km'].toString()) ?? 0,
        isActive:         json['is_active'] as bool? ?? true,
        createdAt:        json['created_at'] as String,
        updatedAt:        json['updated_at'] as String,
      );
}

// ─────────────────────────────────────────────
// DeliveryFare (quote)
// ─────────────────────────────────────────────

class DeliveryFare {
  final String id;
  final String businessCategory;
  final double distanceKm;
  final double baseFare;
  final double perKmRate;
  final double fareAmount;
  final double pickupLatitude;
  final double pickupLongitude;
  final double dropoffLatitude;
  final double dropoffLongitude;
  final String status;   // pending | accepted | declined | completed | cancelled
  final String createdAt;

  const DeliveryFare({
    required this.id,
    required this.businessCategory,
    required this.distanceKm,
    required this.baseFare,
    required this.perKmRate,
    required this.fareAmount,
    required this.pickupLatitude,
    required this.pickupLongitude,
    required this.dropoffLatitude,
    required this.dropoffLongitude,
    required this.status,
    required this.createdAt,
  });

  factory DeliveryFare.fromJson(Map<String, dynamic> json) => DeliveryFare(
        id:               json['id'].toString(),
        businessCategory: json['business_category'] as String,
        distanceKm:       double.tryParse(json['distance_km'].toString()) ?? 0,
        baseFare:         double.tryParse(json['base_fare'].toString()) ?? 0,
        perKmRate:        double.tryParse(json['per_km_rate'].toString()) ?? 0,
        fareAmount:       double.tryParse(json['fare_amount'].toString()) ?? 0,
        pickupLatitude:   double.tryParse(json['pickup_latitude'].toString()) ?? 0,
        pickupLongitude:  double.tryParse(json['pickup_longitude'].toString()) ?? 0,
        dropoffLatitude:  double.tryParse(json['dropoff_latitude'].toString()) ?? 0,
        dropoffLongitude: double.tryParse(json['dropoff_longitude'].toString()) ?? 0,
        status:           json['status'] as String? ?? 'pending',
        createdAt:        json['created_at'] as String,
      );
}

// ─────────────────────────────────────────────
// DriverShift
// ─────────────────────────────────────────────

class DriverShift {
  final int id;
  final bool isActive;
  final String startedAt;
  final String? endedAt;
  final double? startLatitude;
  final double? startLongitude;
  final double? endLatitude;
  final double? endLongitude;

  const DriverShift({
    required this.id,
    required this.isActive,
    required this.startedAt,
    this.endedAt,
    this.startLatitude,
    this.startLongitude,
    this.endLatitude,
    this.endLongitude,
  });

  factory DriverShift.fromJson(Map<String, dynamic> json) => DriverShift(
        id:             json['id'] as int,
        isActive:       json['is_active'] as bool? ?? false,
        startedAt:      json['started_at'] as String,
        endedAt:        json['ended_at'] as String?,
        startLatitude:  json['start_latitude'] != null
            ? double.tryParse(json['start_latitude'].toString())
            : null,
        startLongitude: json['start_longitude'] != null
            ? double.tryParse(json['start_longitude'].toString())
            : null,
        endLatitude:    json['end_latitude'] != null
            ? double.tryParse(json['end_latitude'].toString())
            : null,
        endLongitude:   json['end_longitude'] != null
            ? double.tryParse(json['end_longitude'].toString())
            : null,
      );
}

// ─────────────────────────────────────────────
// DeliveryJob
// ─────────────────────────────────────────────

enum DeliveryJobStatus {
  pending,
  accepted,
  driverAtVendor,
  pickedUp,
  inTransit,
  delivered,
  cancelled,
  failed;

  static DeliveryJobStatus fromString(String s) => switch (s) {
        'pending'         => pending,
        'accepted'        => accepted,
        'driver_at_vendor'=> driverAtVendor,
        'picked_up'       => pickedUp,
        'in_transit'      => inTransit,
        'delivered'       => delivered,
        'cancelled'       => cancelled,
        _                 => failed,
      };

  String get label => switch (this) {
        pending         => 'Pending',
        accepted        => 'Driver on the way',
        driverAtVendor  => 'Driver at vendor',
        pickedUp        => 'Order collected',
        inTransit       => 'On the way to you',
        delivered       => 'Delivered',
        cancelled       => 'Cancelled',
        failed          => 'Failed',
      };
}

class DeliveryJob {
  final String id;
  final DeliveryJobStatus status;
  final double fareAmount;
  final double distanceKm;
  final double pickupLatitude;
  final double pickupLongitude;
  final double dropoffLatitude;
  final double dropoffLongitude;
  final String deliveryNotes;
  final String? proofOfDeliveryImage;
  final String createdAt;
  final String? acceptedAt;
  final String? pickedUpAt;
  final String? deliveredAt;
  final String? cancelledAt;

  // Extra fields returned by `available` endpoint
  final double? driverToPickupKm;
  final int? driverToPickupMinutes;
  final double? pickupToDropoffKm;
  final int? pickupToDropoffMinutes;
  final OrderSummary? order;

  // Returned after accept / arrived-at-vendor / picked-up / in-transit
  final TripInfo? trip;

  const DeliveryJob({
    required this.id,
    required this.status,
    required this.fareAmount,
    required this.distanceKm,
    required this.pickupLatitude,
    required this.pickupLongitude,
    required this.dropoffLatitude,
    required this.dropoffLongitude,
    this.deliveryNotes = '',
    this.proofOfDeliveryImage,
    required this.createdAt,
    this.acceptedAt,
    this.pickedUpAt,
    this.deliveredAt,
    this.cancelledAt,
    this.driverToPickupKm,
    this.driverToPickupMinutes,
    this.pickupToDropoffKm,
    this.pickupToDropoffMinutes,
    this.order,
    this.trip,
  });

  factory DeliveryJob.fromJson(Map<String, dynamic> json) => DeliveryJob(
        id:              json['id'].toString(),
        status:          DeliveryJobStatus.fromString(json['status'] as String? ?? 'pending'),
        fareAmount:      double.tryParse(json['fare_amount'].toString()) ?? 0,
        distanceKm:      double.tryParse(json['distance_km'].toString()) ?? 0,
        pickupLatitude:  double.tryParse(json['pickup_latitude'].toString()) ?? 0,
        pickupLongitude: double.tryParse(json['pickup_longitude'].toString()) ?? 0,
        dropoffLatitude: double.tryParse(json['dropoff_latitude'].toString()) ?? 0,
        dropoffLongitude:double.tryParse(json['dropoff_longitude'].toString()) ?? 0,
        deliveryNotes:   json['delivery_notes'] as String? ?? '',
        proofOfDeliveryImage: json['proof_of_delivery_image'] as String?,
        createdAt:       json['created_at'] as String,
        acceptedAt:      json['accepted_at'] as String?,
        pickedUpAt:      json['picked_up_at'] as String?,
        deliveredAt:     json['delivered_at'] as String?,
        cancelledAt:     json['cancelled_at'] as String?,
        driverToPickupKm: json['driver_to_pickup_km'] != null
            ? double.tryParse(json['driver_to_pickup_km'].toString())
            : null,
        driverToPickupMinutes: json['driver_to_pickup_minutes'] as int?,
        pickupToDropoffKm: json['pickup_to_dropoff_km'] != null
            ? double.tryParse(json['pickup_to_dropoff_km'].toString())
            : null,
        pickupToDropoffMinutes: json['pickup_to_dropoff_minutes'] as int?,
        order: json['order'] != null
            ? OrderSummary.fromJson(json['order'] as Map<String, dynamic>)
            : null,
        trip: json['trip'] != null
            ? TripInfo.fromJson(json['trip'] as Map<String, dynamic>)
            : null,
      );
}

// ─────────────────────────────────────────────
// DriverLocationPing
// ─────────────────────────────────────────────

class DriverLocationPing {
  final int id;
  final String jobId;
  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final double? speedKmh;
  final double? headingDegrees;
  final String timestamp;

  const DriverLocationPing({
    required this.id,
    required this.jobId,
    required this.latitude,
    required this.longitude,
    this.accuracyMeters,
    this.speedKmh,
    this.headingDegrees,
    required this.timestamp,
  });

  factory DriverLocationPing.fromJson(Map<String, dynamic> json) => DriverLocationPing(
        id:             json['id'] as int,
        jobId:          json['job'].toString(),
        latitude:       double.tryParse(json['latitude'].toString()) ?? 0,
        longitude:      double.tryParse(json['longitude'].toString()) ?? 0,
        accuracyMeters: json['accuracy_meters'] != null
            ? (json['accuracy_meters'] as num).toDouble()
            : null,
        speedKmh:       json['speed_kmh'] != null
            ? (json['speed_kmh'] as num).toDouble()
            : null,
        headingDegrees: json['heading_degrees'] != null
            ? (json['heading_degrees'] as num).toDouble()
            : null,
        timestamp:      json['timestamp'] as String,
      );
}

// ─────────────────────────────────────────────
// DriverEarning
// ─────────────────────────────────────────────

class DriverEarning {
  final int id;
  final String jobId;
  final double grossAmount;
  final double platformCommission;
  final double netAmount;
  final String status;   // pending | paid | disputed
  final String? payoutId;
  final String createdAt;

  const DriverEarning({
    required this.id,
    required this.jobId,
    required this.grossAmount,
    required this.platformCommission,
    required this.netAmount,
    required this.status,
    this.payoutId,
    required this.createdAt,
  });

  factory DriverEarning.fromJson(Map<String, dynamic> json) => DriverEarning(
        id:                  json['id'] as int,
        jobId:               json['job'].toString(),
        grossAmount:         double.tryParse(json['gross_amount'].toString()) ?? 0,
        platformCommission:  double.tryParse(json['platform_commission'].toString()) ?? 0,
        netAmount:           double.tryParse(json['net_amount'].toString()) ?? 0,
        status:              json['status'] as String? ?? 'pending',
        payoutId:            json['payout']?.toString(),
        createdAt:           json['created_at'] as String,
      );
}

class EarningsSummary {
  final double totalGross;
  final double totalCommission;
  final double totalNet;
  final double pendingNet;
  final int totalDeliveries;

  const EarningsSummary({
    required this.totalGross,
    required this.totalCommission,
    required this.totalNet,
    required this.pendingNet,
    required this.totalDeliveries,
  });

  factory EarningsSummary.fromJson(Map<String, dynamic> json) => EarningsSummary(
        totalGross:       double.tryParse(json['total_gross'].toString()) ?? 0,
        totalCommission:  double.tryParse(json['total_commission'].toString()) ?? 0,
        totalNet:         double.tryParse(json['total_net'].toString()) ?? 0,
        pendingNet:       double.tryParse(json['pending_net'].toString()) ?? 0,
        totalDeliveries:  json['total_deliveries'] as int? ?? 0,
      );
}

// ─────────────────────────────────────────────
// DriverPayout
// ─────────────────────────────────────────────

class DriverPayout {
  final int id;
  final String periodStart;
  final String periodEnd;
  final double totalGross;
  final double totalCommission;
  final double totalNet;
  final String status;   // pending | processing | paid | failed
  final String paymentReference;
  final String? paidAt;
  final String createdAt;

  const DriverPayout({
    required this.id,
    required this.periodStart,
    required this.periodEnd,
    required this.totalGross,
    required this.totalCommission,
    required this.totalNet,
    required this.status,
    required this.paymentReference,
    this.paidAt,
    required this.createdAt,
  });

  factory DriverPayout.fromJson(Map<String, dynamic> json) => DriverPayout(
        id:               json['id'] as int,
        periodStart:      json['period_start'] as String,
        periodEnd:        json['period_end'] as String,
        totalGross:       double.tryParse(json['total_gross'].toString()) ?? 0,
        totalCommission:  double.tryParse(json['total_commission'].toString()) ?? 0,
        totalNet:         double.tryParse(json['total_net'].toString()) ?? 0,
        status:           json['status'] as String? ?? 'pending',
        paymentReference: json['payment_reference'] as String? ?? '',
        paidAt:           json['paid_at'] as String?,
        createdAt:        json['created_at'] as String,
      );
}

// ─────────────────────────────────────────────
// WebSocket events
// ─────────────────────────────────────────────

class WsLocationUpdate {
  final String jobId;
  final double latitude;
  final double longitude;
  final double? speedKmh;
  final double? headingDegrees;
  final String nextTarget;    // 'pickup' | 'dropoff'
  final double remainingKm;
  final int etaMinutes;

  const WsLocationUpdate({
    required this.jobId,
    required this.latitude,
    required this.longitude,
    this.speedKmh,
    this.headingDegrees,
    required this.nextTarget,
    required this.remainingKm,
    required this.etaMinutes,
  });

  factory WsLocationUpdate.fromJson(Map<String, dynamic> json) => WsLocationUpdate(
        jobId:          json['job_id'] as String,
        latitude:       double.tryParse(json['latitude'].toString()) ?? 0,
        longitude:      double.tryParse(json['longitude'].toString()) ?? 0,
        speedKmh:       json['speed_kmh'] != null
            ? (json['speed_kmh'] as num).toDouble()
            : null,
        headingDegrees: json['heading_degrees'] != null
            ? (json['heading_degrees'] as num).toDouble()
            : null,
        nextTarget:     json['next_target'] as String? ?? 'dropoff',
        remainingKm:    double.tryParse(json['remaining_km'].toString()) ?? 0,
        etaMinutes:     json['eta_minutes'] as int? ?? 0,
      );
}

class WsJobUpdate {
  final String eventType;
  final String jobId;
  final String status;
  final Map<String, dynamic> extra;

  const WsJobUpdate({
    required this.eventType,
    required this.jobId,
    required this.status,
    required this.extra,
  });

  factory WsJobUpdate.fromJson(Map<String, dynamic> json) => WsJobUpdate(
        eventType: json['event_type'] as String,
        jobId:     json['job_id'] as String,
        status:    json['status'] as String,
        extra:     Map<String, dynamic>.from(json)
          ..remove('type')
          ..remove('event_type')
          ..remove('job_id')
          ..remove('status'),
      );
}
```

---

## Dart Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

class DeliveryService {
  static const String _base    = 'https://api.sanoa.co.za';
  static const String _wsBase  = 'wss://api.sanoa.co.za';

  final String token;
  DeliveryService({required this.token});

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  // ── Helpers ─────────────────────────────────────────────────────

  Uri _uri(String path, [Map<String, String>? params]) =>
      Uri.parse('$_base$path').replace(queryParameters: params);

  Future<dynamic> _get(String path, [Map<String, String>? params]) async {
    final res = await http.get(_uri(path, params), headers: _headers);
    _assertOk(res);
    return jsonDecode(res.body);
  }

  Future<dynamic> _post(String path, [Map<String, dynamic>? body]) async {
    final res = await http.post(
      _uri(path),
      headers: _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    _assertOk(res);
    return jsonDecode(res.body);
  }

  void _assertOk(http.Response res) {
    if (res.statusCode >= 400) {
      final data = jsonDecode(res.body);
      final msg  = data['error'] ?? data['detail'] ?? 'Request failed';
      throw DeliveryException(msg, res.statusCode);
    }
  }

  // ── Fare rates ───────────────────────────────────────────────────

  Future<List<FareRate>> getFareRates() async {
    final data = await _get('/api/delivery/fare-rates/') as List;
    return data.map((j) => FareRate.fromJson(j as Map<String, dynamic>)).toList();
  }

  // ── Calculate fare ───────────────────────────────────────────────

  Future<DeliveryFare> calculateFare({
    required int vendorId,
    required int addressId,
    required String businessCategory,
  }) async {
    final data = await _post('/api/delivery/calculate-fare/', {
      'vendor_id': vendorId,
      'address_id': addressId,
      'business_category': businessCategory,
    });
    return DeliveryFare.fromJson(data as Map<String, dynamic>);
  }

  // ── Driver shift ─────────────────────────────────────────────────

  Future<DriverShift> goOnline({double? latitude, double? longitude}) async {
    final data = await _post('/api/delivery/driver/shifts/go-online/', {
      if (latitude  != null) 'latitude':  latitude,
      if (longitude != null) 'longitude': longitude,
    });
    return DriverShift.fromJson(data as Map<String, dynamic>);
  }

  Future<DriverShift> goOffline({double? latitude, double? longitude}) async {
    final data = await _post('/api/delivery/driver/shifts/go-offline/', {
      if (latitude  != null) 'latitude':  latitude,
      if (longitude != null) 'longitude': longitude,
    });
    return DriverShift.fromJson(data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> currentShift() async {
    return await _get('/api/delivery/driver/shifts/current/') as Map<String, dynamic>;
  }

  Future<List<DriverShift>> shiftHistory() async {
    final data = await _get('/api/delivery/driver/shifts/') as List;
    return data.map((j) => DriverShift.fromJson(j as Map<String, dynamic>)).toList();
  }

  // ── GPS location ─────────────────────────────────────────────────

  Future<Map<String, dynamic>> pushLocation({
    required double latitude,
    required double longitude,
    double? accuracyMeters,
    double? speedKmh,
    double? headingDegrees,
  }) async {
    return await _post('/api/delivery/driver/location/', {
      'latitude':  latitude,
      'longitude': longitude,
      if (accuracyMeters  != null) 'accuracy_meters':  accuracyMeters,
      if (speedKmh        != null) 'speed_kmh':        speedKmh,
      if (headingDegrees  != null) 'heading_degrees':  headingDegrees,
    }) as Map<String, dynamic>;
  }

  // ── Jobs ─────────────────────────────────────────────────────────

  Future<List<DeliveryJob>> listMyJobs() async {
    final data = await _get('/api/delivery/jobs/') as List;
    return data.map((j) => DeliveryJob.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<List<DeliveryJob>> availableJobs() async {
    final data = await _get('/api/delivery/jobs/available/') as List;
    return data.map((j) => DeliveryJob.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<DeliveryJob> acceptJob(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/accept/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<void> declineJob(String jobId, {String? reason}) async {
    await _post('/api/delivery/jobs/$jobId/decline/', {
      if (reason != null) 'decline_reason': reason,
    });
  }

  Future<DeliveryJob> arrivedAtVendor(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/arrived-at-vendor/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<DeliveryJob> pickedUp(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/picked-up/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<DeliveryJob> inTransit(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/in-transit/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<DeliveryJob> markDelivered(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/delivered/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<DeliveryJob> cancelJob(String jobId) async {
    final data = await _post('/api/delivery/jobs/$jobId/cancel/');
    return DeliveryJob.fromJson(data as Map<String, dynamic>);
  }

  Future<List<DriverLocationPing>> jobPings(String jobId) async {
    final data = await _get('/api/delivery/jobs/$jobId/pings/') as List;
    return data.map((j) => DriverLocationPing.fromJson(j as Map<String, dynamic>)).toList();
  }

  // ── Customer — track ─────────────────────────────────────────────

  Future<Map<String, dynamic>> trackJob(String jobId) async {
    return await _get('/api/delivery/track/$jobId/') as Map<String, dynamic>;
  }

  Future<void> rateDriver(String jobId, {required int rating, String comment = ''}) async {
    await _post('/api/delivery/track/$jobId/rate/', {
      'rating':  rating,
      'comment': comment,
    });
  }

  // ── Earnings ─────────────────────────────────────────────────────

  Future<List<DriverEarning>> listEarnings() async {
    final data = await _get('/api/delivery/driver/earnings/') as List;
    return data.map((j) => DriverEarning.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<EarningsSummary> earningsSummary() async {
    final data = await _get('/api/delivery/driver/earnings/summary/');
    return EarningsSummary.fromJson(data as Map<String, dynamic>);
  }

  Future<List<DriverPayout>> listPayouts() async {
    final data = await _get('/api/delivery/driver/payouts/') as List;
    return data.map((j) => DriverPayout.fromJson(j as Map<String, dynamic>)).toList();
  }

  // ── WebSocket — Driver job offers ────────────────────────────────

  WebSocketChannel connectDriverJobsChannel() {
    final uri = Uri.parse('$_wsBase/ws/delivery/driver/jobs/?token=$token');
    return WebSocketChannel.connect(uri);
  }

  Stream<dynamic> driverJobStream(WebSocketChannel channel) =>
      channel.stream.map((raw) {
        final json = jsonDecode(raw as String) as Map<String, dynamic>;
        return json; // caller switches on json['type']
      });

  // ── WebSocket — Customer/Driver tracking ─────────────────────────

  WebSocketChannel connectTrackingChannel(String jobId) {
    final uri = Uri.parse('$_wsBase/ws/delivery/track/$jobId/?token=$token');
    return WebSocketChannel.connect(uri);
  }

  Stream<dynamic> trackingStream(WebSocketChannel channel) =>
      channel.stream.map((raw) {
        final json = jsonDecode(raw as String) as Map<String, dynamic>;
        return switch (json['type']) {
          'snapshot'        => json,                           // initial snapshot
          'location_update' => WsLocationUpdate.fromJson(json),
          'job_update'      => WsJobUpdate.fromJson(json),
          _                 => json,
        };
      });
}

// ── Exception ────────────────────────────────────────────────────

class DeliveryException implements Exception {
  final String message;
  final int statusCode;
  const DeliveryException(this.message, this.statusCode);

  @override
  String toString() => 'DeliveryException($statusCode): $message';
}
```

---

## Error Responses

| HTTP Status | Body | Meaning |
|-------------|------|---------|
| `401` | `{"detail": "Authentication credentials were not provided."}` | Missing / expired JWT |
| `403` | `{"error": "Only drivers can accept jobs."}` | Wrong `user_type` |
| `400` | `{"error": "You already have an active job in progress."}` | Driver busy |
| `400` | `{"error": "Job is cancelled — cannot decline."}` | Job not in `pending` state |
| `400` | `{"error": "Distance 35.2km exceeds max 20km."}` | Fare calc out of range |
| `404` | `{"error": "Job not available."}` | Job taken by another driver |
| `404` | `{"error": "Job not found or not assigned to you."}` | Wrong driver / bad ID |

### WebSocket close codes

| Code | Meaning |
|------|---------|
| `4001` | Unauthenticated — missing or invalid token |
| `4003` | Forbidden — wrong user type or no access to job |

---

## Delivery Lifecycle Flow

```
[Customer places order]
        │
        ▼
DeliveryJob created (status: pending)
        │
        │  Signal → dispatch_job_to_nearby_drivers()
        │  WS → new_job pushed to all drivers within 20 km
        │
        ├─ Driver declines → job re-dispatched to other drivers
        │
        ▼
Driver accepts (status: accepted)
  WS → job_update { event_type: driver_accepted, eta_minutes }
        │
        ▼
Driver arrived at vendor (status: driver_at_vendor)
  WS → job_update { event_type: driver_at_vendor }
        │
        ▼
Driver picks up order (status: picked_up)
  WS → job_update { event_type: picked_up, eta_minutes }
        │
        ▼
Driver in transit (status: in_transit)
  WS → job_update { event_type: in_transit, eta_minutes }
  GPS pings → WS location_update { remaining_km, eta_minutes } (every POST /driver/location/)
        │
        ▼
Driver delivers (status: delivered)
  WS → job_update { event_type: delivered }
  DriverEarning created (gross - 20% commission = net)
        │
        ▼
Customer rates driver (1–5 stars)
  DeliveryDriver.average_rating recomputed
```

### Status values

| Status | Description |
|--------|-------------|
| `pending` | Job created, awaiting driver acceptance |
| `accepted` | Driver assigned and heading to vendor |
| `driver_at_vendor` | Driver has arrived at the pickup location |
| `picked_up` | Order collected, heading to customer |
| `in_transit` | Explicit in-transit confirmation |
| `delivered` | Order handed to customer |
| `cancelled` | Cancelled by customer, driver, or admin |
| `failed` | Delivery failed (system/admin use) |

---

## ETA Speed Reference

| Vehicle | Speed used |
|---------|-----------|
| `bicycle` | 15 km/h |
| `motorbike` | 30 km/h (default) |
| `car` | 25 km/h |
| `van` | 20 km/h |
| `truck` | 20 km/h |

ETAs are estimates based on straight-line (haversine) distance at conservative city-traffic speeds. Platform commission is fixed at **20 %**.

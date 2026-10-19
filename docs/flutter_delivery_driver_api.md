# Delivery App — Driver API Update

**Base URL:** `/api/delivery/`  
**Auth:** `Authorization: Bearer <access_token>` on every request

---

## What's New (Phase 3)

### New models added

| Model | Purpose |
|---|---|
| `DriverShift` | Online/offline session tracking |
| `DeliveryJob` | Full job lifecycle (replaces bare DeliveryFare flow) |
| `DriverLocationPing` | GPS snapshots stored while a job is active |
| `DriverEarning` | Per-job earnings record — auto-created on delivery |
| `DriverPayout` | Aggregate payout batches |
| `DriverRating` | Customer rates driver after delivery |

### Existing models — no changes

| Model | Notes |
|---|---|
| `FareRate` | Unchanged |
| `DeliveryDriver` | `is_available` default changed to `false` |
| `DeliveryFare` | Unchanged — legacy quote model, still used for pricing |

### New endpoints

```
POST  /api/delivery/driver/shifts/go-online/
POST  /api/delivery/driver/shifts/go-offline/
GET   /api/delivery/driver/shifts/current/
GET   /api/delivery/driver/shifts/
POST  /api/delivery/driver/location/
GET   /api/delivery/jobs/
GET   /api/delivery/jobs/available/
POST  /api/delivery/jobs/{id}/accept/
POST  /api/delivery/jobs/{id}/decline/
POST  /api/delivery/jobs/{id}/arrived-at-vendor/
POST  /api/delivery/jobs/{id}/picked-up/
POST  /api/delivery/jobs/{id}/delivered/
POST  /api/delivery/jobs/{id}/cancel/
GET   /api/delivery/jobs/{id}/pings/
GET   /api/delivery/driver/earnings/
GET   /api/delivery/driver/earnings/summary/
GET   /api/delivery/driver/payouts/
POST  /api/delivery/track/{jobId}/rate/
GET   /api/delivery/track/{jobId}/
```

### New WebSockets

```
ws://<host>/ws/delivery/driver/jobs/       — driver receives job offers
ws://<host>/ws/delivery/track/<jobId>/     — customer live GPS tracking
```

---

## Enums

### DeliveryJobStatus

| Dart value | JSON string |
|---|---|
| `pending` | `pending` |
| `accepted` | `accepted` |
| `driverAtVendor` | `driver_at_vendor` |
| `pickedUp` | `picked_up` |
| `inTransit` | `in_transit` |
| `delivered` | `delivered` |
| `cancelled` | `cancelled` |
| `failed` | `failed` |

```dart
enum DeliveryJobStatus {
  pending, accepted, driverAtVendor, pickedUp,
  inTransit, delivered, cancelled, failed;

  static DeliveryJobStatus fromJson(String v) => switch (v) {
    'accepted'        => accepted,
    'driver_at_vendor'=> driverAtVendor,
    'picked_up'       => pickedUp,
    'in_transit'      => inTransit,
    'delivered'       => delivered,
    'cancelled'       => cancelled,
    'failed'          => failed,
    _                 => pending,
  };
}
```

---

## Model Classes

### DeliveryDriver

No new fields. `is_available` default is now `false` (driver starts offline).

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `user` | `int` | |
| `userEmail` | `String` | |
| `vehicleType` | `String` | `bicycle \| motorbike \| car \| van` |
| `vehicleRegistration` | `String` | |
| `licenseNumber` | `String` | |
| `isAvailable` | `bool` | `true` = online |
| `currentLatitude` | `String?` | Updated on every GPS ping |
| `currentLongitude` | `String?` | |
| `totalDeliveries` | `int` | |
| `averageRating` | `String` | Decimal string |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory DeliveryDriver.fromJson(Map<String, dynamic> j) => DeliveryDriver(
  id: j['id'] as int,
  user: j['user'] as int,
  userEmail: j['user_email'] as String,
  vehicleType: j['vehicle_type'] as String,
  vehicleRegistration: j['vehicle_registration'] as String? ?? '',
  licenseNumber: j['license_number'] as String? ?? '',
  isAvailable: j['is_available'] as bool,
  currentLatitude: j['current_latitude'] as String?,
  currentLongitude: j['current_longitude'] as String?,
  totalDeliveries: j['total_deliveries'] as int,
  averageRating: j['average_rating'] as String,
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### DriverShift

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `driver` | `int` | |
| `driverEmail` | `String` | |
| `startedAt` | `DateTime` | |
| `endedAt` | `DateTime?` | Null while still online |
| `isActive` | `bool` | |
| `startLatitude` | `String?` | |
| `startLongitude` | `String?` | |
| `endLatitude` | `String?` | |
| `endLongitude` | `String?` | |

```dart
factory DriverShift.fromJson(Map<String, dynamic> j) => DriverShift(
  id: j['id'] as int,
  driver: j['driver'] as int,
  driverEmail: j['driver_email'] as String,
  startedAt: DateTime.parse(j['started_at']),
  endedAt: j['ended_at'] != null ? DateTime.parse(j['ended_at']) : null,
  isActive: j['is_active'] as bool,
  startLatitude: j['start_latitude'] as String?,
  startLongitude: j['start_longitude'] as String?,
  endLatitude: j['end_latitude'] as String?,
  endLongitude: j['end_longitude'] as String?,
);
```

---

### DeliveryJob

A job links to either a retail order or a restaurant order — never both.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `fare` | `int?` | FK to `DeliveryFare` |
| `retailOrder` | `String?` | UUID of `orders.Order` |
| `restaurantOrder` | `String?` | UUID of `restaurant.RestaurantOrder` |
| `driver` | `int?` | Null until accepted |
| `driverEmail` | `String?` | |
| `customer` | `int` | |
| `customerEmail` | `String` | |
| `vendor` | `int` | |
| `vendorName` | `String?` | |
| `status` | `DeliveryJobStatus` | |
| `pickupLatitude` | `String` | |
| `pickupLongitude` | `String` | |
| `dropoffLatitude` | `String` | |
| `dropoffLongitude` | `String` | |
| `distanceKm` | `String` | Decimal string |
| `fareAmount` | `String` | Decimal string |
| `deliveryNotes` | `String` | |
| `proofOfDeliveryImage` | `String?` | URL |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |
| `acceptedAt` | `DateTime?` | |
| `driverAtVendorAt` | `DateTime?` | |
| `pickedUpAt` | `DateTime?` | |
| `deliveredAt` | `DateTime?` | |
| `cancelledAt` | `DateTime?` | |

```dart
factory DeliveryJob.fromJson(Map<String, dynamic> j) => DeliveryJob(
  id: j['id'] as int,
  fare: j['fare'] as int?,
  retailOrder: j['retail_order'] as String?,
  restaurantOrder: j['restaurant_order'] as String?,
  driver: j['driver'] as int?,
  driverEmail: j['driver_email'] as String?,
  customer: j['customer'] as int,
  customerEmail: j['customer_email'] as String,
  vendor: j['vendor'] as int,
  vendorName: j['vendor_name'] as String?,
  status: DeliveryJobStatus.fromJson(j['status']),
  pickupLatitude: j['pickup_latitude'] as String,
  pickupLongitude: j['pickup_longitude'] as String,
  dropoffLatitude: j['dropoff_latitude'] as String,
  dropoffLongitude: j['dropoff_longitude'] as String,
  distanceKm: j['distance_km'] as String,
  fareAmount: j['fare_amount'] as String,
  deliveryNotes: j['delivery_notes'] as String? ?? '',
  proofOfDeliveryImage: j['proof_of_delivery_image'] as String?,
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
  acceptedAt:       j['accepted_at']         != null ? DateTime.parse(j['accepted_at'])         : null,
  driverAtVendorAt: j['driver_at_vendor_at'] != null ? DateTime.parse(j['driver_at_vendor_at']) : null,
  pickedUpAt:       j['picked_up_at']        != null ? DateTime.parse(j['picked_up_at'])        : null,
  deliveredAt:      j['delivered_at']        != null ? DateTime.parse(j['delivered_at'])        : null,
  cancelledAt:      j['cancelled_at']        != null ? DateTime.parse(j['cancelled_at'])        : null,
);
```

---

### DriverLocationPing

Stored only while a job is active. Broadcast live to customer tracking WebSocket.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `job` | `int` | |
| `latitude` | `String` | |
| `longitude` | `String` | |
| `accuracyMeters` | `double?` | |
| `speedKmh` | `double?` | |
| `headingDegrees` | `double?` | |
| `timestamp` | `DateTime` | |

```dart
factory DriverLocationPing.fromJson(Map<String, dynamic> j) => DriverLocationPing(
  id: j['id'] as int,
  job: j['job'] as int,
  latitude: j['latitude'] as String,
  longitude: j['longitude'] as String,
  accuracyMeters: (j['accuracy_meters'] as num?)?.toDouble(),
  speedKmh: (j['speed_kmh'] as num?)?.toDouble(),
  headingDegrees: (j['heading_degrees'] as num?)?.toDouble(),
  timestamp: DateTime.parse(j['timestamp']),
);
```

---

### DriverEarning

Auto-created when a job transitions to `delivered`. Platform commission = **20%**.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `driver` | `int` | |
| `job` | `int` | |
| `jobStatus` | `String` | |
| `payout` | `int?` | FK to `DriverPayout` once batched |
| `grossAmount` | `String` | Full fare amount |
| `platformCommission` | `String` | 20% of gross |
| `netAmount` | `String` | `gross - commission` |
| `status` | `String` | `pending \| paid \| disputed` |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory DriverEarning.fromJson(Map<String, dynamic> j) => DriverEarning(
  id: j['id'] as int,
  driver: j['driver'] as int,
  job: j['job'] as int,
  jobStatus: j['job_status'] as String,
  payout: j['payout'] as int?,
  grossAmount: j['gross_amount'] as String,
  platformCommission: j['platform_commission'] as String,
  netAmount: j['net_amount'] as String,
  status: j['status'] as String,
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### EarningsSummary

Returned by `GET /api/delivery/driver/earnings/summary/`.

| Field | Type | Notes |
|---|---|---|
| `totalGross` | `String` | |
| `totalCommission` | `String` | |
| `totalNet` | `String` | |
| `pendingNet` | `String` | Unpaid earnings |
| `totalDeliveries` | `int` | |

```dart
factory EarningsSummary.fromJson(Map<String, dynamic> j) => EarningsSummary(
  totalGross:       j['total_gross'].toString(),
  totalCommission:  j['total_commission'].toString(),
  totalNet:         j['total_net'].toString(),
  pendingNet:       j['pending_net'].toString(),
  totalDeliveries:  j['total_deliveries'] as int,
);
```

---

### DriverPayout

Aggregate payout batch — read-only from driver perspective.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `driver` | `int` | |
| `periodStart` | `DateTime` | |
| `periodEnd` | `DateTime` | |
| `totalGross` | `String` | |
| `totalCommission` | `String` | |
| `totalNet` | `String` | |
| `status` | `String` | `pending \| processing \| paid \| failed` |
| `paymentReference` | `String` | |
| `paidAt` | `DateTime?` | |
| `earningsCount` | `int` | Number of jobs in this payout |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

---

### DriverRating

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `job` | `int` | |
| `customer` | `int` | |
| `driver` | `int` | |
| `rating` | `int` | 1–5 |
| `comment` | `String` | |
| `createdAt` | `DateTime` | |

Submitting a rating also updates `driver.average_rating` server-side.

---

### TrackDeliveryResponse

Returned by `GET /api/delivery/track/{jobId}/`.

| Field | Type | Notes |
|---|---|---|
| `job` | `DeliveryJob` | |
| `driverCurrentLocation` | `Map<String, String?>?` | `{latitude, longitude}` from driver profile |
| `lastPing` | `DriverLocationPing?` | Most recent stored ping |

```dart
factory TrackDeliveryResponse.fromJson(Map<String, dynamic> j) => TrackDeliveryResponse(
  job: DeliveryJob.fromJson(j['job']),
  driverCurrentLocation: j['driver_current_location'] != null
      ? Map<String, String?>.from(j['driver_current_location'])
      : null,
  lastPing: j['last_ping'] != null
      ? DriverLocationPing.fromJson(j['last_ping'])
      : null,
);
```

---

## Request Body Helpers

```dart
// POST /api/delivery/driver/shifts/go-online/
Map<String, dynamic> buildGoOnlineBody({String? latitude, String? longitude}) => {
  if (latitude != null)  'latitude': latitude,
  if (longitude != null) 'longitude': longitude,
};

// POST /api/delivery/driver/shifts/go-offline/
Map<String, dynamic> buildGoOfflineBody({String? latitude, String? longitude}) => {
  if (latitude != null)  'latitude': latitude,
  if (longitude != null) 'longitude': longitude,
};

// POST /api/delivery/driver/location/
Map<String, dynamic> buildGpsUpdateBody({
  required String latitude,
  required String longitude,
  double? accuracyMeters,
  double? speedKmh,
  double? headingDegrees,
}) => {
  'latitude': latitude,
  'longitude': longitude,
  if (accuracyMeters != null)  'accuracy_meters': accuracyMeters,
  if (speedKmh != null)        'speed_kmh': speedKmh,
  if (headingDegrees != null)  'heading_degrees': headingDegrees,
};

// POST /api/delivery/track/{jobId}/rate/
Map<String, dynamic> buildRateDriverBody({
  required int rating,   // 1–5
  String comment = '',
}) => {
  'rating': rating,
  if (comment.isNotEmpty) 'comment': comment,
};
```

---

## REST Endpoints

### Driver Profile (unchanged)

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/delivery/driver/profile/` | `DeliveryDriver` |
| `PUT` | `/api/delivery/driver/profile/` | `DeliveryDriver` |

---

### Shifts — Go Online / Offline

| Method | URL | Body | Returns |
|---|---|---|---|
| `POST` | `/api/delivery/driver/shifts/go-online/` | `buildGoOnlineBody(...)` | `DriverShift` |
| `POST` | `/api/delivery/driver/shifts/go-offline/` | `buildGoOfflineBody(...)` | `DriverShift` |
| `GET` | `/api/delivery/driver/shifts/current/` | — | `{"online": bool, "shift": DriverShift?}` |
| `GET` | `/api/delivery/driver/shifts/` | — | `List<DriverShift>` |

`go-online` sets `driver.is_available = true` and creates a new `DriverShift`.  
`go-offline` sets `driver.is_available = false` and closes the active shift.

---

### GPS Updates

| Method | URL | Body | Returns |
|---|---|---|---|
| `POST` | `/api/delivery/driver/location/` | `buildGpsUpdateBody(...)` | See below |

**Response:**
```json
{
  "updated": true,
  "current_latitude": "6.5244",
  "current_longitude": "3.3792",
  "active_job": 42,
  "ping": { /* DriverLocationPing or null */ }
}
```

If an active job exists, a `DriverLocationPing` is stored and broadcast over `ws/delivery/track/<jobId>/` automatically.

---

### Jobs (Driver)

| Method | URL | Returns | Notes |
|---|---|---|---|
| `GET` | `/api/delivery/jobs/` | `List<DeliveryJob>` | Driver sees own jobs; customer sees own jobs |
| `GET` | `/api/delivery/jobs/available/` | `List<DeliveryJob>` | Pending unassigned jobs |
| `POST` | `/api/delivery/jobs/{id}/accept/` | `DeliveryJob` | Locks with `select_for_update` |
| `POST` | `/api/delivery/jobs/{id}/decline/` | `{"status", "job_id", "driver"}` | |
| `POST` | `/api/delivery/jobs/{id}/arrived-at-vendor/` | `DeliveryJob` | |
| `POST` | `/api/delivery/jobs/{id}/picked-up/` | `DeliveryJob` | |
| `POST` | `/api/delivery/jobs/{id}/delivered/` | `DeliveryJob` | Auto-creates `DriverEarning` (20% commission) |
| `POST` | `/api/delivery/jobs/{id}/cancel/` | `DeliveryJob` | |

---

### Jobs (Customer)

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/delivery/jobs/{id}/pings/` | `List<DriverLocationPing>` |
| `GET` | `/api/delivery/track/{jobId}/` | `TrackDeliveryResponse` |
| `POST` | `/api/delivery/track/{jobId}/rate/` | `DriverRating` |

---

### Earnings (Driver only)

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/delivery/driver/earnings/` | `List<DriverEarning>` |
| `GET` | `/api/delivery/driver/earnings/summary/` | `EarningsSummary` |
| `GET` | `/api/delivery/driver/payouts/` | `List<DriverPayout>` |

---

### Fare (unchanged)

| Method | URL | Body | Returns |
|---|---|---|---|
| `POST` | `/api/delivery/calculate-fare/` | `{address_id, vendor_id, business_category}` | `DeliveryFare` |
| `GET` | `/api/delivery/fare-rates/` | — | `List<FareRate>` |

`business_category` is `"retail"` or `"restaurant"`.

---

## WebSocket — Driver Job Offers

**URL:** `ws://<host>/ws/delivery/driver/jobs/`  
**Auth:** JWT query param `?token=<access_token>`

### Incoming messages

#### `new_job` — new delivery available

```json
{
  "type": "new_job",
  "job_id": 42,
  "status": "pending",
  "fare_amount": "850.00",
  "distance_km": "3.2",
  "pickup_lat": "6.5244",
  "pickup_lon": "3.3792",
  "dropoff_lat": "6.5312",
  "dropoff_lon": "3.3701"
}
```

#### `job_update` — status change on an accepted job

```json
{
  "type": "job_update",
  "event_type": "accepted",
  "job_id": 42,
  "status": "accepted"
}
```

---

## WebSocket — Customer Live Tracking

**URL:** `ws://<host>/ws/delivery/track/<jobId>/`  
**Auth:** JWT query param `?token=<access_token>`

### On Connect — Snapshot

```json
{
  "type": "snapshot",
  "job_id": 42,
  "status": "accepted",
  "driver_latitude": "6.5244",
  "driver_longitude": "3.3792"
}
```

### Live GPS update

```json
{
  "type": "location_update",
  "job_id": 42,
  "latitude": "6.5280",
  "longitude": "3.3750",
  "speed_kmh": 35.0,
  "heading_degrees": 270.0
}
```

### Status change

```json
{
  "type": "job_update",
  "event_type": "picked_up",
  "job_id": 42,
  "status": "picked_up",
  "message": "Driver has picked up your order.",
  "driver_name": "John D."
}
```

`event_type` values: `accepted` \| `driver_at_vendor` \| `picked_up` \| `delivered` \| `cancelled`

---

## Dart WebSocket Parsing Classes

```dart
class DeliveryWsMessage {
  final String type;
  final Map<String, dynamic> data;

  factory DeliveryWsMessage.fromJson(Map<String, dynamic> j) =>
      DeliveryWsMessage(type: j['type'] as String, data: j);
}

class LocationUpdateMessage {
  final int jobId;
  final String latitude;
  final String longitude;
  final double? speedKmh;
  final double? headingDegrees;

  factory LocationUpdateMessage.fromJson(Map<String, dynamic> j) =>
      LocationUpdateMessage(
        jobId: j['job_id'] as int,
        latitude: j['latitude'] as String,
        longitude: j['longitude'] as String,
        speedKmh: (j['speed_kmh'] as num?)?.toDouble(),
        headingDegrees: (j['heading_degrees'] as num?)?.toDouble(),
      );
}

class JobUpdateMessage {
  final String eventType;
  final int jobId;
  final String status;
  final String? message;
  final String? driverName;

  factory JobUpdateMessage.fromJson(Map<String, dynamic> j) => JobUpdateMessage(
    eventType:  j['event_type'] as String,
    jobId:      j['job_id'] as int,
    status:     j['status'] as String,
    message:    j['message'] as String?,
    driverName: j['driver_name'] as String?,
  );
}
```

---

## Job Status Flow

```
pending
  └─ accept()        → accepted
       └─ arrived-at-vendor() → driver_at_vendor
            └─ picked-up()    → picked_up / in_transit
                 └─ delivered() → delivered  ← DriverEarning auto-created here
                 └─ cancel()    → cancelled
  └─ decline()  (stays pending for another driver)
```

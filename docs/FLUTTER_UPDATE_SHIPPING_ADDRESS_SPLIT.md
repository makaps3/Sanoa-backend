# Flutter Frontend Update — Shipping vs Vendor Address Split

Customer shipping addresses and vendor business addresses now live in **separate tables** with **separate endpoints**. This document lists every endpoint that moved, changed shape, or was added — and includes Dart snippets the app can paste in.

**TL;DR**
- Customers manage their shipping addresses at **`/api/orders/shipping-addresses/`** (new).
- Vendors manage their business addresses at `/api/business/addresses/` (same URL, different semantics — now VendorProfile-scoped).
- Checkout and delivery-fare endpoints now take a **`shipping_address_id`** (UUID of a saved shipping address) instead of raw address fields.
- All address ids are **UUID strings** now.

---

## 1. New — Shipping Address CRUD

Base path: `/api/orders/shipping-addresses/`

All endpoints require `Authorization: Bearer <access_token>`. Only the authenticated customer sees/edits their own rows (staff sees all).

### 1.1 `GET /api/orders/shipping-addresses/`

List the authenticated customer's shipping addresses.

**Response 200** — array (no pagination wrapper):

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "address_type": "shipping",
    "label": "Primary",
    "full_name": "Jane Doe",
    "phone_number": "+27821234567",
    "street_address": "123 Main St",
    "apartment_number": "4B",
    "city": "Cape Town",
    "state_province": "Western Cape",
    "postal_code": "8001",
    "country": "South Africa",
    "latitude": "-33.924870",
    "longitude": "18.424055",
    "is_default": true,
    "delivery_instructions": "Leave at reception.",
    "created_at": "2026-04-18T09:10:00Z",
    "updated_at": "2026-04-18T09:12:00Z"
  }
]
```

### 1.2 `POST /api/orders/shipping-addresses/`

Create a shipping address. Server sets `user = request.user` automatically — **do not send `user`**.

**Request body**:

```json
{
  "address_type": "shipping",
  "label": "Primary",
  "full_name": "Jane Doe",
  "phone_number": "+27821234567",
  "street_address": "123 Main St",
  "apartment_number": "4B",
  "city": "Cape Town",
  "state_province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "latitude": -33.924870,
  "longitude": 18.424055,
  "is_default": true,
  "delivery_instructions": "Leave at reception."
}
```

**Required:** `full_name`, `phone_number`, `street_address`, `city`, `state_province`, `postal_code`.

**Allowed `address_type` values:** `"shipping"`, `"billing"`, `"both"` (default `"shipping"`).

**Defaults on optional fields:**
- `label` → `""`
- `apartment_number` → `""`
- `country` → `"South Africa"`
- `latitude` / `longitude` → `null`
- `is_default` → `false`
- `delivery_instructions` → `""`

Latitude/longitude are **required** before an address can be used for `/api/delivery/calculate-fare/` (the fare endpoint rejects addresses with `null` coords).

**Response 201** — the created object (same shape as 1.1 item).

**Setting `is_default: true` auto-unsets it on any other address for the same user.**

### 1.3 `GET /api/orders/shipping-addresses/{id}/`

Retrieve a single address by UUID. Returns `404` if the id doesn't exist or isn't owned by the caller.

### 1.4 `PATCH /api/orders/shipping-addresses/{id}/`

Partial update. Send only the fields you want to change:

```json
{ "label": "Weekend house", "is_default": false }
```

**Response 200** — updated object.

### 1.5 `PUT /api/orders/shipping-addresses/{id}/`

Full replacement. Same body shape as `POST`.

### 1.6 `DELETE /api/orders/shipping-addresses/{id}/`

Delete the address.

**Response 204** — empty body on success.

Any `Order` that was snapshotted from this row **keeps its shipping info** (the order snapshots shipping_* fields), but its `shipping_address` FK becomes `null`.

### 1.7 `POST /api/orders/shipping-addresses/{id}/set_default/`

Shortcut action to mark an address as the default.

**Request body:** empty `{}`.

**Response 200** — the updated address with `is_default: true`.

---

## 2. Updated — Affected endpoints

### 2.1 `POST /api/orders/orders/` (checkout) — CHANGED

**Breaking change:** the raw `shipping_*` fields have been removed from the request body. Clients pass a `shipping_address_id` when checking out with `fulfillment_type=="delivery"`.

**Request body (delivery):**

```json
{
  "cart_id": "b1c2d3e4-…-uuid",
  "shipping_address_id": "a1b2c3d4-…-uuid",

  "customer_email": "jane@example.com",
  "customer_phone": "+27821234567",

  "fulfillment_type": "delivery",
  "scheduled_for": null,

  "coupon_code": "",
  "order_notes": "Please leave at reception."
}
```

**Request body (pickup / dine-in):** unchanged — `shipping_address_id` not required.

```json
{
  "cart_id": "b1c2d3e4-…-uuid",
  "customer_email": "jane@example.com",
  "customer_phone": "+27821234567",
  "fulfillment_type": "pickup",
  "scheduled_for": "2026-04-18T18:30:00Z"
}
```

**Required-field matrix**:

| Field | delivery | pickup | dine_in |
|---|---|---|---|
| `cart_id` | required | required | required |
| `customer_email` | required | required | required |
| `shipping_address_id` | **required** | ignored | ignored |
| `table_number` | must be empty | must be empty | required |

**Errors**:
- `400` `shipping_address_id: Required when fulfillment_type is 'delivery'.`
- `400` `shipping_address_id: Shipping address not found or not yours.`
- `400` cart empty / negotiation not accepted / expired
- `404` `cart_id` not found or not owned by user

**Response 201** — full `OrderDetailSerializer`. New field: `shipping_address` (UUID or null, points back to the source row).

### 2.2 `GET /api/orders/orders/{id}/` — RESPONSE CHANGED

`OrderDetailSerializer` adds a `shipping_address` FK field; the existing snapshot `shipping_*` fields are unchanged.

```json
{
  "id": "…",
  "order_number": "ORD-20260418-0001",
  "status": "pending",
  "payment_status": "pending",
  "shipping_address": "a1b2c3d4-…-uuid",     // NEW — null if source was deleted
  "shipping_full_name": "Jane Doe",
  "shipping_street_address": "123 Main St",
  "shipping_city": "Cape Town",
  "…": "…"
}
```

Use the snapshot fields for display; use the FK only if you need to let the user jump to the saved address.

### 2.3 `POST /api/delivery/calculate-fare/` — CHANGED

**Breaking change:** `address_id` is now a UUID (referencing `orders.ShippingAddress`), not an int.

**Request body:**

```json
{
  "address_id": "a1b2c3d4-…-uuid",
  "vendor_id": "b1c2d3e4-…-uuid",
  "business_category": "retail"
}
```

**Errors**:
- `404` `Shipping address not found for this customer.`
- `400` `Address does not have coordinates set.` (set `latitude` + `longitude` on the ShippingAddress first)
- `404` vendor not found
- `400` no fare rate for the business category
- `400` distance exceeds the fare rate max

### 2.4 `GET /api/business/addresses/by-user/{user_id}/` — RESPONSE CHANGED (customer branch)

Same URL, same behavior for vendor user ids. For **customer** user ids it now returns rows from `orders.ShippingAddress`:

```json
{
  "user_id": 42,
  "user_email": "jane@example.com",
  "user_type": "customer",
  "source": "shipping_address",
  "count": 1,
  "results": [
    {
      "id": "a1b2c3d4-…-uuid",
      "address_type": "shipping",
      "label": "Primary",
      "full_name": "Jane Doe",
      "phone_number": "+27821234567",
      "street_address": "123 Main St",
      "apartment_number": "4B",
      "city": "Cape Town",
      "state_province": "Western Cape",
      "postal_code": "8001",
      "country": "South Africa",
      "latitude": "-33.924870",
      "longitude": "18.424055",
      "is_default": true,
      "delivery_instructions": "Leave at reception.",
      "created_at": "…",
      "updated_at": "…",
      "source": "shipping_address"
    }
  ]
}
```

**Differences from previous shape:**
- `source` is now `"shipping_address"` (was `"personal"`).
- Each row has a `label` field (new).
- `address_type` enum is now `"shipping"` / `"billing"` / `"both"` (was the mixed `billing`/`shipping`/`both`/`business` from the old combined table).

Vendor responses are unchanged.

### 2.5 `/api/business/addresses/` — SCOPE CHANGED

This endpoint now only handles **vendor business addresses** (linked to a `VendorProfile`).

`GET /api/business/addresses/` returns only the authenticated **vendor's** own business addresses (staff sees all). A customer calling this endpoint will see an empty list.

`POST /api/business/addresses/` requires the authenticated user to have a vendor profile — returns `403 "You must have a vendor profile to create a business address."` otherwise.

**Request body (vendor create):**

```json
{
  "address_type": "business",
  "full_name": "Sweet Treats Cafe",
  "phone_number": "+27821234567",
  "street_address": "55 Long Street",
  "apartment_number": "",
  "city": "Cape Town",
  "state_province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "latitude": -33.924870,
  "longitude": 18.424055,
  "is_default": true,
  "delivery_instructions": ""
}
```

**Response 201** — includes `vendor` (VendorProfile UUID) and `vendor_name` (business name).

### 2.6 `GET /api/accounts/me/` — RESPONSE CHANGED

The `addresses` field resolution changed:
- `user.user_type == 'customer'` → array of `ShippingAddress` rows (from `orders.ShippingAddress`).
- `user.user_type == 'vendor'` → array of vendor `Address` rows (from `business.Address` scoped to the user's VendorProfile).
- No profile / other user types → `[]`.

---

## 3. Dart models

### `ShippingAddress`

```dart
class ShippingAddress {
  final String id;                    // UUID
  final String addressType;           // 'shipping' | 'billing' | 'both'
  final String label;
  final String fullName;
  final String phoneNumber;
  final String streetAddress;
  final String? apartmentNumber;
  final String city;
  final String stateProvince;
  final String postalCode;
  final String country;
  final double? latitude;
  final double? longitude;
  final bool isDefault;
  final String deliveryInstructions;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory ShippingAddress.fromJson(Map<String, dynamic> j) => ShippingAddress(
        id: j['id'] as String,
        addressType: j['address_type'] as String? ?? 'shipping',
        label: j['label'] as String? ?? '',
        fullName: j['full_name'] as String,
        phoneNumber: j['phone_number'] as String,
        streetAddress: j['street_address'] as String,
        apartmentNumber: j['apartment_number'] as String?,
        city: j['city'] as String,
        stateProvince: j['state_province'] as String,
        postalCode: j['postal_code'] as String,
        country: j['country'] as String? ?? 'South Africa',
        latitude: j['latitude'] == null ? null : double.parse(j['latitude'].toString()),
        longitude: j['longitude'] == null ? null : double.parse(j['longitude'].toString()),
        isDefault: j['is_default'] as bool? ?? false,
        deliveryInstructions: j['delivery_instructions'] as String? ?? '',
        createdAt: DateTime.parse(j['created_at'] as String),
        updatedAt: DateTime.parse(j['updated_at'] as String),
      );

  Map<String, dynamic> toCreateJson() => {
        'address_type': addressType,
        if (label.isNotEmpty) 'label': label,
        'full_name': fullName,
        'phone_number': phoneNumber,
        'street_address': streetAddress,
        if (apartmentNumber != null) 'apartment_number': apartmentNumber,
        'city': city,
        'state_province': stateProvince,
        'postal_code': postalCode,
        'country': country,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        'is_default': isDefault,
        if (deliveryInstructions.isNotEmpty)
          'delivery_instructions': deliveryInstructions,
      };
}
```

### `CreateOrderRequest` — update

```dart
class CreateOrderRequest {
  final String cartId;
  final String? shippingAddressId;   // REQUIRED when fulfillmentType == 'delivery'
  final String customerEmail;
  final String? customerPhone;
  final String fulfillmentType;      // 'delivery' | 'pickup' | 'dine_in'
  final DateTime? scheduledFor;
  final String? tableNumber;
  final String? couponCode;
  final String? orderNotes;

  Map<String, dynamic> toJson() => {
        'cart_id': cartId,
        if (fulfillmentType == 'delivery' && shippingAddressId != null)
          'shipping_address_id': shippingAddressId,
        'customer_email': customerEmail,
        if (customerPhone != null) 'customer_phone': customerPhone,
        'fulfillment_type': fulfillmentType,
        if (scheduledFor != null)
          'scheduled_for': scheduledFor!.toUtc().toIso8601String(),
        if (fulfillmentType == 'dine_in' && tableNumber != null)
          'table_number': tableNumber,
        if (couponCode != null) 'coupon_code': couponCode,
        if (orderNotes != null) 'order_notes': orderNotes,
      };
}
```

### `CalculateFareRequest` — update

```dart
class CalculateFareRequest {
  final String addressId;        // UUID of ShippingAddress (was int)
  final String vendorId;         // UUID of VendorProfile
  final String businessCategory; // 'retail' | 'restaurant'

  Map<String, dynamic> toJson() => {
        'address_id': addressId,
        'vendor_id': vendorId,
        'business_category': businessCategory,
      };
}
```

### `VendorAddress` (vendor-side, optional)

Only relevant if your app also has a vendor dashboard.

```dart
class VendorAddress {
  final String id;
  final String vendor;        // VendorProfile UUID
  final String vendorName;
  final String addressType;   // 'billing' | 'shipping' | 'both' | 'business'
  final String fullName;
  final String phoneNumber;
  final String streetAddress;
  final String? apartmentNumber;
  final String city;
  final String stateProvince;
  final String postalCode;
  final String country;
  final double? latitude;
  final double? longitude;
  final bool isDefault;
  final String deliveryInstructions;
  final DateTime createdAt;
  final DateTime updatedAt;
}
```

---

## 4. Migration checklist for the Flutter app

- [ ] Add `ShippingAddress` Dart model + API client (CRUD + set_default).
- [ ] Replace any remaining code that posts raw `shipping_*` fields to `/api/orders/orders/`; pass `shipping_address_id` instead. Required when `fulfillment_type == 'delivery'`.
- [ ] Update the checkout flow: before calling `POST /orders/`, make sure the customer has a saved shipping address. If not, surface the shipping-address create form first.
- [ ] On `CalculateFareRequest`, flip `address_id` from `int` to `String` (UUID).
- [ ] On `GET /api/accounts/me/`, treat `addresses` as a source-dependent list: customers get `ShippingAddress` rows, vendors get vendor `Address` rows. Don't assume a shared shape.
- [ ] On `/api/business/addresses/by-user/{user_id}/` for customers, switch the parser from the old `"personal"` source to `"shipping_address"`. The row fields are the same as the CRUD endpoint above.
- [ ] Remove any Dart code that tried to manage customer addresses at `/api/business/addresses/` — that endpoint is now vendor-only.
- [ ] Before using an address for delivery, ensure `latitude` + `longitude` are populated. Surface a geocode step if the user skipped entering coordinates.

---

## 5. Server-side file reference

| Area | File |
|---|---|
| ShippingAddress model | [orders/models.py](../orders/models.py) |
| ShippingAddress serializer / viewset | [orders/serializers.py](../orders/serializers.py), [orders/views.py](../orders/views.py) |
| ShippingAddress URL | [orders/urls.py](../orders/urls.py) (`shipping-addresses`) |
| ShippingAddress admin | [orders/admin.py](../orders/admin.py) |
| Order checkout using `shipping_address_id` | [orders/serializers.py](../orders/serializers.py) (`OrderCreateSerializer`) |
| `Order.shipping_address` FK | [orders/models.py](../orders/models.py) |
| Vendor Address repointed to VendorProfile | [business/models.py](../business/models.py), [business/serializers.py](../business/serializers.py), [business/views.py](../business/views.py), [business/admin.py](../business/admin.py) |
| Delivery fare using ShippingAddress | [delivery/serializers.py](../delivery/serializers.py), [delivery/views.py](../delivery/views.py), [delivery/models.py](../delivery/models.py) |
| `user.addresses` resolver (customer vs vendor) | [accounts/serializers.py](../accounts/serializers.py) (`UserDetailSerializer.get_addresses`) |
| Migrations | [orders/migrations/0008_shippingaddress_and_order_fk.py](../orders/migrations/0008_shippingaddress_and_order_fk.py), [business/migrations/0012_address_to_vendorprofile.py](../business/migrations/0012_address_to_vendorprofile.py), [delivery/migrations/0005_deliveryfare_address_to_shippingaddress.py](../delivery/migrations/0005_deliveryfare_address_to_shippingaddress.py) |

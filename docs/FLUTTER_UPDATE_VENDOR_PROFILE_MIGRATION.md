# Flutter Frontend Update — Vendor Profile Migration

Everything in this document is a breaking change the Flutter app must adopt.
It covers three independent threads that were completed together:

1. **Order checkout** — now per-cart, per-vendor; address is conditional on fulfillment type.
2. **Addresses** — added coordinates; new `by-user` lookup; `"business"` address type.
3. **Product schema** — `Product.vendor` now references a **VendorProfile**, not a User. Its `id` is a UUID string, not an int.

All examples are Dart/Flutter-oriented.

---

## 1. Order checkout

### `POST /api/orders/orders/`

Creates an order from **one** shopping cart (one vendor). Clients that used to
check out all carts at once must now call this endpoint once per cart.

#### Request body

```jsonc
{
  // NEW — required. Select one of the user's carts (one vendor per checkout).
  "cart_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",

  "customer_email": "customer@example.com",
  "customer_phone": "+27821234567",

  // Address fields (shipping_* only — billing removed from the API surface).
  // REQUIRED when fulfillment_type == "delivery".
  // IGNORED when fulfillment_type == "pickup" or "dine_in".
  "shipping_full_name": "Jane Doe",
  "shipping_street_address": "123 Main St",
  "shipping_apartment_number": "4B",
  "shipping_city": "Cape Town",
  "shipping_state_province": "Western Cape",
  "shipping_postal_code": "8001",
  "shipping_country": "South Africa",

  "fulfillment_type": "delivery",      // "delivery" | "pickup" | "dine_in"
  "scheduled_for": null,                // ISO-8601 or null for ASAP
  "table_number": "",                   // required iff fulfillment_type == "dine_in"

  "coupon_code": "",
  "order_notes": ""
}
```

#### Required-field matrix

| Field | `delivery` | `pickup` | `dine_in` |
|---|---|---|---|
| `cart_id` | required | required | required |
| `customer_email` | required | required | required |
| `shipping_*` (all except apartment_number) | required | ignored | ignored |
| `table_number` | must be empty | must be empty | required |
| `scheduled_for` | optional | optional | optional |

#### Errors

| Status | Condition |
|---|---|
| `400` | cart is empty, wrong fulfillment_type / table_number combination, pending/expired negotiations on cart items |
| `404` | `cart_id` not found or not owned by user |

#### Dart model hint

```dart
class CreateOrderRequest {
  final String cartId;
  final String customerEmail;
  final String? customerPhone;
  final String fulfillmentType;    // 'delivery' | 'pickup' | 'dine_in'
  final DateTime? scheduledFor;
  final String? tableNumber;
  final ShippingAddress? shipping; // required only when delivery
  final String? couponCode;
  final String? orderNotes;

  Map<String, dynamic> toJson() => {
        'cart_id': cartId,
        'customer_email': customerEmail,
        if (customerPhone != null) 'customer_phone': customerPhone,
        'fulfillment_type': fulfillmentType,
        if (scheduledFor != null) 'scheduled_for': scheduledFor!.toUtc().toIso8601String(),
        if (tableNumber != null) 'table_number': tableNumber,
        if (fulfillmentType == 'delivery' && shipping != null) ...shipping!.toJson(),
        if (couponCode != null) 'coupon_code': couponCode,
        if (orderNotes != null) 'order_notes': orderNotes,
      };
}
```

---

## 2. Addresses

### 2.1 New endpoint — `GET /api/business/addresses/by-user/{user_id}/`

Returns addresses for any user (customer OR vendor) by their **User** id.

- **Customers** → personal addresses from the `Address` table.
- **Vendors** → the vendor's business/trading address(es) from their vendor
  profile (address is tied to the business, not to the User row).

Response shape (`source` tells the client where the rows came from):

```jsonc
{
  "user_id": 87,
  "user_email": "corner-shop@example.com",
  "user_type": "vendor",            // "customer" | "vendor" | "driver" | "admin"
  "source": "vendor_profile",       // "personal" | "vendor_profile"
  "count": 1,
  "results": [
    {
      "id": "b1c2d3e4-...",         // UUID for vendor profile rows, int for personal
      "source": "vendor_profile",   // or "personal" / "individual_vendor_profile" / "business_vendor_profile"
      "profile_type": "individual", // vendor rows only
      "address_type": "business",
      "full_name": "Corner Shop Trading",
      "phone_number": "+27821234567",
      "street_address": "55 Long Street",
      "apartment_number": "",
      "city": "Cape Town",
      "state_province": "Western Cape",
      "postal_code": "8001",
      "country": "South Africa",
      "latitude": "-33.924870",
      "longitude": "18.424055",
      "is_default": true,
      "delivery_instructions": ""
    }
  ]
}
```

### 2.2 Existing endpoints — address coordinates now exposed

The existing CRUD endpoints (`GET/POST/PATCH /api/business/addresses/`,
`/api/business/addresses/{id}/`) now return **and accept** `latitude` and
`longitude`. The columns existed already; the serializer was just hiding them.

Use these to fix `POST /api/delivery/calculate-fare/` failures on addresses
created before this change.

```dart
class Address {
  final dynamic id;                 // int for personal, String (UUID) for vendor
  final String addressType;         // 'billing' | 'shipping' | 'both' | 'business'
  final String fullName;
  final String phoneNumber;
  final String streetAddress;
  final String? apartmentNumber;
  final String city;
  final String stateProvince;
  final String postalCode;
  final String country;
  final double? latitude;           // NEW — read these as double from string
  final double? longitude;          // NEW
  final bool isDefault;
  final String deliveryInstructions;

  factory Address.fromJson(Map<String, dynamic> j) => Address(
        id: j['id'],
        addressType: j['address_type'] as String,
        fullName: j['full_name'] as String,
        phoneNumber: j['phone_number'] as String,
        streetAddress: j['street_address'] as String,
        apartmentNumber: j['apartment_number'] as String?,
        city: j['city'] as String,
        stateProvince: j['state_province'] as String,
        postalCode: j['postal_code'] as String,
        country: j['country'] as String,
        latitude: j['latitude'] == null ? null : double.parse(j['latitude'].toString()),
        longitude: j['longitude'] == null ? null : double.parse(j['longitude'].toString()),
        isDefault: j['is_default'] as bool? ?? false,
        deliveryInstructions: j['delivery_instructions'] as String? ?? '',
      );
}
```

### 2.3 New `address_type` value

`address_type` now accepts **4** values:

| Value | Label |
|---|---|
| `billing` | Billing Address |
| `shipping` | Shipping Address |
| `both` | Billing & Shipping |
| `business` | Business Address *(new)* |

Vendor-profile addresses returned by `by-user` use `"business"`. If your Dart
enum for `AddressType` was exhaustive (e.g. a `switch`), add the new case.

---

## 3. Product-vendor schema change (BREAKING)

### What changed

`Product.vendor` is now a foreign key to **`VendorProfile`**, not to `User`.
The old `Product.vendor_profile` field has been renamed to `Product.vendor`.

This means every Product-related endpoint that previously returned
`vendor` as a **user id (integer)** now returns a **VendorProfile id (UUID
string)**.

### Affected endpoints

| Endpoint | What changed |
|---|---|
| `GET /api/products/products/` (list) | `vendor_info.profile_id` still UUID (unchanged), but in nested serializers `vendor` is now a profile UUID |
| `GET /api/products/products/{id}/` (detail) | `vendor` is a UUID string (VendorProfile pk); `vendor_info.id` is still the underlying User id |
| `POST /api/products/products/` (vendor creates) | Server sets `vendor` to the authenticated user's `vendor_profile` automatically. Clients **must not** send a `vendor` field. If the user has no vendor profile, returns `403`. |
| `PATCH /api/products/products/{id}/` | Same — `vendor` isn't a writable field. |
| `GET /api/negotiations/ranking/` (and similar) | Response field `vendor_id` is now a **VendorProfile id (UUID)**, not a user id. Use `vendor_id` as the **store** identifier. |
| `POST /api/negotiations/...` | Internally stores both `vendor` (User) and `vendor_profile` (VendorProfile) — no client-visible change. |

### Field type / shape reference

#### ProductDetailSerializer

```jsonc
{
  "id": "6d...-uuid",
  "name": "Glazed Donuts",
  "vendor": "b1c2d3e4-...-uuid",   // WAS: user id (int). NOW: VendorProfile id (UUID string).
  "vendor_info": {
     "id": "42",                    // underlying User id (string). UNCHANGED semantics.
     "profile_id": "b1c2d3e4-...",  // VendorProfile id. UNCHANGED semantics.
     "profile_type": "individual",
     "name": "Sweet Treats Cafe",
     "email": "sweettreats@sanoa.test",
     "logo": "https://.../logo.png",
     "average_rating": "4.80",
     "review_count": 12
  },
  // ... other product fields unchanged ...
}
```

### Dart model changes

```dart
class Product {
  final String id;
  final String name;
  // CHANGED: vendor used to be int (User id). Now it's a String (VendorProfile UUID).
  final String vendor;             // VendorProfile id
  final VendorInfo? vendorInfo;
  // ...

  factory Product.fromJson(Map<String, dynamic> j) => Product(
        id: j['id'] as String,
        name: j['name'] as String,
        // If your old code did `j['vendor'] as int` — that will now throw.
        vendor: j['vendor'].toString(),
        vendorInfo: j['vendor_info'] == null
            ? null
            : VendorInfo.fromJson(j['vendor_info']),
      );
}

class VendorInfo {
  final String id;          // underlying User id (stringified; unchanged semantics)
  final String? profileId;  // VendorProfile id
  final String? profileType; // 'individual' | 'business' | null
  final String name;        // business/store name
  final String email;
  final String? logo;
  final double averageRating;
  final int reviewCount;

  factory VendorInfo.fromJson(Map<String, dynamic> j) => VendorInfo(
        id: j['id'].toString(),
        profileId: j['profile_id'] as String?,
        profileType: j['profile_type'] as String?,
        name: j['name'] as String,
        email: j['email'] as String,
        logo: j['logo'] as String?,
        averageRating: double.parse(j['average_rating'].toString()),
        reviewCount: j['review_count'] as int,
      );
}
```

### If you used `product.vendor` as a user identifier

Anywhere the Flutter app passed `product.vendor` to an endpoint expecting a
**user id** (e.g. `ShoppingCart.vendor`, addresses by-user), **you must use
`product.vendorInfo.id` instead**. Example:

```dart
// BEFORE:
await api.get('/api/business/addresses/by-user/${product.vendor}/');

// AFTER:
await api.get('/api/business/addresses/by-user/${product.vendorInfo!.id}/');
```

### Cart/Order already handle the mapping server-side

When a customer adds an item to a cart or creates an order, the Flutter app
doesn't need to pass the vendor explicitly — the backend resolves both the
User and VendorProfile from `product.vendor` automatically. No client change
needed for `POST /api/orders/cart/add-item/` or `POST /api/orders/orders/`
beyond what's described in section 1.

---

## 4. Customer profile (reference — unchanged)

No changes. Still at:

- `GET/PATCH /api/accounts/me/` — user + nested `customer_profile`
- `GET/POST/PATCH/DELETE /api/accounts/profiles/customer/` (and `/{id}/`)

Profile is auto-created by signal when the user registers.

---

## 5. Migration checklist for the Flutter app

- [ ] Update `Order.createOrder` to send `cart_id`; drop all `billing_*` fields.
- [ ] Gate the shipping-address form on `fulfillment_type == 'delivery'`.
- [ ] Treat `cart_id` as required on checkout; if the user has multiple carts, show a cart selector.
- [ ] Parse `latitude` / `longitude` on `Address` (they're strings, parse to `double`).
- [ ] Add `'business'` to `AddressType` enum or switch.
- [ ] Change `Product.vendor` type from `int` → `String` (UUID).
- [ ] Audit every call that passes `product.vendor` as a user id; swap to `product.vendorInfo.id`.
- [ ] Audit every call that reads `vendor_id` from the negotiations ranking/engine response; it's now a VendorProfile UUID. Use it as a **store id**, not a user id.
- [ ] Do not send a `vendor` field when creating/updating a Product; backend derives it.
- [ ] If you fetch a vendor's addresses for pickup/delivery estimation, call `/api/business/addresses/by-user/{userId}/` with `vendorInfo.id`.

---

## 6. Quick server-side summary for reference

| Area | File | Change |
|---|---|---|
| Checkout | `orders/views.py`, `orders/serializers.py` | `cart_id` required; address conditional on fulfillment |
| Address API | `business/serializers.py`, `business/views.py` | expose `latitude`/`longitude`; new `by-user` action |
| Address model | `business/models.py` + migration `0011` | `"business"` choice added |
| Product schema | `products/models.py` + migration `0014` | `vendor` now FK to VendorProfile |
| Engine response | `negotiations/engine.py` | `vendor_id` in responses is a VendorProfile UUID |
| Signals | `business/signals.py` | Removed Product from dual-FK sync (prevents OverflowError on save) |

# Flutter API Changes — Reference

Changes introduced in the recent backend refactor. Use this to update the Flutter client.

---

## 1. `vendor_info` is now everywhere a vendor is returned

Every serializer that exposes a vendor now returns a nested `vendor_info` object with profile-first data (business/individual profile → user fallback).

### Shape

```json
{
  "id": "<user-id>",
  "profile_id": "<vendor-profile-uuid or null>",
  "profile_type": "individual" | "business" | null,
  "name": "Sweet Treats Cafe",
  "email": "vendor@example.com",
  "logo": "https://cdn.example.com/logos/vendors/logo.png",
  "average_rating": "4.50",
  "review_count": 12
}
```

### Dart model

```dart
class VendorInfo {
  final String id;            // user id
  final String? profileId;    // vendor_profile UUID
  final String? profileType;  // 'individual' | 'business' | null
  final String name;
  final String email;
  final String? logo;
  final String averageRating; // Decimal string, e.g. "4.50"
  final int reviewCount;

  VendorInfo({
    required this.id,
    required this.profileId,
    required this.profileType,
    required this.name,
    required this.email,
    required this.logo,
    required this.averageRating,
    required this.reviewCount,
  });

  factory VendorInfo.fromJson(Map<String, dynamic> json) => VendorInfo(
        id: json['id'].toString(),
        profileId: json['profile_id'],
        profileType: json['profile_type'],
        name: json['name'] ?? '',
        email: json['email'] ?? '',
        logo: json['logo'],
        averageRating: json['average_rating'] ?? '0.00',
        reviewCount: json['review_count'] ?? 0,
      );
}
```

### Endpoints that now include `vendor_info`

| Endpoint | Serializer |
|---|---|
| `GET /api/products/products/{id}/` | ProductDetailSerializer |
| `GET /api/products/vendor-reviews/` | VendorReviewSerializer |
| `GET /api/orders/cart/my-carts/` | ShoppingCartSerializer |
| `GET /api/negotiations/policies/` | PricePolicySerializer |
| `GET /api/negotiations/negotiated-prices/` | NegotiatedPriceSerializer |
| `GET /api/payments/subaccounts/` | PaystackSubaccountSerializer |
| `GET /api/debit/credit-purchases/` | CreditPurchaseSerializer |

**Fallback rule:** `name` is resolved from VendorProfile → legacy profile → `first_name last_name` → `username` → email local part. Never empty for a valid vendor.

---

## 2. NEW: unified `VendorProfile` model

`BusinessVendorProfile` and `IndividualVendorProfile` are merged into a single `VendorProfile` with a `profile_type` discriminator. The legacy endpoints still work but prefer the new one.

### Endpoints

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/api/business/profiles/vendor/me/` | Current vendor's profile |
| `GET` | `/api/business/profiles/vendor/` | List (admin) / own (vendor) |
| `POST` | `/api/business/profiles/vendor/` | Create (one per user) |
| `PATCH` | `/api/business/profiles/vendor/{id}/` | Update |
| `GET` | `/api/business/profiles/vendor/{id}/` | Detail |

### Response shape

```json
{
  "id": "bea9bf2d-0bd6-4282-ba2b-2a28e79e0d1f",
  "user": 14,
  "user_email": "sweettreats@sanoa.test",
  "profile_type": "individual",
  "business_category": "restaurant",
  "vendor_type": "food_vendor",
  "business_type": "",
  "name": "Sweet Treats Cafe",
  "trading_name": "",
  "description": "Best pastries in town",
  "logo": "/media/logos/vendors/sweet.png",
  "logo_url": "https://cdn.example.com/media/logos/vendors/sweet.png",
  "website": "",
  "qr_code": "/media/qr/vendors/abc.png",
  "qr_code_identifier": "b1a2f3...",
  "id_number": "",
  "id_document": null,
  "proof_of_address": null,
  "selfie_with_id": null,
  "cipc_registration_number": "",
  "cipc_document": null,
  "tax_number": "",
  "tax_clearance_certificate": null,
  "vat_number": "",
  "bee_certificate": null,
  "owner_full_name": "",
  "owner_id_number": "",
  "owner_id_document": null,
  "owner_proof_of_address": null,
  "street_address": "12 Main Rd",
  "city": "Cape Town",
  "province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "latitude": "-33.924870",
  "longitude": "18.424055",
  "bank_name": "FNB",
  "bank_account_number": "1234567890",
  "bank_branch_code": "250655",
  "bank_account_holder": "Sweet Treats Cafe",
  "verification_status": "pending",
  "owner_vetting_passed": false,
  "business_vetting_passed": false,
  "rejection_reason": "",
  "verified_at": null,
  "verified_by": null,
  "total_sales": "0.00",
  "total_orders": 0,
  "average_rating": "0.00",
  "total_reviews": 0,
  "commission_rate": "5.00",
  "store_active": true,
  "accepts_returns": true,
  "return_window_days": 14,
  "opening_hours": {},
  "is_temporarily_closed": false,
  "categories": [],
  "created_at": "2026-04-16T20:19:00Z",
  "updated_at": "2026-04-16T20:19:00Z"
}
```

### Key field mapping (old → new)

| Old (Individual) | Old (Business) | New (VendorProfile) |
|---|---|---|
| `store_name` | `business_name` | `name` |
| `store_description` | `business_description` | `description` |
| `store_logo` | `business_logo` | `logo` (+ `logo_url`) |
| `trading_address` | `business_street_address` | `street_address` |
| `trading_city` | `business_city` | `city` |
| `trading_province` | `business_province` | `province` |
| `trading_postal_code` | `business_postal_code` | `postal_code` |
| — | `business_trading_name` | `trading_name` |
| — | `business_website` | `website` |
| `vendor_type` | — | `vendor_type` (only set when profile_type='individual') |
| — | `business_type` | `business_type` (only set when profile_type='business') |

### Dart model skeleton

```dart
class VendorProfile {
  final String id;
  final int user;
  final String userEmail;
  final String profileType; // 'individual' | 'business'
  final String businessCategory; // 'retail' | 'restaurant'
  final String? vendorType;
  final String? businessType;
  final String name;
  final String tradingName;
  final String description;
  final String? logoUrl;
  final String? website;
  // ... address, banking, verification, metrics
  final String verificationStatus;
  final String averageRating;
  final int totalReviews;
  // ...

  factory VendorProfile.fromJson(Map<String, dynamic> j) => VendorProfile(
    id: j['id'],
    user: j['user'],
    userEmail: j['user_email'],
    profileType: j['profile_type'],
    businessCategory: j['business_category'],
    vendorType: j['vendor_type'],
    businessType: j['business_type'],
    name: j['name'] ?? '',
    tradingName: j['trading_name'] ?? '',
    description: j['description'] ?? '',
    logoUrl: j['logo_url'],
    website: j['website'],
    verificationStatus: j['verification_status'],
    averageRating: j['average_rating'] ?? '0.00',
    totalReviews: j['total_reviews'] ?? 0,
  );
}
```

### Auto-creation on signup

When a user registers with `user_type='vendor'`, a **blank** `VendorProfile` is auto-created (`profile_type='individual'`, `name=''`). The client should show the profile completion form immediately after registration.

### Legacy endpoints (still work, use for reference only)

- `/api/business/profiles/vendor/individual/` → `IndividualVendorProfileViewSet`
- `/api/business/profiles/vendor/business/` → `BusinessVendorProfileViewSet`

Migrate all frontend calls to `/api/business/profiles/vendor/` — the legacy ones remain for rollback safety but should not be called by new code.

---

## 3. NEW: `driver` user type

Added `'driver'` to `USER_TYPE_CHOICES` in accounts.

```dart
enum UserType { customer, vendor, driver, admin }
```

Registration with `user_type='driver'` creates a user but **no profile** is auto-created for drivers. The driver must complete their profile via `PUT /api/delivery/driver/profile/`.

---

## 4. NEW: Delivery app (`/api/delivery/`)

### Customer — calculate fare

**`POST /api/delivery/calculate-fare/`** (customer auth)

Request:
```json
{
  "address_id": 42,
  "vendor_id": "<vendor-user-uuid>",
  "business_category": "retail"
}
```

Response (201):
```json
{
  "id": 1,
  "customer": 5,
  "customer_email": "buyer@example.com",
  "vendor": "<vendor-uuid>",
  "vendor_email": "vendor@example.com",
  "driver": null,
  "driver_email": null,
  "address": 42,
  "business_category": "retail",
  "distance_km": "12.50",
  "base_fare": "20.00",
  "per_km_rate": "8.00",
  "fare_amount": "120.00",
  "pickup_latitude": "-33.924870",
  "pickup_longitude": "18.424055",
  "dropoff_latitude": "-33.980000",
  "dropoff_longitude": "18.500000",
  "status": "pending",
  "decline_reason": "",
  "created_at": "2026-04-16T21:00:00Z",
  "updated_at": "2026-04-16T21:00:00Z",
  "accepted_at": null,
  "completed_at": null
}
```

Errors:
- `400` — distance exceeds max (100km retail, 50km restaurant)
- `400` — customer address has no coordinates
- `400` — vendor has no coordinates
- `403` — caller is not a customer
- `404` — address or vendor not found

### Customer — fare rates

**`GET /api/delivery/fare-rates/`**

```json
[
  {
    "id": 1,
    "business_category": "retail",
    "base_fare": "20.00",
    "per_km_rate": "8.00",
    "max_distance_km": "100.00",
    "is_active": true
  },
  {
    "id": 2,
    "business_category": "restaurant",
    "base_fare": "20.00",
    "per_km_rate": "10.00",
    "max_distance_km": "50.00",
    "is_active": true
  }
]
```

### Driver endpoints (driver auth)

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/api/delivery/driver/requests/` | List pending unassigned fares |
| `POST` | `/api/delivery/driver/requests/{id}/accept/` | Assign self + status → `accepted` |
| `POST` | `/api/delivery/driver/requests/{id}/decline/` | Body: `{"decline_reason": "too far"}` |
| `GET` | `/api/delivery/driver/profile/` | Own driver profile |
| `PUT` | `/api/delivery/driver/profile/` | Update (vehicle, `is_available`, lat/lng) |

### Driver profile shape

```json
{
  "id": 1,
  "user": 25,
  "user_email": "driver@example.com",
  "vehicle_type": "motorbike",
  "vehicle_registration": "CA123456",
  "license_number": "DL-789",
  "is_available": true,
  "current_latitude": "-33.920000",
  "current_longitude": "18.420000",
  "total_deliveries": 0,
  "average_rating": "0.00"
}
```

Vehicle types: `bicycle`, `motorbike`, `car`, `van`.
Fare statuses: `pending`, `accepted`, `declined`, `completed`, `cancelled`.

---

## 5. Address model — new fields

`Address` now has optional coordinates:

```json
{
  "id": 42,
  "user": 5,
  "address_type": "both",
  "full_name": "...",
  "phone_number": "...",
  "street_address": "...",
  "apartment_number": "...",
  "city": "Cape Town",
  "state_province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "is_default": true,
  "delivery_instructions": "",
  "latitude": "-33.924870",   // NEW
  "longitude": "18.424055",   // NEW
  "created_at": "...",
  "updated_at": "..."
}
```

**Important:** `latitude`/`longitude` are required for delivery fare calculation. Update the address form to collect coordinates (or geocode the address client-side).

---

## 6. Payment transaction initialize — new `subscription_payment` / `tier_payment` intents

**`POST /api/payments/transactions/initialize/`**

`payment_intent` choices changed:

| Old | New |
|---|---|
| `order_payment` | `order_payment` (unchanged) |
| `subscription` | `subscription_payment` (**renamed**) |
| — | `tier_payment` (**new**) |
| `deposit` | `deposit` (unchanged) |

### Behavior

- **`order_payment`** — request body unchanged. `order_id` is an Order UUID. `subaccount_code`, `split_code`, `metadata` are honored.
- **`subscription_payment`** — `order_id` is a **Subscription UUID**. `subaccount_code`, `split_code`, `metadata` are **silently ignored**.
- **`tier_payment`** — `order_id` is a **VendorTierSubscription UUID**. `subaccount_code`, `split_code`, `metadata` are **silently ignored**.

### Request examples

**Order payment (unchanged):**
```json
{
  "amount": 250.00,
  "order_id": "<order-uuid>",
  "payment_intent": "order_payment",
  "callback_url": "https://yourapp.com/payment/callback",
  "channels": ["card", "bank_transfer", "eft"],
  "subaccount_code": "ACCT_xxx",
  "split_code": "SPL_xxx",
  "metadata": {"custom_field": "value"}
}
```

**Subscription payment:**
```json
{
  "amount": 99.99,
  "order_id": "<subscription-uuid>",
  "payment_intent": "subscription_payment",
  "callback_url": "https://yourapp.com/payment/callback",
  "channels": ["card"]
}
```

**Tier payment:**
```json
{
  "amount": 199.99,
  "order_id": "<vendor-tier-subscription-uuid>",
  "payment_intent": "tier_payment",
  "callback_url": "https://yourapp.com/payment/callback",
  "channels": ["card"]
}
```

### Response (all intents — HTTP 201)

```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "bxwxvds",
  "reference": "TXN-20260412-000001",
  "transaction_id": "<transaction-uuid>"
}
```

### Transaction detail response

`Transaction` now exposes `subscription` and `vendor_tier_subscription` FKs:

```json
{
  "id": "<txn-uuid>",
  "reference": "TXN-20260412-000001",
  "payment_intent": "subscription_payment",
  "order": null,
  "order_number": null,
  "subscription": "<subscription-uuid>",
  "vendor_tier_subscription": null,
  // ... other fields
}
```

---

## 7. New `vendor_profile` / `supplier_profile` FK on many models

Every vendor-linked table now has both a legacy `vendor` (user id) FK **and** a new `vendor_profile` (UUID) FK. The frontend normally should read `vendor_info.profile_id` — but if you query objects directly, both FKs are populated and in sync.

Tables affected:
- `Product.vendor_profile`
- `VendorReview.vendor_profile`
- `ShoppingCart.vendor_profile`
- `OrderItem.vendor_profile`
- `PricePolicy.vendor_profile`
- `NegotiatedPrice.vendor_profile`
- `PaystackSubaccount.vendor_profile`
- `VendorTierSubscription.vendor_profile`
- `CreditPurchase.vendor_profile`
- `DeliveryFare.vendor_profile`
- `PurchaseOrder.supplier_profile`

---

## Migration checklist for Flutter

- [ ] Add `VendorInfo` model; replace scattered `vendor_email` / `vendor_name` usage with `vendor_info.name`, `vendor_info.logo`, etc.
- [ ] Add `UserType.driver` enum value.
- [ ] Replace `IndividualVendorProfile` / `BusinessVendorProfile` models/forms with a single `VendorProfile` using `profileType` as a discriminator.
- [ ] Point vendor profile calls to `/api/business/profiles/vendor/` (keep old endpoints as fallback until fully migrated).
- [ ] After registration with `user_type='vendor'`, fetch `/api/business/profiles/vendor/me/` — a blank profile already exists; show the completion form.
- [ ] Update `payment_intent` enum: rename `subscription` → `subscription_payment`, add `tier_payment`.
- [ ] For subscription/tier payments, pass the respective UUID in `order_id` and **omit** `subaccount_code` / `split_code` / `metadata`.
- [ ] Add `latitude` / `longitude` to the `Address` form (required for delivery).
- [ ] Build delivery UI: fare calculator (customer), driver request list with accept/decline, driver profile editor.

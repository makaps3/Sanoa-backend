# Flutter Frontend Update — Vendor Collapse (Phase 2)

**Context:** Phase 1 collapsed `Product.vendor` to point at `VendorProfile`. This document covers Phase 2, which applies the same collapse to every other model that held a legacy `vendor=User` + `vendor_profile=VendorProfile` dual FK.

**TL;DR for the Flutter team:**
- Every vendor identifier in API responses is now a **VendorProfile UUID string**, never a User id int.
- Every request body that takes a `vendor_id` (or `supplier_id`) now expects a **VendorProfile UUID**, not a User id.
- `vendor_email` fields are still exposed (read-only convenience) but resolve through `vendor.user.email`.

---

## 1. Models changed

| Model | Old fields | New field | Target |
|---|---|---|---|
| `orders.ShoppingCart` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `orders.OrderItem` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `negotiations.PricePolicy` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` (OneToOne) |
| `negotiations.NegotiatedPrice` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `products.VendorReview` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `payments.PaystackSubaccount` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` (OneToOne) |
| `tiers.VendorTierSubscription` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` (OneToOne) |
| `debit.CreditPurchase` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `delivery.DeliveryFare` | `vendor` (User) + `vendor_profile` | `vendor` | `VendorProfile` |
| `inventory.PurchaseOrder` | `supplier` (User) + `supplier_profile` | `supplier` | `VendorProfile` |

---

## 2. API endpoints affected

### 2.1 Shopping cart — `/api/orders/cart/*`

**Response shape change:** `ShoppingCart.vendor` is now a VendorProfile UUID.

```jsonc
{
  "id": "…",
  "user": 42,
  "vendor": "b1c2d3e4-…-uuid",     // was: int User id. NOW: VendorProfile UUID
  "vendor_email": "store@example.com",
  "vendor_name": "Sweet Treats Cafe",
  "vendor_info": { … },
  "items": [ … ],
  "total_items": 3,
  "total_amount": "249.97",
  "created_at": "…",
  "updated_at": "…"
}
```

**No request-body changes** — the cart is still auto-populated from the product when you call `/api/orders/cart/add-item/`. The backend resolves the vendor through `product.vendor`.

### 2.2 Order items — `/api/orders/orders/{id}/`

`OrderDetailSerializer.items[].vendor` is now a VendorProfile UUID.

```dart
class OrderItem {
  final String vendor; // VendorProfile UUID (was int User id)
}
```

### 2.3 Negotiations — `/api/negotiations/*`

#### `POST /api/negotiations/policy/set-policy/`

No change to the request body. Response field `vendor` is now a VendorProfile UUID.

```jsonc
{
  "id": 12,
  "vendor": "b1c2d3e4-…-uuid",   // was: User id. NOW: VendorProfile UUID
  "vendor_email": "store@example.com",
  "vendor_info": { … },
  "max_markup_percent": "15.00",
  …
}
```

#### `GET /api/negotiations/ranking/` (engine response)

The `vendor_id` field is now a **string UUID** (VendorProfile id), not an int.

```jsonc
{
  "product_id": "…",
  "vendor_id": "b1c2d3e4-…-uuid",   // was IntegerField. NOW CharField (UUID)
  "vendor_name": "Sweet Treats Cafe",
  …
}
```

#### `GET /api/negotiations/my-negotiations/*`

`NegotiatedPriceSerializer.vendor` is a VendorProfile UUID.

### 2.4 Vendor reviews — `/api/products/vendor-reviews/`

`VendorReview.vendor` is a VendorProfile UUID.

Request body for creating a review — `vendor` must be a VendorProfile UUID:

```jsonc
{
  "vendor": "b1c2d3e4-…-uuid",   // was: User id. NOW: VendorProfile UUID
  "rating": 5,
  "title": "Great service",
  "comment": "…"
}
```

The `?vendor=<id>` query param also expects a VendorProfile UUID now.

### 2.5 Paystack subaccounts — `/api/payments/subaccounts/`

Response field `vendor` is a VendorProfile UUID. **Request body is unchanged** — the backend uses `request.user.vendor_profile` automatically.

`403` if the authenticated user has no vendor profile yet.

### 2.6 Tier subscriptions — `/api/tiers/subscriptions/*`

All endpoints unchanged at the request-body level (backend derives the vendor profile). Response field `vendor` is a VendorProfile UUID.

`POST /api/tiers/subscriptions/subscribe/` raises a 400 if the authenticated vendor user has no vendor profile.

### 2.7 Credit / debit purchases — `/api/debit/*`

#### `POST /api/debit/eligibility/`

**Breaking:** `vendor_id` field type changed from `int` to `UUID string`.

```jsonc
{ "vendor_id": "b1c2d3e4-…-uuid" }    // was: { "vendor_id": 42 }
```

#### `POST /api/debit/purchases/create/`

**Breaking:** same `vendor_id` type change.

```jsonc
{
  "vendor_id": "b1c2d3e4-…-uuid",
  "total_amount": "500.00",
  "deposit_amount": "100.00",
  "due_date": "2026-05-18",
  "order_id": 123
}
```

Response `CreditPurchaseSerializer.vendor` is a VendorProfile UUID.

### 2.8 Delivery fare — `/api/delivery/calculate-fare/`

`vendor_id` in the request body was already `UUIDField` in phase 1 (it was already a profile id for the delivery flow), so no request-body change. Just note that `DeliveryFareSerializer.vendor` in responses is a VendorProfile UUID.

### 2.9 Inventory purchase orders — `/api/inventory/purchase-orders/`

**Breaking:** request body `supplier` must be a VendorProfile UUID, not a User id.

```jsonc
{
  "supplier": "b1c2d3e4-…-uuid",   // was: User id int. NOW: VendorProfile UUID
  "warehouse": 1,
  "expected_delivery_date": "2026-05-01",
  "line_items": [ … ]
}
```

Response `PurchaseOrderSerializer.supplier` is a VendorProfile UUID.

---

## 3. Dart model updates

### `ShoppingCart`

```dart
class ShoppingCart {
  final String id;
  final int user;
  final String vendor;          // WAS int. NOW String (VendorProfile UUID).
  final String vendorEmail;
  final String vendorName;
  final VendorInfo? vendorInfo;
  final List<CartItem> items;
  final int totalItems;
  final String totalAmount;

  factory ShoppingCart.fromJson(Map<String, dynamic> j) => ShoppingCart(
        id: j['id'].toString(),
        user: j['user'] as int,
        vendor: j['vendor'].toString(),   // tolerate both shapes during rollout
        vendorEmail: j['vendor_email'] as String? ?? '',
        vendorName: j['vendor_name'] as String? ?? '',
        vendorInfo: j['vendor_info'] == null ? null : VendorInfo.fromJson(j['vendor_info']),
        items: (j['items'] as List).map((e) => CartItem.fromJson(e)).toList(),
        totalItems: j['total_items'] as int,
        totalAmount: j['total_amount'].toString(),
      );
}
```

### `OrderItem`

```dart
class OrderItem {
  final String id;
  final String productName;
  final String? variantName;
  final int quantity;
  final String unitPrice;
  final String totalPrice;
  final String vendor;   // WAS int. NOW String (VendorProfile UUID).
}
```

### `NegotiatedPrice` (and ranking response)

```dart
class NegotiatedPriceOffer {
  final String productId;
  final String vendorId;            // WAS int. NOW String (VendorProfile UUID).
  final String vendorName;
  …
}
```

### `CreditPurchaseCreateRequest`

```dart
class CreditPurchaseCreateRequest {
  final String vendorId;          // WAS int. NOW String (VendorProfile UUID).
  final String totalAmount;
  final String depositAmount;
  final DateTime? dueDate;
  final int? orderId;

  Map<String, dynamic> toJson() => {
        'vendor_id': vendorId,     // send as string
        'total_amount': totalAmount,
        'deposit_amount': depositAmount,
        if (dueDate != null) 'due_date': dueDate!.toIso8601String().split('T').first,
        if (orderId != null) 'order_id': orderId,
      };
}
```

### `PurchaseOrder` (inventory)

```dart
class PurchaseOrder {
  final String supplier;    // WAS int (User id). NOW String (VendorProfile UUID).
}
```

---

## 4. New 403 cases the app must handle

Several mutating endpoints now require the authenticated user to have a `vendor_profile` row. Handle 403/400 gracefully:

- `POST /api/products/products/` — creating a product without a vendor profile → 403
- `POST /api/payments/subaccounts/` — 403
- `POST /api/negotiations/policy/set-policy/` — 400
- `GET /api/negotiations/policy/my-policy/` — 403
- `POST /api/tiers/subscriptions/subscribe/` — 400
- `GET /api/payments/subaccounts/my-subaccount/` — 404

In practice this only affects vendor users whose `vendor_profile` row was never created. Every new vendor created via `POST /api/accounts/register/` gets one auto-created by a signal.

---

## 5. Where the vendor id comes from — a single source of truth

Whenever Flutter needs a vendor id to pass to the API, the canonical source is:

- **From a product** → `product.vendor` (VendorProfile UUID)
- **From a cart** → `cart.vendor`
- **From an order item** → `orderItem.vendor`
- **From the logged-in vendor themselves** → the backend resolves it server-side from the auth token; clients shouldn't need to send it.
- **From the vendor's user record** → `userDetail.vendorProfile?.id` on `GET /api/accounts/me/`

Do **not** use `User.id` for any vendor-id field anymore. The only exception is `/api/business/addresses/by-user/{user_id}/`, which is still keyed by User id because it serves both customers and vendors.

---

## 6. Migration checklist for the Flutter app

- [ ] Flip every `vendor` / `vendorId` / `supplier` field on affected models from `int` → `String`.
- [ ] Do not `.toString()` blindly on JSON values that are still ints — `j['vendor'].toString()` tolerates both during rollout but write defensive parse (`as String` after full rollout).
- [ ] Update `CreditEligibilityRequest` and `CreditPurchaseCreateRequest` payloads to send string UUIDs for `vendor_id`.
- [ ] Update `PurchaseOrderCreateRequest` to send a VendorProfile UUID for `supplier`.
- [ ] Update `VendorReviewCreateRequest` to send a VendorProfile UUID for `vendor`.
- [ ] Add 403/400 handling for the endpoints in section 4 — show a "complete your vendor profile first" banner.
- [ ] Remove any Dart code that looked up a user by the vendor id returned from these endpoints; treat the id as opaque (a store identifier, not a user identifier).
- [ ] For negotiations UI: treat `vendor_id` in ranking results as a store id. Fetch store details via the `vendor_info` payload or `GET /api/business/profiles/vendor/{vendor_id}/`.

---

## 7. Server-side reference

| Change | File | Migration |
|---|---|---|
| ShoppingCart + OrderItem | `orders/models.py`, `orders/views.py`, `orders/serializers.py`, `orders/admin.py` | `orders.0006` |
| PricePolicy + NegotiatedPrice | `negotiations/models.py`, `negotiations/views.py`, `negotiations/serializers.py`, `negotiations/engine.py`, `negotiations/admin.py` | `negotiations.0003` |
| VendorReview | `products/models.py`, `products/serializers.py`, `products/admin.py` | `products.0015` |
| PaystackSubaccount | `payments/models.py`, `payments/views.py`, `payments/serializers.py`, `payments/admin.py` | `payments.0004` |
| VendorTierSubscription | `tiers/models.py`, `tiers/views.py`, `tiers/serializers.py`, `tiers/admin.py` | `tiers.0004` |
| CreditPurchase | `debit/models.py`, `debit/serializers.py`, `debit/admin.py` | `debit.0005` |
| DeliveryFare | `delivery/models.py`, `delivery/views.py`, `delivery/serializers.py`, `delivery/services.py`, `delivery/admin.py` | `delivery.0004` |
| PurchaseOrder | `inventory/models.py`, `inventory/serializers.py`, `inventory/admin.py` | `inventory.0003` |
| Dual-FK sync retired | `business/signals.py` | — |
| Shared admin helpers (VendorBusinessFilter, label, formfield) | `business/admin_helpers.py` | — |

---

## 8. What did NOT change (still User FKs — unaffected)

These models keep their `User`-based FKs because they don't represent the vendor business; they represent a customer or owner:

- `orders.ShoppingCart.user` (the customer who owns the cart)
- `orders.Order.user` (the customer who placed the order)
- `products.VendorReview.user` (the customer who wrote the review)
- `business.BusinessFollower.user` + `.vendor` — still the User FK (not a store-level concept yet)
- `negotiations.NegotiatedPrice.buyer`
- `debit.CreditAccount.user`
- `delivery.DeliveryFare.customer` + `.driver`

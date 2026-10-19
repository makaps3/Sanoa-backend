# Restaurant App — Flutter API Reference

**Generated:** 2026-05-03  
**Base URL:** `/api/restaurant/`  
**Auth:** `Authorization: Bearer <access_token>` on every request (same JWT as retail)  
**Content-Type:** `application/json`

> **NEW APP** — no prior Flutter code exists for this. Build from scratch.
>
> Two vendor business categories exist on the platform:
> - `retail` → `orders/` app (see `flutter_orders_retail_changes.md`)
> - `restaurant` → `restaurant/` app (this document)

---

## Table of Contents

1. [Enums](#1-enums)
2. [Model Classes](#2-model-classes)
3. [Request Body Helpers](#3-request-body-helpers)
4. [REST Endpoints — Cart](#4-rest-endpoints--cart)
5. [REST Endpoints — Orders (Customer)](#5-rest-endpoints--orders-customer)
6. [REST Endpoints — Kitchen Tickets (Vendor)](#6-rest-endpoints--kitchen-tickets-vendor)
7. [WebSocket — Customer Order Tracking](#7-websocket--customer-order-tracking)
8. [WebSocket — Vendor Kitchen Feed](#8-websocket--vendor-kitchen-feed)
9. [Typical Flows](#9-typical-flows)
10. [Important Notes for Flutter Devs](#10-important-notes-for-flutter-devs)

---

## 1. Enums

### RestaurantOrderStatus

| Dart value | JSON string | Label |
|---|---|---|
| `pending` | `pending` | Pending |
| `confirmed` | `confirmed` | Confirmed |
| `preparing` | `preparing` | Preparing |
| `ready` | `ready` | Ready |
| `outForDelivery` | `out_for_delivery` | Out for Delivery |
| `delivered` | `delivered` | Delivered |
| `completed` | `completed` | Completed |
| `cancelled` | `cancelled` | Cancelled |
| `refunded` | `refunded` | Refunded |

`isActive` = `pending | confirmed | preparing | ready | outForDelivery`

```dart
enum RestaurantOrderStatus {
  pending, confirmed, preparing, ready,
  outForDelivery, delivered, completed, cancelled, refunded;

  static RestaurantOrderStatus fromJson(String v) => switch (v) {
    'out_for_delivery' => outForDelivery,
    'confirmed'        => confirmed,
    'preparing'        => preparing,
    'ready'            => ready,
    'delivered'        => delivered,
    'completed'        => completed,
    'cancelled'        => cancelled,
    'refunded'         => refunded,
    _                  => pending,
  };

  String toJson() => this == outForDelivery ? 'out_for_delivery' : name;

  bool get isActive => index <= outForDelivery.index;
}
```

---

### RestaurantFulfillmentType

> **`dine_in` does NOT exist. Only `delivery` and `pickup`.**

| Dart value | JSON string |
|---|---|
| `delivery` | `delivery` |
| `pickup` | `pickup` |

```dart
enum RestaurantFulfillmentType {
  delivery, pickup;

  static RestaurantFulfillmentType fromJson(String v) =>
      v == 'pickup' ? pickup : delivery;

  String toJson() => name;
}
```

---

### RestaurantPaymentStatus

| Dart value | JSON string |
|---|---|
| `pending` | `pending` |
| `paid` | `paid` |
| `partiallyPaid` | `partially_paid` |
| `failed` | `failed` |
| `refunded` | `refunded` |
| `partiallyRefunded` | `partially_refunded` |

---

### KitchenTicketStatus

| Dart value | JSON string |
|---|---|
| `newTicket` | `new` |
| `acknowledged` | `acknowledged` |
| `preparing` | `preparing` |
| `ready` | `ready` |
| `handedOff` | `handed_off` |

```dart
enum KitchenTicketStatus {
  newTicket, acknowledged, preparing, ready, handedOff;

  static KitchenTicketStatus fromJson(String v) => switch (v) {
    'acknowledged' => acknowledged,
    'preparing'    => preparing,
    'ready'        => ready,
    'handed_off'   => handedOff,
    _              => newTicket,
  };

  String toJson() => switch (this) {
    newTicket  => 'new',
    handedOff  => 'handed_off',
    _          => name,
  };
}
```

---

### RestaurantTrackingEventType

| Dart value | JSON string |
|---|---|
| `orderPlaced` | `order_placed` |
| `paymentConfirmed` | `payment_confirmed` |
| `orderConfirmed` | `order_confirmed` |
| `preparing` | `preparing` |
| `ready` | `ready` |
| `driverAssigned` | `driver_assigned` |
| `driverAtVendor` | `driver_at_vendor` |
| `outForDelivery` | `out_for_delivery` |
| `delivered` | `delivered` |
| `completed` | `completed` |
| `cancelled` | `cancelled` |

---

## 2. Model Classes

### RestaurantAddon

Embedded inside cart items and order items as a JSON array.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `name` | `String` | |
| `priceDelta` | `String` | Decimal string, e.g. `"1.50"` |

```dart
class RestaurantAddon {
  final int id;
  final String name;
  final String priceDelta;

  factory RestaurantAddon.fromJson(Map<String, dynamic> j) => RestaurantAddon(
    id: j['id'] as int,
    name: j['name'] as String,
    priceDelta: j['price_delta'].toString(),
  );

  Map<String, dynamic> toJson() => {'id': id, 'name': name, 'price_delta': priceDelta};
}
```

---

### RestaurantCartItem

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `product` | `int` | Product PK |
| `productVariant` | `int?` | Variant PK, null if base product |
| `quantity` | `int` | |
| `priceAtTime` | `String?` | Base price snapshot, decimal string |
| `addonsTotal` | `String` | Sum of all `priceDelta` values |
| `totalPrice` | `String` | `(priceAtTime + addonsTotal) × quantity` |
| `specialInstructions` | `String` | Empty string if none |
| `selectedAddons` | `List<RestaurantAddon>` | |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory RestaurantCartItem.fromJson(Map<String, dynamic> j) => RestaurantCartItem(
  id: j['id'] as String,
  product: j['product'] as int,
  productVariant: j['product_variant'] as int?,
  quantity: j['quantity'] as int,
  priceAtTime: j['price_at_time']?.toString(),
  totalPrice: j['total_price'].toString(),
  addonsTotal: j['addons_total'].toString(),
  specialInstructions: (j['special_instructions'] ?? '') as String,
  selectedAddons: (j['selected_addons'] as List? ?? [])
      .map((e) => RestaurantAddon.fromJson(e)).toList(),
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### RestaurantCart

One cart per restaurant vendor per user. Multiple carts can coexist (one per vendor).

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `user` | `int` | |
| `vendor` | `int` | |
| `vendorName` | `String?` | `trading_name` or `name` |
| `items` | `List<RestaurantCartItem>` | |
| `totalItems` | `int` | Sum of all item quantities |
| `totalAmount` | `String` | Decimal string |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory RestaurantCart.fromJson(Map<String, dynamic> j) => RestaurantCart(
  id: j['id'] as String,
  user: j['user'] as int,
  vendor: j['vendor'] as int,
  vendorName: j['vendor_name'] as String?,
  items: (j['items'] as List? ?? [])
      .map((e) => RestaurantCartItem.fromJson(e)).toList(),
  totalItems: j['total_items'] as int,
  totalAmount: j['total_amount'].toString(),
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### RestaurantOrderItem

Snapshot of the product at time of order.

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `product` | `int` | |
| `productName` | `String` | Snapshot |
| `productSku` | `String` | Snapshot |
| `productVariant` | `int?` | |
| `variantName` | `String` | Empty string if base product |
| `quantity` | `int` | |
| `unitPrice` | `String` | Base price, decimal string |
| `addonsTotal` | `String` | Stored field, decimal string |
| `totalPrice` | `String` | `(unitPrice + addonsTotal) × quantity` |
| `specialInstructions` | `String` | |
| `selectedAddons` | `List<RestaurantAddon>` | |
| `vendor` | `int` | |
| `createdAt` | `DateTime` | |

```dart
factory RestaurantOrderItem.fromJson(Map<String, dynamic> j) => RestaurantOrderItem(
  id: j['id'] as String,
  product: j['product'] as int,
  productName: j['product_name'] as String,
  productSku: j['product_sku'] as String,
  productVariant: j['product_variant'] as int?,
  variantName: (j['variant_name'] ?? '') as String,
  quantity: j['quantity'] as int,
  unitPrice: j['unit_price'].toString(),
  addonsTotal: j['addons_total'].toString(),
  totalPrice: j['total_price'].toString(),
  specialInstructions: (j['special_instructions'] ?? '') as String,
  selectedAddons: (j['selected_addons'] as List? ?? [])
      .map((e) => RestaurantAddon.fromJson(e)).toList(),
  vendor: j['vendor'] as int,
  createdAt: DateTime.parse(j['created_at']),
);
```

---

### RestaurantTrackingEvent

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `eventType` | `RestaurantTrackingEventType` | |
| `message` | `String` | Human-readable, shown to customer |
| `metadata` | `Map<String, dynamic>` | Extra data, may be empty |
| `createdAt` | `DateTime` | |

```dart
factory RestaurantTrackingEvent.fromJson(Map<String, dynamic> j) => RestaurantTrackingEvent(
  id: j['id'] as String,
  eventType: RestaurantTrackingEventType.fromJson(j['event_type']),
  message: j['message'] as String,
  metadata: (j['metadata'] as Map<String, dynamic>?) ?? {},
  createdAt: DateTime.parse(j['created_at']),
);
```

---

### RestaurantOrderListItem

Lightweight — used for order history lists.

| Field | Type |
|---|---|
| `id` | `String` (UUID) |
| `orderNumber` | `String` |
| `vendor` | `int` |
| `vendorName` | `String?` |
| `status` | `RestaurantOrderStatus` |
| `paymentStatus` | `RestaurantPaymentStatus` |
| `fulfillmentType` | `RestaurantFulfillmentType` |
| `totalAmount` | `String` |
| `itemsCount` | `int` |
| `createdAt` | `DateTime` |

---

### RestaurantOrderDetail

Full order object returned by `GET /orders/{id}/` and on checkout.

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `orderNumber` | `String` | Format: `RST-YYYYMMDD-NNNN` |
| `user` | `int` | |
| `vendor` | `int` | |
| `vendorName` | `String?` | |
| `status` | `RestaurantOrderStatus` | |
| `paymentStatus` | `RestaurantPaymentStatus` | |
| `fulfillmentType` | `RestaurantFulfillmentType` | `delivery` or `pickup` only |
| `estimatedPrepMinutes` | `int?` | Null if vendor hasn't set it |
| `scheduledFor` | `DateTime?` | Null for ASAP orders |
| `subtotal` | `String` | |
| `taxAmount` | `String` | |
| `deliveryFee` | `String` | |
| `discountAmount` | `String` | |
| `totalAmount` | `String` | |
| `customerEmail` | `String` | |
| `customerPhone` | `String` | |
| `shippingAddressId` | `String?` | FK to ShippingAddress; may be null |
| `shippingFullName` | `String` | Address snapshot |
| `shippingStreetAddress` | `String` | Address snapshot |
| `shippingApartmentNumber` | `String` | Address snapshot |
| `shippingCity` | `String` | Address snapshot |
| `shippingStateProvince` | `String` | Address snapshot |
| `shippingPostalCode` | `String` | Address snapshot |
| `shippingCountry` | `String` | Address snapshot |
| `couponCode` | `String` | |
| `orderNotes` | `String` | |
| `internalNotes` | `String` | |
| `confirmedAt` | `DateTime?` | |
| `readyAt` | `DateTime?` | |
| `deliveredAt` | `DateTime?` | |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |
| `hasKitchenTicket` | `bool` | False until vendor confirms order |
| `items` | `List<RestaurantOrderItem>` | |
| `trackingEvents` | `List<RestaurantTrackingEvent>` | Oldest first |

---

### KitchenTicket

Visible to vendor staff only. Auto-created when order transitions to `confirmed`.

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `order` | `String` | RestaurantOrder UUID |
| `orderNumber` | `String` | |
| `status` | `KitchenTicketStatus` | |
| `fulfillmentType` | `RestaurantFulfillmentType` | |
| `estimatedPrepMinutes` | `int?` | |
| `items` | `List<RestaurantOrderItem>` | |
| `acknowledgedAt` | `DateTime?` | |
| `startedAt` | `DateTime?` | |
| `readyAt` | `DateTime?` | |
| `handedOffAt` | `DateTime?` | |
| `notes` | `String` | |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory KitchenTicket.fromJson(Map<String, dynamic> j) => KitchenTicket(
  id: j['id'] as String,
  order: j['order'] as String,
  orderNumber: j['order_number'] as String,
  status: KitchenTicketStatus.fromJson(j['status']),
  fulfillmentType: RestaurantFulfillmentType.fromJson(j['fulfillment_type']),
  estimatedPrepMinutes: j['estimated_prep_minutes'] as int?,
  items: (j['items'] as List? ?? [])
      .map((e) => RestaurantOrderItem.fromJson(e)).toList(),
  acknowledgedAt: j['acknowledged_at'] != null ? DateTime.parse(j['acknowledged_at']) : null,
  startedAt:      j['started_at']      != null ? DateTime.parse(j['started_at'])      : null,
  readyAt:        j['ready_at']        != null ? DateTime.parse(j['ready_at'])        : null,
  handedOffAt:    j['handed_off_at']   != null ? DateTime.parse(j['handed_off_at'])   : null,
  notes: (j['notes'] ?? '') as String,
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

## 3. Request Body Helpers

### Add item to cart

```dart
// POST /api/restaurant/cart/add-item/
Map<String, dynamic> buildAddRestaurantItemBody({
  required int product,
  int? productVariant,
  int quantity = 1,
  String specialInstructions = '',
  List<Map<String, dynamic>> selectedAddons = const [],
  // addon shape: {'id': 3, 'name': 'Extra Cheese', 'price_delta': '1.50'}
}) => {
  'product': product,
  if (productVariant != null) 'product_variant': productVariant,
  'quantity': quantity,
  if (specialInstructions.isNotEmpty) 'special_instructions': specialInstructions,
  if (selectedAddons.isNotEmpty) 'selected_addons': selectedAddons,
};
```

### Create order (checkout)

```dart
// POST /api/restaurant/orders/
Map<String, dynamic> buildCreateRestaurantOrderBody({
  required String cartId,                          // UUID string
  required RestaurantFulfillmentType fulfillmentType,
  String? shippingAddressId,                       // UUID — required for delivery
  String customerEmail = '',
  String customerPhone = '',
  String couponCode = '',
  String orderNotes = '',
  DateTime? scheduledFor,
}) {
  assert(
    fulfillmentType != RestaurantFulfillmentType.delivery || shippingAddressId != null,
    'shippingAddressId is required for delivery orders',
  );
  return {
    'cart_id': cartId,
    'fulfillment_type': fulfillmentType.toJson(),
    if (shippingAddressId != null) 'shipping_address_id': shippingAddressId,
    if (customerEmail.isNotEmpty) 'customer_email': customerEmail,
    if (customerPhone.isNotEmpty) 'customer_phone': customerPhone,
    if (couponCode.isNotEmpty)    'coupon_code': couponCode,
    if (orderNotes.isNotEmpty)    'order_notes': orderNotes,
    if (scheduledFor != null)     'scheduled_for': scheduledFor.toIso8601String(),
  };
}
```

### Update order status (admin/vendor)

```dart
// POST /api/restaurant/orders/{id}/update-status/
Map<String, dynamic> buildUpdateRestaurantOrderStatusBody({
  required RestaurantOrderStatus newStatus,
  String comment = '',
}) => {
  'status': newStatus.toJson(),
  if (comment.isNotEmpty) 'comment': comment,
};
```

---

## 4. REST Endpoints — Cart

### `GET /api/restaurant/cart/my-carts/`

Returns all carts for the current user — one per restaurant vendor.

**Response:** `List<RestaurantCart>`

---

### `GET /api/restaurant/cart/{cart_id}/detail/`

Full cart with items for a specific vendor.

**Response:** `RestaurantCart`

---

### `POST /api/restaurant/cart/add-item/`

Adds a product to the correct vendor cart (auto-creates cart if needed).

**Body:** `buildAddRestaurantItemBody(...)`

**Response:** `RestaurantCart`  
HTTP `201` if a new line was created, `200` if an existing line was merged (quantity incremented).

> Items without addons/instructions that share the same `product + variant` are merged. Items with addons or instructions always create a new line.

---

### `POST /api/restaurant/cart/{cart_id}/increment-item/{item_id}/`

Increments the line item quantity by 1.

**Response:** `RestaurantCart`

---

### `POST /api/restaurant/cart/{cart_id}/decrement-item/{item_id}/`

Decrements quantity by 1. Deletes the item if quantity would reach 0. Deletes the cart if no items remain.

**Response:** `RestaurantCart` or `{"status": "cart_deleted"}`

---

### `POST /api/restaurant/cart/{cart_id}/remove-item/{item_id}/`

Removes the item entirely regardless of quantity. Deletes the cart if no items remain.

**Response:** `RestaurantCart` or `{"status": "cart_deleted"}`

---

### `POST /api/restaurant/cart/{cart_id}/clear/`

Deletes the cart and all its items.

**Response:** `{"status": "cart_deleted"}`

---

## 5. REST Endpoints — Orders (Customer)

### `GET /api/restaurant/orders/`

Paginated order list.

- Customers see their own orders
- Vendor users (`user_type='vendor'`) see orders for their restaurant
- Staff see all

**Response:**
```json
{
  "count": 12,
  "next": "...",
  "previous": null,
  "results": [ /* List<RestaurantOrderListItem> */ ]
}
```

---

### `POST /api/restaurant/orders/`

Checkout — converts the cart into an order and deletes the cart.

**Body:** `buildCreateRestaurantOrderBody(...)`

**Response:** `RestaurantOrderDetail` (HTTP 201)

**Side effects:**
- Cart is deleted
- First tracking event `order_placed` is created and pushed to WebSocket

**Errors:**
- `404` if cart not found or doesn't belong to current user
- `400` if cart is empty
- `400` if `fulfillment_type=delivery` and `shipping_address_id` is missing or not owned by user

---

### `GET /api/restaurant/orders/{id}/`

**Response:** `RestaurantOrderDetail`

---

### `POST /api/restaurant/orders/{id}/cancel/`

Cancel an order. Only allowed when `status` is `pending` or `confirmed`.

**Response:** `RestaurantOrderDetail`

**Errors:**
- `400` if order cannot be cancelled (already preparing, ready, etc.)

---

### `POST /api/restaurant/orders/{id}/update-status/`

Admin or vendor staff only. Moves order through the status flow.

**Body:** `buildUpdateRestaurantOrderStatusBody(...)`

**Response:** `RestaurantOrderDetail`

**Side effects when transitioning to:**
| New status | Side effect |
|---|---|
| `confirmed` | `KitchenTicket` is auto-created |
| `ready` | `order.ready_at` is set |
| `delivered` | `order.delivered_at` is set |
| Any | Tracking event pushed to customer WebSocket |

---

### `GET /api/restaurant/orders/{id}/tracking/`

Full tracking timeline for an order (oldest first).

**Response:** `List<RestaurantTrackingEvent>`

---

## 6. REST Endpoints — Kitchen Tickets (Vendor)

All endpoints require `user_type = 'vendor'` or staff. Regular customers get an empty list.

### `GET /api/restaurant/kitchen/tickets/`

Paginated kitchen ticket list.

**Response:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [ /* List<KitchenTicket> */ ]
}
```

---

### `GET /api/restaurant/kitchen/tickets/{id}/`

**Response:** `KitchenTicket`

---

### `POST /api/restaurant/kitchen/tickets/{id}/acknowledge/`

Marks ticket as `acknowledged`. Only valid from status `new`.

**Response:** `KitchenTicket`

---

### `POST /api/restaurant/kitchen/tickets/{id}/start-preparing/`

Marks ticket as `preparing`. Valid from `new` or `acknowledged`.

**Response:** `KitchenTicket`

**Side effects:**
- `RestaurantOrder.status` → `preparing`
- Tracking event `preparing` pushed to customer WebSocket: *"The kitchen is preparing your order."*

---

### `POST /api/restaurant/kitchen/tickets/{id}/mark-ready/`

Marks ticket as `ready`. Only valid from `preparing`.

**Response:** `KitchenTicket`

**Side effects:**
- `RestaurantOrder.status` → `ready`, `order.ready_at` set
- Tracking event `ready` pushed to customer WebSocket
  - Delivery: *"Your order is ready and waiting for a driver."*
  - Pickup: *"Your order is ready for pickup!"*

---

### `POST /api/restaurant/kitchen/tickets/{id}/hand-off/`

Marks ticket as `handed_off`. Only valid from `ready`.

**Response:** `KitchenTicket`

**Side effects by fulfillment type:**

| Fulfillment | Order status | Tracking event | Message |
|---|---|---|---|
| `delivery` | `out_for_delivery` | `out_for_delivery` | *"Your order is on its way!"* |
| `pickup` | `completed` | `completed` | *"Order ready for pickup. Enjoy!"* |

---

## 7. WebSocket — Customer Order Tracking

**URL:** `ws/restaurant/orders/{order_id}/tracking/`

Replace `{order_id}` with the UUID from `RestaurantOrderDetail.id`.

**Auth:** JWT as query param: `?token=<access_token>`

---

### On Connect — Snapshot

Server immediately sends:

```json
{
  "type": "order_snapshot",
  "order_status": "preparing",
  "tracking_events": [
    {
      "id": "uuid",
      "event_type": "order_placed",
      "message": "Your order has been placed.",
      "metadata": {},
      "created_at": "2026-05-03T12:00:00.000Z"
    }
  ]
}
```

---

### Live Events — `order_update`

Pushed whenever order status changes:

```json
{
  "type": "order_update",
  "event_type": "preparing",
  "message": "The kitchen is preparing your order.",
  "metadata": {},
  "order_status": "preparing",
  "created_at": "2026-05-03T12:10:00.000Z"
}
```

**Events that trigger a push:**

| Event | Triggered by |
|---|---|
| `order_placed` | Order creation |
| `preparing` | Kitchen `start-preparing` |
| `ready` | Kitchen `mark-ready` |
| `out_for_delivery` | Kitchen `hand-off` (delivery) |
| `completed` | Kitchen `hand-off` (pickup) |
| `cancelled` | Customer or vendor cancel |
| Any status | Admin `update-status` |

---

### Dart Parsing Classes

```dart
class RestaurantWsMessage {
  final String type;
  final Map<String, dynamic> raw;

  factory RestaurantWsMessage.fromJson(Map<String, dynamic> j) =>
      RestaurantWsMessage(type: j['type'] as String, raw: j);

  bool get isSnapshot => type == 'order_snapshot';
  bool get isUpdate   => type == 'order_update';
}

class RestaurantOrderSnapshotMessage {
  final RestaurantOrderStatus orderStatus;
  final List<RestaurantTrackingEvent> trackingEvents;

  factory RestaurantOrderSnapshotMessage.fromJson(Map<String, dynamic> j) =>
      RestaurantOrderSnapshotMessage(
        orderStatus: RestaurantOrderStatus.fromJson(j['order_status']),
        trackingEvents: (j['tracking_events'] as List? ?? [])
            .map((e) => RestaurantTrackingEvent.fromJson(e)).toList(),
      );
}

class RestaurantOrderUpdateMessage {
  final RestaurantTrackingEventType eventType;
  final String message;
  final Map<String, dynamic> metadata;
  final RestaurantOrderStatus orderStatus;
  final DateTime createdAt;

  factory RestaurantOrderUpdateMessage.fromJson(Map<String, dynamic> j) =>
      RestaurantOrderUpdateMessage(
        eventType:   RestaurantTrackingEventType.fromJson(j['event_type']),
        message:     j['message'] as String,
        metadata:    (j['metadata'] as Map<String, dynamic>?) ?? {},
        orderStatus: RestaurantOrderStatus.fromJson(j['order_status']),
        createdAt:   DateTime.parse(j['created_at']),
      );
}
```

---

## 8. WebSocket — Vendor Kitchen Feed

**URL:** `ws/restaurant/kitchen/`

**Auth:** Must be a vendor user (`user_type = 'vendor'`). JWT query param: `?token=<access_token>`

---

### On Connect

No snapshot is sent. Server joins the vendor to their kitchen channel group.

---

### Live Events — `new_order`

Pushed when an order transitions to `confirmed` for this vendor:

```json
{
  "type": "new_order",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_number": "RST-20260503-0042",
  "fulfillment_type": "delivery",
  "estimated_prep_minutes": 15,
  "items_count": 3,
  "total_amount": "28.50"
}
```

> `estimated_prep_minutes` may be `null`.

After receiving `new_order`, fetch the full ticket:
```
GET /api/restaurant/kitchen/tickets/
```

---

### Dart Parsing Class

```dart
class KitchenNewOrderMessage {
  final String orderId;
  final String orderNumber;
  final RestaurantFulfillmentType fulfillmentType;
  final int? estimatedPrepMinutes;
  final int itemsCount;
  final String totalAmount;

  factory KitchenNewOrderMessage.fromJson(Map<String, dynamic> j) =>
      KitchenNewOrderMessage(
        orderId:               j['order_id'] as String,
        orderNumber:           j['order_number'] as String,
        fulfillmentType:       RestaurantFulfillmentType.fromJson(j['fulfillment_type']),
        estimatedPrepMinutes:  j['estimated_prep_minutes'] as int?,
        itemsCount:            j['items_count'] as int,
        totalAmount:           j['total_amount'].toString(),
      );
}
```

---

## 9. Typical Flows

### Customer — Place a Delivery Order

```
1. Browse products from a restaurant vendor
2. POST /api/restaurant/cart/add-item/         ← repeat for each item
3. GET  /api/restaurant/cart/my-carts/         ← show cart review screen
4. POST /api/restaurant/orders/                ← checkout (cart deleted on success)
5. Connect WebSocket  ws/restaurant/orders/{order_id}/tracking/
6. Display real-time status updates
7. POST /api/restaurant/orders/{id}/cancel/    ← optional, while status allows
```

### Customer — Pickup Order

Same as delivery but pass `fulfillment_type: 'pickup'` and omit `shipping_address_id`.

### Vendor Kitchen — Process an Order

```
1. Connect WebSocket  ws/restaurant/kitchen/
2. Listen for 'new_order' events
3. GET  /api/restaurant/kitchen/tickets/       ← fetch full ticket details
4. POST .../acknowledge/                       → status: acknowledged
5. POST .../start-preparing/                   → status: preparing  (customer notified)
6. POST .../mark-ready/                        → status: ready      (customer notified)
7. POST .../hand-off/                          → status: handed_off
   ├─ delivery: customer sees "Out for Delivery"
   └─ pickup:   customer sees "Completed"
```

---

## 10. Important Notes for Flutter Devs

### No dine_in
`dine_in` does **not** exist. Only `delivery` and `pickup`. Do not show a "Dine In" option anywhere.

### No table_number
There is no `table_number` field on any model or endpoint.

### Multiple carts
A user can have multiple `RestaurantCart` objects simultaneously — one per restaurant vendor. Design your cart state management to handle a `Map<vendorId, RestaurantCart>`.

### Cart deduplication
- Items **without** addons/special_instructions that match an existing `product + variant` line → quantity is incremented (merged)
- Items **with** addons or instructions → always create a new line

### Addon pricing
- `unit_price` = base product/variant price (does **not** include addons)
- `addons_total` = sum of all `price_delta` values for selected addons
- Displayed effective item price = `unit_price + addons_total`
- Line total = `(unit_price + addons_total) × quantity`

### estimated_prep_minutes
Optional — `null` if the vendor hasn't configured it. Show a countdown timer only when non-null.

### delivered vs completed
| Status | Meaning |
|---|---|
| `delivered` | Delivery orders: driver marked the job complete |
| `completed` | Pickup orders: vendor handed food to customer |

Treat both as "done" in the customer UI.

### hasKitchenTicket
`false` until the vendor confirms the order. Use this flag to conditionally show live-prep progress UI.

### Order number format
Pattern: `RST-YYYYMMDD-NNNN` (e.g. `RST-20260503-0042`). Generated server-side — never set by the client.

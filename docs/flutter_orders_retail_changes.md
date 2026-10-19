# Orders App — Retail-Only Update

**Base URL:** `/api/orders/`

> The `orders/` app is now **strictly for retail orders**.  
> Restaurant ordering has moved to the new `/api/restaurant/` app (see `flutter_restaurant_api.md`).

---

## What Changed

### Removed from `CartItem`

| Removed field | Was |
|---|---|
| `special_instructions` | `String` |
| `selected_addons` | `List<Map>` |
| `addons_total` | Decimal computed property |

`total_price` is now simply `quantity × price_at_time` — no addon calculation.

---

### Removed from `Order`

| Removed | Details |
|---|---|
| `fulfillment_type: 'dine_in'` | Only `delivery` and `pickup` remain |
| `estimated_prep_minutes` | `int?` |
| `scheduled_for` | `DateTime?` |
| `table_number` | `String` |
| Status `received` | Restaurant-only status — removed |
| Status `preparing` | Restaurant-only status — removed |
| Status `ready` | Restaurant-only status — removed |
| Status `out_for_delivery` | Restaurant-only status — removed |
| Status `completed` | Restaurant-only status — removed |

**Remaining statuses:** `pending` \| `processing` \| `shipped` \| `delivered` \| `cancelled` \| `refunded` \| `partially_refunded`

---

### Removed from `OrderItem`

| Removed field | Was |
|---|---|
| `special_instructions` | `String` |
| `selected_addons` | `List<Map>` |

---

### Affected Flutter Screens

| Screen | Action needed |
|---|---|
| `CartPage` | Remove add-on selector; remove special instructions field |
| `CheckoutPage` | Remove `dine_in` option, `table_number`, `scheduled_for` |
| `OrderDetailPage` | Remove prep-time display; remove restaurant-only statuses |
| `OrderStatusChip` | Remove `received`, `preparing`, `ready`, `out_for_delivery`, `completed` |

---

## Enums

### RetailFulfillmentType

> `dine_in` does **not** exist.

| Dart value | JSON string |
|---|---|
| `delivery` | `delivery` |
| `pickup` | `pickup` |

```dart
enum RetailFulfillmentType { delivery, pickup }

RetailFulfillmentType fulfillmentFromString(String v) =>
    RetailFulfillmentType.values.firstWhere(
      (e) => e.name == v,
      orElse: () => RetailFulfillmentType.delivery,
    );
```

---

### RetailOrderStatus

| Dart value | JSON string |
|---|---|
| `pending` | `pending` |
| `processing` | `processing` |
| `shipped` | `shipped` |
| `delivered` | `delivered` |
| `cancelled` | `cancelled` |
| `refunded` | `refunded` |
| `partiallyRefunded` | `partially_refunded` |

```dart
enum RetailOrderStatus {
  pending, processing, shipped, delivered,
  cancelled, refunded, partiallyRefunded,
}

RetailOrderStatus retailStatusFromString(String v) => switch (v) {
  'processing'        => RetailOrderStatus.processing,
  'shipped'           => RetailOrderStatus.shipped,
  'delivered'         => RetailOrderStatus.delivered,
  'cancelled'         => RetailOrderStatus.cancelled,
  'refunded'          => RetailOrderStatus.refunded,
  'partially_refunded'=> RetailOrderStatus.partiallyRefunded,
  _                   => RetailOrderStatus.pending,
};
```

---

## Model Classes

### CartItem

> **Changed:** `special_instructions`, `selected_addons`, `addons_total` removed.  
> `total_price = quantity × price_at_time`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `product` | `int` | |
| `productData` | `Map?` | Expanded product info |
| `productVariant` | `int?` | |
| `quantity` | `int` | |
| `priceAtTime` | `String` | Decimal string |
| `totalPrice` | `String` | `quantity × priceAtTime` |
| `isNegotiated` | `bool` | |
| `originalPrice` | `String?` | |
| `negotiationDirection` | `String?` | |
| `adjustmentPercent` | `String?` | |
| `negotiationStatus` | `String?` | |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory CartItem.fromJson(Map<String, dynamic> j) => CartItem(
  id: j['id'] as int,
  product: j['product'] as int,
  productData: j['product_data'] as Map<String, dynamic>?,
  productVariant: j['product_variant'] as int?,
  quantity: j['quantity'] as int,
  priceAtTime: j['price_at_time'] as String? ?? '0.00',
  totalPrice: j['total_price'] as String? ?? '0.00',
  isNegotiated: j['is_negotiated'] as bool? ?? false,
  originalPrice: j['original_price'] as String?,
  negotiationDirection: j['negotiation_direction'] as String?,
  adjustmentPercent: j['adjustment_percent'] as String?,
  negotiationStatus: j['negotiation_status'] as String?,
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### ShoppingCart

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `user` | `int` | |
| `vendor` | `int` | |
| `vendorEmail` | `String?` | |
| `vendorName` | `String?` | |
| `vendorInfo` | `Map?` | |
| `items` | `List<CartItem>` | |
| `totalItems` | `int` | |
| `totalAmount` | `String` | Decimal string |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |

```dart
factory ShoppingCart.fromJson(Map<String, dynamic> j) => ShoppingCart(
  id: j['id'] as String,
  user: j['user'] as int,
  vendor: j['vendor'] as int,
  vendorEmail: j['vendor_email'] as String?,
  vendorName: j['vendor_name'] as String?,
  vendorInfo: j['vendor_info'] as Map<String, dynamic>?,
  items: (j['items'] as List? ?? []).map((e) => CartItem.fromJson(e)).toList(),
  totalItems: j['total_items'] as int? ?? 0,
  totalAmount: j['total_amount'] as String? ?? '0.00',
  createdAt: DateTime.parse(j['created_at']),
  updatedAt: DateTime.parse(j['updated_at']),
);
```

---

### OrderItem

> **Changed:** `special_instructions` and `selected_addons` removed.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `product` | `int` | |
| `productName` | `String` | Snapshot |
| `productSku` | `String` | Snapshot |
| `productVariant` | `int?` | |
| `variantName` | `String` | Empty string if base product |
| `quantity` | `int` | |
| `unitPrice` | `String` | Decimal string |
| `totalPrice` | `String` | Decimal string |
| `vendor` | `int` | |
| `createdAt` | `DateTime` | |

```dart
factory OrderItem.fromJson(Map<String, dynamic> j) => OrderItem(
  id: j['id'] as int,
  product: j['product'] as int,
  productName: j['product_name'] as String,
  productSku: j['product_sku'] as String,
  productVariant: j['product_variant'] as int?,
  variantName: j['variant_name'] as String? ?? '',
  quantity: j['quantity'] as int,
  unitPrice: j['unit_price'] as String,
  totalPrice: j['total_price'] as String,
  vendor: j['vendor'] as int,
  createdAt: DateTime.parse(j['created_at']),
);
```

---

### OrderStatusHistory

| Field | Type |
|---|---|
| `id` | `int` |
| `order` | `String` (UUID) |
| `previousStatus` | `String` |
| `newStatus` | `String` |
| `changedBy` | `int?` |
| `changedByEmail` | `String?` |
| `comment` | `String` |
| `createdAt` | `DateTime` |

---

### OrderListItem

| Field | Type |
|---|---|
| `id` | `String` (UUID) |
| `orderNumber` | `String` |
| `userEmail` | `String` |
| `status` | `RetailOrderStatus` |
| `paymentStatus` | `String` |
| `totalAmount` | `String` |
| `itemsCount` | `int` |
| `vendorId` | `String?` |
| `vendorName` | `String?` |
| `fulfillmentType` | `RetailFulfillmentType` |
| `createdAt` | `DateTime` |

---

### OrderDetail

> **Changed:** `fulfillment_type` no longer has `dine_in`. `estimated_prep_minutes`, `scheduled_for`, `table_number` removed.

| Field | Type | Notes |
|---|---|---|
| `id` | `String` | UUID |
| `orderNumber` | `String` | |
| `user` | `int` | |
| `userEmail` | `String` | |
| `status` | `RetailOrderStatus` | |
| `paymentStatus` | `String` | |
| `vendorId` | `String?` | |
| `vendorName` | `String?` | |
| `subtotal` | `String` | |
| `taxAmount` | `String` | |
| `shippingCost` | `String` | |
| `discountAmount` | `String` | |
| `totalAmount` | `String` | |
| `customerEmail` | `String` | |
| `customerPhone` | `String` | |
| `billingFullName` | `String` | |
| `billingStreetAddress` | `String` | |
| `billingCity` | `String` | |
| `billingStateProvince` | `String` | |
| `billingPostalCode` | `String` | |
| `billingCountry` | `String` | |
| `shippingAddress` | `String?` | FK reference |
| `shippingFullName` | `String` | Snapshot |
| `shippingStreetAddress` | `String` | Snapshot |
| `shippingCity` | `String` | Snapshot |
| `shippingStateProvince` | `String` | Snapshot |
| `shippingPostalCode` | `String` | Snapshot |
| `shippingCountry` | `String` | Snapshot |
| `fulfillmentType` | `RetailFulfillmentType` | `delivery` or `pickup` only |
| `couponCode` | `String` | |
| `orderNotes` | `String` | |
| `shippedAt` | `DateTime?` | |
| `deliveredAt` | `DateTime?` | |
| `createdAt` | `DateTime` | |
| `updatedAt` | `DateTime` | |
| `items` | `List<OrderItem>` | |
| `statusHistory` | `List<OrderStatusHistory>` | |

---

## Request Body Helpers

### Add item to cart

> **Changed:** body no longer accepts `special_instructions` or `selected_addons`.

```dart
// POST /api/orders/cart/add-item/
Map<String, dynamic> buildAddItemBody({
  required int productId,
  int? productVariantId,
  int quantity = 1,
  String? negotiationId,
}) => {
  'product': productId,
  if (productVariantId != null) 'product_variant': productVariantId,
  'quantity': quantity,
  if (negotiationId != null) 'negotiation_id': negotiationId,
};
```

### Create order

> **Changed:** `fulfillment_type` is `delivery | pickup` only (no `dine_in`). `table_number` and `scheduled_for` removed.

```dart
// POST /api/orders/orders/
Map<String, dynamic> buildCreateOrderBody({
  required String cartId,
  required String customerEmail,
  String customerPhone = '',
  String fulfillmentType = 'delivery',  // 'delivery' | 'pickup'
  String? shippingAddressId,            // required when fulfillmentType == 'delivery'
  String couponCode = '',
  String orderNotes = '',
}) => {
  'cart_id': cartId,
  'customer_email': customerEmail,
  if (customerPhone.isNotEmpty)    'customer_phone': customerPhone,
  'fulfillment_type': fulfillmentType,
  if (shippingAddressId != null)   'shipping_address_id': shippingAddressId,
  if (couponCode.isNotEmpty)       'coupon_code': couponCode,
  if (orderNotes.isNotEmpty)       'order_notes': orderNotes,
};
```

### Update order status (admin only)

```dart
// POST /api/orders/orders/{id}/update-status/
Map<String, dynamic> buildUpdateStatusBody({
  required String status,
  // pending | processing | shipped | delivered | cancelled | refunded | partially_refunded
  String comment = '',
}) => {
  'status': status,
  if (comment.isNotEmpty) 'comment': comment,
};
```

---

## REST Endpoints

All URLs are unchanged — only the request/response fields changed.

### Cart

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/orders/cart/my-carts/` | `List<ShoppingCart>` |
| `GET` | `/api/orders/cart/{cartId}/detail/` | `ShoppingCart` |
| `POST` | `/api/orders/cart/add-item/` | `ShoppingCart` |
| `POST` | `/api/orders/cart/{cartId}/increment-item/{itemId}/` | `ShoppingCart` |
| `POST` | `/api/orders/cart/{cartId}/decrement-item/{itemId}/` | `ShoppingCart` or `{"status":"cart_deleted"}` |
| `POST` | `/api/orders/cart/{cartId}/remove-item/{itemId}/` | `ShoppingCart` or `{"status":"cart_deleted"}` |
| `POST` | `/api/orders/cart/{cartId}/clear/` | `{"status":"cart_deleted"}` |

### Orders

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/orders/orders/` | Paginated `OrderListItem` |
| `POST` | `/api/orders/orders/` | `OrderDetail` (HTTP 201) |
| `GET` | `/api/orders/orders/{id}/` | `OrderDetail` |
| `POST` | `/api/orders/orders/{id}/cancel/` | `OrderDetail` |
| `POST` | `/api/orders/orders/{id}/update-status/` | `OrderDetail` (admin only) |

### Shipping Addresses

| Method | URL | Returns |
|---|---|---|
| `GET` | `/api/orders/shipping-addresses/` | `List<ShippingAddress>` |
| `POST` | `/api/orders/shipping-addresses/` | `ShippingAddress` |
| `PUT` | `/api/orders/shipping-addresses/{id}/` | `ShippingAddress` |
| `DELETE` | `/api/orders/shipping-addresses/{id}/` | `204 No Content` |
| `POST` | `/api/orders/shipping-addresses/{id}/set_default/` | `ShippingAddress` |

### Coupons

| Method | URL | Returns |
|---|---|---|
| `POST` | `/api/orders/coupons/validate/` | `CouponValidationResult` |

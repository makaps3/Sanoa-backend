# Sanoa Orders API - Complete Documentation

> **Base URL:** `https://your-domain.com/api/orders/`
>
> **Authentication:** JWT Bearer Token
>
> **Header:** `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Shopping Cart](#1-shopping-cart)
2. [Orders](#2-orders)
3. [Coupons](#3-coupons)
4. [Dart Models](#4-dart-models)
5. [Dart API Service](#5-dart-api-service)

---

## 1. Shopping Cart

Multi-vendor cart system. Each cart is tied to **one vendor** — adding items from different vendors creates separate carts. A user can have up to **3 active carts** at a time.

### 1.1 List My Carts

```
GET /api/orders/cart/my-carts/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "user": 3,
    "vendor": 5,
    "vendor_email": "vendor@example.com",
    "vendor_name": "TechStore SA",
    "items": [
      {
        "id": 10,
        "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "product_data": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "name": "Wireless Earbuds",
          "slug": "wireless-earbuds",
          "category_name": "Electronics",
          "brand_name": "Samsung",
          "price": "299.99",
          "compare_at_price": "399.99",
          "discount_percentage": "25.01",
          "is_featured": true,
          "primary_image": null,
          "average_rating": "4.50",
          "review_count": 12,
          "likes_count": 45,
          "sales_count": 100,
          "status": "active",
          "qr_code": null
        },
        "product_variant": null,
        "quantity": 2,
        "price_at_time": "299.99",
        "total_price": "599.98",
        "created_at": "2026-03-20T10:00:00Z",
        "updated_at": "2026-03-20T10:00:00Z"
      }
    ],
    "total_items": 2,
    "total_amount": "599.98",
    "created_at": "2026-03-20T09:55:00Z",
    "updated_at": "2026-03-20T10:00:00Z"
  }
]
```

### 1.2 Get Cart Detail

```
GET /api/orders/cart/{cart_id}/detail/
```

**Auth:** Authenticated (own carts only)

**Response `200 OK`:** Single cart object (same shape as list item).

### 1.3 Add Item to Cart

```
POST /api/orders/cart/add-item/
```

**Auth:** Authenticated

Automatically routes the item to the correct vendor cart. Creates a new cart if one doesn't exist for that vendor. If the item already exists in the cart, its quantity is incremented.

| Field           | Type    | Required | Description                                       |
|-----------------|---------|----------|---------------------------------------------------|
| product         | UUID    | Yes      | Product ID                                        |
| product_variant | integer | No       | Product variant ID (if ordering a specific variant)|
| quantity        | integer | No       | Quantity to add. Default: `1`                     |

**Response `201 Created`** (new item) or **`200 OK`** (quantity updated): The full cart object.

**Response `400 Bad Request`** (max carts reached):

```json
{
  "error": "You can only have 3 active carts. Please clear or checkout an existing cart before adding items from a new vendor.",
  "current_carts": 3
}
```

### 1.4 Remove Item from Cart

```
POST /api/orders/cart/{cart_id}/remove-item/{item_id}/
```

**Auth:** Authenticated (own carts only)

Removes the specified item. If the cart becomes empty, it is automatically deleted.

**Response `200 OK`:** Updated cart object, or:

```json
{
  "status": "cart_deleted",
  "message": "Cart was empty and has been removed."
}
```

### 1.5 Clear Cart

```
POST /api/orders/cart/{cart_id}/clear/
```

**Auth:** Authenticated (own carts only)

Deletes all items and the cart itself.

**Response `200 OK`:**

```json
{ "status": "cart_deleted" }
```

---

## 2. Orders

### 2.1 List Orders

```
GET /api/orders/orders/
```

**Auth:** Authenticated (users see own orders; staff see all)

**Pagination:** 20 per page (max 100). Query params: `page`, `page_size`.

**Filter Query Params:**

| Param             | Type     | Description                           |
|-------------------|----------|---------------------------------------|
| status            | string   | `pending`, `processing`, `shipped`, `delivered`, `cancelled`, `refunded`, `partially_refunded` |
| payment_status    | string   | `pending`, `paid`, `partially_paid`, `failed`, `refunded`, `partially_refunded` |
| created_date_from | datetime | Orders created on or after (ISO 8601) |
| created_date_to   | datetime | Orders created on or before           |
| amount_min        | number   | Minimum total_amount                  |
| amount_max        | number   | Maximum total_amount                  |

**Response `200 OK`:**

```json
{
  "count": 42,
  "next": "https://domain.com/api/orders/orders/?page=2",
  "previous": null,
  "page_size": 20,
  "total_pages": 3,
  "current_page": 1,
  "results": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "order_number": "ORD-20260320-0001",
      "user_email": "customer@example.com",
      "status": "pending",
      "payment_status": "pending",
      "total_amount": "599.98",
      "items_count": 2,
      "created_at": "2026-03-20T11:00:00Z"
    }
  ]
}
```

### 2.2 Retrieve Order

```
GET /api/orders/orders/{id}/
```

**Auth:** Authenticated (own orders or staff)

**Response `200 OK`:**

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "order_number": "ORD-20260320-0001",
  "user": 3,
  "user_email": "customer@example.com",
  "status": "pending",
  "payment_status": "pending",
  "subtotal": "599.98",
  "tax_amount": "0.00",
  "shipping_cost": "50.00",
  "discount_amount": "0.00",
  "total_amount": "649.98",
  "customer_email": "customer@example.com",
  "customer_phone": "+27821234567",
  "billing_full_name": "John Doe",
  "billing_street_address": "123 Main Rd",
  "billing_apartment_number": "Apt 4B",
  "billing_city": "Johannesburg",
  "billing_state_province": "Gauteng",
  "billing_postal_code": "2000",
  "billing_country": "South Africa",
  "shipping_full_name": "John Doe",
  "shipping_street_address": "123 Main Rd",
  "shipping_apartment_number": "Apt 4B",
  "shipping_city": "Johannesburg",
  "shipping_state_province": "Gauteng",
  "shipping_postal_code": "2000",
  "shipping_country": "South Africa",
  "coupon_code": "",
  "order_notes": "Please leave at the gate",
  "internal_notes": "",
  "shipped_at": null,
  "delivered_at": null,
  "items": [
    {
      "id": 1,
      "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "product_name": "Wireless Earbuds",
      "product_sku": "SKU-A1B2C3D4",
      "product_variant": null,
      "variant_name": "",
      "quantity": 2,
      "unit_price": "299.99",
      "total_price": "599.98",
      "vendor": 5,
      "created_at": "2026-03-20T11:00:00Z"
    }
  ],
  "status_history": [
    {
      "id": 1,
      "order": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "previous_status": "",
      "new_status": "pending",
      "changed_by": null,
      "changed_by_email": null,
      "comment": "Order created",
      "created_at": "2026-03-20T11:00:00Z"
    }
  ],
  "created_at": "2026-03-20T11:00:00Z",
  "updated_at": "2026-03-20T11:00:00Z"
}
```

### 2.3 Create Order

```
POST /api/orders/orders/
```

**Auth:** Authenticated

Creates a new order. The `order_number` is auto-generated in the format `ORD-YYYYMMDD-NNNN`.

| Field                       | Type   | Required | Description                          |
|-----------------------------|--------|----------|--------------------------------------|
| customer_email              | string | Yes      | Customer's email for this order      |
| customer_phone              | string | No       | Customer's phone number              |
| billing_full_name           | string | Yes      | Billing name                         |
| billing_street_address      | string | Yes      | Billing street address               |
| billing_apartment_number    | string | No       | Billing apt/unit number              |
| billing_city                | string | Yes      | Billing city                         |
| billing_state_province      | string | Yes      | Billing state/province               |
| billing_postal_code         | string | Yes      | Billing postal code                  |
| billing_country             | string | Yes      | Billing country                      |
| shipping_full_name          | string | Yes      | Shipping name                        |
| shipping_street_address     | string | Yes      | Shipping street address              |
| shipping_apartment_number   | string | No       | Shipping apt/unit number             |
| shipping_city               | string | Yes      | Shipping city                        |
| shipping_state_province     | string | Yes      | Shipping state/province              |
| shipping_postal_code        | string | Yes      | Shipping postal code                 |
| shipping_country            | string | Yes      | Shipping country                     |
| coupon_code                 | string | No       | Coupon/discount code to apply        |
| order_notes                 | string | No       | Customer-facing notes                |

**Response `201 Created`:** The created order (detail serializer shape).

### 2.4 Update Order

```
PUT /api/orders/orders/{id}/
PATCH /api/orders/orders/{id}/
```

**Auth:** Authenticated

Writable fields: `status`, `payment_status`, `shipping_cost`, `customer_email`, `customer_phone`, billing address fields, shipping address fields, `coupon_code`, `order_notes`, `internal_notes`.

Read-only fields: `id`, `order_number`, `subtotal`, `tax_amount`, `discount_amount`, `total_amount`, `shipped_at`, `delivered_at`, `created_at`, `updated_at`.

### 2.5 Delete Order

```
DELETE /api/orders/orders/{id}/
```

**Auth:** Authenticated

**Response `204 No Content`**

### 2.6 Cancel Order

```
POST /api/orders/orders/{id}/cancel/
```

**Auth:** Authenticated (own orders)

Can only cancel orders with status `pending` or `processing`. Automatically creates a status history entry.

**Response `200 OK`:** Updated order detail object with `status: "cancelled"`.

**Response `400 Bad Request`:**

```json
{ "error": "This order cannot be cancelled." }
```

### 2.7 Update Order Status (Admin)

```
POST /api/orders/orders/{id}/update_status/
```

**Auth:** Admin only

Updates the order status and creates a status history entry. Automatically sets `shipped_at` or `delivered_at` timestamps when applicable.

| Field   | Type   | Required | Description                                                                                   |
|---------|--------|----------|-----------------------------------------------------------------------------------------------|
| status  | string | Yes      | `pending`, `processing`, `shipped`, `delivered`, `cancelled`, `refunded`, `partially_refunded` |
| comment | string | No       | Reason or note for the status change                                                          |

**Response `200 OK`:** Updated order detail object.

**Response `400 Bad Request`:**

```json
{ "error": "Invalid status. Must be one of: ['pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded', 'partially_refunded']" }
```

---

## 3. Coupons

All CRUD endpoints are **admin-only** except the validate endpoint.

### 3.1 List Coupons (Admin)

```
GET /api/orders/coupons/
```

**Auth:** Admin only

**Search:** `?search=` searches in `code` and `name`.

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "code": "SAVE20",
    "name": "Save 20%",
    "description": "Get 20% off your order",
    "coupon_type": "percentage",
    "value": "20.00",
    "minimum_order_amount": "100.00",
    "max_uses": 500,
    "max_uses_per_user": 1,
    "usage_count": 42,
    "start_date": "2026-03-01T00:00:00Z",
    "end_date": "2026-04-30T23:59:59Z",
    "is_active": true,
    "created_at": "2026-02-28T10:00:00Z",
    "updated_at": "2026-03-15T08:00:00Z"
  }
]
```

### 3.2 Retrieve Coupon (Admin)

```
GET /api/orders/coupons/{id}/
```

**Auth:** Admin only

### 3.3 Create Coupon (Admin)

```
POST /api/orders/coupons/
```

**Auth:** Admin only

| Field                | Type     | Required | Description                                                      |
|----------------------|----------|----------|------------------------------------------------------------------|
| code                 | string   | Yes      | Unique coupon code (max 50 chars)                                |
| name                 | string   | Yes      | Coupon display name                                              |
| description          | string   | No       | Coupon description                                               |
| coupon_type          | string   | No       | `percentage` (default), `fixed_amount`, `free_shipping`          |
| value                | decimal  | Yes      | Percentage (0-100) or fixed amount in Rands                      |
| minimum_order_amount | decimal  | No       | Minimum order total required to use coupon                       |
| max_uses             | integer  | No       | Total usage limit (`null` = unlimited)                           |
| max_uses_per_user    | integer  | No       | Per-user limit. Default: `1`                                     |
| start_date           | datetime | Yes      | Coupon becomes valid (ISO 8601)                                  |
| end_date             | datetime | No       | Coupon expires (`null` = no expiry)                              |
| is_active            | boolean  | No       | Default: `true`                                                  |

**Response `201 Created`:** The created coupon object.

### 3.4 Update Coupon (Admin)

```
PUT /api/orders/coupons/{id}/
PATCH /api/orders/coupons/{id}/
```

**Auth:** Admin only

### 3.5 Delete Coupon (Admin)

```
DELETE /api/orders/coupons/{id}/
```

**Auth:** Admin only

**Response `204 No Content`**

### 3.6 Validate Coupon

```
POST /api/orders/coupons/validate/
```

**Auth:** Authenticated (any user)

Validates a coupon code against the current user and optional order amount. Checks: active status, date validity, usage limits (global and per-user), and minimum order amount.

| Field        | Type    | Required | Description                          |
|--------------|---------|----------|--------------------------------------|
| code         | string  | Yes      | Coupon code to validate              |
| order_amount | decimal | No       | Current order total (for min checks) |

**Response `200 OK` (valid):**

```json
{
  "valid": true,
  "message": "Coupon is valid",
  "coupon": {
    "id": 1,
    "code": "SAVE20",
    "name": "Save 20%",
    "description": "Get 20% off your order",
    "coupon_type": "percentage",
    "value": "20.00",
    "minimum_order_amount": "100.00",
    "max_uses": 500,
    "max_uses_per_user": 1,
    "usage_count": 42,
    "start_date": "2026-03-01T00:00:00Z",
    "end_date": "2026-04-30T23:59:59Z",
    "is_active": true,
    "created_at": "2026-02-28T10:00:00Z",
    "updated_at": "2026-03-15T08:00:00Z"
  },
  "discount_amount": "40.00"
}
```

**Response `200 OK` (invalid):**

```json
{
  "valid": false,
  "message": "Coupon has expired"
}
```

**Response `404 Not Found`:**

```json
{
  "valid": false,
  "message": "Coupon not found"
}
```

---

## 4. Dart Models

```dart
// ═══════════════════════════════════════════════════════════════════════
// Cart Item
// ═══════════════════════════════════════════════════════════════════════

class CartItem {
  final int id;
  final String product;
  final Map<String, dynamic>? productData;
  final int? productVariant;
  final int quantity;
  final double priceAtTime;
  final double totalPrice;
  final DateTime createdAt;
  final DateTime updatedAt;

  CartItem({
    required this.id,
    required this.product,
    this.productData,
    this.productVariant,
    required this.quantity,
    required this.priceAtTime,
    required this.totalPrice,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CartItem.fromJson(Map<String, dynamic> json) {
    return CartItem(
      id: json['id'],
      product: json['product'].toString(),
      productData: json['product_data'],
      productVariant: json['product_variant'],
      quantity: json['quantity'],
      priceAtTime: double.parse(json['price_at_time'].toString()),
      totalPrice: double.parse(json['total_price'].toString()),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'product': product,
    if (productVariant != null) 'product_variant': productVariant,
    'quantity': quantity,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Shopping Cart
// ═══════════════════════════════════════════════════════════════════════

class ShoppingCart {
  final int id;
  final int user;
  final int vendor;
  final String vendorEmail;
  final String vendorName;
  final List<CartItem> items;
  final int totalItems;
  final double totalAmount;
  final DateTime createdAt;
  final DateTime updatedAt;

  ShoppingCart({
    required this.id,
    required this.user,
    required this.vendor,
    required this.vendorEmail,
    required this.vendorName,
    required this.items,
    required this.totalItems,
    required this.totalAmount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ShoppingCart.fromJson(Map<String, dynamic> json) {
    return ShoppingCart(
      id: json['id'],
      user: json['user'],
      vendor: json['vendor'],
      vendorEmail: json['vendor_email'],
      vendorName: json['vendor_name'],
      items: (json['items'] as List).map((e) => CartItem.fromJson(e)).toList(),
      totalItems: json['total_items'],
      totalAmount: double.parse(json['total_amount'].toString()),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Order Item
// ═══════════════════════════════════════════════════════════════════════

class OrderItem {
  final int id;
  final String product;
  final String productName;
  final String productSku;
  final int? productVariant;
  final String variantName;
  final int quantity;
  final double unitPrice;
  final double totalPrice;
  final int vendor;
  final DateTime createdAt;

  OrderItem({
    required this.id,
    required this.product,
    required this.productName,
    required this.productSku,
    this.productVariant,
    required this.variantName,
    required this.quantity,
    required this.unitPrice,
    required this.totalPrice,
    required this.vendor,
    required this.createdAt,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) {
    return OrderItem(
      id: json['id'],
      product: json['product'].toString(),
      productName: json['product_name'],
      productSku: json['product_sku'],
      productVariant: json['product_variant'],
      variantName: json['variant_name'] ?? '',
      quantity: json['quantity'],
      unitPrice: double.parse(json['unit_price'].toString()),
      totalPrice: double.parse(json['total_price'].toString()),
      vendor: json['vendor'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Order Status History
// ═══════════════════════════════════════════════════════════════════════

class OrderStatusHistory {
  final int id;
  final String order;
  final String previousStatus;
  final String newStatus;
  final int? changedBy;
  final String? changedByEmail;
  final String comment;
  final DateTime createdAt;

  OrderStatusHistory({
    required this.id,
    required this.order,
    required this.previousStatus,
    required this.newStatus,
    this.changedBy,
    this.changedByEmail,
    required this.comment,
    required this.createdAt,
  });

  factory OrderStatusHistory.fromJson(Map<String, dynamic> json) {
    return OrderStatusHistory(
      id: json['id'],
      order: json['order'].toString(),
      previousStatus: json['previous_status'] ?? '',
      newStatus: json['new_status'],
      changedBy: json['changed_by'],
      changedByEmail: json['changed_by_email'],
      comment: json['comment'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Order (List view - lightweight)
// ═══════════════════════════════════════════════════════════════════════

class OrderListItem {
  final String id;
  final String orderNumber;
  final String userEmail;
  final String status;
  final String paymentStatus;
  final double totalAmount;
  final int itemsCount;
  final DateTime createdAt;

  OrderListItem({
    required this.id,
    required this.orderNumber,
    required this.userEmail,
    required this.status,
    required this.paymentStatus,
    required this.totalAmount,
    required this.itemsCount,
    required this.createdAt,
  });

  factory OrderListItem.fromJson(Map<String, dynamic> json) {
    return OrderListItem(
      id: json['id'],
      orderNumber: json['order_number'],
      userEmail: json['user_email'],
      status: json['status'],
      paymentStatus: json['payment_status'],
      totalAmount: double.parse(json['total_amount'].toString()),
      itemsCount: json['items_count'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Order (Detail view - full)
// ═══════════════════════════════════════════════════════════════════════

class OrderDetail {
  final String id;
  final String orderNumber;
  final int user;
  final String userEmail;
  final String status;
  final String paymentStatus;

  // Pricing
  final double subtotal;
  final double taxAmount;
  final double shippingCost;
  final double discountAmount;
  final double totalAmount;

  // Customer info
  final String customerEmail;
  final String customerPhone;

  // Billing address
  final String billingFullName;
  final String billingStreetAddress;
  final String billingApartmentNumber;
  final String billingCity;
  final String billingStateProvince;
  final String billingPostalCode;
  final String billingCountry;

  // Shipping address
  final String shippingFullName;
  final String shippingStreetAddress;
  final String shippingApartmentNumber;
  final String shippingCity;
  final String shippingStateProvince;
  final String shippingPostalCode;
  final String shippingCountry;

  // Additional
  final String couponCode;
  final String orderNotes;
  final String internalNotes;

  // Tracking
  final DateTime? shippedAt;
  final DateTime? deliveredAt;

  // Related
  final List<OrderItem> items;
  final List<OrderStatusHistory> statusHistory;

  final DateTime createdAt;
  final DateTime updatedAt;

  OrderDetail({
    required this.id,
    required this.orderNumber,
    required this.user,
    required this.userEmail,
    required this.status,
    required this.paymentStatus,
    required this.subtotal,
    required this.taxAmount,
    required this.shippingCost,
    required this.discountAmount,
    required this.totalAmount,
    required this.customerEmail,
    required this.customerPhone,
    required this.billingFullName,
    required this.billingStreetAddress,
    required this.billingApartmentNumber,
    required this.billingCity,
    required this.billingStateProvince,
    required this.billingPostalCode,
    required this.billingCountry,
    required this.shippingFullName,
    required this.shippingStreetAddress,
    required this.shippingApartmentNumber,
    required this.shippingCity,
    required this.shippingStateProvince,
    required this.shippingPostalCode,
    required this.shippingCountry,
    required this.couponCode,
    required this.orderNotes,
    required this.internalNotes,
    this.shippedAt,
    this.deliveredAt,
    required this.items,
    required this.statusHistory,
    required this.createdAt,
    required this.updatedAt,
  });

  factory OrderDetail.fromJson(Map<String, dynamic> json) {
    return OrderDetail(
      id: json['id'],
      orderNumber: json['order_number'],
      user: json['user'],
      userEmail: json['user_email'],
      status: json['status'],
      paymentStatus: json['payment_status'],
      subtotal: double.parse(json['subtotal'].toString()),
      taxAmount: double.parse(json['tax_amount'].toString()),
      shippingCost: double.parse(json['shipping_cost'].toString()),
      discountAmount: double.parse(json['discount_amount'].toString()),
      totalAmount: double.parse(json['total_amount'].toString()),
      customerEmail: json['customer_email'],
      customerPhone: json['customer_phone'] ?? '',
      billingFullName: json['billing_full_name'],
      billingStreetAddress: json['billing_street_address'],
      billingApartmentNumber: json['billing_apartment_number'] ?? '',
      billingCity: json['billing_city'],
      billingStateProvince: json['billing_state_province'],
      billingPostalCode: json['billing_postal_code'],
      billingCountry: json['billing_country'],
      shippingFullName: json['shipping_full_name'],
      shippingStreetAddress: json['shipping_street_address'],
      shippingApartmentNumber: json['shipping_apartment_number'] ?? '',
      shippingCity: json['shipping_city'],
      shippingStateProvince: json['shipping_state_province'],
      shippingPostalCode: json['shipping_postal_code'],
      shippingCountry: json['shipping_country'],
      couponCode: json['coupon_code'] ?? '',
      orderNotes: json['order_notes'] ?? '',
      internalNotes: json['internal_notes'] ?? '',
      shippedAt: json['shipped_at'] != null ? DateTime.parse(json['shipped_at']) : null,
      deliveredAt: json['delivered_at'] != null ? DateTime.parse(json['delivered_at']) : null,
      items: (json['items'] as List).map((e) => OrderItem.fromJson(e)).toList(),
      statusHistory: (json['status_history'] as List)
          .map((e) => OrderStatusHistory.fromJson(e))
          .toList(),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Order Create Request
// ═══════════════════════════════════════════════════════════════════════

class OrderCreateRequest {
  final String customerEmail;
  final String? customerPhone;

  // Billing
  final String billingFullName;
  final String billingStreetAddress;
  final String? billingApartmentNumber;
  final String billingCity;
  final String billingStateProvince;
  final String billingPostalCode;
  final String billingCountry;

  // Shipping
  final String shippingFullName;
  final String shippingStreetAddress;
  final String? shippingApartmentNumber;
  final String shippingCity;
  final String shippingStateProvince;
  final String shippingPostalCode;
  final String shippingCountry;

  // Optional
  final String? couponCode;
  final String? orderNotes;

  OrderCreateRequest({
    required this.customerEmail,
    this.customerPhone,
    required this.billingFullName,
    required this.billingStreetAddress,
    this.billingApartmentNumber,
    required this.billingCity,
    required this.billingStateProvince,
    required this.billingPostalCode,
    required this.billingCountry,
    required this.shippingFullName,
    required this.shippingStreetAddress,
    this.shippingApartmentNumber,
    required this.shippingCity,
    required this.shippingStateProvince,
    required this.shippingPostalCode,
    required this.shippingCountry,
    this.couponCode,
    this.orderNotes,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'customer_email': customerEmail,
      'billing_full_name': billingFullName,
      'billing_street_address': billingStreetAddress,
      'billing_city': billingCity,
      'billing_state_province': billingStateProvince,
      'billing_postal_code': billingPostalCode,
      'billing_country': billingCountry,
      'shipping_full_name': shippingFullName,
      'shipping_street_address': shippingStreetAddress,
      'shipping_city': shippingCity,
      'shipping_state_province': shippingStateProvince,
      'shipping_postal_code': shippingPostalCode,
      'shipping_country': shippingCountry,
    };
    if (customerPhone != null) map['customer_phone'] = customerPhone;
    if (billingApartmentNumber != null) map['billing_apartment_number'] = billingApartmentNumber;
    if (shippingApartmentNumber != null) map['shipping_apartment_number'] = shippingApartmentNumber;
    if (couponCode != null) map['coupon_code'] = couponCode;
    if (orderNotes != null) map['order_notes'] = orderNotes;
    return map;
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Coupon
// ═══════════════════════════════════════════════════════════════════════

class Coupon {
  final int id;
  final String code;
  final String name;
  final String description;
  final String couponType;
  final double value;
  final double? minimumOrderAmount;
  final int? maxUses;
  final int maxUsesPerUser;
  final int usageCount;
  final DateTime startDate;
  final DateTime? endDate;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;

  Coupon({
    required this.id,
    required this.code,
    required this.name,
    required this.description,
    required this.couponType,
    required this.value,
    this.minimumOrderAmount,
    this.maxUses,
    required this.maxUsesPerUser,
    required this.usageCount,
    required this.startDate,
    this.endDate,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Coupon.fromJson(Map<String, dynamic> json) {
    return Coupon(
      id: json['id'],
      code: json['code'],
      name: json['name'],
      description: json['description'] ?? '',
      couponType: json['coupon_type'],
      value: double.parse(json['value'].toString()),
      minimumOrderAmount: json['minimum_order_amount'] != null
          ? double.parse(json['minimum_order_amount'].toString())
          : null,
      maxUses: json['max_uses'],
      maxUsesPerUser: json['max_uses_per_user'],
      usageCount: json['usage_count'],
      startDate: DateTime.parse(json['start_date']),
      endDate: json['end_date'] != null ? DateTime.parse(json['end_date']) : null,
      isActive: json['is_active'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'code': code,
    'name': name,
    'description': description,
    'coupon_type': couponType,
    'value': value.toString(),
    if (minimumOrderAmount != null) 'minimum_order_amount': minimumOrderAmount.toString(),
    if (maxUses != null) 'max_uses': maxUses,
    'max_uses_per_user': maxUsesPerUser,
    'start_date': startDate.toIso8601String(),
    if (endDate != null) 'end_date': endDate!.toIso8601String(),
    'is_active': isActive,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Coupon Validation Response
// ═══════════════════════════════════════════════════════════════════════

class CouponValidationResponse {
  final bool valid;
  final String message;
  final Coupon? coupon;
  final double? discountAmount;

  CouponValidationResponse({
    required this.valid,
    required this.message,
    this.coupon,
    this.discountAmount,
  });

  factory CouponValidationResponse.fromJson(Map<String, dynamic> json) {
    return CouponValidationResponse(
      valid: json['valid'],
      message: json['message'],
      coupon: json['coupon'] != null ? Coupon.fromJson(json['coupon']) : null,
      discountAmount: json['discount_amount'] != null
          ? double.parse(json['discount_amount'].toString())
          : null,
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Paginated Response (reusable)
// ═══════════════════════════════════════════════════════════════════════

class PaginatedResponse<T> {
  final int count;
  final String? next;
  final String? previous;
  final int pageSize;
  final int totalPages;
  final int currentPage;
  final List<T> results;

  PaginatedResponse({
    required this.count,
    this.next,
    this.previous,
    required this.pageSize,
    required this.totalPages,
    required this.currentPage,
    required this.results,
  });

  factory PaginatedResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) fromJson,
  ) {
    return PaginatedResponse(
      count: json['count'],
      next: json['next'],
      previous: json['previous'],
      pageSize: json['page_size'],
      totalPages: json['total_pages'],
      currentPage: json['current_page'],
      results: (json['results'] as List).map((e) => fromJson(e)).toList(),
    );
  }
}
```

---

## 5. Dart API Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class OrdersApiService {
  final String baseUrl;
  final String? accessToken;

  OrdersApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (accessToken != null) 'Authorization': 'Bearer $accessToken',
  };

  // ═════════════════════════════════════════════════════════════════════
  // Shopping Cart
  // ═════════════════════════════════════════════════════════════════════

  /// List all of the current user's carts (one per vendor)
  Future<List<ShoppingCart>> getMyCarts() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/orders/cart/my-carts/'),
      headers: _headers,
    );
    return (jsonDecode(response.body) as List)
        .map((e) => ShoppingCart.fromJson(e))
        .toList();
  }

  /// Get a specific cart by ID
  Future<ShoppingCart> getCartDetail(int cartId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/orders/cart/$cartId/detail/'),
      headers: _headers,
    );
    return ShoppingCart.fromJson(jsonDecode(response.body));
  }

  /// Add item to cart (auto-routes to the correct vendor cart)
  Future<ShoppingCart> addItemToCart({
    required String productId,
    int? productVariantId,
    int quantity = 1,
  }) async {
    final body = <String, dynamic>{
      'product': productId,
      'quantity': quantity,
    };
    if (productVariantId != null) body['product_variant'] = productVariantId;

    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/cart/add-item/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 400) {
      throw Exception(jsonDecode(response.body)['error']);
    }

    return ShoppingCart.fromJson(jsonDecode(response.body));
  }

  /// Remove a specific item from a cart
  Future<Map<String, dynamic>> removeItemFromCart(int cartId, int itemId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/cart/$cartId/remove-item/$itemId/'),
      headers: _headers,
    );
    return jsonDecode(response.body);
  }

  /// Clear and delete an entire cart
  Future<void> clearCart(int cartId) async {
    await http.post(
      Uri.parse('$baseUrl/api/orders/cart/$cartId/clear/'),
      headers: _headers,
    );
  }

  // ═════════════════════════════════════════════════════════════════════
  // Orders
  // ═════════════════════════════════════════════════════════════════════

  /// List orders with optional filters and pagination
  Future<PaginatedResponse<OrderListItem>> getOrders({
    int page = 1,
    int pageSize = 20,
    String? status,
    String? paymentStatus,
    String? createdDateFrom,
    String? createdDateTo,
    double? amountMin,
    double? amountMax,
  }) async {
    final params = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (status != null) params['status'] = status;
    if (paymentStatus != null) params['payment_status'] = paymentStatus;
    if (createdDateFrom != null) params['created_date_from'] = createdDateFrom;
    if (createdDateTo != null) params['created_date_to'] = createdDateTo;
    if (amountMin != null) params['amount_min'] = amountMin.toString();
    if (amountMax != null) params['amount_max'] = amountMax.toString();

    final uri = Uri.parse('$baseUrl/api/orders/orders/')
        .replace(queryParameters: params);

    final response = await http.get(uri, headers: _headers);
    return PaginatedResponse.fromJson(
      jsonDecode(response.body),
      OrderListItem.fromJson,
    );
  }

  /// Get full order details by ID
  Future<OrderDetail> getOrder(String id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/orders/orders/$id/'),
      headers: _headers,
    );
    return OrderDetail.fromJson(jsonDecode(response.body));
  }

  /// Create a new order
  Future<OrderDetail> createOrder(OrderCreateRequest request) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/orders/'),
      headers: _headers,
      body: jsonEncode(request.toJson()),
    );
    return OrderDetail.fromJson(jsonDecode(response.body));
  }

  /// Partial update an order
  Future<OrderDetail> patchOrder(String id, Map<String, dynamic> fields) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/orders/orders/$id/'),
      headers: _headers,
      body: jsonEncode(fields),
    );
    return OrderDetail.fromJson(jsonDecode(response.body));
  }

  /// Delete an order
  Future<void> deleteOrder(String id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/orders/orders/$id/'),
      headers: _headers,
    );
  }

  /// Cancel an order (must be pending or processing)
  Future<OrderDetail> cancelOrder(String id) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/orders/$id/cancel/'),
      headers: _headers,
    );
    if (response.statusCode == 400) {
      throw Exception(jsonDecode(response.body)['error']);
    }
    return OrderDetail.fromJson(jsonDecode(response.body));
  }

  /// Admin: Update order status with optional comment
  Future<OrderDetail> updateOrderStatus(
    String id, {
    required String status,
    String? comment,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/orders/$id/update_status/'),
      headers: _headers,
      body: jsonEncode({
        'status': status,
        if (comment != null) 'comment': comment,
      }),
    );
    if (response.statusCode == 400) {
      throw Exception(jsonDecode(response.body)['error']);
    }
    return OrderDetail.fromJson(jsonDecode(response.body));
  }

  // ═════════════════════════════════════════════════════════════════════
  // Coupons
  // ═════════════════════════════════════════════════════════════════════

  /// List all coupons (admin only)
  Future<List<Coupon>> getCoupons({String? search}) async {
    final params = <String, String>{};
    if (search != null) params['search'] = search;

    final uri = Uri.parse('$baseUrl/api/orders/coupons/')
        .replace(queryParameters: params.isNotEmpty ? params : null);

    final response = await http.get(uri, headers: _headers);
    return (jsonDecode(response.body) as List)
        .map((e) => Coupon.fromJson(e))
        .toList();
  }

  /// Get a single coupon by ID (admin only)
  Future<Coupon> getCoupon(int id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/orders/coupons/$id/'),
      headers: _headers,
    );
    return Coupon.fromJson(jsonDecode(response.body));
  }

  /// Create a coupon (admin only)
  Future<Coupon> createCoupon(Coupon coupon) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/coupons/'),
      headers: _headers,
      body: jsonEncode(coupon.toJson()),
    );
    return Coupon.fromJson(jsonDecode(response.body));
  }

  /// Update a coupon (admin only)
  Future<Coupon> updateCoupon(int id, Map<String, dynamic> fields) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/orders/coupons/$id/'),
      headers: _headers,
      body: jsonEncode(fields),
    );
    return Coupon.fromJson(jsonDecode(response.body));
  }

  /// Delete a coupon (admin only)
  Future<void> deleteCoupon(int id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/orders/coupons/$id/'),
      headers: _headers,
    );
  }

  /// Validate a coupon code (any authenticated user)
  Future<CouponValidationResponse> validateCoupon({
    required String code,
    double? orderAmount,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/orders/coupons/validate/'),
      headers: _headers,
      body: jsonEncode({
        'code': code,
        if (orderAmount != null) 'order_amount': orderAmount.toString(),
      }),
    );
    return CouponValidationResponse.fromJson(jsonDecode(response.body));
  }
}
```

---

## Error Responses

All endpoints return standard DRF error responses:

| Status | Meaning             | When                                       |
|--------|---------------------|--------------------------------------------|
| 400    | Bad Request         | Validation errors, invalid status, max carts reached |
| 401    | Unauthorized        | Missing or invalid JWT token               |
| 403    | Forbidden           | Not admin (coupon CRUD), not owner         |
| 404    | Not Found           | Order/cart/coupon does not exist            |

**Validation error shape:**

```json
{
  "field_name": ["Error message here."],
  "non_field_errors": ["General validation error."]
}
```

---

## Order Status Flow

```
pending → processing → shipped → delivered
   ↓         ↓
 cancelled  cancelled
   ↓         ↓
 refunded  refunded / partially_refunded
```

## Payment Status Values

| Status              | Description                          |
|---------------------|--------------------------------------|
| `pending`           | Awaiting payment                     |
| `paid`              | Fully paid                           |
| `partially_paid`    | Partial payment received             |
| `failed`            | Payment failed                       |
| `refunded`          | Fully refunded                       |
| `partially_refunded`| Partially refunded                   |

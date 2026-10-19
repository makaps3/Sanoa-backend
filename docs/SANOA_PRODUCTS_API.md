# Sanoa Products API - Complete Documentation

> **Base URL:** `https://your-domain.com/api/products/`
>
> **Authentication:** JWT Bearer Token (unless noted as public)
>
> **Header:** `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Categories](#1-categories)
2. [Brands](#2-brands)
3. [Products](#3-products)
4. [Product Reviews](#4-product-reviews)
5. [Wishlist](#5-wishlist)
6. [Product Likes](#6-product-likes)
7. [Vendor Reviews](#7-vendor-reviews)
8. [Dart Models](#8-dart-models)
9. [Dart API Service](#9-dart-api-service)

---

## 1. Categories

Categories use a hierarchical parent-child structure. Lookup is by `slug`, not `id`.

### 1.1 List All Categories

```
GET /api/products/categories/
```

**Auth:** Public
**Pagination:** None (returns all active categories)

**Response `200 OK`:**

```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "Electronics",
      "slug": "electronics",
      "description": "Electronic devices and accessories",
      "parent": null,
      "image": "https://domain.com/media/categories/electronics.jpg",
      "is_active": true,
      "sort_order": 0,
      "meta_title": "",
      "meta_description": "",
      "full_path": "Electronics",
      "children_count": 2,
      "products_count": 15,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### 1.2 Retrieve Category

```
GET /api/products/categories/{slug}/
```

**Auth:** Public

**Response `200 OK`:** Single category object (same shape as list item).

### 1.3 Create Category

```
POST /api/products/categories/
```

**Auth:** Vendor or Admin

| Field            | Type    | Required | Description                       |
|------------------|---------|----------|-----------------------------------|
| name             | string  | Yes      | Unique category name              |
| description      | string  | No       | Category description              |
| parent           | integer | No       | Parent category ID (for nesting)  |
| image            | file    | No       | Category image                    |
| is_active        | boolean | No       | Default: `true`                   |
| sort_order       | integer | No       | Display order. Default: `0`       |
| meta_title       | string  | No       | SEO title                         |
| meta_description | string  | No       | SEO description                   |

**Response `201 Created`:** The created category object.

### 1.4 Update Category

```
PUT /api/products/categories/{slug}/
PATCH /api/products/categories/{slug}/
```

**Auth:** Vendor or Admin

### 1.5 Delete Category

```
DELETE /api/products/categories/{slug}/
```

**Auth:** Vendor or Admin

**Response `204 No Content`**

---

## 2. Brands

Lookup is by `slug`, not `id`.

### 2.1 List All Brands

```
GET /api/products/brands/
```

**Auth:** Public

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Samsung",
    "slug": "samsung",
    "description": "Korean electronics manufacturer",
    "logo": "https://domain.com/media/brands/samsung.png",
    "website": "https://samsung.com",
    "is_active": true,
    "products_count": 8,
    "created_at": "2026-01-10T08:00:00Z",
    "updated_at": "2026-01-10T08:00:00Z"
  }
]
```

### 2.2 Retrieve Brand

```
GET /api/products/brands/{slug}/
```

**Auth:** Public

### 2.3 Create Brand

```
POST /api/products/brands/
```

**Auth:** Vendor or Admin

| Field       | Type   | Required | Description          |
|-------------|--------|----------|----------------------|
| name        | string | Yes      | Unique brand name    |
| description | string | No       | Brand description    |
| logo        | file   | No       | Brand logo image     |
| website     | string | No       | Brand website URL    |
| is_active   | boolean| No       | Default: `true`      |

**Response `201 Created`:** The created brand object.

### 2.4 Update Brand

```
PUT /api/products/brands/{slug}/
PATCH /api/products/brands/{slug}/
```

**Auth:** Vendor or Admin

### 2.5 Delete Brand

```
DELETE /api/products/brands/{slug}/
```

**Auth:** Vendor or Admin

---

## 3. Products

### 3.1 List Products

```
GET /api/products/products/
```

**Auth:** Public (only `active` products shown to non-staff; staff see all)

**Pagination:** 20 per page (max 100). Query params: `page`, `page_size`.

**Filter / Search / Ordering Query Params:**

| Param        | Type   | Description                                     |
|--------------|--------|-------------------------------------------------|
| search       | string | Search in name, description, short_description, sku |
| category     | string | Filter by category slug (case-insensitive)      |
| brand        | string | Filter by brand slug (case-insensitive)         |
| status       | string | `draft`, `active`, `inactive`, `out_of_stock`, `discontinued` |
| is_featured  | boolean| `true` / `false`                                |
| price_min    | number | Minimum price                                   |
| price_max    | number | Maximum price                                   |
| ordering     | string | `price`, `-price`, `created_at`, `-created_at`, `sales_count`, `-sales_count`, `views_count`, `-views_count`, `name`, `-name` |

**Response `200 OK`:**

```json
{
  "count": 150,
  "next": "https://domain.com/api/products/products/?page=2",
  "previous": null,
  "page_size": 20,
  "total_pages": 8,
  "current_page": 1,
  "results": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Wireless Earbuds",
      "slug": "wireless-earbuds",
      "category_name": "Electronics",
      "brand_name": "Samsung",
      "price": "299.99",
      "compare_at_price": "399.99",
      "discount_percentage": "25.01",
      "is_featured": true,
      "primary_image": {
        "id": 1,
        "image": "https://domain.com/media/products/earbuds.jpg",
        "alt_text": "Wireless earbuds front view",
        "is_primary": true,
        "sort_order": 0,
        "created_at": "2026-02-01T12:00:00Z"
      },
      "average_rating": "4.50",
      "review_count": 12,
      "likes_count": 45,
      "sales_count": 100,
      "status": "active",
      "qr_code": "https://domain.com/media/qrcodes/products/product_uuid.png"
    }
  ]
}
```

### 3.2 Retrieve Product

```
GET /api/products/products/{id}/
```

**Auth:** Public

**Response `200 OK`:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Wireless Earbuds",
  "slug": "wireless-earbuds",
  "description": "Premium wireless earbuds with noise cancellation...",
  "short_description": "Premium wireless earbuds",
  "category": 1,
  "category_name": "Electronics",
  "brand": 1,
  "brand_name": "Samsung",
  "vendor": 5,
  "vendor_email": "vendor@example.com",
  "price": "299.99",
  "compare_at_price": "399.99",
  "cost_per_item": "150.00",
  "discount_percentage": "25.01",
  "sku": "SKU-A1B2C3D4",
  "barcode": "1234567890123",
  "qr_code": "https://domain.com/media/qrcodes/products/product_uuid.png",
  "qr_code_identifier": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "track_inventory": true,
  "continue_selling_when_out_of_stock": false,
  "weight": "50.00",
  "length": "8.00",
  "width": "5.00",
  "height": "3.00",
  "status": "active",
  "is_featured": true,
  "is_digital": false,
  "requires_shipping": true,
  "meta_title": "Best Wireless Earbuds 2026",
  "meta_description": "Shop premium wireless earbuds with noise cancellation",
  "average_rating": "4.50",
  "review_count": 12,
  "likes_count": 45,
  "views_count": 320,
  "sales_count": 100,
  "images": [
    {
      "id": 1,
      "image": "https://domain.com/media/products/earbuds.jpg",
      "alt_text": "Front view",
      "is_primary": true,
      "sort_order": 0,
      "created_at": "2026-02-01T12:00:00Z"
    }
  ],
  "variants": [
    {
      "id": 1,
      "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Black",
      "sku": "SKU-A1B2C3D4-1F2A3B",
      "price": null,
      "compare_at_price": null,
      "weight": null,
      "inventory_quantity": 25,
      "is_active": true,
      "effective_price": "299.99",
      "created_at": "2026-02-01T12:00:00Z",
      "updated_at": "2026-02-01T12:00:00Z"
    },
    {
      "id": 2,
      "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "White",
      "sku": "SKU-A1B2C3D4-4D5E6F",
      "price": "319.99",
      "compare_at_price": null,
      "weight": null,
      "inventory_quantity": 10,
      "is_active": true,
      "effective_price": "319.99",
      "created_at": "2026-02-01T12:00:00Z",
      "updated_at": "2026-02-01T12:00:00Z"
    }
  ],
  "specifications": {
    "Material": "Silicone",
    "Battery Life": "8 hours",
    "Connectivity": "Bluetooth 5.3",
    "Water Resistance": "IPX5"
  },
  "reviews": [
    {
      "id": 1,
      "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "user_email": "customer@example.com",
      "user_name": "John Doe",
      "rating": 5,
      "title": "Excellent sound quality",
      "comment": "Best earbuds I've ever owned.",
      "is_approved": true,
      "is_verified_purchase": true,
      "helpful_count": 3,
      "created_at": "2026-02-15T14:00:00Z",
      "updated_at": "2026-02-15T14:00:00Z"
    }
  ],
  "created_at": "2026-02-01T12:00:00Z",
  "updated_at": "2026-03-01T08:00:00Z"
}
```

### 3.3 Create Product

```
POST /api/products/products/
```

**Auth:** Vendor or Admin

A QR code is automatically generated on creation.

| Field                              | Type    | Required | Description                                  |
|------------------------------------|---------|----------|----------------------------------------------|
| name                               | string  | Yes      | Product name (max 300 chars)                 |
| description                        | string  | Yes      | Full product description                     |
| short_description                  | string  | No       | Brief summary (max 500 chars)                |
| category                           | integer | Yes      | Category ID                                  |
| brand                              | integer | No       | Brand ID                                     |
| price                              | decimal | Yes      | Selling price                                |
| compare_at_price                   | decimal | No       | Original price (shows discount)              |
| cost_per_item                      | decimal | No       | Vendor's cost (for profit calc)              |
| sku                                | string  | No       | Auto-generated if not provided               |
| barcode                            | string  | No       | Product barcode                              |
| track_inventory                    | boolean | No       | Default: `true`                              |
| continue_selling_when_out_of_stock | boolean | No       | Default: `false`                             |
| weight                             | decimal | No       | Weight in grams                              |
| length                             | decimal | No       | Length in cm                                 |
| width                              | decimal | No       | Width in cm                                  |
| height                             | decimal | No       | Height in cm                                 |
| status                             | string  | No       | `draft` (default), `active`, `inactive`, `out_of_stock`, `discontinued` |
| is_featured                        | boolean | No       | Default: `false`                             |
| is_digital                         | boolean | No       | Default: `false`                             |
| requires_shipping                  | boolean | No       | Default: `true`                              |
| meta_title                         | string  | No       | SEO title                                    |
| meta_description                   | string  | No       | SEO description                              |
| specifications                     | object  | No       | Key-value pairs, e.g. `{"Color": "Red", "Material": "Cotton"}` |

**Response `201 Created`:** The created product (detail serializer shape).

### 3.4 Update Product

```
PUT /api/products/products/{id}/
PATCH /api/products/products/{id}/
```

**Auth:** Vendor or Admin

Same fields as create. Use `PATCH` for partial updates.

### 3.5 Delete Product

```
DELETE /api/products/products/{id}/
```

**Auth:** Vendor or Admin

**Response `204 No Content`**

### 3.6 Increment Views

```
POST /api/products/products/{id}/increment_views/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
{
  "views_count": 321
}
```

### 3.7 Scan QR Code

```
GET /api/products/products/scan-qr/?code={qr_code_identifier}
```

**Auth:** Public

| Param | Type   | Required | Description                      |
|-------|--------|----------|----------------------------------|
| code  | string | Yes      | The `qr_code_identifier` (UUID)  |

**Response `200 OK`:** Full product detail object.

**Response `404 Not Found`:** Product not found for the given code.

### 3.8 Recommended Products (ML-powered)

```
GET /api/products/products/recommended/?limit=20
```

**Auth:** Authenticated

| Param | Type    | Required | Description                    |
|-------|---------|----------|--------------------------------|
| limit | integer | No       | Number of results. Default: 20 |

**Response `200 OK`:** Array of product list objects, ordered by recommendation score.

### 3.9 Similar Products

```
GET /api/products/products/{id}/similar/?limit=10
```

**Auth:** Public

| Param | Type    | Required | Description                    |
|-------|---------|----------|--------------------------------|
| limit | integer | No       | Number of results. Default: 10 |

**Response `200 OK`:** Array of product list objects, ordered by similarity score.

---

## 4. Product Reviews

### 4.1 List Reviews

```
GET /api/products/reviews/?product={product_id}
```

**Auth:** Public (only approved reviews shown to non-staff)

| Param   | Type   | Required | Description                |
|---------|--------|----------|----------------------------|
| product | UUID   | No       | Filter by product ID       |

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "user_email": "customer@example.com",
    "user_name": "John Doe",
    "rating": 5,
    "title": "Great product",
    "comment": "Highly recommended!",
    "is_approved": true,
    "is_verified_purchase": true,
    "helpful_count": 3,
    "created_at": "2026-02-15T14:00:00Z",
    "updated_at": "2026-02-15T14:00:00Z"
  }
]
```

### 4.2 Create Review

```
POST /api/products/reviews/
```

**Auth:** Authenticated (one review per user per product)

| Field   | Type    | Required | Description                  |
|---------|---------|----------|------------------------------|
| product | UUID    | Yes      | Product ID                   |
| rating  | integer | Yes      | 1-5 stars                    |
| title   | string  | No       | Review title (max 200 chars) |
| comment | string  | No       | Review body                  |

**Response `201 Created`:** The created review object.

### 4.3 Update Review

```
PUT /api/products/reviews/{id}/
PATCH /api/products/reviews/{id}/
```

**Auth:** Authenticated

### 4.4 Delete Review

```
DELETE /api/products/reviews/{id}/
```

**Auth:** Authenticated

---

## 5. Wishlist

Private save-for-later list. Users can only see their own wishlist items.

### 5.1 List My Wishlist

```
GET /api/products/wishlist/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
[
  {
    "id": 1,
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
      "primary_image": { "..." : "..." },
      "average_rating": "4.50",
      "review_count": 12,
      "likes_count": 45,
      "sales_count": 100,
      "status": "active",
      "qr_code": "https://domain.com/media/qrcodes/products/product_uuid.png"
    },
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

### 5.2 Add to Wishlist

```
POST /api/products/wishlist/
```

**Auth:** Authenticated

| Field   | Type | Required | Description |
|---------|------|----------|-------------|
| product | UUID | Yes      | Product ID  |

**Response `201 Created`:** The created wishlist item.

### 5.3 Remove from Wishlist

```
DELETE /api/products/wishlist/{id}/
```

**Auth:** Authenticated

**Response `204 No Content`**

---

## 6. Product Likes

Public social signals (different from wishlist which is private).

### 6.1 My Likes

```
GET /api/products/likes/my-likes/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "product": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "product_data": { "..." : "..." },
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

### 6.2 Like a Product

```
POST /api/products/likes/like/
```

**Auth:** Authenticated

| Field   | Type | Required | Description |
|---------|------|----------|-------------|
| product | UUID | Yes      | Product ID  |

**Response `201 Created`:** The created like object.

**Response `400 Bad Request`:**

```json
{ "detail": "You already liked this product." }
```

### 6.3 Unlike a Product

```
POST /api/products/likes/unlike/
```

**Auth:** Authenticated

| Field      | Type | Required | Description |
|------------|------|----------|-------------|
| product_id | UUID | Yes      | Product ID  |

**Response `200 OK`:**

```json
{ "status": "unliked" }
```

**Response `400 Bad Request`:**

```json
{ "error": "You have not liked this product." }
```

### 6.4 Like Count for a Product

```
GET /api/products/likes/count/{product_id}/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
{
  "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "likes_count": 45,
  "is_liked": true
}
```

---

## 7. Vendor Reviews

Rate a vendor's overall service, delivery, and professionalism (separate from product reviews).

### 7.1 List Vendor Reviews

```
GET /api/products/vendor-reviews/?vendor={vendor_user_id}
```

**Auth:** Public (only approved reviews shown to non-staff)

| Param  | Type    | Required | Description               |
|--------|---------|----------|---------------------------|
| vendor | integer | No       | Filter by vendor user ID  |

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "vendor": 5,
    "user_email": "customer@example.com",
    "user_name": "John Doe",
    "vendor_email": "vendor@example.com",
    "rating": 4,
    "title": "Fast delivery",
    "comment": "Great service, will order again.",
    "is_approved": true,
    "is_verified_purchase": false,
    "helpful_count": 2,
    "created_at": "2026-03-05T09:00:00Z",
    "updated_at": "2026-03-05T09:00:00Z"
  }
]
```

### 7.2 Create Vendor Review

```
POST /api/products/vendor-reviews/
```

**Auth:** Authenticated (one review per user per vendor; cannot review yourself; vendor must have `user_type: "vendor"`)

| Field   | Type    | Required | Description                    |
|---------|---------|----------|--------------------------------|
| vendor  | integer | Yes      | Vendor user ID                 |
| rating  | integer | Yes      | 1-5 stars                      |
| title   | string  | No       | Review title (max 200 chars)   |
| comment | string  | No       | Review body                    |

**Response `201 Created`:** The created vendor review object.

**Validation Errors:**

```json
{ "non_field_errors": ["You cannot review yourself."] }
{ "non_field_errors": ["You can only review vendors."] }
```

### 7.3 Update Vendor Review

```
PUT /api/products/vendor-reviews/{id}/
PATCH /api/products/vendor-reviews/{id}/
```

**Auth:** Authenticated

### 7.4 Delete Vendor Review

```
DELETE /api/products/vendor-reviews/{id}/
```

**Auth:** Authenticated

### 7.5 Vendor Review Summary

```
GET /api/products/vendor-reviews/vendor-summary/{vendor_user_id}/
```

**Auth:** Public

**Response `200 OK`:**

```json
{
  "vendor_id": "5",
  "average_rating": 4.25,
  "total_reviews": 20,
  "breakdown": {
    "1_star": 1,
    "2_star": 0,
    "3_star": 3,
    "4_star": 8,
    "5_star": 8
  }
}
```

---

## 8. Dart Models

```dart
// ═══════════════════════════════════════════════════════════════════════
// Category
// ═══════════════════════════════════════════════════════════════════════

class Category {
  final int id;
  final String name;
  final String slug;
  final String description;
  final int? parent;
  final String? image;
  final bool isActive;
  final int sortOrder;
  final String metaTitle;
  final String metaDescription;
  final String fullPath;
  final int childrenCount;
  final int productsCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  Category({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    this.parent,
    this.image,
    required this.isActive,
    required this.sortOrder,
    required this.metaTitle,
    required this.metaDescription,
    required this.fullPath,
    required this.childrenCount,
    required this.productsCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Category.fromJson(Map<String, dynamic> json) {
    return Category(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      description: json['description'] ?? '',
      parent: json['parent'],
      image: json['image'],
      isActive: json['is_active'],
      sortOrder: json['sort_order'],
      metaTitle: json['meta_title'] ?? '',
      metaDescription: json['meta_description'] ?? '',
      fullPath: json['full_path'],
      childrenCount: json['children_count'],
      productsCount: json['products_count'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'description': description,
    'parent': parent,
    'is_active': isActive,
    'sort_order': sortOrder,
    'meta_title': metaTitle,
    'meta_description': metaDescription,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Brand
// ═══════════════════════════════════════════════════════════════════════

class Brand {
  final int id;
  final String name;
  final String slug;
  final String description;
  final String? logo;
  final String website;
  final bool isActive;
  final int productsCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  Brand({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    this.logo,
    required this.website,
    required this.isActive,
    required this.productsCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Brand.fromJson(Map<String, dynamic> json) {
    return Brand(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      description: json['description'] ?? '',
      logo: json['logo'],
      website: json['website'] ?? '',
      isActive: json['is_active'],
      productsCount: json['products_count'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'description': description,
    'website': website,
    'is_active': isActive,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Product Image
// ═══════════════════════════════════════════════════════════════════════

class ProductImage {
  final int id;
  final String image;
  final String altText;
  final bool isPrimary;
  final int sortOrder;
  final DateTime createdAt;

  ProductImage({
    required this.id,
    required this.image,
    required this.altText,
    required this.isPrimary,
    required this.sortOrder,
    required this.createdAt,
  });

  factory ProductImage.fromJson(Map<String, dynamic> json) {
    return ProductImage(
      id: json['id'],
      image: json['image'],
      altText: json['alt_text'] ?? '',
      isPrimary: json['is_primary'],
      sortOrder: json['sort_order'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Product Variant
// ═══════════════════════════════════════════════════════════════════════

class ProductVariant {
  final int id;
  final String product;
  final String name;
  final String sku;
  final double? price;
  final double? compareAtPrice;
  final double? weight;
  final int inventoryQuantity;
  final bool isActive;
  final double effectivePrice;
  final DateTime createdAt;
  final DateTime updatedAt;

  ProductVariant({
    required this.id,
    required this.product,
    required this.name,
    required this.sku,
    this.price,
    this.compareAtPrice,
    this.weight,
    required this.inventoryQuantity,
    required this.isActive,
    required this.effectivePrice,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ProductVariant.fromJson(Map<String, dynamic> json) {
    return ProductVariant(
      id: json['id'],
      product: json['product'],
      name: json['name'],
      sku: json['sku'],
      price: json['price'] != null ? double.parse(json['price'].toString()) : null,
      compareAtPrice: json['compare_at_price'] != null
          ? double.parse(json['compare_at_price'].toString())
          : null,
      weight: json['weight'] != null ? double.parse(json['weight'].toString()) : null,
      inventoryQuantity: json['inventory_quantity'],
      isActive: json['is_active'],
      effectivePrice: double.parse(json['effective_price'].toString()),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'product': product,
    'name': name,
    'price': price?.toString(),
    'compare_at_price': compareAtPrice?.toString(),
    'weight': weight?.toString(),
    'inventory_quantity': inventoryQuantity,
    'is_active': isActive,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Product (List view - lightweight)
// ═══════════════════════════════════════════════════════════════════════

class ProductListItem {
  final String id;
  final String name;
  final String slug;
  final String categoryName;
  final String? brandName;
  final double price;
  final double? compareAtPrice;
  final double discountPercentage;
  final bool isFeatured;
  final ProductImage? primaryImage;
  final double averageRating;
  final int reviewCount;
  final int likesCount;
  final int salesCount;
  final String status;
  final String? qrCode;

  ProductListItem({
    required this.id,
    required this.name,
    required this.slug,
    required this.categoryName,
    this.brandName,
    required this.price,
    this.compareAtPrice,
    required this.discountPercentage,
    required this.isFeatured,
    this.primaryImage,
    required this.averageRating,
    required this.reviewCount,
    required this.likesCount,
    required this.salesCount,
    required this.status,
    this.qrCode,
  });

  factory ProductListItem.fromJson(Map<String, dynamic> json) {
    return ProductListItem(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      categoryName: json['category_name'],
      brandName: json['brand_name'],
      price: double.parse(json['price'].toString()),
      compareAtPrice: json['compare_at_price'] != null
          ? double.parse(json['compare_at_price'].toString())
          : null,
      discountPercentage: double.parse(json['discount_percentage'].toString()),
      isFeatured: json['is_featured'],
      primaryImage: json['primary_image'] != null
          ? ProductImage.fromJson(json['primary_image'])
          : null,
      averageRating: double.parse(json['average_rating'].toString()),
      reviewCount: json['review_count'],
      likesCount: json['likes_count'],
      salesCount: json['sales_count'],
      status: json['status'],
      qrCode: json['qr_code'],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Product (Detail view - full)
// ═══════════════════════════════════════════════════════════════════════

class ProductDetail {
  final String id;
  final String name;
  final String slug;
  final String description;
  final String shortDescription;
  final int category;
  final String categoryName;
  final int? brand;
  final String? brandName;
  final int vendor;
  final String vendorEmail;
  final double price;
  final double? compareAtPrice;
  final double? costPerItem;
  final double discountPercentage;
  final String sku;
  final String barcode;
  final String? qrCode;
  final String qrCodeIdentifier;
  final bool trackInventory;
  final bool continueSellingWhenOutOfStock;
  final double? weight;
  final double? length;
  final double? width;
  final double? height;
  final String status;
  final bool isFeatured;
  final bool isDigital;
  final bool requiresShipping;
  final String metaTitle;
  final String metaDescription;
  final double averageRating;
  final int reviewCount;
  final int likesCount;
  final int viewsCount;
  final int salesCount;
  final List<ProductImage> images;
  final List<ProductVariant> variants;
  final Map<String, dynamic> specifications;
  final List<ProductReview> reviews;
  final DateTime createdAt;
  final DateTime updatedAt;

  ProductDetail({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    required this.shortDescription,
    required this.category,
    required this.categoryName,
    this.brand,
    this.brandName,
    required this.vendor,
    required this.vendorEmail,
    required this.price,
    this.compareAtPrice,
    this.costPerItem,
    required this.discountPercentage,
    required this.sku,
    required this.barcode,
    this.qrCode,
    required this.qrCodeIdentifier,
    required this.trackInventory,
    required this.continueSellingWhenOutOfStock,
    this.weight,
    this.length,
    this.width,
    this.height,
    required this.status,
    required this.isFeatured,
    required this.isDigital,
    required this.requiresShipping,
    required this.metaTitle,
    required this.metaDescription,
    required this.averageRating,
    required this.reviewCount,
    required this.likesCount,
    required this.viewsCount,
    required this.salesCount,
    required this.images,
    required this.variants,
    required this.specifications,
    required this.reviews,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ProductDetail.fromJson(Map<String, dynamic> json) {
    return ProductDetail(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      description: json['description'],
      shortDescription: json['short_description'] ?? '',
      category: json['category'],
      categoryName: json['category_name'],
      brand: json['brand'],
      brandName: json['brand_name'],
      vendor: json['vendor'],
      vendorEmail: json['vendor_email'],
      price: double.parse(json['price'].toString()),
      compareAtPrice: json['compare_at_price'] != null
          ? double.parse(json['compare_at_price'].toString())
          : null,
      costPerItem: json['cost_per_item'] != null
          ? double.parse(json['cost_per_item'].toString())
          : null,
      discountPercentage: double.parse(json['discount_percentage'].toString()),
      sku: json['sku'],
      barcode: json['barcode'] ?? '',
      qrCode: json['qr_code'],
      qrCodeIdentifier: json['qr_code_identifier'],
      trackInventory: json['track_inventory'],
      continueSellingWhenOutOfStock: json['continue_selling_when_out_of_stock'],
      weight: json['weight'] != null ? double.parse(json['weight'].toString()) : null,
      length: json['length'] != null ? double.parse(json['length'].toString()) : null,
      width: json['width'] != null ? double.parse(json['width'].toString()) : null,
      height: json['height'] != null ? double.parse(json['height'].toString()) : null,
      status: json['status'],
      isFeatured: json['is_featured'],
      isDigital: json['is_digital'],
      requiresShipping: json['requires_shipping'],
      metaTitle: json['meta_title'] ?? '',
      metaDescription: json['meta_description'] ?? '',
      averageRating: double.parse(json['average_rating'].toString()),
      reviewCount: json['review_count'],
      likesCount: json['likes_count'],
      viewsCount: json['views_count'],
      salesCount: json['sales_count'],
      images: (json['images'] as List).map((e) => ProductImage.fromJson(e)).toList(),
      variants: (json['variants'] as List).map((e) => ProductVariant.fromJson(e)).toList(),
      specifications: Map<String, dynamic>.from(json['specifications'] ?? {}),
      reviews: (json['reviews'] as List).map((e) => ProductReview.fromJson(e)).toList(),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Product Create/Update Request
// ═══════════════════════════════════════════════════════════════════════

class ProductCreateRequest {
  final String name;
  final String description;
  final String? shortDescription;
  final int category;
  final int? brand;
  final double price;
  final double? compareAtPrice;
  final double? costPerItem;
  final String? sku;
  final String? barcode;
  final bool? trackInventory;
  final bool? continueSellingWhenOutOfStock;
  final double? weight;
  final double? length;
  final double? width;
  final double? height;
  final String? status;
  final bool? isFeatured;
  final bool? isDigital;
  final bool? requiresShipping;
  final String? metaTitle;
  final String? metaDescription;
  final Map<String, dynamic>? specifications;

  ProductCreateRequest({
    required this.name,
    required this.description,
    this.shortDescription,
    required this.category,
    this.brand,
    required this.price,
    this.compareAtPrice,
    this.costPerItem,
    this.sku,
    this.barcode,
    this.trackInventory,
    this.continueSellingWhenOutOfStock,
    this.weight,
    this.length,
    this.width,
    this.height,
    this.status,
    this.isFeatured,
    this.isDigital,
    this.requiresShipping,
    this.metaTitle,
    this.metaDescription,
    this.specifications,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'name': name,
      'description': description,
      'category': category,
      'price': price.toString(),
    };
    if (shortDescription != null) map['short_description'] = shortDescription;
    if (brand != null) map['brand'] = brand;
    if (compareAtPrice != null) map['compare_at_price'] = compareAtPrice.toString();
    if (costPerItem != null) map['cost_per_item'] = costPerItem.toString();
    if (sku != null) map['sku'] = sku;
    if (barcode != null) map['barcode'] = barcode;
    if (trackInventory != null) map['track_inventory'] = trackInventory;
    if (continueSellingWhenOutOfStock != null) {
      map['continue_selling_when_out_of_stock'] = continueSellingWhenOutOfStock;
    }
    if (weight != null) map['weight'] = weight.toString();
    if (length != null) map['length'] = length.toString();
    if (width != null) map['width'] = width.toString();
    if (height != null) map['height'] = height.toString();
    if (status != null) map['status'] = status;
    if (isFeatured != null) map['is_featured'] = isFeatured;
    if (isDigital != null) map['is_digital'] = isDigital;
    if (requiresShipping != null) map['requires_shipping'] = requiresShipping;
    if (metaTitle != null) map['meta_title'] = metaTitle;
    if (metaDescription != null) map['meta_description'] = metaDescription;
    if (specifications != null) map['specifications'] = specifications;
    return map;
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Product Review
// ═══════════════════════════════════════════════════════════════════════

class ProductReview {
  final int id;
  final String product;
  final String userEmail;
  final String userName;
  final int rating;
  final String title;
  final String comment;
  final bool isApproved;
  final bool isVerifiedPurchase;
  final int helpfulCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  ProductReview({
    required this.id,
    required this.product,
    required this.userEmail,
    required this.userName,
    required this.rating,
    required this.title,
    required this.comment,
    required this.isApproved,
    required this.isVerifiedPurchase,
    required this.helpfulCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ProductReview.fromJson(Map<String, dynamic> json) {
    return ProductReview(
      id: json['id'],
      product: json['product'].toString(),
      userEmail: json['user_email'],
      userName: json['user_name'],
      rating: json['rating'],
      title: json['title'] ?? '',
      comment: json['comment'] ?? '',
      isApproved: json['is_approved'],
      isVerifiedPurchase: json['is_verified_purchase'],
      helpfulCount: json['helpful_count'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'product': product,
    'rating': rating,
    'title': title,
    'comment': comment,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Wishlist Item
// ═══════════════════════════════════════════════════════════════════════

class WishlistItem {
  final int id;
  final String product;
  final ProductListItem? productData;
  final DateTime createdAt;

  WishlistItem({
    required this.id,
    required this.product,
    this.productData,
    required this.createdAt,
  });

  factory WishlistItem.fromJson(Map<String, dynamic> json) {
    return WishlistItem(
      id: json['id'],
      product: json['product'].toString(),
      productData: json['product_data'] != null
          ? ProductListItem.fromJson(json['product_data'])
          : null,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Product Like
// ═══════════════════════════════════════════════════════════════════════

class ProductLike {
  final int id;
  final String product;
  final ProductListItem? productData;
  final DateTime createdAt;

  ProductLike({
    required this.id,
    required this.product,
    this.productData,
    required this.createdAt,
  });

  factory ProductLike.fromJson(Map<String, dynamic> json) {
    return ProductLike(
      id: json['id'],
      product: json['product'].toString(),
      productData: json['product_data'] != null
          ? ProductListItem.fromJson(json['product_data'])
          : null,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Like Count Response
// ═══════════════════════════════════════════════════════════════════════

class LikeCountResponse {
  final String productId;
  final int likesCount;
  final bool isLiked;

  LikeCountResponse({
    required this.productId,
    required this.likesCount,
    required this.isLiked,
  });

  factory LikeCountResponse.fromJson(Map<String, dynamic> json) {
    return LikeCountResponse(
      productId: json['product_id'].toString(),
      likesCount: json['likes_count'],
      isLiked: json['is_liked'],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Vendor Review
// ═══════════════════════════════════════════════════════════════════════

class VendorReview {
  final int id;
  final int vendor;
  final String userEmail;
  final String userName;
  final String vendorEmail;
  final int rating;
  final String title;
  final String comment;
  final bool isApproved;
  final bool isVerifiedPurchase;
  final int helpfulCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  VendorReview({
    required this.id,
    required this.vendor,
    required this.userEmail,
    required this.userName,
    required this.vendorEmail,
    required this.rating,
    required this.title,
    required this.comment,
    required this.isApproved,
    required this.isVerifiedPurchase,
    required this.helpfulCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory VendorReview.fromJson(Map<String, dynamic> json) {
    return VendorReview(
      id: json['id'],
      vendor: json['vendor'],
      userEmail: json['user_email'],
      userName: json['user_name'],
      vendorEmail: json['vendor_email'],
      rating: json['rating'],
      title: json['title'] ?? '',
      comment: json['comment'] ?? '',
      isApproved: json['is_approved'],
      isVerifiedPurchase: json['is_verified_purchase'],
      helpfulCount: json['helpful_count'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'vendor': vendor,
    'rating': rating,
    'title': title,
    'comment': comment,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Vendor Review Summary
// ═══════════════════════════════════════════════════════════════════════

class VendorReviewSummary {
  final String vendorId;
  final double averageRating;
  final int totalReviews;
  final Map<String, int> breakdown;

  VendorReviewSummary({
    required this.vendorId,
    required this.averageRating,
    required this.totalReviews,
    required this.breakdown,
  });

  factory VendorReviewSummary.fromJson(Map<String, dynamic> json) {
    return VendorReviewSummary(
      vendorId: json['vendor_id'].toString(),
      averageRating: (json['average_rating'] as num).toDouble(),
      totalReviews: json['total_reviews'],
      breakdown: Map<String, int>.from(json['breakdown']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Paginated Response
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

## 9. Dart API Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ProductsApiService {
  final String baseUrl;
  final String? accessToken;

  ProductsApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (accessToken != null) 'Authorization': 'Bearer $accessToken',
  };

  // ═════════════════════════════════════════════════════════════════════
  // Categories
  // ═════════════════════════════════════════════════════════════════════

  /// List all active categories
  Future<List<Category>> getCategories() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/categories/'),
      headers: _headers,
    );
    final data = jsonDecode(response.body);
    return (data['results'] as List).map((e) => Category.fromJson(e)).toList();
  }

  /// Get a single category by slug
  Future<Category> getCategory(String slug) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/categories/$slug/'),
      headers: _headers,
    );
    return Category.fromJson(jsonDecode(response.body));
  }

  /// Create a new category
  Future<Category> createCategory(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/categories/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    return Category.fromJson(jsonDecode(response.body));
  }

  // ═════════════════════════════════════════════════════════════════════
  // Brands
  // ═════════════════════════════════════════════════════════════════════

  /// List all active brands
  Future<List<Brand>> getBrands() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/brands/'),
      headers: _headers,
    );
    final data = jsonDecode(response.body);
    return (data as List).map((e) => Brand.fromJson(e)).toList();
  }

  /// Get a single brand by slug
  Future<Brand> getBrand(String slug) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/brands/$slug/'),
      headers: _headers,
    );
    return Brand.fromJson(jsonDecode(response.body));
  }

  /// Create a new brand
  Future<Brand> createBrand(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/brands/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    return Brand.fromJson(jsonDecode(response.body));
  }

  // ═════════════════════════════════════════════════════════════════════
  // Products
  // ═════════════════════════════════════════════════════════════════════

  /// List products with optional filters
  Future<PaginatedResponse<ProductListItem>> getProducts({
    int page = 1,
    int pageSize = 20,
    String? search,
    String? category,
    String? brand,
    String? status,
    bool? isFeatured,
    double? priceMin,
    double? priceMax,
    String? ordering,
  }) async {
    final params = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (search != null) params['search'] = search;
    if (category != null) params['category'] = category;
    if (brand != null) params['brand'] = brand;
    if (status != null) params['status'] = status;
    if (isFeatured != null) params['is_featured'] = isFeatured.toString();
    if (priceMin != null) params['price_min'] = priceMin.toString();
    if (priceMax != null) params['price_max'] = priceMax.toString();
    if (ordering != null) params['ordering'] = ordering;

    final uri = Uri.parse('$baseUrl/api/products/products/')
        .replace(queryParameters: params);

    final response = await http.get(uri, headers: _headers);
    return PaginatedResponse.fromJson(
      jsonDecode(response.body),
      ProductListItem.fromJson,
    );
  }

  /// Get full product details by ID
  Future<ProductDetail> getProduct(String id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/products/$id/'),
      headers: _headers,
    );
    return ProductDetail.fromJson(jsonDecode(response.body));
  }

  /// Create a new product (vendor/admin only)
  Future<Map<String, dynamic>> createProduct(ProductCreateRequest request) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/products/'),
      headers: _headers,
      body: jsonEncode(request.toJson()),
    );
    return jsonDecode(response.body);
  }

  /// Update a product (PUT - full update)
  Future<Map<String, dynamic>> updateProduct(
      String id, ProductCreateRequest request) async {
    final response = await http.put(
      Uri.parse('$baseUrl/api/products/products/$id/'),
      headers: _headers,
      body: jsonEncode(request.toJson()),
    );
    return jsonDecode(response.body);
  }

  /// Partial update a product (PATCH)
  Future<Map<String, dynamic>> patchProduct(
      String id, Map<String, dynamic> fields) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/products/products/$id/'),
      headers: _headers,
      body: jsonEncode(fields),
    );
    return jsonDecode(response.body);
  }

  /// Delete a product
  Future<void> deleteProduct(String id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/products/$id/'),
      headers: _headers,
    );
  }

  /// Increment product view count
  Future<int> incrementViews(String productId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/products/$productId/increment_views/'),
      headers: _headers,
    );
    return jsonDecode(response.body)['views_count'];
  }

  /// Look up a product by QR code identifier
  Future<ProductDetail> scanQrCode(String code) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/products/scan-qr/?code=$code'),
      headers: _headers,
    );
    return ProductDetail.fromJson(jsonDecode(response.body));
  }

  /// Get ML-powered recommended products for current user
  Future<List<ProductListItem>> getRecommended({int limit = 20}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/products/recommended/?limit=$limit'),
      headers: _headers,
    );
    return (jsonDecode(response.body) as List)
        .map((e) => ProductListItem.fromJson(e))
        .toList();
  }

  /// Get products similar to a given product
  Future<List<ProductListItem>> getSimilar(String productId,
      {int limit = 10}) async {
    final response = await http.get(
      Uri.parse(
          '$baseUrl/api/products/products/$productId/similar/?limit=$limit'),
      headers: _headers,
    );
    return (jsonDecode(response.body) as List)
        .map((e) => ProductListItem.fromJson(e))
        .toList();
  }

  // ═════════════════════════════════════════════════════════════════════
  // Product Reviews
  // ═════════════════════════════════════════════════════════════════════

  /// List reviews, optionally filtered by product
  Future<List<ProductReview>> getReviews({String? productId}) async {
    final uri = productId != null
        ? '$baseUrl/api/products/reviews/?product=$productId'
        : '$baseUrl/api/products/reviews/';
    final response = await http.get(Uri.parse(uri), headers: _headers);
    return (jsonDecode(response.body) as List)
        .map((e) => ProductReview.fromJson(e))
        .toList();
  }

  /// Create a product review
  Future<ProductReview> createReview({
    required String productId,
    required int rating,
    String? title,
    String? comment,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/reviews/'),
      headers: _headers,
      body: jsonEncode({
        'product': productId,
        'rating': rating,
        if (title != null) 'title': title,
        if (comment != null) 'comment': comment,
      }),
    );
    return ProductReview.fromJson(jsonDecode(response.body));
  }

  /// Delete a product review
  Future<void> deleteReview(int id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/reviews/$id/'),
      headers: _headers,
    );
  }

  // ═════════════════════════════════════════════════════════════════════
  // Wishlist
  // ═════════════════════════════════════════════════════════════════════

  /// List current user's wishlist
  Future<List<WishlistItem>> getWishlist() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/wishlist/'),
      headers: _headers,
    );
    return (jsonDecode(response.body) as List)
        .map((e) => WishlistItem.fromJson(e))
        .toList();
  }

  /// Add a product to wishlist
  Future<WishlistItem> addToWishlist(String productId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/wishlist/'),
      headers: _headers,
      body: jsonEncode({'product': productId}),
    );
    return WishlistItem.fromJson(jsonDecode(response.body));
  }

  /// Remove from wishlist by wishlist item ID
  Future<void> removeFromWishlist(int id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/wishlist/$id/'),
      headers: _headers,
    );
  }

  // ═════════════════════════════════════════════════════════════════════
  // Product Likes
  // ═════════════════════════════════════════════════════════════════════

  /// List current user's liked products
  Future<List<ProductLike>> getMyLikes() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/likes/my-likes/'),
      headers: _headers,
    );
    return (jsonDecode(response.body) as List)
        .map((e) => ProductLike.fromJson(e))
        .toList();
  }

  /// Like a product
  Future<ProductLike> likeProduct(String productId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/likes/like/'),
      headers: _headers,
      body: jsonEncode({'product': productId}),
    );
    return ProductLike.fromJson(jsonDecode(response.body));
  }

  /// Unlike a product
  Future<void> unlikeProduct(String productId) async {
    await http.post(
      Uri.parse('$baseUrl/api/products/likes/unlike/'),
      headers: _headers,
      body: jsonEncode({'product_id': productId}),
    );
  }

  /// Get like count and whether current user has liked a product
  Future<LikeCountResponse> getLikeCount(String productId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/likes/count/$productId/'),
      headers: _headers,
    );
    return LikeCountResponse.fromJson(jsonDecode(response.body));
  }

  // ═════════════════════════════════════════════════════════════════════
  // Vendor Reviews
  // ═════════════════════════════════════════════════════════════════════

  /// List vendor reviews, optionally filtered by vendor
  Future<List<VendorReview>> getVendorReviews({int? vendorId}) async {
    final uri = vendorId != null
        ? '$baseUrl/api/products/vendor-reviews/?vendor=$vendorId'
        : '$baseUrl/api/products/vendor-reviews/';
    final response = await http.get(Uri.parse(uri), headers: _headers);
    return (jsonDecode(response.body) as List)
        .map((e) => VendorReview.fromJson(e))
        .toList();
  }

  /// Create a vendor review
  Future<VendorReview> createVendorReview({
    required int vendorId,
    required int rating,
    String? title,
    String? comment,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/vendor-reviews/'),
      headers: _headers,
      body: jsonEncode({
        'vendor': vendorId,
        'rating': rating,
        if (title != null) 'title': title,
        if (comment != null) 'comment': comment,
      }),
    );
    return VendorReview.fromJson(jsonDecode(response.body));
  }

  /// Delete a vendor review
  Future<void> deleteVendorReview(int id) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/vendor-reviews/$id/'),
      headers: _headers,
    );
  }

  /// Get vendor review summary (average, total, breakdown)
  Future<VendorReviewSummary> getVendorReviewSummary(int vendorId) async {
    final response = await http.get(
      Uri.parse(
          '$baseUrl/api/products/vendor-reviews/vendor-summary/$vendorId/'),
      headers: _headers,
    );
    return VendorReviewSummary.fromJson(jsonDecode(response.body));
  }
}
```

---

## Error Responses

All endpoints return standard DRF error responses:

| Status | Meaning                | When                                          |
|--------|------------------------|-----------------------------------------------|
| 400    | Bad Request            | Validation errors, missing required fields    |
| 401    | Unauthorized           | Missing or invalid JWT token                  |
| 403    | Forbidden              | User lacks permission (not vendor/admin)      |
| 404    | Not Found              | Resource does not exist                       |
| 405    | Method Not Allowed     | HTTP method not supported on endpoint         |

**Validation error shape:**

```json
{
  "field_name": ["Error message here."],
  "non_field_errors": ["General validation error."]
}
```

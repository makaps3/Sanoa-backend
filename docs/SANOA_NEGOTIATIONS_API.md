# Sanoa Negotiations API - Complete Documentation

> **Base URL:** `https://your-domain.com/api/negotiations/`
>
> **Authentication:** JWT Bearer Token (required for most endpoints; search is public)
>
> **Header:** `Authorization: Bearer <access_token>`
>
> **Currency:** ZAR (South African Rand)

---

## Table of Contents

1. [Product Search with Negotiation](#1-product-search-with-negotiation)
2. [Negotiate Single Product](#2-negotiate-single-product)
3. [Accept Negotiation](#3-accept-negotiation)
4. [Price Policy Management](#4-price-policy-management)
5. [My Negotiations](#5-my-negotiations)
6. [Dart Models](#6-dart-models)
7. [Dart API Service](#7-dart-api-service)

---

## 1. Product Search with Negotiation

### 1.1 Search Products with Negotiation

```
GET /api/negotiations/search/
```

**Auth:** Public (but authenticated users get personalized results)

**Query Params:**
- `query` (string, optional): Search term
- `category` (string, optional): Category filter
- `latitude` (float, optional): Buyer's latitude
- `longitude` (float, optional): Buyer's longitude
- `limit` (int, optional): Max results (1-100, default 50)

**Response `200 OK`:**

```json
{
  "count": 25,
  "results": [
    {
      "product_id": "a1b2c3d4-...",
      "name": "Running Shoes",
      "slug": "running-shoes",
      "sku": "RS-001",
      "category": "Footwear",
      "brand": "Nike",
      "vendor_id": 12,
      "vendor_name": "Sports Store",
      "vendor_type": "vendor",
      "original_price": "1200.00",
      "negotiated_price": "1080.00",
      "adjustment_percent": "-10.00",
      "direction": "discount",
      "price_factors": {
        "demand": "low",
        "vendor_tier": "premium",
        "distance": 5.2
      },
      "average_rating": "4.5",
      "total_reviews": 150,
      "follower_count": 500,
      "tier_name": "Premium",
      "tier_level": 2,
      "distance_km": 5.2,
      "priority_score": 85.5,
      "primary_image": "https://domain.com/media/products/shoes.jpg",
      "views_count": 1200,
      "sales_count": 300
    }
  ]
}
```

Products are ranked by vendor priority (subscription tier, reviews, followers) and prices are automatically negotiated based on demand and vendor policies.

---

## 2. Negotiate Single Product

### 2.1 Negotiate Price for Product

```
POST /api/negotiations/negotiate/
```

**Auth:** Required

**Body:**

```json
{
  "product_id": "a1b2c3d4-...",
  "latitude": -26.2041,
  "longitude": 28.0473
}
```

**Success `200 OK`:**

```json
{
  "negotiation_id": "b2c3d4e5-...",
  "product_id": "a1b2c3d4-...",
  "product_name": "Running Shoes",
  "original_price": "1200.00",
  "negotiated_price": "1080.00",
  "adjustment_percent": "-10.00",
  "direction": "discount",
  "factors": {
    "demand": "low",
    "vendor_tier": "premium",
    "distance": 5.2
  },
  "expires_at": "2026-03-24T12:00:00Z"
}
```

Creates a 24-hour negotiation offer. Use the `negotiation_id` to accept it.

**Errors:**
- `404` if product not found or inactive
- `400` if validation fails

---

## 3. Accept Negotiation

### 3.1 Accept Negotiated Price

```
POST /api/negotiations/{negotiation_id}/accept/
```

**Auth:** Required (must be the buyer)

**Response `200 OK`:** The accepted negotiation record

```json
{
  "id": "b2c3d4e5-...",
  "product": "a1b2c3d4-...",
  "product_name": "Running Shoes",
  "buyer": 15,
  "buyer_email": "buyer@example.com",
  "vendor": 12,
  "vendor_email": "vendor@example.com",
  "original_price": "1200.00",
  "negotiated_price": "1080.00",
  "adjustment_percent": "-10.00",
  "direction": "discount",
  "factors": {
    "demand": "low",
    "vendor_tier": "premium",
    "distance": 5.2
  },
  "status": "accepted",
  "expires_at": "2026-03-24T12:00:00Z",
  "created_at": "2026-03-23T12:00:00Z"
}
```

**Errors:**
- `404` if negotiation not found or not yours
- `400` if expired

---

## 4. Price Policy Management

### 4.1 Get My Price Policy

```
GET /api/negotiations/policy/my-policy/
```

**Auth:** Required (vendor only)

**Response `200 OK`:**

```json
{
  "id": 5,
  "vendor": 12,
  "vendor_email": "vendor@example.com",
  "max_markup_percent": "15.00",
  "max_discount_percent": "10.00",
  "auto_negotiate": true,
  "is_active": true,
  "created_at": "2026-01-01T10:00:00Z",
  "updated_at": "2026-03-20T08:00:00Z"
}
```

If no policy exists, returns defaults:

```json
{
  "status": "none",
  "message": "No price policy set. Defaults apply (15% markup, 10% discount).",
  "defaults": {
    "max_markup_percent": "15.00",
    "max_discount_percent": "10.00",
    "auto_negotiate": true
  }
}
```

### 4.2 Set/Update Price Policy

```
POST /api/negotiations/policy/set-policy/
```

**Auth:** Required (vendor only)

**Body:**

```json
{
  "max_markup_percent": "20.00",
  "max_discount_percent": "15.00",
  "auto_negotiate": true
}
```

**Response `200 OK`:** Updated policy object

**Validation:**
- `max_markup_percent`: 0-50
- `max_discount_percent`: 0-50

---

## 5. My Negotiations

### 5.1 Negotiation History

```
GET /api/negotiations/my-negotiations/history/
```

**Auth:** Required

**Response `200 OK`:** Array of negotiation records (last 50)

### 5.2 Active Offers

```
GET /api/negotiations/my-negotiations/active/
```

**Auth:** Required

**Response `200 OK`:** Array of active (non-expired) offers

---

## 6. Dart Models

```dart
class NegotiatedProductResult {
  final String productId;
  final String name;
  final String slug;
  final String sku;
  final String? category;
  final String? brand;
  final int vendorId;
  final String vendorName;
  final String vendorType;
  final String originalPrice;
  final String negotiatedPrice;
  final String adjustmentPercent;
  final String direction;
  final Map<String, dynamic> priceFactors;
  final String averageRating;
  final int totalReviews;
  final int followerCount;
  final String? tierName;
  final int tierLevel;
  final double? distanceKm;
  final double priorityScore;
  final String? primaryImage;
  final int viewsCount;
  final int salesCount;

  NegotiatedProductResult({
    required this.productId,
    required this.name,
    required this.slug,
    required this.sku,
    this.category,
    this.brand,
    required this.vendorId,
    required this.vendorName,
    required this.vendorType,
    required this.originalPrice,
    required this.negotiatedPrice,
    required this.adjustmentPercent,
    required this.direction,
    required this.priceFactors,
    required this.averageRating,
    required this.totalReviews,
    required this.followerCount,
    this.tierName,
    required this.tierLevel,
    this.distanceKm,
    required this.priorityScore,
    this.primaryImage,
    required this.viewsCount,
    required this.salesCount,
  });

  factory NegotiatedProductResult.fromJson(Map<String, dynamic> json) => NegotiatedProductResult(
        productId: json['product_id'],
        name: json['name'],
        slug: json['slug'],
        sku: json['sku'],
        category: json['category'],
        brand: json['brand'],
        vendorId: json['vendor_id'],
        vendorName: json['vendor_name'],
        vendorType: json['vendor_type'],
        originalPrice: json['original_price'],
        negotiatedPrice: json['negotiated_price'],
        adjustmentPercent: json['adjustment_percent'],
        direction: json['direction'],
        priceFactors: json['price_factors'] as Map<String, dynamic>,
        averageRating: json['average_rating'],
        totalReviews: json['total_reviews'],
        followerCount: json['follower_count'],
        tierName: json['tier_name'],
        tierLevel: json['tier_level'],
        distanceKm: json['distance_km']?.toDouble(),
        priorityScore: json['priority_score'].toDouble(),
        primaryImage: json['primary_image'],
        viewsCount: json['views_count'],
        salesCount: json['sales_count'],
      );
}

class NegotiationOffer {
  final String negotiationId;
  final String productId;
  final String productName;
  final String originalPrice;
  final String negotiatedPrice;
  final String adjustmentPercent;
  final String direction;
  final Map<String, dynamic> factors;
  final String expiresAt;

  NegotiationOffer({
    required this.negotiationId,
    required this.productId,
    required this.productName,
    required this.originalPrice,
    required this.negotiatedPrice,
    required this.adjustmentPercent,
    required this.direction,
    required this.factors,
    required this.expiresAt,
  });

  factory NegotiationOffer.fromJson(Map<String, dynamic> json) => NegotiationOffer(
        negotiationId: json['negotiation_id'],
        productId: json['product_id'],
        productName: json['product_name'],
        originalPrice: json['original_price'],
        negotiatedPrice: json['negotiated_price'],
        adjustmentPercent: json['adjustment_percent'],
        direction: json['direction'],
        factors: json['factors'] as Map<String, dynamic>,
        expiresAt: json['expires_at'],
      );
}

class NegotiatedPrice {
  final String id;
  final String product;
  final String productName;
  final int buyer;
  final String buyerEmail;
  final int vendor;
  final String vendorEmail;
  final String originalPrice;
  final String negotiatedPrice;
  final String adjustmentPercent;
  final String direction;
  final Map<String, dynamic> factors;
  final String status;
  final String expiresAt;
  final DateTime createdAt;

  NegotiatedPrice({
    required this.id,
    required this.product,
    required this.productName,
    required this.buyer,
    required this.buyerEmail,
    required this.vendor,
    required this.vendorEmail,
    required this.originalPrice,
    required this.negotiatedPrice,
    required this.adjustmentPercent,
    required this.direction,
    required this.factors,
    required this.status,
    required this.expiresAt,
    required this.createdAt,
  });

  factory NegotiatedPrice.fromJson(Map<String, dynamic> json) => NegotiatedPrice(
        id: json['id'],
        product: json['product'],
        productName: json['product_name'],
        buyer: json['buyer'],
        buyerEmail: json['buyer_email'],
        vendor: json['vendor'],
        vendorEmail: json['vendor_email'],
        originalPrice: json['original_price'],
        negotiatedPrice: json['negotiated_price'],
        adjustmentPercent: json['adjustment_percent'],
        direction: json['direction'],
        factors: json['factors'] as Map<String, dynamic>,
        status: json['status'],
        expiresAt: json['expires_at'],
        createdAt: DateTime.parse(json['created_at']),
      );
}

class PricePolicy {
  final int id;
  final int vendor;
  final String vendorEmail;
  final String maxMarkupPercent;
  final String maxDiscountPercent;
  final bool autoNegotiate;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;

  PricePolicy({
    required this.id,
    required this.vendor,
    required this.vendorEmail,
    required this.maxMarkupPercent,
    required this.maxDiscountPercent,
    required this.autoNegotiate,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory PricePolicy.fromJson(Map<String, dynamic> json) => PricePolicy(
        id: json['id'],
        vendor: json['vendor'],
        vendorEmail: json['vendor_email'],
        maxMarkupPercent: json['max_markup_percent'],
        maxDiscountPercent: json['max_discount_percent'],
        autoNegotiate: json['auto_negotiate'],
        isActive: json['is_active'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}

class PricePolicyDefaults {
  final String status;
  final String message;
  final Map<String, dynamic> defaults;

  PricePolicyDefaults({
    required this.status,
    required this.message,
    required this.defaults,
  });

  factory PricePolicyDefaults.fromJson(Map<String, dynamic> json) => PricePolicyDefaults(
        status: json['status'],
        message: json['message'],
        defaults: json['defaults'] as Map<String, dynamic>,
      );
}
```

---

## 7. Dart API Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class NegotiationsApiService {
  final String baseUrl;
  final String? accessToken;

  NegotiationsApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (accessToken != null) 'Authorization': 'Bearer $accessToken',
      };

  Future<Map<String, dynamic>> searchProducts({
    String? query,
    String? category,
    double? latitude,
    double? longitude,
    int limit = 50,
  }) async {
    final queryParams = <String>[];
    if (query != null) queryParams.add('query=${Uri.encodeComponent(query)}');
    if (category != null) queryParams.add('category=${Uri.encodeComponent(category)}');
    if (latitude != null) queryParams.add('latitude=$latitude');
    if (longitude != null) queryParams.add('longitude=$longitude');
    queryParams.add('limit=$limit');

    final uri = Uri.parse('$baseUrl/api/negotiations/search/?${queryParams.join('&')}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) {
      throw Exception('Failed to search products: ${response.body}');
    }
    final data = jsonDecode(response.body);
    return {
      'count': data['count'],
      'results': (data['results'] as List)
          .map((e) => NegotiatedProductResult.fromJson(e as Map<String, dynamic>))
          .toList(),
    };
  }

  Future<NegotiationOffer> negotiateProduct({
    required String productId,
    double? latitude,
    double? longitude,
  }) async {
    final body = <String, dynamic>{
      'product_id': productId,
      if (latitude != null) 'latitude': latitude,
      if (longitude != null) 'longitude': longitude,
    };
    final response = await http.post(
      Uri.parse('$baseUrl/api/negotiations/negotiate/'),
      headers: _headers,
      body: jsonEncode(body),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to negotiate product: ${response.body}');
    }
    return NegotiationOffer.fromJson(jsonDecode(response.body));
  }

  Future<NegotiatedPrice> acceptNegotiation(String negotiationId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/negotiations/$negotiationId/accept/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to accept negotiation: ${response.body}');
    }
    return NegotiatedPrice.fromJson(jsonDecode(response.body));
  }

  Future<dynamic> getMyPricePolicy() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/negotiations/policy/my-policy/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to get price policy: ${response.body}');
    }
    final data = jsonDecode(response.body);
    if (data.containsKey('status')) {
      return PricePolicyDefaults.fromJson(data);
    } else {
      return PricePolicy.fromJson(data);
    }
  }

  Future<PricePolicy> setPricePolicy({
    required String maxMarkupPercent,
    required String maxDiscountPercent,
    required bool autoNegotiate,
  }) async {
    final body = {
      'max_markup_percent': maxMarkupPercent,
      'max_discount_percent': maxDiscountPercent,
      'auto_negotiate': autoNegotiate,
    };
    final response = await http.post(
      Uri.parse('$baseUrl/api/negotiations/policy/set-policy/'),
      headers: _headers,
      body: jsonEncode(body),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to set price policy: ${response.body}');
    }
    return PricePolicy.fromJson(jsonDecode(response.body));
  }

  Future<List<NegotiatedPrice>> getNegotiationHistory() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/negotiations/my-negotiations/history/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to get negotiation history: ${response.body}');
    }
    return (jsonDecode(response.body) as List)
        .map((e) => NegotiatedPrice.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<NegotiatedPrice>> getActiveOffers() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/negotiations/my-negotiations/active/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to get active offers: ${response.body}');
    }
    return (jsonDecode(response.body) as List)
        .map((e) => NegotiatedPrice.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
```

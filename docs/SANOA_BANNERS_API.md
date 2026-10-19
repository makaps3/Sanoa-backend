# Sanoa Banners API - Complete Documentation

> **Base URL:** `https://your-domain.com/api/products/`
>
> **Authentication:** JWT Bearer Token (unless noted as public)
>
> **Header:** `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Banners](#1-banners)
2. [Banner Images](#2-banner-images)
3. [Banners by Parent Category](#3-banners-by-parent-category)
4. [Dart Models](#4-dart-models)
5. [Dart API Service](#5-dart-api-service)

---

## 1. Banners

Banners are promotional items linked to categories. Each banner can have multiple images. List endpoints only return active banners within their scheduled date range. No pagination.

### 1.1 List All Banners

```
GET /api/products/banners/
```

**Auth:** Public
**Pagination:** None

**Query Parameters:**

| Param    | Type   | Required | Description                    |
|----------|--------|----------|--------------------------------|
| category | int    | No       | Filter by category ID          |

**Response `200 OK`:**

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Fresh Produce Deals",
    "subtitle": "Farm-fresh fruits and vegetables delivered to your door",
    "category": 669,
    "category_name": "Fresh Produce",
    "images": [
      {
        "id": 1,
        "image": "https://domain.com/media/banners/banner_fresh_produce_1.jpg",
        "alt_text": "Colourful fresh vegetables",
        "is_primary": true,
        "sort_order": 0,
        "created_at": "2026-04-01T10:00:00Z"
      },
      {
        "id": 2,
        "image": "https://domain.com/media/banners/banner_fresh_produce_2.jpg",
        "alt_text": "Fresh fruits display",
        "is_primary": false,
        "sort_order": 1,
        "created_at": "2026-04-01T10:00:00Z"
      }
    ],
    "primary_image": {
      "id": 1,
      "image": "https://domain.com/media/banners/banner_fresh_produce_1.jpg",
      "alt_text": "Colourful fresh vegetables",
      "is_primary": true,
      "sort_order": 0,
      "created_at": "2026-04-01T10:00:00Z"
    },
    "is_active": true,
    "sort_order": 0,
    "start_date": null,
    "end_date": null,
    "created_at": "2026-04-01T10:00:00Z"
  }
]
```

### 1.2 Retrieve Banner

```
GET /api/products/banners/{id}/
```

**Auth:** Public

**Response `200 OK`:** Single banner object (same shape as list item).

### 1.3 Create Banner

```
POST /api/products/banners/
```

**Auth:** Vendor or Admin

| Field      | Type     | Required | Description                                  |
|------------|----------|----------|----------------------------------------------|
| title      | string   | Yes      | Banner title (max 300 chars)                 |
| subtitle   | string   | No       | Banner subtitle (max 500 chars)              |
| category   | integer  | Yes      | Category ID to link the banner to            |
| is_active  | boolean  | No       | Default: `true`                              |
| sort_order | integer  | No       | Display order. Default: `0`                  |
| start_date | datetime | No       | Schedule start (ISO 8601). Null = immediate  |
| end_date   | datetime | No       | Schedule end (ISO 8601). Null = no expiry    |

**Response `201 Created`:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Fresh Produce Deals",
  "subtitle": "Farm-fresh fruits and vegetables delivered to your door",
  "category": 669,
  "category_name": "Fresh Produce",
  "images": [],
  "primary_image": null,
  "is_active": true,
  "sort_order": 0,
  "start_date": null,
  "end_date": null,
  "created_at": "2026-04-01T10:00:00Z"
}
```

### 1.4 Update Banner

```
PUT /api/products/banners/{id}/
PATCH /api/products/banners/{id}/
```

**Auth:** Vendor or Admin

Body fields same as create. `PATCH` allows partial updates.

**Response `200 OK`:** The updated banner object.

### 1.5 Delete Banner

```
DELETE /api/products/banners/{id}/
```

**Auth:** Vendor or Admin

**Response `204 No Content`**

---

## 2. Banner Images

Each banner can have multiple images. One image can be marked as `is_primary`.

### 2.1 List Banner Images

```
GET /api/products/banners/{id}/images/
```

**Auth:** Authenticated

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "image": "https://domain.com/media/banners/banner_fresh_produce_1.jpg",
    "alt_text": "Colourful fresh vegetables",
    "is_primary": true,
    "sort_order": 0,
    "created_at": "2026-04-01T10:00:00Z"
  },
  {
    "id": 2,
    "image": "https://domain.com/media/banners/banner_fresh_produce_2.jpg",
    "alt_text": "Fresh fruits display",
    "is_primary": false,
    "sort_order": 1,
    "created_at": "2026-04-01T10:00:00Z"
  }
]
```

### 2.2 Add Image to Banner

```
POST /api/products/banners/{id}/images/
```

**Auth:** Authenticated
**Content-Type:** `multipart/form-data`

| Field      | Type    | Required | Description                                       |
|------------|---------|----------|---------------------------------------------------|
| image      | file    | Yes      | Image file (JPEG, PNG, etc.)                      |
| alt_text   | string  | No       | Alt text for accessibility (max 200 chars)         |
| is_primary | boolean | No       | Mark as primary image. Default: `false`            |
| sort_order | integer | No       | Display order. Default: `0`                        |

> **Note:** Setting `is_primary: true` automatically unsets the previous primary image for that banner.

**Response `201 Created`:**

```json
{
  "id": 3,
  "image": "https://domain.com/media/banners/banner_image.jpg",
  "alt_text": "New banner image",
  "is_primary": true,
  "sort_order": 2,
  "created_at": "2026-04-01T12:00:00Z"
}
```

### 2.3 Delete Banner Image

```
DELETE /api/products/banners/{id}/images/{image_id}/
```

**Auth:** Authenticated

**Response `204 No Content`**

---

## 3. Banners by Parent Category

Returns all active banners linked to a parent category **and** any of its child categories. Useful for displaying relevant banners on a category page.

### 3.1 Get Banners by Parent Category

```
GET /api/products/banners/by-parent-category/
```

**Auth:** Public

**Query Parameters:**

| Param              | Type | Required | Description                  |
|--------------------|------|----------|------------------------------|
| parent_category_id | int  | Yes      | ID of the parent category    |

**Response `200 OK`:**

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Fresh Produce Deals",
    "subtitle": "Farm-fresh fruits and vegetables delivered to your door",
    "category": 669,
    "category_name": "Fresh Produce",
    "images": [
      {
        "id": 1,
        "image": "https://domain.com/media/banners/banner_fresh_produce_1.jpg",
        "alt_text": "Colourful fresh vegetables",
        "is_primary": true,
        "sort_order": 0,
        "created_at": "2026-04-01T10:00:00Z"
      }
    ],
    "primary_image": {
      "id": 1,
      "image": "https://domain.com/media/banners/banner_fresh_produce_1.jpg",
      "alt_text": "Colourful fresh vegetables",
      "is_primary": true,
      "sort_order": 0,
      "created_at": "2026-04-01T10:00:00Z"
    },
    "is_active": true,
    "sort_order": 0,
    "start_date": null,
    "end_date": null,
    "created_at": "2026-04-01T10:00:00Z"
  }
]
```

**Error `400 Bad Request`:**

```json
{
  "error": "parent_category_id is required."
}
```

**Error `404 Not Found`:** If the parent category does not exist or is inactive.

---

## 4. Dart Models

```dart
// ═══════════════════════════════════════════════════════════════════════
// Banner Image
// ═══════════════════════════════════════════════════════════════════════

class BannerImage {
  final int id;
  final String image;
  final String altText;
  final bool isPrimary;
  final int sortOrder;
  final DateTime createdAt;

  BannerImage({
    required this.id,
    required this.image,
    required this.altText,
    required this.isPrimary,
    required this.sortOrder,
    required this.createdAt,
  });

  factory BannerImage.fromJson(Map<String, dynamic> json) {
    return BannerImage(
      id: json['id'],
      image: json['image'],
      altText: json['alt_text'] ?? '',
      isPrimary: json['is_primary'],
      sortOrder: json['sort_order'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
    'alt_text': altText,
    'is_primary': isPrimary,
    'sort_order': sortOrder,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Banner
// ═══════════════════════════════════════════════════════════════════════

class Banner {
  final String id;
  final String title;
  final String subtitle;
  final int category;
  final String categoryName;
  final List<BannerImage> images;
  final BannerImage? primaryImage;
  final bool isActive;
  final int sortOrder;
  final DateTime? startDate;
  final DateTime? endDate;
  final DateTime createdAt;

  Banner({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.category,
    required this.categoryName,
    required this.images,
    this.primaryImage,
    required this.isActive,
    required this.sortOrder,
    this.startDate,
    this.endDate,
    required this.createdAt,
  });

  factory Banner.fromJson(Map<String, dynamic> json) {
    return Banner(
      id: json['id'],
      title: json['title'],
      subtitle: json['subtitle'] ?? '',
      category: json['category'],
      categoryName: json['category_name'],
      images: (json['images'] as List)
          .map((e) => BannerImage.fromJson(e))
          .toList(),
      primaryImage: json['primary_image'] != null
          ? BannerImage.fromJson(json['primary_image'])
          : null,
      isActive: json['is_active'],
      sortOrder: json['sort_order'],
      startDate: json['start_date'] != null
          ? DateTime.parse(json['start_date'])
          : null,
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'])
          : null,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Banner Create/Update Request
// ═══════════════════════════════════════════════════════════════════════

class BannerCreateRequest {
  final String title;
  final String? subtitle;
  final int category;
  final bool? isActive;
  final int? sortOrder;
  final DateTime? startDate;
  final DateTime? endDate;

  BannerCreateRequest({
    required this.title,
    this.subtitle,
    required this.category,
    this.isActive,
    this.sortOrder,
    this.startDate,
    this.endDate,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'title': title,
      'category': category,
    };
    if (subtitle != null) map['subtitle'] = subtitle;
    if (isActive != null) map['is_active'] = isActive;
    if (sortOrder != null) map['sort_order'] = sortOrder;
    if (startDate != null) map['start_date'] = startDate!.toIso8601String();
    if (endDate != null) map['end_date'] = endDate!.toIso8601String();
    return map;
  }
}
```

---

## 5. Dart API Service

```dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class BannersApiService {
  final String baseUrl;
  final String? accessToken;

  BannersApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (accessToken != null) 'Authorization': 'Bearer $accessToken',
  };

  Map<String, String> get _authHeaders => {
    if (accessToken != null) 'Authorization': 'Bearer $accessToken',
  };

  // ═════════════════════════════════════════════════════════════════════
  // Banners - CRUD
  // ═════════════════════════════════════════════════════════════════════

  /// List all active banners (optionally filtered by category)
  Future<List<Banner>> getBanners({int? categoryId}) async {
    final params = <String, String>{};
    if (categoryId != null) params['category'] = categoryId.toString();

    final uri = Uri.parse('$baseUrl/api/products/banners/')
        .replace(queryParameters: params.isNotEmpty ? params : null);

    final response = await http.get(uri, headers: _headers);
    final data = jsonDecode(response.body) as List;
    return data.map((e) => Banner.fromJson(e)).toList();
  }

  /// Get a single banner by ID
  Future<Banner> getBanner(String bannerId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/'),
      headers: _headers,
    );
    return Banner.fromJson(jsonDecode(response.body));
  }

  /// Create a new banner
  Future<Banner> createBanner(BannerCreateRequest request) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/products/banners/'),
      headers: _headers,
      body: jsonEncode(request.toJson()),
    );
    return Banner.fromJson(jsonDecode(response.body));
  }

  /// Update a banner (full update)
  Future<Banner> updateBanner(String bannerId, BannerCreateRequest request) async {
    final response = await http.put(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/'),
      headers: _headers,
      body: jsonEncode(request.toJson()),
    );
    return Banner.fromJson(jsonDecode(response.body));
  }

  /// Partially update a banner
  Future<Banner> patchBanner(String bannerId, Map<String, dynamic> fields) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/'),
      headers: _headers,
      body: jsonEncode(fields),
    );
    return Banner.fromJson(jsonDecode(response.body));
  }

  /// Delete a banner
  Future<void> deleteBanner(String bannerId) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/'),
      headers: _headers,
    );
  }

  // ═════════════════════════════════════════════════════════════════════
  // Banners - By Parent Category
  // ═════════════════════════════════════════════════════════════════════

  /// Get all active banners for a parent category and its children
  Future<List<Banner>> getBannersByParentCategory(int parentCategoryId) async {
    final uri = Uri.parse('$baseUrl/api/products/banners/by-parent-category/')
        .replace(queryParameters: {
      'parent_category_id': parentCategoryId.toString(),
    });

    final response = await http.get(uri, headers: _headers);
    final data = jsonDecode(response.body) as List;
    return data.map((e) => Banner.fromJson(e)).toList();
  }

  // ═════════════════════════════════════════════════════════════════════
  // Banner Images
  // ═════════════════════════════════════════════════════════════════════

  /// List all images for a banner
  Future<List<BannerImage>> getBannerImages(String bannerId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/images/'),
      headers: _headers,
    );
    final data = jsonDecode(response.body) as List;
    return data.map((e) => BannerImage.fromJson(e)).toList();
  }

  /// Upload an image to a banner
  Future<BannerImage> addBannerImage(
    String bannerId, {
    required File imageFile,
    String? altText,
    bool isPrimary = false,
    int sortOrder = 0,
  }) async {
    final uri = Uri.parse('$baseUrl/api/products/banners/$bannerId/images/');
    final request = http.MultipartRequest('POST', uri);

    // Auth header
    if (accessToken != null) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }

    // File
    request.files.add(
      await http.MultipartFile.fromPath('image', imageFile.path),
    );

    // Fields
    if (altText != null) request.fields['alt_text'] = altText;
    request.fields['is_primary'] = isPrimary.toString();
    request.fields['sort_order'] = sortOrder.toString();

    final streamedResponse = await request.send();
    final responseBody = await streamedResponse.stream.bytesToString();
    return BannerImage.fromJson(jsonDecode(responseBody));
  }

  /// Delete a specific image from a banner
  Future<void> deleteBannerImage(String bannerId, int imageId) async {
    await http.delete(
      Uri.parse('$baseUrl/api/products/banners/$bannerId/images/$imageId/'),
      headers: _headers,
    );
  }
}
```

---

## Usage Examples

### Flutter — Display banners on a category page

```dart
final service = BannersApiService(
  baseUrl: 'https://your-domain.com',
  accessToken: userToken,
);

// Get banners for "Food & Groceries" parent category (id: 668)
final banners = await service.getBannersByParentCategory(668);

for (final banner in banners) {
  print('${banner.title} — ${banner.images.length} images');
  if (banner.primaryImage != null) {
    print('  Primary: ${banner.primaryImage!.image}');
  }
}
```

### Flutter — Create a banner and upload images

```dart
// 1. Create the banner
final banner = await service.createBanner(BannerCreateRequest(
  title: 'Summer Sale',
  subtitle: 'Up to 50% off on selected items',
  category: 669,
  isActive: true,
  sortOrder: 0,
));

// 2. Upload images
final primaryImg = await service.addBannerImage(
  banner.id,
  imageFile: File('/path/to/hero-image.jpg'),
  altText: 'Summer sale hero banner',
  isPrimary: true,
);

final secondImg = await service.addBannerImage(
  banner.id,
  imageFile: File('/path/to/promo-image.jpg'),
  altText: 'Featured products',
  sortOrder: 1,
);

print('Banner created with ${banner.images.length + 2} images');
```

### Flutter — PageView banner carousel widget

```dart
class BannerCarousel extends StatelessWidget {
  final List<Banner> banners;

  const BannerCarousel({super.key, required this.banners});

  @override
  Widget build(BuildContext context) {
    // Flatten all banner images for a carousel
    final allImages = banners
        .expand((b) => b.images.map((img) => _CarouselItem(banner: b, image: img)))
        .toList();

    return SizedBox(
      height: 200,
      child: PageView.builder(
        itemCount: allImages.length,
        itemBuilder: (context, index) {
          final item = allImages[index];
          return GestureDetector(
            onTap: () {
              // Navigate to category page
              Navigator.pushNamed(
                context,
                '/category/${item.banner.category}',
              );
            },
            child: Stack(
              fit: StackFit.expand,
              children: [
                Image.network(item.image.image, fit: BoxFit.cover),
                Positioned(
                  bottom: 16,
                  left: 16,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.banner.title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (item.banner.subtitle.isNotEmpty)
                        Text(
                          item.banner.subtitle,
                          style: const TextStyle(color: Colors.white70),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _CarouselItem {
  final Banner banner;
  final BannerImage image;

  _CarouselItem({required this.banner, required this.image});
}
```

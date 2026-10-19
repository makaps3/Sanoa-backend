# Sanoa — Storefront Mode & Product Customization — Dart / Flutter Guide

This document is for the **Flutter frontend team**. It covers:

1. **Storefront modes** — Shopping (retail) vs Restaurants (restaurant)
2. **Product customization/options system** — addon groups with required choices, optional extras, multi-select, and price adjustments

---

## Table of Contents

1. [Storefront Toggle](#1-storefront-toggle)
2. [Endpoints — Storefront & Discovery](#2-endpoints--storefront--discovery)
3. [Product Customization System](#3-product-customization-system)
4. [Addon Group Endpoints](#4-addon-group-endpoints)
5. [Addon Endpoints](#5-addon-endpoints)
6. [Product Detail Response (with addon groups)](#6-product-detail-response-with-addon-groups)
7. [Cart Integration](#7-cart-integration)
8. [Order & Fulfillment](#8-order--fulfillment)
9. [Dart Models](#9-dart-models)
10. [Dart API Service](#10-dart-api-service)
11. [Industry Examples](#11-industry-examples)
12. [UI Wiring (Riverpod)](#12-ui-wiring-riverpod)
13. [Frontend Checklist](#13-frontend-checklist)
14. [Backend Reference](#14-backend-reference)

---

## 1. Storefront Toggle

Hold a single piece of state — `StorefrontMode` — and pass its value as a
`business_category` query parameter on discovery/category endpoints.

```dart
enum StorefrontMode { retail, restaurant }

extension StorefrontModeApi on StorefrontMode {
  String get apiValue => switch (this) {
        StorefrontMode.retail => 'retail',
        StorefrontMode.restaurant => 'restaurant',
      };

  String get label => switch (this) {
        StorefrontMode.retail => 'Shopping',
        StorefrontMode.restaurant => 'Restaurants',
      };
}
```

---

## 2. Endpoints — Storefront & Discovery

### 2.1 Discover stores

`GET /api/business/discover-stores/?business_category=restaurant`

### 2.2 List categories

`GET /api/products/categories/?business_category=retail`

### 2.3 Vendor profile

| Field | Type | Notes |
|---|---|---|
| `business_category` | string | `retail` or `restaurant` |
| `opening_hours` | object | Weekday-keyed windows `{"0": [{"open":"08:00","close":"21:00"}]}` |
| `is_temporarily_closed` | bool | Manual override |
| `is_open_now` | bool | Computed, read-only |

### 2.4 Product variants

`GET / POST / PATCH / DELETE /api/products/variants/?product={uuid}`

---

## 3. Product Customization System

The backend provides a **structured addon group system** that is flexible enough for any product type. The key concept:

```
Product
  └── AddonGroup (e.g. "Choose your sauce")
        ├── Addon ("BBQ", price_delta: 0)
        ├── Addon ("Mayo", price_delta: 0)
        └── Addon ("Truffle aioli", price_delta: 5.00)
  └── AddonGroup (e.g. "Extra toppings")
        ├── Addon ("Extra cheese", price_delta: 5.00)
        ├── Addon ("Bacon", price_delta: 8.00)
        └── Addon ("Avocado", price_delta: 10.00)
```

Each **AddonGroup** defines:
- `group_type`: `single` (radio button) or `multiple` (checkboxes)
- `is_required`: Must the customer make a selection?
- `min_selection`: Minimum number of choices (e.g. 1 sauce, 2 sides)
- `max_selection`: Maximum number of choices (e.g. max 3 toppings)

Each **Addon** within a group defines:
- `name`: Display name
- `price_delta`: Price adjustment (positive adds, negative subtracts, 0 = no change)
- `is_default`: Pre-selected when the product page loads

**Normal products with no options simply have an empty `addon_groups` list.**

---

## 4. Addon Group Endpoints

`GET / POST / PATCH / DELETE /api/products/addon-groups/`

**Permissions:** Public read; vendor (product owner) or admin can create/update/delete.

### Query Params

| Param | Type | Notes |
|---|---|---|
| `product` | UUID | Filter groups by parent product |

### Create Addon Group

```
POST /api/products/addon-groups/
```

```json
{
  "product": "8ce3...e1",
  "name": "Choose your sauce",
  "group_type": "single",
  "is_required": true,
  "min_selection": 1,
  "max_selection": 1,
  "is_active": true,
  "sort_order": 0
}
```

### Response

```json
{
  "id": 1,
  "product": "8ce3...e1",
  "name": "Choose your sauce",
  "group_type": "single",
  "is_required": true,
  "min_selection": 1,
  "max_selection": 1,
  "is_active": true,
  "sort_order": 0,
  "addons": [
    {
      "id": 1,
      "group": 1,
      "name": "BBQ Sauce",
      "price_delta": "0.00",
      "is_default": true,
      "is_active": true,
      "sort_order": 0,
      "created_at": "...",
      "updated_at": "..."
    },
    {
      "id": 2,
      "group": 1,
      "name": "Truffle aioli",
      "price_delta": "5.00",
      "is_default": false,
      "is_active": true,
      "sort_order": 1
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### AddonGroup Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `product` | UUID | Yes | Parent product |
| `name` | string | Yes | Group display name |
| `group_type` | enum | No | `single` (default) or `multiple` |
| `is_required` | bool | No | Default `false` |
| `min_selection` | int | No | Default `0` |
| `max_selection` | int | No | Default `1` |
| `is_active` | bool | No | Default `true` |
| `sort_order` | int | No | Display order |

---

## 5. Addon Endpoints

`GET / POST / PATCH / DELETE /api/products/addons/`

**Permissions:** Public read; vendor (product owner) or admin can create/update/delete.

### Query Params

| Param | Type | Notes |
|---|---|---|
| `group` | int | Filter addons by group ID |
| `product` | UUID | Filter addons by product (across all groups) |

### Create Addon

```
POST /api/products/addons/
```

```json
{
  "group": 1,
  "name": "Extra cheese",
  "price_delta": 5.00,
  "is_default": false,
  "is_active": true,
  "sort_order": 0
}
```

### Addon Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `group` | int | Yes | Parent addon group ID |
| `name` | string | Yes | Display name |
| `price_delta` | decimal | No | Price adjustment (default `0.00`) |
| `is_default` | bool | No | Pre-selected (default `false`) |
| `is_active` | bool | No | Default `true` |
| `sort_order` | int | No | Display order |

---

## 6. Product Detail Response (with addon groups)

`GET /api/products/products/{id}/`

The product detail now includes `addon_groups` (replaces the old flat `addons` list):

```json
{
  "id": "8ce3...e1",
  "name": "Classic Burger",
  "price": "65.00",
  "variants": [
    {"id": 1, "name": "Single", "effective_price": "65.00"},
    {"id": 2, "name": "Double", "effective_price": "85.00"}
  ],
  "addon_groups": [
    {
      "id": 1,
      "name": "Choose your sauce",
      "group_type": "single",
      "is_required": true,
      "min_selection": 1,
      "max_selection": 1,
      "addons": [
        {"id": 1, "name": "BBQ Sauce", "price_delta": "0.00", "is_default": true},
        {"id": 2, "name": "Mayo", "price_delta": "0.00", "is_default": false},
        {"id": 3, "name": "Truffle aioli", "price_delta": "5.00", "is_default": false}
      ]
    },
    {
      "id": 2,
      "name": "Extra toppings",
      "group_type": "multiple",
      "is_required": false,
      "min_selection": 0,
      "max_selection": 5,
      "addons": [
        {"id": 4, "name": "Extra cheese", "price_delta": "5.00", "is_default": false},
        {"id": 5, "name": "Bacon", "price_delta": "8.00", "is_default": false},
        {"id": 6, "name": "Avocado", "price_delta": "10.00", "is_default": false}
      ]
    },
    {
      "id": 3,
      "name": "Choose 2 sides",
      "group_type": "multiple",
      "is_required": true,
      "min_selection": 2,
      "max_selection": 2,
      "addons": [
        {"id": 7, "name": "Fries", "price_delta": "0.00", "is_default": true},
        {"id": 8, "name": "Onion rings", "price_delta": "5.00", "is_default": false},
        {"id": 9, "name": "Coleslaw", "price_delta": "0.00", "is_default": true},
        {"id": 10, "name": "Side salad", "price_delta": "0.00", "is_default": false}
      ]
    }
  ],
  "images": [],
  "reviews": []
}
```

**Products with no customization options** return `"addon_groups": []`.

---

## 7. Cart Integration

When adding to cart, send `selected_addons` as a snapshot with group context:

```json
{
  "product": "8ce3...e1",
  "product_variant": 2,
  "quantity": 1,
  "special_instructions": "No pickles",
  "selected_addons": [
    {"group_id": 1, "addon_id": 2, "name": "Mayo", "price_delta": "0.00"},
    {"group_id": 2, "addon_id": 4, "name": "Extra cheese", "price_delta": "5.00"},
    {"group_id": 2, "addon_id": 5, "name": "Bacon", "price_delta": "8.00"},
    {"group_id": 3, "addon_id": 7, "name": "Fries", "price_delta": "0.00"},
    {"group_id": 3, "addon_id": 9, "name": "Coleslaw", "price_delta": "0.00"}
  ]
}
```

### Frontend validation before sending

For each `addon_group` where `is_required == true`, validate:
- At least `min_selection` addons from that group are selected
- At most `max_selection` addons from that group are selected
- For `single` type groups, exactly 1 addon is selected

### Price calculation

```
unit_price = variant.effective_price ?? product.price
addons_total = sum of all selected_addons[].price_delta
line_total = quantity * (unit_price + addons_total)
```

---

## 8. Order & Fulfillment

### Fulfillment types

| Type | Description |
|---|---|
| `delivery` | Default. Standard shipping/delivery |
| `pickup` | Customer picks up from vendor |
| `dine_in` | Restaurant dine-in. Requires `table_number` |

### Restaurant order statuses

```
received → preparing → ready → out_for_delivery → completed
                         ↘ (pickup / dine_in)  → completed
```

### Order item snapshot

Each `OrderItem` persists the `special_instructions` and `selected_addons`
snapshot so the kitchen sees exactly what was ordered — changes to the
product catalog after ordering don't affect existing orders.

---

## 9. Dart Models

```dart
class ProductAddonGroup {
  ProductAddonGroup({
    required this.id,
    required this.name,
    required this.type,
    required this.isRequired,
    required this.minSelection,
    required this.maxSelection,
    required this.addons,
  });

  final int id;
  final String name;

  /// 'single' = radio buttons, 'multiple' = checkboxes
  final String type;
  final bool isRequired;

  /// e.g. 1 sauce minimum
  final int minSelection;

  /// e.g. max 3 extras
  final int maxSelection;

  final List<ProductAddon> addons;

  factory ProductAddonGroup.fromJson(Map<String, dynamic> json) {
    return ProductAddonGroup(
      id: json['id'] as int,
      name: json['name'] as String,
      type: json['group_type'] ?? 'single',
      isRequired: json['is_required'] ?? false,
      minSelection: json['min_selection'] ?? 0,
      maxSelection: json['max_selection'] ?? 1,
      addons: (json['addons'] as List<dynamic>? ?? [])
          .map((e) => ProductAddon.fromJson(e))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'group_type': type,
        'is_required': isRequired,
        'min_selection': minSelection,
        'max_selection': maxSelection,
        'addons': addons.map((e) => e.toJson()).toList(),
      };

  /// Validate that a list of selected addon IDs satisfies this group's rules.
  String? validate(List<int> selectedAddonIds) {
    final count = addons.where((a) => selectedAddonIds.contains(a.id)).length;

    if (isRequired && count < minSelection) {
      return 'Please select at least $minSelection option(s) for "$name"';
    }
    if (count > maxSelection) {
      return 'Maximum $maxSelection option(s) allowed for "$name"';
    }
    return null; // valid
  }
}

class ProductAddon {
  ProductAddon({
    required this.id,
    required this.name,
    required this.priceDelta,
    this.isDefault = false,
  });

  final int id;
  final String name;
  final double priceDelta;
  final bool isDefault;

  factory ProductAddon.fromJson(Map<String, dynamic> json) {
    return ProductAddon(
      id: json['id'] as int,
      name: json['name'] as String,
      priceDelta: double.tryParse(json['price_delta'].toString()) ?? 0.0,
      isDefault: json['is_default'] ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'price_delta': priceDelta,
        'is_default': isDefault,
      };

  /// Snapshot shape stored in cart/order for history
  Map<String, dynamic> toCartSnapshot(int groupId) => {
        'group_id': groupId,
        'addon_id': id,
        'name': name,
        'price_delta': priceDelta.toStringAsFixed(2),
      };
}

class SelectedAddon {
  final int groupId;
  final int addonId;
  final String name;
  final double priceDelta;

  SelectedAddon({
    required this.groupId,
    required this.addonId,
    required this.name,
    required this.priceDelta,
  });

  factory SelectedAddon.fromJson(Map<String, dynamic> json) {
    return SelectedAddon(
      groupId: json['group_id'],
      addonId: json['addon_id'],
      name: json['name'] ?? '',
      priceDelta: double.tryParse(json['price_delta'].toString()) ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'group_id': groupId,
        'addon_id': addonId,
        'name': name,
        'price_delta': priceDelta.toStringAsFixed(2),
      };
}

class ProductVariant {
  ProductVariant({
    required this.id,
    required this.name,
    required this.effectivePrice,
    this.inventoryQuantity = 0,
    this.isActive = true,
  });

  final int id;
  final String name;
  final double effectivePrice;
  final int inventoryQuantity;
  final bool isActive;

  factory ProductVariant.fromJson(Map<String, dynamic> json) => ProductVariant(
        id: json['id'] as int,
        name: json['name'] as String,
        effectivePrice: double.parse(json['effective_price'].toString()),
        inventoryQuantity: (json['inventory_quantity'] as int?) ?? 0,
        isActive: (json['is_active'] as bool?) ?? true,
      );
}

class StoreSummary {
  StoreSummary({
    required this.id,
    required this.vendorType,
    required this.businessCategory,
    required this.isOpenNow,
    required this.name,
    this.logo,
    this.distanceKm,
    this.averageRating = 0,
  });

  final int id;
  final String vendorType;
  final StorefrontMode businessCategory;
  final bool isOpenNow;
  final String name;
  final String? logo;
  final double? distanceKm;
  final double averageRating;

  factory StoreSummary.fromJson(Map<String, dynamic> json) => StoreSummary(
        id: json['id'] as int,
        vendorType: json['vendor_type'] as String,
        businessCategory:
            (json['business_category'] as String?) == 'restaurant'
                ? StorefrontMode.restaurant
                : StorefrontMode.retail,
        isOpenNow: (json['is_open_now'] as bool?) ?? true,
        name: json['name'] as String,
        logo: json['logo'] as String?,
        distanceKm: (json['distance_km'] as num?)?.toDouble(),
        averageRating: (json['average_rating'] as num?)?.toDouble() ?? 0,
      );
}

enum FulfillmentType { delivery, pickup, dineIn }

extension FulfillmentTypeApi on FulfillmentType {
  String get apiValue => switch (this) {
        FulfillmentType.delivery => 'delivery',
        FulfillmentType.pickup => 'pickup',
        FulfillmentType.dineIn => 'dine_in',
      };
}

class OpeningHours {
  final Map<int, List<({String open, String close})>> windows;
  const OpeningHours(this.windows);

  factory OpeningHours.fromJson(Map<String, dynamic> json) {
    final out = <int, List<({String open, String close})>>{};
    for (final entry in json.entries) {
      final day = int.tryParse(entry.key);
      if (day == null) continue;
      final list = (entry.value as List? ?? const [])
          .cast<Map<String, dynamic>>()
          .map((w) => (open: w['open'] as String, close: w['close'] as String))
          .toList();
      out[day] = list;
    }
    return OpeningHours(out);
  }

  Map<String, dynamic> toJson() => {
        for (final e in windows.entries)
          e.key.toString():
              e.value.map((w) => {'open': w.open, 'close': w.close}).toList(),
      };
}
```

---

## 10. Dart API Service

```dart
class StorefrontApi {
  StorefrontApi(this._dio);
  final Dio _dio;

  // ── Discovery ─────────────────────────────────────────────

  Future<DiscoverStoresResponse> discoverStores({
    required StorefrontMode mode,
    double? latitude,
    double? longitude,
  }) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/api/business/discover-stores/',
      queryParameters: {
        'business_category': mode.apiValue,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
      },
    );
    return DiscoverStoresResponse.fromJson(res.data!);
  }

  Future<List<Category>> listCategories({required StorefrontMode mode}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/api/products/categories/',
      queryParameters: {'business_category': mode.apiValue},
    );
    final results = (res.data!['results'] as List).cast<Map<String, dynamic>>();
    return results.map(Category.fromJson).toList();
  }

  // ── Product Variants ──────────────────────────────────────

  Future<List<ProductVariant>> productVariants(String productId) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/api/products/variants/',
      queryParameters: {'product': productId},
    );
    final results = (res.data!['results'] ?? res.data!) as List;
    return results
        .cast<Map<String, dynamic>>()
        .map(ProductVariant.fromJson)
        .toList();
  }

  // ── Addon Groups (with nested addons) ─────────────────────

  Future<List<ProductAddonGroup>> productAddonGroups(String productId) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/api/products/addon-groups/',
      queryParameters: {'product': productId},
    );
    final results = (res.data!['results'] ?? res.data!) as List;
    return results
        .cast<Map<String, dynamic>>()
        .map(ProductAddonGroup.fromJson)
        .toList();
  }

  /// Create an addon group (vendor/admin only)
  Future<ProductAddonGroup> createAddonGroup({
    required String productId,
    required String name,
    String groupType = 'single',
    bool isRequired = false,
    int minSelection = 0,
    int maxSelection = 1,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/api/products/addon-groups/',
      data: {
        'product': productId,
        'name': name,
        'group_type': groupType,
        'is_required': isRequired,
        'min_selection': minSelection,
        'max_selection': maxSelection,
      },
    );
    return ProductAddonGroup.fromJson(res.data!);
  }

  /// Create an addon within a group (vendor/admin only)
  Future<ProductAddon> createAddon({
    required int groupId,
    required String name,
    double priceDelta = 0,
    bool isDefault = false,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/api/products/addons/',
      data: {
        'group': groupId,
        'name': name,
        'price_delta': priceDelta,
        'is_default': isDefault,
      },
    );
    return ProductAddon.fromJson(res.data!);
  }

  // ── Cart ──────────────────────────────────────────────────

  /// Validate addon selections before adding to cart.
  /// Returns null if valid, or a list of error messages.
  List<String>? validateAddonSelections({
    required List<ProductAddonGroup> groups,
    required List<SelectedAddon> selectedAddons,
  }) {
    final errors = <String>[];

    for (final group in groups) {
      final selectedInGroup =
          selectedAddons.where((s) => s.groupId == group.id).length;

      if (group.isRequired && selectedInGroup < group.minSelection) {
        errors.add(
          'Select at least ${group.minSelection} option(s) for "${group.name}"',
        );
      }
      if (selectedInGroup > group.maxSelection) {
        errors.add(
          'Maximum ${group.maxSelection} option(s) for "${group.name}"',
        );
      }
    }

    return errors.isEmpty ? null : errors;
  }

  Future<void> addToCart({
    required String productId,
    int? variantId,
    int quantity = 1,
    String specialInstructions = '',
    List<SelectedAddon> selectedAddons = const [],
  }) async {
    await _dio.post('/api/orders/cart-items/', data: {
      'product': productId,
      if (variantId != null) 'product_variant': variantId,
      'quantity': quantity,
      'special_instructions': specialInstructions,
      'selected_addons': selectedAddons.map((a) => a.toJson()).toList(),
    });
  }

  // ── Checkout ──────────────────────────────────────────────

  Future<Map<String, dynamic>> placeOrder({
    required FulfillmentType fulfillment,
    String? tableNumber,
    DateTime? scheduledFor,
    required Map<String, dynamic> address,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/api/orders/orders/',
      data: {
        ...address,
        'fulfillment_type': fulfillment.apiValue,
        if (tableNumber != null && fulfillment == FulfillmentType.dineIn)
          'table_number': tableNumber,
        if (scheduledFor != null)
          'scheduled_for': scheduledFor.toUtc().toIso8601String(),
      },
    );
    return res.data!;
  }
}
```

---

## 11. Industry Examples

### Food Ordering (Burger)

```
Product: "Classic Burger" — R65

Addon Groups:
  1. "Choose your sauce" — required, single, min=1, max=1
     → BBQ (R0) | Mayo (R0) | Chili (R0) | Truffle aioli (+R5)

  2. "Extra toppings" — optional, multiple, min=0, max=5
     → Extra cheese (+R5) | Bacon (+R8) | Avocado (+R10) | Jalapeños (+R3)

  3. "Choose 2 sides" — required, multiple, min=2, max=2
     → Fries (R0) | Onion rings (+R5) | Coleslaw (R0) | Side salad (R0)

  4. "Drink" — optional, single, min=0, max=1
     → Coke (R0) | Sprite (R0) | Water (R0) | Milkshake (+R15)
```

### Fashion (T-Shirt)

```
Product: "Cotton T-Shirt" — R199

Addon Groups:
  1. "Size" — required, single, min=1, max=1
     → S (R0) | M (R0) | L (R0) | XL (+R20) | XXL (+R40)

  2. "Color" — required, single, min=1, max=1
     → Black (R0) | White (R0) | Navy (R0) | Red (R0)
```

### Electronics (Phone)

```
Product: "Smartphone X" — R8999

Addon Groups:
  1. "Storage" — required, single, min=1, max=1
     → 64GB (R0) | 128GB (+R1500) | 256GB (+R3000) | 512GB (+R5000)

  2. "Color" — required, single, min=1, max=1
     → Midnight Black (R0) | Silver (R0) | Gold (+R500)

  3. "Warranty" — optional, single, min=0, max=1
     → 1 Year Standard (R0) | 2 Year Extended (+R999) | 3 Year Premium (+R1499)

  4. "Accessories" — optional, multiple, min=0, max=3
     → Screen protector (+R149) | Case (+R299) | Wireless charger (+R399)
```

### Normal Product (Book — no options)

```
Product: "Django for Beginners" — R450

Addon Groups: [] (empty — no customization needed)
```

---

## 12. UI Wiring (Riverpod)

```dart
final storefrontModeProvider =
    StateProvider<StorefrontMode>((ref) => StorefrontMode.retail);

/// Tracks selected addons per group for the current product being viewed
final selectedAddonsProvider =
    StateProvider.family<List<SelectedAddon>, String>(
  (ref, productId) => [],
);

class AddonGroupWidget extends ConsumerWidget {
  const AddonGroupWidget({
    super.key,
    required this.productId,
    required this.group,
  });

  final String productId;
  final ProductAddonGroup group;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = ref.watch(selectedAddonsProvider(productId));
    final selectedInGroup =
        selected.where((s) => s.groupId == group.id).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Row(
          children: [
            Text(
              group.name,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (group.isRequired)
              Container(
                margin: const EdgeInsets.only(left: 8),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'Required',
                  style: TextStyle(fontSize: 10, color: Colors.red.shade700),
                ),
              ),
          ],
        ),
        if (group.maxSelection > 1)
          Text(
            'Select ${group.minSelection}-${group.maxSelection}',
            style: Theme.of(context).textTheme.bodySmall,
          ),

        // Options
        ...group.addons.map((addon) {
          final isSelected =
              selectedInGroup.any((s) => s.addonId == addon.id);

          return CheckboxListTile(
            title: Text(addon.name),
            subtitle: addon.priceDelta != 0
                ? Text(
                    '${addon.priceDelta > 0 ? "+" : ""}R${addon.priceDelta.toStringAsFixed(2)}',
                  )
                : null,
            value: isSelected,
            onChanged: (checked) {
              final notifier =
                  ref.read(selectedAddonsProvider(productId).notifier);
              final current = List<SelectedAddon>.from(notifier.state);

              if (checked == true) {
                // For single-select, remove other selections in this group
                if (group.type == 'single') {
                  current.removeWhere((s) => s.groupId == group.id);
                }
                // Check max
                final countInGroup =
                    current.where((s) => s.groupId == group.id).length;
                if (countInGroup >= group.maxSelection) return;

                current.add(SelectedAddon(
                  groupId: group.id,
                  addonId: addon.id,
                  name: addon.name,
                  priceDelta: addon.priceDelta,
                ));
              } else {
                current.removeWhere(
                  (s) => s.groupId == group.id && s.addonId == addon.id,
                );
              }

              notifier.state = current;
            },
          );
        }),
      ],
    );
  }
}
```

---

## 13. Frontend Checklist

### Product Detail Screen
- [ ] Fetch `addon_groups` from product detail (embedded in response)
- [ ] For each group, render the appropriate UI:
  - `single` + `is_required` → **Radio buttons** (must select 1)
  - `single` + not required → **Radio buttons with "None" option**
  - `multiple` → **Checkboxes** with `min_selection`/`max_selection` enforcement
- [ ] Pre-select addons where `is_default == true`
- [ ] Show `price_delta` badge on each option ("+R5.00" or "included")
- [ ] Calculate and display running total: `base_price + sum(selected price_deltas)`
- [ ] Validate all required groups before enabling "Add to Cart" button
- [ ] Send `selected_addons` with `group_id`, `addon_id`, `name`, `price_delta` to cart

### Vendor Product Management
- [ ] Add "Customization Options" section when editing a product
- [ ] CRUD for addon groups: `POST/PATCH/DELETE /api/products/addon-groups/`
- [ ] CRUD for addons within groups: `POST/PATCH/DELETE /api/products/addons/`
- [ ] Drag-to-reorder using `sort_order` field

### Cart Screen
- [ ] Display selected addons under each cart line item
- [ ] Show per-line addon total
- [ ] Multiple lines for same product with different addons is valid

### Storefront
- [ ] `StorefrontMode` toggle (Shopping / Restaurants)
- [ ] Pass `business_category` on discovery and category endpoints
- [ ] Show `is_open_now` badge on restaurant stores
- [ ] Opening hours display on vendor profile

### Order & Fulfillment
- [ ] Fulfillment type picker for restaurant orders
- [ ] Table number input for dine-in
- [ ] Restaurant-specific order status tracking

---

## 14. Backend Reference

| Concern | File(s) |
|---|---|
| `ProductAddonGroup` + `ProductAddon` models | [products/models.py](../products/models.py) |
| Addon group/addon serializers | [products/serializers.py](../products/serializers.py) |
| `ProductAddonGroupViewSet` + `ProductAddonViewSet` | [products/views.py](../products/views.py) |
| URL routes (`addon-groups/`, `addons/`) | [products/urls.py](../products/urls.py) |
| Admin (inline addons in groups) | [products/admin.py](../products/admin.py) |
| Vendor `business_category` + opening hours | [business/models.py](../business/models.py) |
| Category `business_category` filter | [products/views.py](../products/views.py) |
| Cart `selected_addons` snapshot | [orders/models.py](../orders/models.py) |
| Order fulfillment fields | [orders/models.py](../orders/models.py) |

### Migrations

```
products.0012_addon_groups    OK
```

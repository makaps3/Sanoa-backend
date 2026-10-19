# Vendor Inventory Service — Flutter

Copy this class into your Flutter project.

**Dependency required** (`pubspec.yaml`):
```yaml
dependencies:
  http: ^1.2.0
```

---

## The Rule

| Method | URL contains | Auth |
|--------|-------------|------|
| `GET` | `vendor/<vendor_uuid>/...` | No token — `vendor_uuid` alone routes to the vendor |
| `POST` | `vendor/<vendor_uuid>/...` | JWT required — `vendor_uuid` routes to vendor, `Authorization` validates the user |

---

## Service Class

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class VendorInventoryService {
  static const String _baseUrl = '/api/inventory';

  /// GET requests — no token needed.
  static Map<String, String> _getHeaders() {
    return {'Content-Type': 'application/json'};
  }

  /// POST requests — vendor_uuid identifies the vendor,
  /// Authorization Bearer token validates the authenticated user.
  static Map<String, String> _postHeaders(String? token) {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (token != null) headers['Authorization'] = 'Bearer $token';
    return headers;
  }

  // ── Warehouses ────────────────────────────────────────────────────────────

  static Future<http.Response> getWarehouses(String vendorUuid) {
    return http.get(
      Uri.parse('$_baseUrl/vendor/$vendorUuid/warehouses/'),
      headers: _getHeaders(),
    );
  }

  static Future<http.Response> createWarehouse(
    String vendorUuid,
    Map<String, dynamic> body,
    String? token,
  ) {
    return http.post(
      Uri.parse('$_baseUrl/vendor/$vendorUuid/warehouses/'),
      headers: _postHeaders(token),
      body: jsonEncode(body),
    );
  }

  // ── Inventory Items ───────────────────────────────────────────────────────

  /// [stockStatus]: 'in_stock' | 'low_stock' | 'out_of_stock' | 'backordered' | 'discontinued'
  static Future<http.Response> getInventoryItems(
    String vendorUuid, {
    String? stockStatus,
  }) {
    final uri = Uri.parse('$_baseUrl/vendor/$vendorUuid/items/').replace(
      queryParameters: {
        if (stockStatus != null) 'stock_status': stockStatus,
      },
    );
    return http.get(uri, headers: _getHeaders());
  }

  static Future<http.Response> createInventoryItem(
    String vendorUuid,
    Map<String, dynamic> body,
    String? token,
  ) {
    return http.post(
      Uri.parse('$_baseUrl/vendor/$vendorUuid/items/'),
      headers: _postHeaders(token),
      body: jsonEncode(body),
    );
  }

  // ── Stock Movements ───────────────────────────────────────────────────────

  /// [movementType]: 'purchase' | 'sale' | 'return' | 'adjustment' | 'transfer' | 'damage' | etc.
  static Future<http.Response> getStockMovements(
    String vendorUuid, {
    String? movementType,
  }) {
    final uri = Uri.parse('$_baseUrl/vendor/$vendorUuid/movements/').replace(
      queryParameters: {
        if (movementType != null) 'movement_type': movementType,
      },
    );
    return http.get(uri, headers: _getHeaders());
  }

  // ── Purchase Orders ───────────────────────────────────────────────────────

  /// [status]: 'draft' | 'sent' | 'confirmed' | 'partially_received' | 'received' | 'cancelled'
  static Future<http.Response> getPurchaseOrders(
    String vendorUuid, {
    String? status,
  }) {
    final uri = Uri.parse('$_baseUrl/vendor/$vendorUuid/purchase-orders/').replace(
      queryParameters: {
        if (status != null) 'status': status,
      },
    );
    return http.get(uri, headers: _getHeaders());
  }

  /// supplier is auto-set from vendor_uuid.
  /// created_by is auto-set from the JWT token on the backend.
  static Future<http.Response> createPurchaseOrder(
    String vendorUuid,
    Map<String, dynamic> body,
    String? token,
  ) {
    return http.post(
      Uri.parse('$_baseUrl/vendor/$vendorUuid/purchase-orders/'),
      headers: _postHeaders(token),
      body: jsonEncode(body),
    );
  }

  // ── Stock Alerts ──────────────────────────────────────────────────────────

  /// [status]: 'active' | 'acknowledged' | 'resolved' | 'dismissed'
  /// [alertType]: 'low_stock' | 'out_of_stock' | 'reorder_point' | 'overstock' | 'expired' | 'damage'
  static Future<http.Response> getAlerts(
    String vendorUuid, {
    String? status,
    String? alertType,
  }) {
    final uri = Uri.parse('$_baseUrl/vendor/$vendorUuid/alerts/').replace(
      queryParameters: {
        if (status != null) 'status': status,
        if (alertType != null) 'alert_type': alertType,
      },
    );
    return http.get(uri, headers: _getHeaders());
  }

  /// inventory_item in body must belong to this vendor's products.
  static Future<http.Response> createAlert(
    String vendorUuid,
    Map<String, dynamic> body,
    String? token,
  ) {
    return http.post(
      Uri.parse('$_baseUrl/vendor/$vendorUuid/alerts/'),
      headers: _postHeaders(token),
      body: jsonEncode(body),
    );
  }
}
```

---

## Usage

```dart
// vendor_uuid comes from GET /api/accounts/me/
final vendorUuid = userProfile['vendor_profile']['id'];

// token comes from login response (store securely)
final token = await storage.read(key: 'access_token');
```

### GET — no token needed

```dart
// List inventory items filtered by stock status
final response = await VendorInventoryService.getInventoryItems(
  vendorUuid,
  stockStatus: 'low_stock',
);
```

### POST — token required

```dart
// Create warehouse — manager auto-linked to authenticated user on backend
final response = await VendorInventoryService.createWarehouse(
  vendorUuid,
  {
    'name': 'Lagos Main Warehouse',
    'code': 'LGS-001',
    'street_address': '12 Apapa Road',
    'city': 'Lagos',
    'state_province': 'Lagos',
    'postal_code': '100001',
    'country': 'Nigeria',
    'is_active': true,
    'is_default': false,
  },
  token,
);
```

```dart
// Create purchase order — supplier auto-set from vendorUuid, created_by from token
final response = await VendorInventoryService.createPurchaseOrder(
  vendorUuid,
  {
    'warehouse': 1,
    'status': 'draft',
    'expected_delivery_date': '2026-06-01T00:00:00Z',
    'tax_amount': '0.00',
    'shipping_cost': '0.00',
    'notes': 'Monthly restock',
  },
  token,
);
```

```dart
// Create inventory item — product must belong to this vendor
final response = await VendorInventoryService.createInventoryItem(
  vendorUuid,
  {
    'product': '<product-uuid>',
    'warehouse': 1,
    'quantity_on_hand': 100,
    'minimum_stock_level': 10,
    'reorder_point': 20,
    'reorder_quantity': 50,
    'unit_cost': '15.00',
  },
  token,
);
```

```dart
// Create alert — inventory_item must belong to this vendor
final response = await VendorInventoryService.createAlert(
  vendorUuid,
  {
    'inventory_item': 5,
    'alert_type': 'low_stock',
    'message': 'Stock running low.',
    'current_stock_level': 5,
    'threshold_level': 10,
  },
  token,
);
```

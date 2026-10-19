# Sanoa Inventory API - Complete Documentation

> **Base URL:** `https://your-domain.com/api/inventory/`
>
> **Authentication:** JWT Bearer Token
>
> **Header:** `Authorization: Bearer <access_token>`
>
> **Permission:** `IsAuthenticated`, plus `IsVendorOrAdmin` for resource management

---

## Table of Contents

1. [Warehouses](#1-warehouses)
2. [Inventory Items](#2-inventory-items)
3. [Stock Movements](#3-stock-movements)
4. [Purchase Orders](#4-purchase-orders)
5. [Stock Alerts](#5-stock-alerts)
6. [Dart Models](#6-dart-models)
7. [Dart API Service](#7-dart-api-service)

---

## 1. Warehouses

### 1.1 List Warehouses

```
GET /api/inventory/warehouses/
```

Query params:
- `search` by name/code/city
- `ordering` (e.g. `name`)

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Main Warehouse",
    "code": "MW-001",
    "description": "Primary stock facility",
    "street_address": "123 Main St",
    "city": "Johannesburg",
    "state_province": "Gauteng",
    "postal_code": "2000",
    "country": "South Africa",
    "phone_number": "+27123456789",
    "email": "warehouse@example.com",
    "manager": 42,
    "manager_email": "manager@example.com",
    "is_active": true,
    "is_default": true,
    "created_at": "2026-01-01T10:00:00Z",
    "updated_at": "2026-03-20T08:30:00Z"
  }
]
```

### 1.2 Retrieve Warehouse

```
GET /api/inventory/warehouses/{id}/
```

### 1.3 Create Warehouse

```
POST /api/inventory/warehouses/
```

Body fields:
- `name`, `code`, `street_address`, `city`, `state_province`, `postal_code`, `country`
- `description`, `phone_number`, `email`, `manager`, `is_active`, `is_default`

**Response `201 Created`** returns warehouse object.

### 1.4 Update Warehouse

```
PUT /api/inventory/warehouses/{id}/
PATCH /api/inventory/warehouses/{id}/
```

### 1.5 Delete Warehouse

```
DELETE /api/inventory/warehouses/{id}/
```

**Response `204 No Content`**

---

## 2. Inventory Items

### 2.1 List Inventory Items

```
GET /api/inventory/items/
```

Query params:
- `search` (product name or location code)
- `filter[warehouse]=<id>`
- `filter[stock_status]=in_stock|low_stock|out_of_stock|backordered|discontinued`
- `ordering` (e.g. `product__name`)

**Response `200 OK`:**

```json
[
  {
    "id": 28,
    "product": 10,
    "product_name": "Black Sneakers",
    "product_variant": 7,
    "warehouse": 1,
    "warehouse_name": "Main Warehouse",
    "location_code": "A1-B2",
    "quantity_on_hand": 120,
    "quantity_reserved": 15,
    "quantity_available": 105,
    "minimum_stock_level": 20,
    "maximum_stock_level": 500,
    "reorder_point": 30,
    "reorder_quantity": 200,
    "stock_status": "in_stock",
    "unit_cost": "120.00",
    "inventory_value": "14400.00",
    "created_at": "2026-01-05T09:15:00Z",
    "updated_at": "2026-03-21T14:20:00Z"
  }
]
```

### 2.2 Retrieve Item

```
GET /api/inventory/items/{id}/
```

### 2.3 Create Item

```
POST /api/inventory/items/
```

Required fields:
- `product`, `warehouse`, `quantity_on_hand`, `quantity_reserved`

Optional:
- `product_variant`, `location_code`, `minimum_stock_level`, `maximum_stock_level`, `reorder_point`, `reorder_quantity`, `unit_cost`

**Response `201 Created`** with created item.

### 2.4 Update Item

```
PUT /api/inventory/items/{id}/
PATCH /api/inventory/items/{id}/
```

### 2.5 Delete Item

```
DELETE /api/inventory/items/{id}/
```

**Response `204 No Content`**

### 2.6 Low Stock Items

```
GET /api/inventory/items/low_stock/
```

Returns items with `stock_status == low_stock`.

### 2.7 Out of Stock Items

```
GET /api/inventory/items/out_of_stock/
```

Returns items with `stock_status == out_of_stock`.

---

## 3. Stock Movements

### 3.1 List Stock Movements

```
GET /api/inventory/movements/
```

Query params:
- `filter[movement_type]=purchase|sale|return|adjustment|transfer|damage|theft|expired|reserved|unreserved`
- `filter[inventory_item]=<id>`

**Response `200 OK`:**

```json
[
  {
    "id": "686a241c-...",
    "inventory_item": 28,
    "product_name": "Black Sneakers",
    "movement_type": "purchase",
    "quantity": 50,
    "quantity_before": 70,
    "quantity_after": 120,
    "reference_number": "PO-20260322-001",
    "performed_by": 42,
    "performed_by_email": "staff@example.com",
    "unit_cost": "120.00",
    "notes": "Received inbound shipment",
    "created_at": "2026-03-22T12:00:00Z"
  }
]
```

### 3.2 Retrieve Stock Movement

```
GET /api/inventory/movements/{id}/
```

---

## 4. Purchase Orders

### 4.1 List Purchase Orders

```
GET /api/inventory/purchase-orders/
```

Query params:
- `filter[status]=draft|sent|confirmed|partially_received|received|cancelled`
- `filter[warehouse]=<id>`
- `search` by `po_number` or `notes`

**Response `200 OK`:** list each PO with property fields.

### 4.2 Retrieve Purchase Order

```
GET /api/inventory/purchase-orders/{id}/
```

### 4.3 Create Purchase Order

```
POST /api/inventory/purchase-orders/
```

Body fields:
- `warehouse`, `supplier`, `status`, `expected_delivery_date`, `actual_delivery_date`, `tax_amount`, `shipping_cost`, `notes`, `terms_and_conditions`
- `line_items` are read-only in this serializer; create via separate line-item endpoint (not implemented under this app route) or via object update API with nested behavior.

`po_number`, `order_date`, `subtotal`, `total_amount`, `created_by` are read-only.

**Response `201 Created`**

### 4.4 Update Purchase Order

```
PUT /api/inventory/purchase-orders/{id}/
PATCH /api/inventory/purchase-orders/{id}/
```

### 4.5 Delete Purchase Order

```
DELETE /api/inventory/purchase-orders/{id}/
```

**Response `204 No Content`**

### 4.6 Create / Update Line Items

`PurchaseOrderLineItem` is not direct viewset here, but line items are returned in `line_items` field.
- `POST /api/inventory/purchase-orders/{id}/` with only PO fields; line items are not handled by this endpoint.

---

## 5. Stock Alerts

### 5.1 List Stock Alerts

```
GET /api/inventory/alerts/
```

Query params:
- `filter[alert_type]=low_stock|out_of_stock|reorder_point|overstock|expired|damage`
- `filter[status]=active|acknowledged|resolved|dismissed`

**Response `200 OK`:**

```json
[
  {
    "id": 53,
    "inventory_item": 28,
    "product_name": "Black Sneakers",
    "warehouse_name": "Main Warehouse",
    "alert_type": "low_stock",
    "status": "active",
    "message": "Quantity available 5 below reorder threshold",
    "current_stock_level": 5,
    "threshold_level": 10,
    "acknowledged_by": null,
    "acknowledged_at": null,
    "resolution_notes": "",
    "created_at": "2026-03-22T13:00:00Z",
    "updated_at": "2026-03-22T13:00:00Z"
  }
]
```

### 5.2 Retrieve Stock Alert

```
GET /api/inventory/alerts/{id}/
```

### 5.3 Create Stock Alert

```
POST /api/inventory/alerts/
```

Fields:
- `inventory_item`, `alert_type`, `message`, `current_stock_level`, `threshold_level`
- `status` optional, default `active`

### 5.4 Update Stock Alert

```
PUT /api/inventory/alerts/{id}/
PATCH /api/inventory/alerts/{id}/
```

### 5.5 Delete Stock Alert

```
DELETE /api/inventory/alerts/{id}/
```

### 5.6 Acknowledge Alert

```
POST /api/inventory/alerts/{id}/acknowledge/
```

Response: updated alert with `status: acknowledged`, `acknowledged_by`, `acknowledged_at`.

### 5.7 Resolve Alert

```
POST /api/inventory/alerts/{id}/resolve/
```

Body:
```json
{ "resolution_notes": "Ordered stock and verified"
}
```

Response: updated alert with `status: resolved` and `resolution_notes`.

---

## 6. Dart Models

```dart
class Warehouse {
  final int id;
  final String name;
  final String code;
  final String? description;
  final String streetAddress;
  final String city;
  final String stateProvince;
  final String postalCode;
  final String country;
  final String? phoneNumber;
  final String? email;
  final int? manager;
  final String? managerEmail;
  final bool isActive;
  final bool isDefault;
  final DateTime createdAt;
  final DateTime updatedAt;

  Warehouse({
    required this.id,
    required this.name,
    required this.code,
    this.description,
    required this.streetAddress,
    required this.city,
    required this.stateProvince,
    required this.postalCode,
    required this.country,
    this.phoneNumber,
    this.email,
    this.manager,
    this.managerEmail,
    required this.isActive,
    required this.isDefault,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Warehouse.fromJson(Map<String, dynamic> json) => Warehouse(
        id: json['id'],
        name: json['name'],
        code: json['code'],
        description: json['description'],
        streetAddress: json['street_address'],
        city: json['city'],
        stateProvince: json['state_province'],
        postalCode: json['postal_code'],
        country: json['country'],
        phoneNumber: json['phone_number'],
        email: json['email'],
        manager: json['manager'],
        managerEmail: json['manager_email'],
        isActive: json['is_active'],
        isDefault: json['is_default'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}

class InventoryItem {
  final int id;
  final int product;
  final String productName;
  final int? productVariant;
  final int warehouse;
  final String warehouseName;
  final String locationCode;
  final int quantityOnHand;
  final int quantityReserved;
  final int quantityAvailable;
  final int minimumStockLevel;
  final int? maximumStockLevel;
  final int reorderPoint;
  final int reorderQuantity;
  final String stockStatus;
  final String? unitCost;
  final String inventoryValue;
  final DateTime createdAt;
  final DateTime updatedAt;

  InventoryItem({
    required this.id,
    required this.product,
    required this.productName,
    this.productVariant,
    required this.warehouse,
    required this.warehouseName,
    required this.locationCode,
    required this.quantityOnHand,
    required this.quantityReserved,
    required this.quantityAvailable,
    required this.minimumStockLevel,
    this.maximumStockLevel,
    required this.reorderPoint,
    required this.reorderQuantity,
    required this.stockStatus,
    this.unitCost,
    required this.inventoryValue,
    required this.createdAt,
    required this.updatedAt,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) => InventoryItem(
        id: json['id'],
        product: json['product'],
        productName: json['product_name'],
        productVariant: json['product_variant'],
        warehouse: json['warehouse'],
        warehouseName: json['warehouse_name'],
        locationCode: json['location_code'] ?? '',
        quantityOnHand: json['quantity_on_hand'],
        quantityReserved: json['quantity_reserved'],
        quantityAvailable: json['quantity_available'],
        minimumStockLevel: json['minimum_stock_level'],
        maximumStockLevel: json['maximum_stock_level'],
        reorderPoint: json['reorder_point'],
        reorderQuantity: json['reorder_quantity'],
        stockStatus: json['stock_status'],
        unitCost: json['unit_cost'],
        inventoryValue: json['inventory_value'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}

class StockMovement {
  final String id;
  final int inventoryItem;
  final String productName;
  final String movementType;
  final int quantity;
  final int quantityBefore;
  final int quantityAfter;
  final String? referenceNumber;
  final int? performedBy;
  final String? performedByEmail;
  final String? unitCost;
  final String notes;
  final DateTime createdAt;

  StockMovement({
    required this.id,
    required this.inventoryItem,
    required this.productName,
    required this.movementType,
    required this.quantity,
    required this.quantityBefore,
    required this.quantityAfter,
    this.referenceNumber,
    this.performedBy,
    this.performedByEmail,
    this.unitCost,
    required this.notes,
    required this.createdAt,
  });

  factory StockMovement.fromJson(Map<String, dynamic> json) => StockMovement(
        id: json['id'],
        inventoryItem: json['inventory_item'],
        productName: json['product_name'],
        movementType: json['movement_type'],
        quantity: json['quantity'],
        quantityBefore: json['quantity_before'],
        quantityAfter: json['quantity_after'],
        referenceNumber: json['reference_number'],
        performedBy: json['performed_by'],
        performedByEmail: json['performed_by_email'],
        unitCost: json['unit_cost'],
        notes: json['notes'] ?? '',
        createdAt: DateTime.parse(json['created_at']),
      );
}

class PurchaseOrder {
  final String id;
  final String poNumber;
  final int warehouse;
  final String warehouseName;
  final int supplier;
  final String supplierEmail;
  final String status;
  final DateTime orderDate;
  final DateTime? expectedDeliveryDate;
  final DateTime? actualDeliveryDate;
  final String subtotal;
  final String taxAmount;
  final String shippingCost;
  final String totalAmount;
  final String notes;
  final String termsAndConditions;
  final int? createdBy;
  final List<dynamic> lineItems;
  final DateTime createdAt;
  final DateTime updatedAt;

  PurchaseOrder({
    required this.id,
    required this.poNumber,
    required this.warehouse,
    required this.warehouseName,
    required this.supplier,
    required this.supplierEmail,
    required this.status,
    required this.orderDate,
    this.expectedDeliveryDate,
    this.actualDeliveryDate,
    required this.subtotal,
    required this.taxAmount,
    required this.shippingCost,
    required this.totalAmount,
    required this.notes,
    required this.termsAndConditions,
    this.createdBy,
    required this.lineItems,
    required this.createdAt,
    required this.updatedAt,
  });

  factory PurchaseOrder.fromJson(Map<String, dynamic> json) => PurchaseOrder(
        id: json['id'],
        poNumber: json['po_number'],
        warehouse: json['warehouse'],
        warehouseName: json['warehouse_name'],
        supplier: json['supplier'],
        supplierEmail: json['supplier_email'],
        status: json['status'],
        orderDate: DateTime.parse(json['order_date']),
        expectedDeliveryDate:
            json['expected_delivery_date'] != null ? DateTime.parse(json['expected_delivery_date']) : null,
        actualDeliveryDate:
            json['actual_delivery_date'] != null ? DateTime.parse(json['actual_delivery_date']) : null,
        subtotal: json['subtotal'],
        taxAmount: json['tax_amount'],
        shippingCost: json['shipping_cost'],
        totalAmount: json['total_amount'],
        notes: json['notes'] ?? '',
        termsAndConditions: json['terms_and_conditions'] ?? '',
        createdBy: json['created_by'],
        lineItems: (json['line_items'] as List).map((e) => e as Map<String, dynamic>).toList(),
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}

class StockAlert {
  final int id;
  final int inventoryItem;
  final String productName;
  final String warehouseName;
  final String alertType;
  final String status;
  final String message;
  final int currentStockLevel;
  final int? thresholdLevel;
  final int? acknowledgedBy;
  final DateTime? acknowledgedAt;
  final String resolutionNotes;
  final DateTime createdAt;
  final DateTime updatedAt;

  StockAlert({
    required this.id,
    required this.inventoryItem,
    required this.productName,
    required this.warehouseName,
    required this.alertType,
    required this.status,
    required this.message,
    required this.currentStockLevel,
    this.thresholdLevel,
    this.acknowledgedBy,
    this.acknowledgedAt,
    required this.resolutionNotes,
    required this.createdAt,
    required this.updatedAt,
  });

  factory StockAlert.fromJson(Map<String, dynamic> json) => StockAlert(
        id: json['id'],
        inventoryItem: json['inventory_item'],
        productName: json['product_name'],
        warehouseName: json['warehouse_name'],
        alertType: json['alert_type'],
        status: json['status'],
        message: json['message'],
        currentStockLevel: json['current_stock_level'],
        thresholdLevel: json['threshold_level'],
        acknowledgedBy: json['acknowledged_by'],
        acknowledgedAt:
            json['acknowledged_at'] != null ? DateTime.parse(json['acknowledged_at']) : null,
        resolutionNotes: json['resolution_notes'] ?? '',
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}
```

---

## 7. Dart API Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class InventoryApiService {
  final String baseUrl;
  final String? accessToken;

  InventoryApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (accessToken != null) 'Authorization': 'Bearer $accessToken',
      };

  // Warehouses
  Future<List<Warehouse>> listWarehouses({String? search, String? ordering}) async {
    final query = <String>[];
    if (search != null) query.add('search=${Uri.encodeComponent(search)}');
    if (ordering != null) query.add('ordering=${Uri.encodeComponent(ordering)}');

    final uri = Uri.parse('$baseUrl/api/inventory/warehouses/${query.isNotEmpty ? '?${query.join('&')}' : ''}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) {
      throw Exception('Failed to list warehouses: ${response.body}');
    }
    return (jsonDecode(response.body) as List)
        .map((e) => Warehouse.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Warehouse> getWarehouse(int id) async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/warehouses/$id/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to load warehouse: ${response.body}');
    return Warehouse.fromJson(jsonDecode(response.body));
  }

  Future<Warehouse> createWarehouse(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/inventory/warehouses/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 201) throw Exception('Failed to create warehouse: ${response.body}');
    return Warehouse.fromJson(jsonDecode(response.body));
  }

  Future<Warehouse> updateWarehouse(int id, Map<String, dynamic> data) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/inventory/warehouses/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 200) throw Exception('Failed to update warehouse: ${response.body}');
    return Warehouse.fromJson(jsonDecode(response.body));
  }

  Future<void> deleteWarehouse(int id) async {
    final response = await http.delete(Uri.parse('$baseUrl/api/inventory/warehouses/$id/'), headers: _headers);
    if (response.statusCode != 204) throw Exception('Failed to delete warehouse: ${response.body}');
  }

  // Inventory items
  Future<List<InventoryItem>> listInventoryItems({int? warehouseId, String? stockStatus, String? search}) async {
    final query = <String>[];
    if (warehouseId != null) query.add('warehouse=$warehouseId');
    if (stockStatus != null) query.add('stock_status=$stockStatus');
    if (search != null) query.add('search=${Uri.encodeComponent(search)}');

    final uri = Uri.parse('$baseUrl/api/inventory/items/${query.isNotEmpty ? '?${query.join('&')}' : ''}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list inventory items: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => InventoryItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<InventoryItem> getInventoryItem(int id) async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/items/$id/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to load inventory item: ${response.body}');
    return InventoryItem.fromJson(jsonDecode(response.body));
  }

  Future<InventoryItem> createInventoryItem(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/inventory/items/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 201) throw Exception('Failed to create inventory item: ${response.body}');
    return InventoryItem.fromJson(jsonDecode(response.body));
  }

  Future<InventoryItem> updateInventoryItem(int id, Map<String, dynamic> data) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/inventory/items/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 200) throw Exception('Failed to update inventory item: ${response.body}');
    return InventoryItem.fromJson(jsonDecode(response.body));
  }

  Future<void> deleteInventoryItem(int id) async {
    final response = await http.delete(Uri.parse('$baseUrl/api/inventory/items/$id/'), headers: _headers);
    if (response.statusCode != 204) throw Exception('Failed to delete inventory item: ${response.body}');
  }

  Future<List<InventoryItem>> listLowStockItems() async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/items/low_stock/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list low stock items: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => InventoryItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<InventoryItem>> listOutOfStockItems() async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/items/out_of_stock/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list out of stock items: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => InventoryItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Stock movements
  Future<List<StockMovement>> listStockMovements({String? movementType, int? inventoryItem}) async {
    final query = <String>[];
    if (movementType != null) query.add('movement_type=$movementType');
    if (inventoryItem != null) query.add('inventory_item=$inventoryItem');
    final uri = Uri.parse('$baseUrl/api/inventory/movements/${query.isNotEmpty ? '?${query.join('&')}' : ''}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list stock movements: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => StockMovement.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<StockMovement> getStockMovement(String id) async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/movements/$id/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to load stock movement: ${response.body}');
    return StockMovement.fromJson(jsonDecode(response.body));
  }

  // Purchase orders
  Future<List<PurchaseOrder>> listPurchaseOrders({String? status, int? warehouseId, String? search}) async {
    final query = <String>[];
    if (status != null) query.add('status=$status');
    if (warehouseId != null) query.add('warehouse=$warehouseId');
    if (search != null) query.add('search=${Uri.encodeComponent(search)}');
    final uri = Uri.parse('$baseUrl/api/inventory/purchase-orders/${query.isNotEmpty ? '?${query.join('&')}' : ''}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list purchase orders: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => PurchaseOrder.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<PurchaseOrder> getPurchaseOrder(String id) async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/purchase-orders/$id/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to load purchase order: ${response.body}');
    return PurchaseOrder.fromJson(jsonDecode(response.body));
  }

  Future<PurchaseOrder> createPurchaseOrder(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/inventory/purchase-orders/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 201) throw Exception('Failed to create purchase order: ${response.body}');
    return PurchaseOrder.fromJson(jsonDecode(response.body));
  }

  Future<PurchaseOrder> updatePurchaseOrder(String id, Map<String, dynamic> data) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/inventory/purchase-orders/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 200) throw Exception('Failed to update purchase order: ${response.body}');
    return PurchaseOrder.fromJson(jsonDecode(response.body));
  }

  Future<void> deletePurchaseOrder(String id) async {
    final response = await http.delete(Uri.parse('$baseUrl/api/inventory/purchase-orders/$id/'), headers: _headers);
    if (response.statusCode != 204) throw Exception('Failed to delete purchase order: ${response.body}');
  }

  // Stock alerts
  Future<List<StockAlert>> listStockAlerts({String? status, String? alertType}) async {
    final query = <String>[];
    if (status != null) query.add('status=$status');
    if (alertType != null) query.add('alert_type=$alertType');
    final uri = Uri.parse('$baseUrl/api/inventory/alerts/${query.isNotEmpty ? '?${query.join('&')}' : ''}');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to list stock alerts: ${response.body}');
    return (jsonDecode(response.body) as List)
        .map((e) => StockAlert.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<StockAlert> getStockAlert(int id) async {
    final response = await http.get(Uri.parse('$baseUrl/api/inventory/alerts/$id/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to load stock alert: ${response.body}');
    return StockAlert.fromJson(jsonDecode(response.body));
  }

  Future<StockAlert> createStockAlert(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/inventory/alerts/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 201) throw Exception('Failed to create stock alert: ${response.body}');
    return StockAlert.fromJson(jsonDecode(response.body));
  }

  Future<StockAlert> updateStockAlert(int id, Map<String, dynamic> data) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/api/inventory/alerts/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    if (response.statusCode != 200) throw Exception('Failed to update stock alert: ${response.body}');
    return StockAlert.fromJson(jsonDecode(response.body));
  }

  Future<void> deleteStockAlert(int id) async {
    final response = await http.delete(Uri.parse('$baseUrl/api/inventory/alerts/$id/'), headers: _headers);
    if (response.statusCode != 204) throw Exception('Failed to delete stock alert: ${response.body}');
  }

  Future<StockAlert> acknowledgeStockAlert(int id) async {
    final response = await http.post(Uri.parse('$baseUrl/api/inventory/alerts/$id/acknowledge/'), headers: _headers);
    if (response.statusCode != 200) throw Exception('Failed to acknowledge stock alert: ${response.body}');
    return StockAlert.fromJson(jsonDecode(response.body));
  }

  Future<StockAlert> resolveStockAlert(int id, {String resolutionNotes = ''}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/inventory/alerts/$id/resolve/'),
      headers: _headers,
      body: jsonEncode({'resolution_notes': resolutionNotes}),
    );
    if (response.statusCode != 200) throw Exception('Failed to resolve stock alert: ${response.body}');
    return StockAlert.fromJson(jsonDecode(response.body));
  }
}
```

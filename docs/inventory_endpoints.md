# Inventory Endpoints

Base URL: `/api/inventory/`

---

## Admin-Only Endpoints

> Requires `is_staff` or `is_superuser`. For the admin platform only.

### Warehouses

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/inventory/warehouses/` | List all warehouses |
| `POST` | `/api/inventory/warehouses/` | Create a warehouse |
| `GET` | `/api/inventory/warehouses/<id>/` | Retrieve a warehouse |
| `PUT/PATCH` | `/api/inventory/warehouses/<id>/` | Update a warehouse |
| `DELETE` | `/api/inventory/warehouses/<id>/` | Delete a warehouse |

### Inventory Items

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/inventory/items/` | List all items across all vendors |
| `POST` | `/api/inventory/items/` | Create an inventory item |
| `GET` | `/api/inventory/items/<id>/` | Retrieve an item |
| `PUT/PATCH` | `/api/inventory/items/<id>/` | Update an item |
| `DELETE` | `/api/inventory/items/<id>/` | Delete an item |
| `GET` | `/api/inventory/items/low_stock/` | All low-stock items across all vendors |
| `GET` | `/api/inventory/items/out_of_stock/` | All out-of-stock items across all vendors |

**Query params:** `?warehouse=<id>` `?stock_status=in_stock|low_stock|out_of_stock|backordered|discontinued`

### Stock Movements

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/inventory/movements/` | Full audit trail of all stock movements |
| `GET` | `/api/inventory/movements/<id>/` | Single stock movement detail |

**Query params:** `?movement_type=purchase|sale|return|adjustment|transfer|damage|theft|expired|reserved|unreserved` `?inventory_item=<id>`

### Purchase Orders

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/inventory/purchase-orders/` | List all purchase orders across all vendors |
| `POST` | `/api/inventory/purchase-orders/` | Create a purchase order |
| `GET` | `/api/inventory/purchase-orders/<id>/` | Retrieve a purchase order |
| `PUT/PATCH` | `/api/inventory/purchase-orders/<id>/` | Update a purchase order |
| `DELETE` | `/api/inventory/purchase-orders/<id>/` | Delete a purchase order |

**Query params:** `?status=draft|sent|confirmed|partially_received|received|cancelled` `?warehouse=<id>`

### Stock Alerts

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/inventory/alerts/` | List all stock alerts across all vendors |
| `POST` | `/api/inventory/alerts/` | Create a stock alert |
| `GET` | `/api/inventory/alerts/<id>/` | Retrieve an alert |
| `PUT/PATCH` | `/api/inventory/alerts/<id>/` | Update an alert |
| `DELETE` | `/api/inventory/alerts/<id>/` | Delete an alert |
| `POST` | `/api/inventory/alerts/<id>/acknowledge/` | Acknowledge an alert |
| `POST` | `/api/inventory/alerts/<id>/resolve/` | Resolve an alert |

**Query params:** `?alert_type=low_stock|out_of_stock|reorder_point|overstock|expired|damage` `?status=active|acknowledged|resolved|dismissed`

**Resolve request body:**
```json
{
  "resolution_notes": "Restocked from supplier."
}
```

---

## Vendor-Scoped Endpoints

> Pass the **VendorProfile UUID** (`vendor_profile.id`) in the URL.
> All data is filtered to products and inventory belonging to that vendor.
> `GET` endpoints are public (no JWT). `POST` endpoints require JWT.

### Warehouses

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/inventory/vendor/<vendor_uuid>/warehouses/` | None | Warehouses that hold this vendor's inventory |
| `POST` | `/api/inventory/vendor/<vendor_uuid>/warehouses/` | JWT | Create a new warehouse |

**GET:** Returns only warehouses that contain at least one inventory item belonging to this vendor's products.

**POST request body:**
```json
{
  "name": "Lagos Main Warehouse",
  "code": "LGS-001",
  "description": "Primary storage for Lagos region",
  "street_address": "12 Apapa Road",
  "city": "Lagos",
  "state_province": "Lagos",
  "postal_code": "100001",
  "country": "Nigeria",
  "phone_number": "+2348012345678",
  "email": "warehouse@vendor.com",
  "is_active": true,
  "is_default": false
}
```

**Example:**
```
GET /api/inventory/vendor/3fa85f64-5717-4562-b3fc-2c963f66afa6/warehouses/
```

### Inventory Items

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/inventory/vendor/<vendor_uuid>/items/` | None | List inventory items for this vendor's products |
| `POST` | `/api/inventory/vendor/<vendor_uuid>/items/` | JWT | Create an inventory item for this vendor's product |

**GET query params:** `?stock_status=in_stock|low_stock|out_of_stock|backordered|discontinued`

**POST request body:**
```json
{
  "product": "<product-uuid>",
  "product_variant": "<variant-id or null>",
  "warehouse": "<warehouse-id>",
  "location_code": "A1-B2",
  "quantity_on_hand": 100,
  "quantity_reserved": 0,
  "minimum_stock_level": 10,
  "maximum_stock_level": 500,
  "reorder_point": 20,
  "reorder_quantity": 50,
  "unit_cost": "15.00"
}
```

> `product` must belong to the vendor identified by `vendor_uuid`, otherwise a `403` is returned.

**Example:**
```
GET /api/inventory/vendor/3fa85f64-5717-4562-b3fc-2c963f66afa6/items/?stock_status=low_stock
```

### Stock Movements

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/inventory/vendor/<vendor_uuid>/movements/` | None | Stock movement history for this vendor |

**Query params:** `?movement_type=purchase|sale|return|adjustment|transfer|damage|theft|expired|reserved|unreserved`

**Example:**
```
GET /api/inventory/vendor/3fa85f64-5717-4562-b3fc-2c963f66afa6/movements/?movement_type=sale
```

### Purchase Orders

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/inventory/vendor/<vendor_uuid>/purchase-orders/` | None | List purchase orders where this vendor is the supplier |
| `POST` | `/api/inventory/vendor/<vendor_uuid>/purchase-orders/` | JWT | Create a purchase order (supplier auto-set from URL) |

**GET query params:** `?status=draft|sent|confirmed|partially_received|received|cancelled`

**POST request body:**
```json
{
  "warehouse": "<warehouse-id>",
  "status": "draft",
  "expected_delivery_date": "2026-06-01T00:00:00Z",
  "tax_amount": "0.00",
  "shipping_cost": "0.00",
  "notes": "Monthly restock",
  "terms_and_conditions": ""
}
```

> `supplier` and `created_by` are auto-set from `vendor_uuid` and the JWT token — do not include them in the request body.

**Example:**
```
GET /api/inventory/vendor/3fa85f64-5717-4562-b3fc-2c963f66afa6/purchase-orders/?status=confirmed
```

### Stock Alerts

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `GET` | `/api/inventory/vendor/<vendor_uuid>/alerts/` | None | List stock alerts for this vendor's items |
| `POST` | `/api/inventory/vendor/<vendor_uuid>/alerts/` | JWT | Create a stock alert for this vendor's inventory item |

**GET query params:** `?status=active|acknowledged|resolved|dismissed` `?alert_type=low_stock|out_of_stock|reorder_point|overstock|expired|damage`

**POST request body:**
```json
{
  "inventory_item": "<inventory-item-id>",
  "alert_type": "low_stock",
  "message": "Stock is running low on this item.",
  "current_stock_level": 5,
  "threshold_level": 10
}
```

> `inventory_item` must belong to a product owned by this vendor, otherwise a `403` is returned.

**Example:**
```
GET /api/inventory/vendor/3fa85f64-5717-4562-b3fc-2c963f66afa6/alerts/?status=active
```

---

## Flutter Integration Note

All calls in `AdminInventoryService` are missing the `/api/` prefix. Update the base URL:

```dart
// Before
static const String _baseUrl = '/inventory';

// After
static const String _baseUrl = '/api/inventory';
```

The `vendor_uuid` value comes from the authenticated user's profile:

```dart
// From GET /api/accounts/me/ response
final vendorUuid = response['vendor_profile']['id'];
```

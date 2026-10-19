"""
Tests for inventory app
"""
import pytest
from decimal import Decimal
from rest_framework import status
from inventory.models import Warehouse, InventoryItem, StockMovement, PurchaseOrder, StockAlert


# ── Model Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestWarehouseModel:
    def test_create_warehouse(self, warehouse):
        assert warehouse.code == 'WH-001'
        assert str(warehouse) == 'Main Warehouse (WH-001)'

    def test_only_one_default_warehouse(self, warehouse):
        wh2 = Warehouse.objects.create(
            name='Second', code='WH-002', street_address='2',
            city='C', state_province='S', postal_code='2', country='US',
            is_default=True,
        )
        warehouse.refresh_from_db()
        assert not warehouse.is_default
        assert wh2.is_default


@pytest.mark.django_db
class TestInventoryItemModel:
    def test_auto_calculate_available(self, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=100, quantity_reserved=20,
        )
        assert item.quantity_available == 80
        assert item.stock_status == 'in_stock'

    def test_low_stock_status(self, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=8, quantity_reserved=0,
            minimum_stock_level=10,
        )
        assert item.stock_status == 'low_stock'
        assert item.is_low_stock is True

    def test_out_of_stock_status(self, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=5, quantity_reserved=5,
        )
        assert item.quantity_available == 0
        assert item.stock_status == 'out_of_stock'

    def test_inventory_value(self, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=50, unit_cost=Decimal('10.00'),
        )
        assert item.inventory_value == Decimal('500.00')

    def test_needs_reorder(self, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=15, reorder_point=20,
        )
        assert item.needs_reorder is True


@pytest.mark.django_db
class TestStockAlertModel:
    def test_acknowledge_alert(self, product, warehouse, admin_user):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse, quantity_on_hand=5,
            minimum_stock_level=10,
        )
        alert = StockAlert.objects.create(
            inventory_item=item, alert_type='low_stock',
            message='Low stock', current_stock_level=5, threshold_level=10,
        )
        alert.acknowledge(admin_user)
        assert alert.status == 'acknowledged'
        assert alert.acknowledged_by == admin_user

    def test_resolve_alert(self, product, warehouse, admin_user):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse, quantity_on_hand=5,
            minimum_stock_level=10,
        )
        alert = StockAlert.objects.create(
            inventory_item=item, alert_type='low_stock',
            message='Low stock', current_stock_level=5, threshold_level=10,
        )
        alert.resolve(admin_user, notes='Restocked')
        assert alert.status == 'resolved'
        assert alert.resolution_notes == 'Restocked'


@pytest.mark.django_db
class TestPurchaseOrderModel:
    def test_create_purchase_order(self, vendor_user, warehouse, admin_user):
        po = PurchaseOrder.objects.create(
            supplier=vendor_user.vendor_profile, warehouse=warehouse, created_by=admin_user,
        )
        assert po.po_number.startswith('PO-')
        assert po.status == 'draft'


# ── API Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestWarehouseAPI:
    def test_list_warehouses(self, admin_client, warehouse):
        response = admin_client.get('/api/inventory/warehouses/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_warehouse(self, admin_client):
        data = {
            'name': 'New WH', 'code': 'WH-NEW',
            'street_address': '1 St', 'city': 'City',
            'state_province': 'ST', 'postal_code': '111', 'country': 'US',
        }
        response = admin_client.post('/api/inventory/warehouses/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_customer_cannot_access_warehouses(self, auth_client):
        response = auth_client.get('/api/inventory/warehouses/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInventoryItemAPI:
    def test_list_inventory(self, admin_client, product, warehouse):
        InventoryItem.objects.create(
            product=product, warehouse=warehouse, quantity_on_hand=100,
        )
        response = admin_client.get('/api/inventory/items/')
        assert response.status_code == status.HTTP_200_OK

    def test_low_stock_endpoint(self, admin_client, product, warehouse):
        InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=5, minimum_stock_level=10,
        )
        response = admin_client.get('/api/inventory/items/low_stock/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_out_of_stock_endpoint(self, admin_client, product, warehouse):
        InventoryItem.objects.create(
            product=product, warehouse=warehouse,
            quantity_on_hand=0,
        )
        response = admin_client.get('/api/inventory/items/out_of_stock/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestStockAlertAPI:
    def test_acknowledge_alert(self, admin_client, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse, quantity_on_hand=5,
            minimum_stock_level=10,
        )
        alert = StockAlert.objects.create(
            inventory_item=item, alert_type='low_stock',
            message='Low stock', current_stock_level=5,
        )
        response = admin_client.post(f'/api/inventory/alerts/{alert.id}/acknowledge/')
        assert response.status_code == status.HTTP_200_OK
        alert.refresh_from_db()
        assert alert.status == 'acknowledged'

    def test_resolve_alert(self, admin_client, product, warehouse):
        item = InventoryItem.objects.create(
            product=product, warehouse=warehouse, quantity_on_hand=5,
            minimum_stock_level=10,
        )
        alert = StockAlert.objects.create(
            inventory_item=item, alert_type='low_stock',
            message='Low stock', current_stock_level=5,
        )
        response = admin_client.post(
            f'/api/inventory/alerts/{alert.id}/resolve/',
            {'resolution_notes': 'Restocked to 100 units'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        alert.refresh_from_db()
        assert alert.status == 'resolved'

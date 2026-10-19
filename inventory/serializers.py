"""
Serializers for inventory app
"""
from rest_framework import serializers
from .models import Warehouse, InventoryItem, StockMovement, PurchaseOrder, PurchaseOrderLineItem, StockAlert


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse model"""

    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    vendor_uuid = serializers.UUIDField(source='vendor.id', read_only=True, allow_null=True)

    class Meta:
        model = Warehouse
        fields = [
            'id', 'name', 'code', 'description', 'street_address',
            'city', 'state_province', 'postal_code', 'country',
            'phone_number', 'email',
            'vendor', 'vendor_uuid', 'created_by', 'created_by_email',
            'is_active', 'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'vendor_uuid', 'created_by', 'created_by_email', 'created_at', 'updated_at']


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serializer for InventoryItem model"""

    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'product', 'product_name', 'product_variant',
            'warehouse', 'warehouse_name', 'location_code',
            'quantity_on_hand', 'quantity_reserved', 'quantity_available',
            'minimum_stock_level', 'maximum_stock_level',
            'reorder_point', 'reorder_quantity', 'stock_status',
            'unit_cost', 'inventory_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'stock_status', 'quantity_available',
            'inventory_value', 'created_at', 'updated_at'
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement model"""

    product_name = serializers.CharField(source='inventory_item.product.name', read_only=True)
    performed_by_email = serializers.CharField(source='performed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'inventory_item', 'product_name', 'movement_type',
            'quantity', 'quantity_before', 'quantity_after',
            'reference_number', 'performed_by', 'performed_by_email',
            'unit_cost', 'notes', 'created_at'
        ]
        read_only_fields = fields


class PurchaseOrderLineItemSerializer(serializers.ModelSerializer):
    """Serializer for PurchaseOrderLineItem model"""

    product_name = serializers.CharField(source='product.name', read_only=True)
    quantity_pending = serializers.IntegerField(read_only=True)
    is_fully_received = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrderLineItem
        fields = [
            'id', 'product', 'product_name', 'product_variant',
            'quantity_ordered', 'quantity_received', 'quantity_pending',
            'unit_cost', 'total_cost', 'is_fully_received', 'notes'
        ]
        read_only_fields = ['id', 'total_cost']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """Serializer for PurchaseOrder model"""

    supplier_email = serializers.CharField(source='supplier.user.email', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    line_items = PurchaseOrderLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'warehouse', 'warehouse_name',
            'supplier', 'supplier_email', 'status',
            'order_date', 'expected_delivery_date', 'actual_delivery_date',
            'subtotal', 'tax_amount', 'shipping_cost', 'total_amount',
            'notes', 'terms_and_conditions',
            'created_by', 'line_items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'po_number', 'order_date', 'actual_delivery_date',
            'subtotal', 'total_amount',
            'created_by', 'created_at', 'updated_at'
        ]


class VendorPurchaseOrderCreateSerializer(PurchaseOrderSerializer):
    """Like PurchaseOrderSerializer but supplier is read-only — auto-set from the URL vendor_uuid."""

    class Meta(PurchaseOrderSerializer.Meta):
        read_only_fields = PurchaseOrderSerializer.Meta.read_only_fields + ['supplier']


class StockAlertSerializer(serializers.ModelSerializer):
    """Serializer for StockAlert model"""

    product_name = serializers.CharField(source='inventory_item.product.name', read_only=True)
    warehouse_name = serializers.CharField(source='inventory_item.warehouse.name', read_only=True)

    class Meta:
        model = StockAlert
        fields = [
            'id', 'inventory_item', 'product_name', 'warehouse_name',
            'alert_type', 'status', 'message',
            'current_stock_level', 'threshold_level',
            'acknowledged_by', 'acknowledged_at', 'resolution_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'acknowledged_by', 'acknowledged_at',
            'created_at', 'updated_at'
        ]

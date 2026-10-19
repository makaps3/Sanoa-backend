from django.contrib import admin
from django.utils.html import format_html
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import (
    Warehouse, InventoryItem, StockMovement, PurchaseOrder,
    PurchaseOrderLineItem, StockAlert
)


class PurchaseOrderSupplierFilter(_BaseVendorBusinessFilter):
    title = 'supplier'
    parameter_name = 'supplier'
    filter_field_name = 'supplier'
    products_relation = 'purchase_orders'


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'city', 'state_province', 'country',
        'vendor', 'created_by', 'is_active', 'is_default'
    ]
    list_filter = ['is_active', 'is_default', 'country', 'state_province']
    search_fields = [
        'name', 'code', 'city', 'state_province',
        'created_by__email', 'phone_number', 'email'
    ]
    readonly_fields = ['created_by', 'created_at', 'updated_at']

    fieldsets = [
        ('Basic Info', {
            'fields': ['name', 'code', 'description', 'vendor', 'created_by']
        }),
        ('Address', {
            'fields': [
                'street_address', 'city', 'state_province',
                'postal_code', 'country'
            ]
        }),
        ('Contact Info', {
            'fields': ['phone_number', 'email']
        }),
        ('Settings', {
            'fields': ['is_active', 'is_default']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'product_variant', 'warehouse', 'stock_status',
        'quantity_on_hand', 'quantity_reserved', 'quantity_available',
        'minimum_stock_level', 'is_low_stock', 'needs_reorder'
    ]
    list_filter = [
        'stock_status', 'warehouse'
    ]
    search_fields = [
        'product__name', 'product_variant__name', 'location_code',
        'warehouse__name'
    ]
    readonly_fields = [
        'quantity_available', 'is_low_stock', 'needs_reorder',
        'inventory_value', 'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('Product Info', {
            'fields': ['product', 'product_variant', 'warehouse', 'location_code']
        }),
        ('Stock Levels', {
            'fields': [
                'quantity_on_hand', 'quantity_reserved', 'quantity_available',
                'stock_status'
            ]
        }),
        ('Stock Management', {
            'fields': [
                'minimum_stock_level', 'maximum_stock_level',
                'reorder_point', 'reorder_quantity'
            ]
        }),
        ('Costing', {
            'fields': ['unit_cost', 'inventory_value']
        }),
        ('Status', {
            'fields': ['is_low_stock', 'needs_reorder'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'product', 'product_variant', 'warehouse'
        )
    
    actions = ['mark_as_low_stock', 'mark_as_in_stock']
    
    def mark_as_low_stock(self, request, queryset):
        updated = queryset.update(stock_status='low_stock')
        self.message_user(request, f'{updated} items marked as low stock.')
    mark_as_low_stock.short_description = "Mark selected items as low stock"
    
    def mark_as_in_stock(self, request, queryset):
        updated = queryset.update(stock_status='in_stock')
        self.message_user(request, f'{updated} items marked as in stock.')
    mark_as_in_stock.short_description = "Mark selected items as in stock"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'inventory_item', 'movement_type', 'quantity',
        'quantity_before', 'quantity_after', 'order',
        'performed_by', 'created_at'
    ]
    list_filter = ['movement_type', 'created_at']
    search_fields = [
        'inventory_item__product__name', 'reference_number',
        'notes', 'performed_by__email'
    ]
    readonly_fields = ['id', 'total_cost', 'created_at']
    
    fieldsets = [
        ('Movement Info', {
            'fields': [
                'id', 'inventory_item', 'movement_type', 'quantity'
            ]
        }),
        ('Related Objects', {
            'fields': ['order', 'purchase_order', 'performed_by']
        }),
        ('Additional Details', {
            'fields': ['reference_number', 'notes', 'unit_cost', 'total_cost']
        }),
        ('Audit Trail', {
            'fields': ['quantity_before', 'quantity_after']
        }),
        ('Timestamp', {
            'fields': ['created_at']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'inventory_item__product', 'performed_by', 'order'
        )


class PurchaseOrderLineItemInline(admin.TabularInline):
    model = PurchaseOrderLineItem
    extra = 0
    readonly_fields = ['total_cost', 'is_fully_received', 'quantity_pending']
    fields = [
        'product', 'product_variant', 'quantity_ordered',
        'quantity_received', 'unit_cost', 'total_cost',
        'is_fully_received', 'quantity_pending'
    ]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'po_number', 'supplier_display', 'warehouse', 'status',
        'total_amount', 'order_date', 'expected_delivery_date'
    ]
    list_filter = [PurchaseOrderSupplierFilter, 'status', 'warehouse', 'order_date', 'expected_delivery_date']
    search_fields = [
        'po_number',
        'supplier__name', 'supplier__trading_name',
        'notes',
    ]

    @admin.display(description='Supplier', ordering='supplier__name')
    def supplier_display(self, obj):
        return vendor_profile_label(obj.supplier)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'supplier':
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'supplier', 'supplier__user', 'warehouse', 'created_by',
        )
    readonly_fields = [
        'id', 'po_number', 'order_date', 'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('Order Info', {
            'fields': [
                'id', 'po_number', 'supplier', 'warehouse',
                'status', 'created_by'
            ]
        }),
        ('Dates', {
            'fields': [
                'order_date', 'expected_delivery_date', 'actual_delivery_date'
            ]
        }),
        ('Financial', {
            'fields': [
                'subtotal', 'tax_amount', 'shipping_cost', 'total_amount'
            ]
        }),
        ('Additional Info', {
            'fields': ['notes', 'terms_and_conditions'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    inlines = [PurchaseOrderLineItemInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'supplier', 'warehouse', 'created_by'
        )
    
    actions = ['mark_as_confirmed', 'mark_as_received']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} purchase orders marked as confirmed.')
    mark_as_confirmed.short_description = "Mark selected POs as confirmed"
    
    def mark_as_received(self, request, queryset):
        from django.utils import timezone
        updated = 0
        for po in queryset:
            if po.status in ['confirmed', 'partially_received']:
                po.status = 'received'
                po.actual_delivery_date = timezone.now()
                po.save()
                updated += 1
        self.message_user(request, f'{updated} purchase orders marked as received.')
    mark_as_received.short_description = "Mark selected POs as received"


@admin.register(PurchaseOrderLineItem)
class PurchaseOrderLineItemAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order', 'product', 'product_variant',
        'quantity_ordered', 'quantity_received', 'unit_cost',
        'total_cost', 'is_fully_received'
    ]
    list_filter = ['purchase_order__status']
    search_fields = [
        'purchase_order__po_number', 'product__name',
        'product_variant__name'
    ]
    readonly_fields = ['total_cost', 'is_fully_received', 'quantity_pending']
    
    fieldsets = [
        ('Purchase Order', {
            'fields': ['purchase_order']
        }),
        ('Product Info', {
            'fields': ['product', 'product_variant']
        }),
        ('Quantities', {
            'fields': [
                'quantity_ordered', 'quantity_received',
                'is_fully_received', 'quantity_pending'
            ]
        }),
        ('Pricing', {
            'fields': ['unit_cost', 'total_cost']
        }),
        ('Additional Info', {
            'fields': ['notes']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'purchase_order', 'product', 'product_variant'
        )


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = [
        'inventory_item', 'alert_type', 'status',
        'current_stock_level', 'threshold_level',
        'acknowledged_by', 'created_at'
    ]
    list_filter = ['alert_type', 'status', 'created_at', 'acknowledged_at']
    search_fields = [
        'inventory_item__product__name', 'message',
        'acknowledged_by__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Alert Info', {
            'fields': [
                'inventory_item', 'alert_type', 'status', 'message'
            ]
        }),
        ('Stock Details', {
            'fields': ['current_stock_level', 'threshold_level']
        }),
        ('Actions Taken', {
            'fields': [
                'acknowledged_by', 'acknowledged_at', 'resolution_notes'
            ]
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'inventory_item__product', 'acknowledged_by'
        )
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def acknowledge_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(status='active'):
            alert.acknowledge(request.user)
            updated += 1
        self.message_user(request, f'{updated} alerts acknowledged.')
    acknowledge_alerts.short_description = "Acknowledge selected alerts"
    
    def resolve_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(status__in=['active', 'acknowledged']):
            alert.resolve(request.user, 'Resolved via admin action')
            updated += 1
        self.message_user(request, f'{updated} alerts resolved.')
    resolve_alerts.short_description = "Resolve selected alerts"

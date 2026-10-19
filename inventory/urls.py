from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet, InventoryItemViewSet,
    StockMovementViewSet, PurchaseOrderViewSet, StockAlertViewSet,
    VendorWarehousesView, VendorInventoryItemsView, VendorStockMovementsView,
    VendorPurchaseOrdersView, VendorStockAlertsView,
)

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'items', InventoryItemViewSet, basename='inventory-item')
router.register(r'movements', StockMovementViewSet, basename='stock-movement')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-order')
router.register(r'alerts', StockAlertViewSet, basename='stock-alert')

urlpatterns = [
    # Vendor-scoped endpoints
    path('vendor/<uuid:vendor_uuid>/warehouses/', VendorWarehousesView.as_view(), name='vendor-warehouses'),
    path('vendor/<uuid:vendor_uuid>/items/', VendorInventoryItemsView.as_view(), name='vendor-inventory-items'),
    path('vendor/<uuid:vendor_uuid>/movements/', VendorStockMovementsView.as_view(), name='vendor-stock-movements'),
    path('vendor/<uuid:vendor_uuid>/purchase-orders/', VendorPurchaseOrdersView.as_view(), name='vendor-purchase-orders'),
    path('vendor/<uuid:vendor_uuid>/alerts/', VendorStockAlertsView.as_view(), name='vendor-stock-alerts'),

    # Admin endpoints
    path('', include(router.urls)),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShippingAddressViewSet, ShoppingCartViewSet, OrderViewSet, CouponViewSet,
    VendorOrderListView, VendorDashboardView,
    VendorOrderQueueView, VendorOrderPendingAlertsView,
)

router = DefaultRouter()
router.register(r'shipping-addresses', ShippingAddressViewSet, basename='shipping-address')
router.register(r'cart', ShoppingCartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'coupons', CouponViewSet, basename='coupon')

urlpatterns = [
    path('vendor/<uuid:vendor_uuid>/orders/', VendorOrderListView.as_view(), name='vendor-orders'),
    path('vendor/<uuid:vendor_uuid>/dashboard/', VendorDashboardView.as_view(), name='vendor-dashboard'),
    path('vendor/<uuid:vendor_uuid>/queue/', VendorOrderQueueView.as_view(), name='vendor-order-queue'),
    path('vendor/<uuid:vendor_uuid>/pending-alerts/', VendorOrderPendingAlertsView.as_view(), name='vendor-order-pending-alerts'),
    path('', include(router.urls)),
]

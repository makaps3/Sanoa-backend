from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BusinessTierViewSet, VendorTierSubscriptionViewSet,
    AdminBusinessTierViewSet, AdminVendorTierSubscriptionViewSet,
)

router = DefaultRouter()
router.register(r'plans', BusinessTierViewSet, basename='business-tier')
router.register(r'subscriptions', VendorTierSubscriptionViewSet, basename='vendor-tier-subscription')

admin_router = DefaultRouter()
admin_router.register(r'plans', AdminBusinessTierViewSet, basename='admin-business-tier')
admin_router.register(r'subscriptions', AdminVendorTierSubscriptionViewSet, basename='admin-vendor-tier-sub')

urlpatterns = [
    path('admin/', include(admin_router.urls)),
    path('', include(router.urls)),
]

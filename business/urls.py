"""
URL configuration for business app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from analytics.vendor_views import (
    VendorAnalyticsOverviewView,
    VendorOrderAnalyticsView,
    VendorProductAnalyticsView,
    VendorCategoryAnalyticsView,
    VendorCustomerAnalyticsView,
    VendorNegotiationAnalyticsView,
    VendorPaymentAnalyticsView,
    VendorSubscriptionAnalyticsView,
)
from .views import (
    IndividualVendorProfileViewSet,
    BusinessVendorProfileViewSet,
    VendorProfileViewSet,
    VettingApplicationViewSet,
    VendorDocumentViewSet,
    AddressViewSet,
    BusinessFollowerViewSet,
    StoreDiscoveryView,
)
from .employee_views import (
    VendorEmployeePermissionCatalogView,
    MyVendorEmployeesView,
    MyVendorEmployeeDetailView,
    MyVendorEmployeeActionView,
    MyVendorEmployeeResetPasswordView,
    ChangeTemporaryPasswordView,
)
from .hours_views import (
    OperatingHoursView,
    OperatingHoursDayView,
    StoreStatusView,
)

router = DefaultRouter()
router.register(r'profiles/vendor/individual', IndividualVendorProfileViewSet, basename='individual-vendor-profile')
router.register(r'profiles/vendor/business', BusinessVendorProfileViewSet, basename='business-vendor-profile')
router.register(r'profiles/vendor', VendorProfileViewSet, basename='vendor-profile')
router.register(r'vetting', VettingApplicationViewSet, basename='vetting-application')
router.register(r'vendor-documents', VendorDocumentViewSet, basename='vendor-document')
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'followers', BusinessFollowerViewSet, basename='business-follower')

urlpatterns = [
    path('discover-stores/', StoreDiscoveryView.as_view(), name='store-discovery'),

    # Vendor analytics — all scoped to a vendor UUID
    # Vendor accesses their own data; admin can access any vendor.
    path('analytics/<uuid:vendor_id>/overview/',      VendorAnalyticsOverviewView.as_view(),     name='vendor-analytics-overview'),
    path('analytics/<uuid:vendor_id>/orders/',        VendorOrderAnalyticsView.as_view(),        name='vendor-analytics-orders'),
    path('analytics/<uuid:vendor_id>/products/',      VendorProductAnalyticsView.as_view(),      name='vendor-analytics-products'),
    path('analytics/<uuid:vendor_id>/categories/',    VendorCategoryAnalyticsView.as_view(),     name='vendor-analytics-categories'),
    path('analytics/<uuid:vendor_id>/customers/',     VendorCustomerAnalyticsView.as_view(),     name='vendor-analytics-customers'),
    path('analytics/<uuid:vendor_id>/negotiations/',  VendorNegotiationAnalyticsView.as_view(),  name='vendor-analytics-negotiations'),
    path('analytics/<uuid:vendor_id>/payments/',      VendorPaymentAnalyticsView.as_view(),      name='vendor-analytics-payments'),
    path('analytics/<uuid:vendor_id>/subscription/',  VendorSubscriptionAnalyticsView.as_view(), name='vendor-analytics-subscription'),

    # Vendor-side employee management (manager only for
    # mutating ops). All paths scoped to the caller's vendor.
    path('me/employees/catalog/',
         VendorEmployeePermissionCatalogView.as_view(),
         name='vendor-employee-catalog'),
    path('me/employees/',
         MyVendorEmployeesView.as_view(), name='my-vendor-employees'),
    path('me/employees/<uuid:employee_id>/',
         MyVendorEmployeeDetailView.as_view(),
         name='my-vendor-employee-detail'),
    path('me/employees/<uuid:employee_id>/action/',
         MyVendorEmployeeActionView.as_view(),
         name='my-vendor-employee-action'),
    path('me/employees/<uuid:employee_id>/reset-password/',
         MyVendorEmployeeResetPasswordView.as_view(),
         name='my-vendor-employee-reset-password'),

    # Auth utility — used by employees on first login to replace
    # the manager-generated temporary password.
    path('me/change-temporary-password/',
         ChangeTemporaryPasswordView.as_view(),
         name='change-temporary-password'),

    # Operating hours (Mon–Sun) + open/closed state — scoped to the
    # caller's own vendor profile.
    path('me/operating-hours/',
         OperatingHoursView.as_view(), name='my-operating-hours'),
    path('me/operating-hours/<int:day>/',
         OperatingHoursDayView.as_view(), name='my-operating-hours-day'),
    path('me/store-status/',
         StoreStatusView.as_view(), name='my-store-status'),

    path('', include(router.urls)),
]

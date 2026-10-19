from django.urls import include, path
from rest_framework.routers import DefaultRouter
from analytics.driver_views import (
    DriverAnalyticsOverviewView,
    DriverEarningsAnalyticsView,
    DriverPerformanceAnalyticsView,
)

from .views import (
    CalculateFareView,
    DeliveryJobViewSet,
    DriverEarningViewSet,
    DriverLocationView,
    DriverPayoutViewSet,
    DriverProfileView,
    DriverRequestViewSet,
    DriverShiftViewSet,
    FareRateViewSet,
    RateDriverView,
    TrackDeliveryView,
)

router = DefaultRouter()
router.register(r'fare-rates', FareRateViewSet, basename='fare-rate')
router.register(r'driver/requests', DriverRequestViewSet, basename='driver-request')
router.register(r'driver/shifts', DriverShiftViewSet, basename='driver-shift')
router.register(r'jobs', DeliveryJobViewSet, basename='delivery-job')
router.register(r'driver/earnings', DriverEarningViewSet, basename='driver-earning')
router.register(r'driver/payouts', DriverPayoutViewSet, basename='driver-payout')

urlpatterns = [
    path('calculate-fare/', CalculateFareView.as_view(), name='calculate-fare'),

    # Driver analytics
    path('driver/analytics/overview/', DriverAnalyticsOverviewView.as_view(), name='driver-analytics-overview'),
    path('driver/analytics/earnings/', DriverEarningsAnalyticsView.as_view(), name='driver-analytics-earnings'),
    path('driver/analytics/performance/', DriverPerformanceAnalyticsView.as_view(), name='driver-analytics-performance'),

    path('driver/profile/', DriverProfileView.as_view(), name='driver-profile'),
    path('driver/location/', DriverLocationView.as_view(), name='driver-location'),
    # DeliveryJob uses the default integer AutoField PK, so these routes
    # take <int:job_id>. The <uuid:...> converter was matching nothing and
    # made every customer track / rate request 404 before reaching the view.
    path('track/<int:job_id>/', TrackDeliveryView.as_view(), name='track-delivery'),
    path('track/<int:job_id>/rate/', RateDriverView.as_view(), name='rate-driver'),
    path('', include(router.urls)),
]

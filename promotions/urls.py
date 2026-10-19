from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminAnalyticsOverviewView,
    AdminBannerViewSet,
    AdminCouponViewSet,
    AdminPromotionViewSet,
    ApplyCouponView,
    CartSummaryView,
    MyPromotionsView,
    PublicBannerListView,
    PublicPromotionListView,
    RemoveCouponView,
    TargetCategoriesView,
    ValidateCouponView,
    VendorAnalyticsOverviewView,
    VendorBannerViewSet,
    VendorCouponViewSet,
    VendorPromotionViewSet,
)

app_name = 'promotions'

router = SimpleRouter()
router.register(r'vendor/promotions', VendorPromotionViewSet,
                basename='vendor-promotion')
router.register(r'vendor/coupons', VendorCouponViewSet,
                basename='vendor-coupon')
router.register(r'admin/promotions', AdminPromotionViewSet,
                basename='admin-promotion')
router.register(r'admin/coupons', AdminCouponViewSet,
                basename='admin-coupon')
router.register(r'vendor/banners', VendorBannerViewSet,
                basename='vendor-banner')
router.register(r'admin/banners', AdminBannerViewSet,
                basename='admin-banner')

urlpatterns = [
    # Customer
    path('', PublicPromotionListView.as_view(), name='list'),
    path('mine/', MyPromotionsView.as_view(), name='mine'),
    path('cart-summary/', CartSummaryView.as_view(), name='cart-summary'),
    path('coupons/apply/', ApplyCouponView.as_view(), name='coupon-apply'),
    path('coupons/remove/', RemoveCouponView.as_view(), name='coupon-remove'),
    path('coupons/validate/', ValidateCouponView.as_view(),
         name='coupon-validate'),
    # Customer: home carousel banners
    path('banners/', PublicBannerListView.as_view(), name='banners'),
    # Vendor + Admin: aggregate analytics overview
    path('vendor/analytics/', VendorAnalyticsOverviewView.as_view(),
         name='vendor-analytics'),
    path('admin/analytics/', AdminAnalyticsOverviewView.as_view(),
         name='admin-analytics'),
    # Vendor + Admin: category picker for targeting
    path('categories/', TargetCategoriesView.as_view(), name='categories'),
    # Vendor + Admin CRUD
    path('', include(router.urls)),
]

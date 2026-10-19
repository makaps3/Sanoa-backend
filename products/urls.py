from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, BrandViewSet, ProductViewSet,
    ProductReviewViewSet, WishlistViewSet,
    ProductLikeViewSet, VendorReviewViewSet,
    CategoryProductsView, BannerViewSet,
    ProductVariantViewSet,
    ProductAddonGroupViewSet, ProductAddonViewSet,
    VendorProductListView, VendorCategoryViewSet,
    AdminProductListView,
)
from .home_views import (
    customer_home, restaurant_detail, retail_detail, category_showcase,
    recommended_products,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')
router.register(r'addon-groups', ProductAddonGroupViewSet, basename='addon-group')
router.register(r'addons', ProductAddonViewSet, basename='product-addon')
router.register(r'reviews', ProductReviewViewSet, basename='review')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'likes', ProductLikeViewSet, basename='product-like')
router.register(r'vendor-reviews', VendorReviewViewSet, basename='vendor-review')
router.register(r'banners', BannerViewSet, basename='banner')

_vc = VendorCategoryViewSet.as_view

urlpatterns = [
    # Platform admin — all products
    path('admin/all/', AdminProductListView.as_view(), name='admin-all-products'),

    # Vendor product list
    path('vendor/<uuid:vendor_uuid>/products/', VendorProductListView.as_view(), name='vendor-products'),

    # Vendor category management
    path('vendor/<uuid:vendor_uuid>/categories/',
         _vc({'get': 'list', 'post': 'create'}), name='vendor-categories'),
    path('vendor/<uuid:vendor_uuid>/categories/select/',
         _vc({'post': 'select'}), name='vendor-category-select'),
    path('vendor/<uuid:vendor_uuid>/categories/<int:pk>/',
         _vc({'delete': 'destroy'}), name='vendor-category-detail'),

    path('category-products/', CategoryProductsView.as_view(), name='category-products'),

    # Curated home-screen feed (retail or restaurant in one payload)
    path('home/', customer_home, name='customer-home'),

    # Smart recommendations from the customer's order history (retail/restaurant)
    path('recommended-for-you/', recommended_products, name='recommended-for-you'),

    # Public single-vendor storefront payloads — same shape for both kinds.
    path('restaurants/<uuid:vendor_uuid>/', restaurant_detail, name='restaurant-detail'),
    path('retail/<uuid:vendor_uuid>/', retail_detail, name='retail-detail'),

    # Category showcase — five curated sections (featured / most-ordered /
    # new / top-rated / most-viewed), each with a top-pick and full list.
    path('categories/<int:category_id>/showcase/',
         category_showcase, name='category-showcase'),

    path('', include(router.urls)),
]

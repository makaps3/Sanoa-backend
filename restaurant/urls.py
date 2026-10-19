from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RestaurantCartViewSet,
    RestaurantOrderViewSet,
    KitchenTicketViewSet,
)

router = DefaultRouter()
router.register(r'cart', RestaurantCartViewSet, basename='restaurant-cart')
router.register(r'orders', RestaurantOrderViewSet, basename='restaurant-order')
router.register(r'kitchen/tickets', KitchenTicketViewSet, basename='kitchen-ticket')

urlpatterns = [
    path('', include(router.urls)),
]

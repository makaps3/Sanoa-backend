from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiveNegotiationsView,
    AllNegotiationsView,
    MyNegotiationRoomsView,
    NegotiationHistoryView,
    NegotiationRoomDetailView,
    PricePolicyViewSet,
    RoomMessagesView,
    RoomOffersView,
    StartNegotiationView,
    SwitchModeView,
    VendorActiveNegotiationsView,
    VendorNegotiationHistoryView,
    VendorNegotiationRoomsView,
)

router = DefaultRouter()
router.register(r'policy', PricePolicyViewSet, basename='price-policy')

urlpatterns = [
    # All negotiations list (admin = all, vendor = vendor rooms, buyer = buyer rooms)
    path('', AllNegotiationsView.as_view(), name='all-negotiations'),

    # Buyer — room management
    path('start/', StartNegotiationView.as_view(), name='start-negotiation'),
    path('rooms/', MyNegotiationRoomsView.as_view(), name='my-rooms'),
    path('rooms/<uuid:pk>/', NegotiationRoomDetailView.as_view(), name='room-detail'),
    path('rooms/<uuid:pk>/messages/', RoomMessagesView.as_view(), name='room-messages'),
    path('rooms/<uuid:pk>/offers/', RoomOffersView.as_view(), name='room-offers'),

    # Buyer — active deals & history
    path('active/', ActiveNegotiationsView.as_view(), name='active-negotiations'),
    path('history/', NegotiationHistoryView.as_view(), name='negotiation-history'),

    # Vendor — room management
    path('vendor/<uuid:vendor_uuid>/rooms/', VendorNegotiationRoomsView.as_view(), name='vendor-rooms'),
    path('vendor/rooms/<uuid:pk>/switch-mode/', SwitchModeView.as_view(), name='switch-mode'),

    # Vendor — active deals & history
    path('vendor/<uuid:vendor_uuid>/active/', VendorActiveNegotiationsView.as_view(), name='vendor-active'),
    path('vendor/<uuid:vendor_uuid>/history/', VendorNegotiationHistoryView.as_view(), name='vendor-history'),

    path('', include(router.urls)),
]

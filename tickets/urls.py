from django.urls import path

from .views import (
    AdminTicketsView,
    MyTicketsView,
    TicketDetailView,
    TicketMarkReadView,
    TicketMessagesView,
    TicketMetaView,
    TicketStatusView,
    TicketVendorSearchView,
    VendorTicketsView,
)

app_name = 'tickets'

urlpatterns = [
    path('', MyTicketsView.as_view(), name='my-tickets'),
    path('meta/', TicketMetaView.as_view(), name='meta'),
    path('vendors/', TicketVendorSearchView.as_view(), name='vendor-search'),
    path('vendor/', VendorTicketsView.as_view(), name='vendor-tickets'),
    path('admin/', AdminTicketsView.as_view(), name='admin-tickets'),
    path('<uuid:ticket_id>/', TicketDetailView.as_view(), name='detail'),
    path('<uuid:ticket_id>/messages/',
         TicketMessagesView.as_view(), name='messages'),
    path('<uuid:ticket_id>/read/',
         TicketMarkReadView.as_view(), name='read'),
    path('<uuid:ticket_id>/status/',
         TicketStatusView.as_view(), name='status'),
]

from django.urls import path
from .views import (
    NotificationListView,
    UnreadCountView,
    MarkReadView,
    MarkAllReadView,
    NotificationDetailView,
    NotificationPreferenceView,
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('mark-all-read/', MarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('<uuid:pk>/mark-read/', MarkReadView.as_view(), name='notification-mark-read'),
    path('<uuid:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
]

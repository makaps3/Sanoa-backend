"""
Notification REST API.

GET    /api/notifications/                 → paginated list (newest first)
GET    /api/notifications/unread-count/    → {"count": 5}
POST   /api/notifications/<id>/mark-read/ → mark one read
POST   /api/notifications/mark-all-read/  → mark all read
DELETE /api/notifications/<id>/           → delete a notification
GET    /api/notifications/preferences/    → get preference settings
PATCH  /api/notifications/preferences/    → update preference settings
"""
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationListView(generics.ListAPIView):
    """
    List all notifications for the authenticated user, newest first.

    Query params:
      category  — filter by category (order, payment, credit, etc.)
      unread    — ?unread=true to return only unread
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        if self.request.query_params.get('unread', '').lower() == 'true':
            qs = qs.filter(is_read=False)
        return qs


class UnreadCountView(APIView):
    """Return the number of unread notifications for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        return Response({'count': count})


class MarkReadView(APIView):
    """Mark a single notification as read."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        notif.mark_read()
        return Response(NotificationSerializer(notif).data)


class MarkAllReadView(APIView):
    """Mark all notifications for the authenticated user as read."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response({'marked_read': updated})


class NotificationDetailView(generics.RetrieveDestroyAPIView):
    """GET or DELETE a single notification by UUID."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


# Alias kept so any cached import of the old name still resolves.
NotificationDeleteView = NotificationDetailView


class NotificationPreferenceView(APIView):
    """GET or PATCH notification preferences for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create_prefs(self, user):
        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        return prefs

    def get(self, request):
        prefs = self._get_or_create_prefs(request.user)
        return Response(NotificationPreferenceSerializer(prefs).data)

    def patch(self, request):
        prefs = self._get_or_create_prefs(request.user)
        serializer = NotificationPreferenceSerializer(
            prefs, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

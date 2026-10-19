"""
API views for the audit trail.
Admin-only endpoints for viewing and querying audit logs.
"""
from django.utils import timezone
from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from core.permissions import IsAdminUser
from audit.models import AuditLog, LoginAttempt
from audit.serializers import (
    AuditLogSerializer,
    AuditLogSummarySerializer,
    LoginAttemptSerializer,
)
from audit.filters import AuditLogFilter, LoginAttemptFilter


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only viewset for browsing audit logs.

    list: Get paginated audit logs (summary view)
    retrieve: Get full details of a single audit log entry
    stats: Get audit statistics and summary counts
    by_object: Get audit trail for a specific object
    by_user: Get audit trail for a specific user
    """

    queryset = AuditLog.objects.select_related('user').all()
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AuditLogFilter
    search_fields = [
        'user_email', 'description', 'target_model',
        'target_id', 'ip_address', 'request_path',
    ]
    ordering_fields = ['timestamp', 'category', 'action', 'status']
    ordering = ['-timestamp']

    def get_serializer_class(self):
        if self.action == 'list':
            return AuditLogSummarySerializer
        return AuditLogSerializer

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get audit statistics for the dashboard."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_events = AuditLog.objects.count()
        events_today = AuditLog.objects.filter(timestamp__gte=today_start).count()
        failed_logins_today = AuditLog.objects.filter(
            timestamp__gte=today_start,
            action='login_failed',
        ).count()

        events_by_category = dict(
            AuditLog.objects.values_list('category')
            .annotate(count=Count('id'))
            .values_list('category', 'count')
        )

        events_by_status = dict(
            AuditLog.objects.values_list('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

        top_users = list(
            AuditLog.objects.exclude(user_email='')
            .values('user_email')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        return Response({
            'total_events': total_events,
            'events_today': events_today,
            'failed_logins_today': failed_logins_today,
            'events_by_category': events_by_category,
            'events_by_status': events_by_status,
            'top_users': top_users,
        })

    @action(detail=False, methods=['get'], url_path='by-object')
    def by_object(self, request):
        """
        Get the audit trail for a specific object.
        Query params: target_model, target_id
        """
        target_model = request.query_params.get('target_model')
        target_id = request.query_params.get('target_id')

        if not target_model or not target_id:
            return Response(
                {'error': 'Both target_model and target_id query params are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logs = self.get_queryset().filter(
            target_model=target_model,
            target_id=target_id,
        )
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = AuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-user/(?P<user_id>[^/.]+)')
    def by_user(self, request, user_id=None):
        """Get the audit trail for a specific user."""
        logs = self.get_queryset().filter(user_id=user_id)
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = AuditLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only viewset for browsing login attempts.
    Useful for security monitoring.
    """

    queryset = LoginAttempt.objects.all()
    serializer_class = LoginAttemptSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = LoginAttemptFilter
    search_fields = ['email', 'ip_address']
    ordering_fields = ['timestamp', 'status']
    ordering = ['-timestamp']

    @action(detail=False, methods=['get'], url_path='suspicious')
    def suspicious(self, request):
        """
        Get IPs with multiple failed login attempts in the last 24 hours.
        """
        since = timezone.now() - timezone.timedelta(hours=24)
        suspicious = (
            LoginAttempt.objects
            .filter(status='failed', timestamp__gte=since)
            .values('ip_address', 'email')
            .annotate(attempts=Count('id'))
            .filter(attempts__gte=5)
            .order_by('-attempts')
        )
        return Response(list(suspicious))

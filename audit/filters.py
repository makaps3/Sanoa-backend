"""
Django-filter filtersets for audit log queries.
"""
import django_filters
from audit.models import AuditLog, LoginAttempt


class AuditLogFilter(django_filters.FilterSet):
    """Filter for AuditLog queries."""

    timestamp_from = django_filters.DateTimeFilter(
        field_name='timestamp', lookup_expr='gte',
    )
    timestamp_to = django_filters.DateTimeFilter(
        field_name='timestamp', lookup_expr='lte',
    )
    date = django_filters.DateFilter(
        field_name='timestamp', lookup_expr='date',
    )

    class Meta:
        model = AuditLog
        fields = [
            'category', 'action', 'status',
            'user', 'user_email',
            'target_model', 'target_id',
            'ip_address',
            'request_method', 'response_status_code',
        ]


class LoginAttemptFilter(django_filters.FilterSet):
    """Filter for LoginAttempt queries."""

    timestamp_from = django_filters.DateTimeFilter(
        field_name='timestamp', lookup_expr='gte',
    )
    timestamp_to = django_filters.DateTimeFilter(
        field_name='timestamp', lookup_expr='lte',
    )

    class Meta:
        model = LoginAttempt
        fields = ['email', 'ip_address', 'status']

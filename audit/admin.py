"""
Admin interface for the audit trail.
Read-only views for admins to browse and search audit logs.
"""
from django.contrib import admin
from audit.models import AuditLog, LoginAttempt


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user_email', 'category', 'action',
        'status', 'target_model', 'target_id', 'short_description',
    ]
    list_filter = ['category', 'action', 'status', 'timestamp']
    search_fields = [
        'user_email', 'description', 'target_model',
        'target_id', 'ip_address', 'request_path',
    ]
    readonly_fields = [
        'id', 'user', 'user_email', 'ip_address', 'user_agent',
        'category', 'action', 'status', 'description',
        'target_model', 'target_id', 'target_repr',
        'changes', 'extra_data',
        'request_method', 'request_path',
        'response_status_code', 'request_duration_ms',
        'timestamp',
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50

    def short_description(self, obj):
        return obj.description[:80] if obj.description else ''
    short_description.short_description = 'Description'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete audit logs
        return request.user.is_superuser


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'email', 'ip_address', 'status', 'failure_reason']
    list_filter = ['status', 'timestamp']
    search_fields = ['email', 'ip_address']
    readonly_fields = [
        'id', 'email', 'ip_address', 'user_agent',
        'status', 'failure_reason', 'timestamp',
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

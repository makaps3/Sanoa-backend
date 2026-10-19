from django.contrib import admin
from django.utils.html import format_html
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id_short', 'recipient', 'notification_type', 'category',
        'title', 'is_read_badge', 'created_at',
    ]
    list_filter = ['category', 'notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__email', 'title', 'body']
    readonly_fields = ['id', 'created_at', 'read_at']
    ordering = ['-created_at']
    list_per_page = 50

    def id_short(self, obj):
        return str(obj.id)[:8] + '…'
    id_short.short_description = 'ID'

    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color:green;font-weight:bold;">Read</span>')
        return format_html('<span style="color:orange;font-weight:bold;">Unread</span>')
    is_read_badge.short_description = 'Read'

    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        self.message_user(request, f'{updated} notification(s) marked as read.')
    mark_as_read.short_description = 'Mark selected as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
    mark_as_unread.short_description = 'Mark selected as unread'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'order_notifications', 'payment_notifications',
        'credit_notifications', 'in_app_enabled', 'push_enabled', 'updated_at',
    ]
    search_fields = ['user__email']
    readonly_fields = ['updated_at']

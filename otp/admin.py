from django.contrib import admin

from .models import OTPCode


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'purpose', 'is_used', 'attempts', 'created_at', 'expires_at']
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['user__email', 'code']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']

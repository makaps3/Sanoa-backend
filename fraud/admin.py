from django.contrib import admin
from django.utils.html import format_html

from .models import FraudEvent, FraudProfile

_RISK_COLORS = {
    'low':      '#2e7d32',
    'medium':   '#f57c00',
    'high':     '#c62828',
    'critical': '#4a148c',
}


class FraudEventInline(admin.TabularInline):
    model  = FraudEvent
    extra  = 0
    max_num = 25
    can_delete = False
    ordering = ['-created_at']
    readonly_fields = [
        'event_type', 'severity', 'description',
        'entity_type', 'entity_id', 'ml_score',
        'is_resolved', 'is_false_positive', 'created_at',
    ]
    fields = readonly_fields


@admin.register(FraudProfile)
class FraudProfileAdmin(admin.ModelAdmin):
    list_display  = [
        'subject', 'risk_badge', 'score_display',
        'is_flagged', 'is_reviewed', 'review_outcome',
        'refund_count', 'dispute_count', 'last_scored_at',
    ]
    list_filter   = ['risk_level', 'is_flagged', 'is_reviewed', 'review_outcome']
    search_fields = ['user__email', 'vendor__name']
    readonly_fields = [
        'risk_score', 'risk_level', 'is_flagged', 'auto_flagged_at',
        'last_scored_at', 'score_features',
        'total_orders', 'total_order_value',
        'refund_count', 'dispute_count', 'failed_payment_count',
        'created_at', 'updated_at',
    ]
    inlines = [FraudEventInline]
    fieldsets = [
        ('Subject',  {'fields': ('user', 'vendor')}),
        ('Risk',     {'fields': ('risk_score', 'risk_level', 'is_flagged', 'auto_flagged_at', 'last_scored_at')}),
        ('Stats',    {'fields': ('total_orders', 'total_order_value', 'refund_count', 'dispute_count', 'failed_payment_count')}),
        ('Review',   {'fields': ('is_reviewed', 'reviewed_by', 'reviewed_at', 'review_outcome', 'review_notes')}),
        ('Features', {'fields': ('score_features',), 'classes': ('collapse',)}),
    ]

    @admin.display(description='Subject')
    def subject(self, obj):
        if obj.user_id:
            return f"👤 {obj.user.email}"
        return f"🏪 {obj.vendor.name}"

    @admin.display(description='Risk Level')
    def risk_badge(self, obj):
        color = _RISK_COLORS.get(obj.risk_level, '#666')
        return format_html(
            '<span style="color:white;background:{};padding:2px 10px;'
            'border-radius:4px;font-weight:bold;">{}</span>',
            color,
            obj.risk_level.upper(),
        )

    @admin.display(description='Score', ordering='risk_score')
    def score_display(self, obj):
        return f"{obj.risk_score:.1f}"


@admin.register(FraudEvent)
class FraudEventAdmin(admin.ModelAdmin):
    list_display  = [
        'event_type', 'severity_badge', 'description_short',
        'entity_type', 'entity_id', 'is_resolved', 'created_at',
    ]
    list_filter   = ['event_type', 'severity', 'entity_type', 'is_resolved', 'is_false_positive']
    search_fields = ['description', 'entity_id', 'profile__user__email', 'profile__vendor__name']
    readonly_fields = [
        'id', 'profile', 'event_type', 'severity', 'description',
        'entity_type', 'entity_id', 'metadata', 'ml_score', 'created_at',
    ]

    @admin.display(description='Severity')
    def severity_badge(self, obj):
        color = _RISK_COLORS.get(obj.severity, '#666')
        return format_html(
            '<span style="color:white;background:{};padding:1px 8px;'
            'border-radius:4px;">{}</span>',
            color,
            obj.severity.upper(),
        )

    @admin.display(description='Description')
    def description_short(self, obj):
        return obj.description[:80] + ('…' if len(obj.description) > 80 else '')

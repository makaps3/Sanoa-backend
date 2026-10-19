from django.contrib import admin

from .models import Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('sender', 'sender_role', 'kind', 'body', 'created_at')
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'target_type', 'category', 'urgency',
                    'status', 'customer', 'vendor', 'created_at')
    list_filter = ('target_type', 'category', 'urgency', 'status')
    search_fields = ('subject', 'customer__email', 'vendor__name')
    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'sender_role', 'kind', 'created_at')
    list_filter = ('sender_role', 'kind')

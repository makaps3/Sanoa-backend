from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    fields = ('kind', 'sender', 'body', 'is_deleted', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'delivery_job', 'customer', 'driver',
                    'status', 'last_message_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('customer__email', 'driver__email',
                     'last_message_preview')
    readonly_fields = ('created_at', 'last_message_at')
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'kind', 'sender',
                    'is_deleted', 'created_at')
    list_filter = ('kind', 'is_deleted')
    search_fields = ('body', 'sender__email')
    readonly_fields = ('created_at',)

from django.contrib import admin

from .models import TradeMessage


@admin.register(TradeMessage)
class TradeMessageAdmin(admin.ModelAdmin):
    list_display = ['trade', 'sender', 'message_type', 'created_at', 'read_at']
    list_filter = ['message_type']
    search_fields = ['sender__username', 'content']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['trade', 'sender']

from django.contrib import admin

from .models import Trade, TradeProposal, TradeProposalItem, TradeShipment


class TradeProposalItemInline(admin.TabularInline):
    model = TradeProposalItem
    extra = 0
    readonly_fields = ['id', 'direction', 'user_book', 'created_at']


@admin.register(TradeProposal)
class TradeProposalAdmin(admin.ModelAdmin):
    list_display = ['proposer', 'recipient', 'status', 'created_at', 'expires_at']
    list_filter = ['status']
    search_fields = ['proposer__username', 'recipient__username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['proposer', 'recipient', 'origin_match']
    inlines = [TradeProposalItemInline]


class TradeShipmentInline(admin.TabularInline):
    model = TradeShipment
    extra = 0
    readonly_fields = ['id', 'sender', 'receiver', 'user_book', 'status', 'created_at']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['id', 'source_type', 'status', 'created_at', 'completed_at', 'auto_close_at']
    list_filter = ['source_type', 'status']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [TradeShipmentInline]


@admin.register(TradeShipment)
class TradeShipmentAdmin(admin.ModelAdmin):
    list_display = ['trade', 'sender', 'receiver', 'status', 'shipped_at', 'received_at']
    list_filter = ['status']
    search_fields = ['sender__username', 'receiver__username', 'tracking_number']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['trade', 'sender', 'receiver', 'user_book']

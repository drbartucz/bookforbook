from django.contrib import admin

from .models import Match, MatchLeg


class MatchLegInline(admin.TabularInline):
    model = MatchLeg
    extra = 0
    readonly_fields = ['id', 'sender', 'receiver', 'user_book', 'position', 'status']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'match_type', 'status', 'detected_at', 'expires_at']
    list_filter = ['match_type', 'status']
    search_fields = ['id']
    ordering = ['-detected_at']
    readonly_fields = ['id', 'detected_at', 'updated_at']
    inlines = [MatchLegInline]


@admin.register(MatchLeg)
class MatchLegAdmin(admin.ModelAdmin):
    list_display = ['match', 'sender', 'receiver', 'user_book', 'position', 'status']
    list_filter = ['status']
    search_fields = ['sender__username', 'receiver__username']
    readonly_fields = ['id']
    raw_id_fields = ['match', 'sender', 'receiver', 'user_book']

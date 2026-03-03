from django.contrib import admin

from .models import UserBook, WishlistItem


@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'condition', 'status', 'created_at']
    list_filter = ['condition', 'status']
    search_fields = ['user__username', 'user__email', 'book__title', 'book__isbn_13']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'book']


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'min_condition', 'is_active', 'created_at']
    list_filter = ['min_condition', 'is_active']
    search_fields = ['user__username', 'book__title', 'book__isbn_13']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'book']

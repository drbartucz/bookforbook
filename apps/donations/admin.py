from django.contrib import admin

from .models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['donor', 'institution', 'user_book', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['donor__username', 'institution__username', 'institution__institution_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['donor', 'institution', 'user_book']

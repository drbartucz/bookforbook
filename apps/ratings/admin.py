from django.contrib import admin

from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['rater', 'rated', 'score', 'book_condition_accurate', 'created_at']
    list_filter = ['score', 'book_condition_accurate']
    search_fields = ['rater__username', 'rated__username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['trade', 'rater', 'rated']

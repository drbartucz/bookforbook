from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'isbn_13', 'isbn_10', 'authors_display', 'publish_year', 'created_at']
    list_filter = ['publish_year']
    search_fields = ['title', 'isbn_13', 'isbn_10']
    ordering = ['title']
    readonly_fields = ['id', 'created_at', 'updated_at']

    @admin.display(description='Authors')
    def authors_display(self, obj):
        return ', '.join(obj.authors[:2]) if obj.authors else '—'

from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'isbn_13', 'isbn_10', 'authors_display', 'publish_year', 'created_at']
    list_filter = ['publish_year']
    # Keep admin search on scalar columns to avoid backend-specific JSON lookups.
    search_fields = ['title', 'isbn_13', 'isbn_10']
    ordering = ['title']
    readonly_fields = ['id', 'created_at', 'updated_at']

    @admin.display(description='authors')
    def authors_display(self, obj: Book) -> str:
        if isinstance(obj.authors, list):
            return ', '.join(str(author) for author in obj.authors[:3])
        if isinstance(obj.authors, str):
            return obj.authors
        if obj.authors is None:
            return ''
        return str(obj.authors)

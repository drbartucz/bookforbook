from rest_framework import serializers

from .models import Book


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            'id', 'isbn_13', 'isbn_10', 'title', 'authors',
            'publisher', 'publish_year', 'cover_image_url',
            'cover_image_cached', 'page_count', 'subjects',
            'description', 'open_library_key', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class BookLookupSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=20)

    def validate_isbn(self, value):
        from .services.openlibrary import normalize_isbn
        normalized = normalize_isbn(value)
        if not normalized:
            raise serializers.ValidationError(
                'Invalid ISBN. Please enter a valid 10 or 13-digit ISBN.'
            )
        return value

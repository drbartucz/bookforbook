from rest_framework import serializers

from apps.books.models import Book
from apps.books.serializers import BookSerializer

from .models import ConditionChoices, UserBook, WishlistItem


class BrowseBookSerializer(serializers.ModelSerializer):
    """Serializer for the browse/available endpoint. Emits Book fields plus
    copy_count (number of available listings) and condition (best available)."""

    copy_count = serializers.IntegerField(read_only=True)
    condition = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "isbn_13",
            "isbn_10",
            "title",
            "authors",
            "publisher",
            "publish_year",
            "cover_image_url",
            "page_count",
            "physical_format",
            "subjects",
            "description",
            "copy_count",
            "condition",
        ]

    def get_condition(self, obj):
        return getattr(obj, "best_condition", None)


class BrowseWantedSerializer(serializers.ModelSerializer):
    """Serializer for the browse/wanted endpoint. Emits Book fields plus
    want_count (number of active wishlist entries for this book)."""

    want_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "isbn_13",
            "isbn_10",
            "title",
            "authors",
            "publisher",
            "publish_year",
            "cover_image_url",
            "page_count",
            "physical_format",
            "subjects",
            "description",
            "want_count",
        ]


class UserBookSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user_id = serializers.UUIDField(read_only=True, source="user.id")
    username = serializers.CharField(read_only=True, source="user.username")
    want_count = serializers.SerializerMethodField()
    is_institution_wanted = serializers.SerializerMethodField()

    class Meta:
        model = UserBook
        fields = [
            "id",
            "user_id",
            "username",
            "book",
            "condition",
            "condition_notes",
            "status",
            "want_count",
            "is_institution_wanted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "username",
            "book",
            "want_count",
            "is_institution_wanted",
            "created_at",
            "updated_at",
        ]

    def get_want_count(self, obj):
        return getattr(obj, 'want_count', 0) or 0

    def get_is_institution_wanted(self, obj):
        return bool(getattr(obj, 'is_institution_wanted', False))


class UserBookCreateSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=20)
    condition = serializers.ChoiceField(choices=ConditionChoices.choices)
    condition_notes = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )

    def validate_isbn(self, value):
        from apps.books.services.openlibrary import normalize_isbn

        normalized = normalize_isbn(value)
        if not normalized:
            raise serializers.ValidationError("Invalid ISBN format.")
        return value

    def create(self, validated_data):
        from apps.books.services.openlibrary import get_or_create_book

        isbn = validated_data.pop("isbn")
        book = get_or_create_book(isbn, minimal=True)
        user = self.context["request"].user
        return UserBook.objects.create(user=user, book=book, **validated_data)


class UserBookUpdateSerializer(serializers.ModelSerializer):
    condition_notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=500
    )

    class Meta:
        model = UserBook
        fields = ["condition", "condition_notes", "status"]

    def validate_status(self, value):
        # Users can only manually set certain statuses
        allowed = [UserBook.Status.AVAILABLE, UserBook.Status.REMOVED]
        if value not in allowed:
            raise serializers.ValidationError(
                f'You can only set status to: {", ".join(allowed)}'
            )
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status == UserBook.Status.RESERVED:
            raise serializers.ValidationError(
                "Cannot modify a book that is currently reserved for a trade."
            )
        return attrs


class WishlistItemSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user_id = serializers.UUIDField(read_only=True, source="user.id")
    viewer_can_gift = serializers.SerializerMethodField()
    viewer_user_book_id = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            "id",
            "user_id",
            "book",
            "min_condition",
            "edition_preference",
            "allow_translations",
            "exclude_abridged",
            "format_preferences",
            "is_active",
            "viewer_can_gift",
            "viewer_user_book_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_id", "book", "viewer_can_gift", "viewer_user_book_id", "created_at", "updated_at"]

    def get_viewer_can_gift(self, obj):
        viewer_book_id_map = self.context.get('viewer_book_id_map', {})
        return obj.book_id in viewer_book_id_map

    def get_viewer_user_book_id(self, obj):
        viewer_book_id_map = self.context.get('viewer_book_id_map', {})
        val = viewer_book_id_map.get(obj.book_id)
        return str(val) if val else None


class WishlistItemCreateSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=20)
    min_condition = serializers.ChoiceField(
        choices=ConditionChoices.choices,
        default=ConditionChoices.ACCEPTABLE,
    )
    edition_preference = serializers.ChoiceField(
        choices=WishlistItem.EditionPreference.choices,
        default=WishlistItem.EditionPreference.SAME_LANGUAGE,
    )
    allow_translations = serializers.BooleanField(required=False, default=False)
    exclude_abridged = serializers.BooleanField(required=False, default=True)
    format_preferences = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
        default=list,
    )

    def validate_isbn(self, value):
        from apps.books.services.openlibrary import normalize_isbn

        normalized = normalize_isbn(value)
        if not normalized:
            raise serializers.ValidationError("Invalid ISBN format.")
        return value

    def validate(self, attrs):
        from apps.books.services.openlibrary import normalize_isbn, get_or_create_book

        isbn = attrs["isbn"]
        book = get_or_create_book(isbn, minimal=True)
        user = self.context["request"].user

        allowed_formats = {
            "hardcover",
            "paperback",
            "mass_market",
            "large_print",
            "audiobook",
        }
        format_preferences = attrs.get("format_preferences", [])
        invalid_formats = [
            fmt for fmt in format_preferences if fmt not in allowed_formats
        ]
        if invalid_formats:
            raise serializers.ValidationError(
                {
                    "format_preferences": f'Unsupported format(s): {", ".join(invalid_formats)}'
                }
            )

        preference = attrs.get(
            "edition_preference", WishlistItem.EditionPreference.SAME_LANGUAGE
        )
        if preference == WishlistItem.EditionPreference.EXACT:
            attrs["allow_translations"] = False
            attrs["format_preferences"] = []
        elif preference == WishlistItem.EditionPreference.SAME_LANGUAGE:
            attrs["allow_translations"] = False
        elif preference == WishlistItem.EditionPreference.ANY_LANGUAGE:
            attrs["allow_translations"] = True

        if WishlistItem.objects.filter(user=user, book=book).exists():
            raise serializers.ValidationError(
                {"isbn": "This book is already on your wishlist."}
            )
        attrs["book"] = book
        return attrs

    def create(self, validated_data):
        validated_data.pop("isbn")
        user = self.context["request"].user
        return WishlistItem.objects.create(user=user, **validated_data)


class WishlistItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WishlistItem
        fields = [
            "min_condition",
            "edition_preference",
            "allow_translations",
            "exclude_abridged",
            "format_preferences",
            "is_active",
        ]

    def validate(self, attrs):
        allowed_formats = {
            "hardcover",
            "paperback",
            "mass_market",
            "large_print",
            "audiobook",
        }
        format_preferences = attrs.get("format_preferences")
        if format_preferences is not None:
            invalid_formats = [
                fmt for fmt in format_preferences if fmt not in allowed_formats
            ]
            if invalid_formats:
                raise serializers.ValidationError(
                    {
                        "format_preferences": f'Unsupported format(s): {", ".join(invalid_formats)}'
                    }
                )

        preference = attrs.get("edition_preference")
        if preference == WishlistItem.EditionPreference.EXACT:
            attrs["allow_translations"] = False
            attrs["format_preferences"] = []
        elif preference == WishlistItem.EditionPreference.SAME_LANGUAGE:
            attrs["allow_translations"] = False
        elif preference == WishlistItem.EditionPreference.ANY_LANGUAGE:
            attrs["allow_translations"] = True

        return attrs

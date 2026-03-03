from rest_framework import serializers

from apps.books.serializers import BookSerializer

from .models import ConditionChoices, UserBook, WishlistItem


class UserBookSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user_id = serializers.UUIDField(read_only=True, source='user.id')
    username = serializers.CharField(read_only=True, source='user.username')

    class Meta:
        model = UserBook
        fields = [
            'id', 'user_id', 'username', 'book',
            'condition', 'condition_notes', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'username', 'book', 'created_at', 'updated_at']


class UserBookCreateSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=20)
    condition = serializers.ChoiceField(choices=ConditionChoices.choices)
    condition_notes = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate_isbn(self, value):
        from apps.books.services.openlibrary import normalize_isbn
        normalized = normalize_isbn(value)
        if not normalized:
            raise serializers.ValidationError('Invalid ISBN format.')
        return value

    def create(self, validated_data):
        from apps.books.services.openlibrary import get_or_create_book
        isbn = validated_data.pop('isbn')
        book = get_or_create_book(isbn)
        user = self.context['request'].user
        return UserBook.objects.create(user=user, book=book, **validated_data)


class UserBookUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBook
        fields = ['condition', 'condition_notes', 'status']

    def validate_status(self, value):
        # Users can only manually set certain statuses
        allowed = [UserBook.Status.AVAILABLE, UserBook.Status.REMOVED]
        if value not in allowed:
            raise serializers.ValidationError(
                f'You can only set status to: {", ".join(allowed)}'
            )
        return value


class WishlistItemSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user_id = serializers.UUIDField(read_only=True, source='user.id')

    class Meta:
        model = WishlistItem
        fields = [
            'id', 'user_id', 'book', 'min_condition',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'book', 'created_at', 'updated_at']


class WishlistItemCreateSerializer(serializers.Serializer):
    isbn = serializers.CharField(max_length=20)
    min_condition = serializers.ChoiceField(
        choices=ConditionChoices.choices,
        default=ConditionChoices.ACCEPTABLE,
    )

    def validate_isbn(self, value):
        from apps.books.services.openlibrary import normalize_isbn
        normalized = normalize_isbn(value)
        if not normalized:
            raise serializers.ValidationError('Invalid ISBN format.')
        return value

    def validate(self, attrs):
        from apps.books.services.openlibrary import normalize_isbn, get_or_create_book
        isbn = attrs['isbn']
        book = get_or_create_book(isbn)
        user = self.context['request'].user

        if WishlistItem.objects.filter(user=user, book=book).exists():
            raise serializers.ValidationError(
                {'isbn': 'This book is already on your wishlist.'}
            )
        attrs['book'] = book
        return attrs

    def create(self, validated_data):
        validated_data.pop('isbn')
        user = self.context['request'].user
        return WishlistItem.objects.create(user=user, **validated_data)


class WishlistItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WishlistItem
        fields = ['min_condition', 'is_active']

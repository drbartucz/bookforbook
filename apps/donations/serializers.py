from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer
from apps.inventory.serializers import UserBookSerializer

from .models import Donation


class DonationSerializer(serializers.ModelSerializer):
    donor = UserPublicProfileSerializer(read_only=True)
    recipient = UserPublicProfileSerializer(read_only=True)
    user_book = UserBookSerializer(read_only=True)
    recipient_address = serializers.SerializerMethodField()
    is_recipient = serializers.SerializerMethodField()

    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'recipient', 'user_book',
            'status', 'message', 'recipient_address', 'is_recipient',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_is_recipient(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.recipient

    def get_recipient_address(self, obj):
        """Reveal recipient address only after donation is accepted."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if obj.status not in [Donation.Status.ACCEPTED, Donation.Status.SHIPPED, Donation.Status.RECEIVED]:
            return None
        if request.user != obj.donor and request.user != obj.recipient:
            return None
        if request.user == obj.donor:
            r = obj.recipient
            return {
                'institution_name': getattr(r, 'institution_name', None),
                'full_name': r.full_name,
                'address_line_1': r.address_line_1,
                'address_line_2': r.address_line_2,
                'city': r.city,
                'state': r.state,
                'zip_code': r.zip_code,
            }
        return None


_CONDITION_RANK = {'like_new': 4, 'very_good': 3, 'good': 2, 'acceptable': 1}


class DonationCreateSerializer(serializers.Serializer):
    recipient_id = serializers.UUIDField()
    user_book_id = serializers.UUIDField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        from apps.accounts.models import User
        from apps.inventory.models import UserBook, WishlistItem

        request = self.context['request']
        donor = request.user

        try:
            recipient = User.objects.get(pk=attrs['recipient_id'], is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'recipient_id': 'User not found.'})

        if recipient == donor:
            raise serializers.ValidationError({'recipient_id': 'You cannot gift a book to yourself.'})

        if recipient.is_institutional:
            if not recipient.is_verified:
                raise serializers.ValidationError(
                    {'recipient_id': 'Institution not found or not verified.'}
                )
        else:
            # For individuals, the book must be on their active wishlist
            try:
                user_book_for_check = UserBook.objects.get(pk=attrs['user_book_id'])
            except UserBook.DoesNotExist:
                raise serializers.ValidationError({'user_book_id': 'Book not available.'})
            wishlist_item = WishlistItem.objects.filter(
                user=recipient,
                book=user_book_for_check.book,
                is_active=True,
            ).first()
            if not wishlist_item:
                raise serializers.ValidationError(
                    {'recipient_id': "This book is not on that user's wishlist."}
                )
            if _CONDITION_RANK.get(user_book_for_check.condition, 0) < _CONDITION_RANK.get(wishlist_item.min_condition, 0):
                raise serializers.ValidationError(
                    {'user_book_id': "Your book's condition does not meet the recipient's minimum preference."}
                )

        try:
            user_book = UserBook.objects.get(
                pk=attrs['user_book_id'],
                user=donor,
                status=UserBook.Status.AVAILABLE,
            )
        except UserBook.DoesNotExist:
            raise serializers.ValidationError({'user_book_id': 'Book not available.'})

        attrs['recipient'] = recipient
        attrs['user_book'] = user_book
        attrs['donor'] = donor
        return attrs

    def create(self, validated_data):
        return Donation.objects.create(
            donor=validated_data['donor'],
            recipient=validated_data['recipient'],
            user_book=validated_data['user_book'],
            message=validated_data.get('message', ''),
        )

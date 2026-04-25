from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer
from apps.inventory.serializers import UserBookSerializer

from .models import Donation


class DonationSerializer(serializers.ModelSerializer):
    donor = UserPublicProfileSerializer(read_only=True)
    institution = UserPublicProfileSerializer(read_only=True)
    user_book = UserBookSerializer(read_only=True)
    institution_address = serializers.SerializerMethodField()
    is_recipient = serializers.SerializerMethodField()

    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'institution', 'user_book',
            'status', 'message', 'institution_address', 'is_recipient',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_is_recipient(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.institution

    def get_institution_address(self, obj):
        """Reveal institution address only after donation is accepted."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if obj.status not in [Donation.Status.ACCEPTED, Donation.Status.SHIPPED, Donation.Status.RECEIVED]:
            return None
        if request.user != obj.donor and request.user != obj.institution:
            return None
        # Reveal institution's address to the donor
        if request.user == obj.donor:
            institution = obj.institution
            return {
                'institution_name': institution.institution_name,
                'full_name': institution.full_name,
                'address_line_1': institution.address_line_1,
                'address_line_2': institution.address_line_2,
                'city': institution.city,
                'state': institution.state,
                'zip_code': institution.zip_code,
            }
        return None


class DonationCreateSerializer(serializers.Serializer):
    institution_id = serializers.UUIDField()
    user_book_id = serializers.UUIDField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        from apps.accounts.models import User
        from apps.inventory.models import UserBook

        request = self.context['request']
        donor = request.user

        # Validate institution
        try:
            institution = User.objects.get(
                pk=attrs['institution_id'],
                account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
                is_verified=True,
                is_active=True,
            )
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'institution_id': 'Institution not found or not verified.'}
            )

        # Validate user_book belongs to donor and is available
        try:
            user_book = UserBook.objects.get(
                pk=attrs['user_book_id'],
                user=donor,
                status=UserBook.Status.AVAILABLE,
            )
        except UserBook.DoesNotExist:
            raise serializers.ValidationError({'user_book_id': 'Book not available.'})

        attrs['institution'] = institution
        attrs['user_book'] = user_book
        attrs['donor'] = donor
        return attrs

    def create(self, validated_data):
        return Donation.objects.create(
            donor=validated_data['donor'],
            institution=validated_data['institution'],
            user_book=validated_data['user_book'],
            message=validated_data.get('message', ''),
        )

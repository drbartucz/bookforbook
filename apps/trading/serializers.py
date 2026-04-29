from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer
from apps.inventory.serializers import UserBookSerializer

from .models import Trade, TradeProposal, TradeProposalItem, TradeShipment


class TradeProposalItemSerializer(serializers.ModelSerializer):
    user_book = UserBookSerializer(read_only=True)

    class Meta:
        model = TradeProposalItem
        fields = ['id', 'direction', 'user_book', 'created_at']
        read_only_fields = fields


class TradeProposalSerializer(serializers.ModelSerializer):
    proposer = UserPublicProfileSerializer(read_only=True)
    recipient = UserPublicProfileSerializer(read_only=True)
    items = TradeProposalItemSerializer(many=True, read_only=True)

    class Meta:
        model = TradeProposal
        fields = [
            'id', 'proposer', 'recipient', 'origin_match',
            'status', 'message', 'items',
            'created_at', 'updated_at', 'expires_at',
        ]
        read_only_fields = fields


class TradeProposalCreateSerializer(serializers.Serializer):
    recipient_id = serializers.UUIDField()
    proposer_book_id = serializers.UUIDField(help_text='UserBook ID the proposer will send')
    recipient_book_id = serializers.UUIDField(help_text='UserBook ID the recipient will send')
    message = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    origin_match_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        from apps.accounts.models import User
        from apps.inventory.models import UserBook
        from apps.matching.services.direct_matcher import user_at_match_limit

        request = self.context['request']
        proposer = request.user

        # Validate recipient
        try:
            recipient = User.objects.get(pk=attrs['recipient_id'], is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'recipient_id': 'User not found.'})

        if recipient == proposer:
            raise serializers.ValidationError({'recipient_id': 'You cannot propose a trade with yourself.'})

        # Validate proposer_book
        try:
            proposer_book = UserBook.objects.get(
                pk=attrs['proposer_book_id'],
                user=proposer,
                status=UserBook.Status.AVAILABLE,
            )
        except UserBook.DoesNotExist:
            raise serializers.ValidationError({'proposer_book_id': 'Book not available.'})

        # Validate recipient_book
        try:
            recipient_book = UserBook.objects.get(
                pk=attrs['recipient_book_id'],
                user=recipient,
                status=UserBook.Status.AVAILABLE,
            )
        except UserBook.DoesNotExist:
            raise serializers.ValidationError({'recipient_book_id': 'Book not available.'})

        # Check match limits
        if user_at_match_limit(proposer):
            raise serializers.ValidationError(
                'You have reached your active match limit. Complete existing trades to make room.'
            )
        if user_at_match_limit(recipient):
            raise serializers.ValidationError(
                'The recipient has reached their active match limit.'
            )

        attrs['proposer'] = proposer
        attrs['recipient'] = recipient
        attrs['proposer_book'] = proposer_book
        attrs['recipient_book'] = recipient_book
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        from apps.inventory.models import UserBook
        from apps.trading.models import TradeProposalItem

        proposer = validated_data['proposer']
        recipient = validated_data['recipient']
        message = validated_data.get('message', '')
        origin_match_id = validated_data.get('origin_match_id')

        with transaction.atomic():
            try:
                proposer_book = UserBook.objects.select_for_update().get(
                    pk=validated_data['proposer_book'].pk,
                    user=proposer,
                    status=UserBook.Status.AVAILABLE,
                )
            except UserBook.DoesNotExist:
                raise serializers.ValidationError(
                    {'proposer_book_id': 'Book is no longer available.'}
                )

            try:
                recipient_book = UserBook.objects.select_for_update().get(
                    pk=validated_data['recipient_book'].pk,
                    user=recipient,
                    status=UserBook.Status.AVAILABLE,
                )
            except UserBook.DoesNotExist:
                raise serializers.ValidationError(
                    {'recipient_book_id': 'Book is no longer available.'}
                )

            proposal = TradeProposal.objects.create(
                proposer=proposer,
                recipient=recipient,
                message=message,
                origin_match_id=origin_match_id,
            )
            TradeProposalItem.objects.create(
                proposal=proposal,
                direction=TradeProposalItem.Direction.PROPOSER_SENDS,
                user_book=proposer_book,
            )
            TradeProposalItem.objects.create(
                proposal=proposal,
                direction=TradeProposalItem.Direction.RECIPIENT_SENDS,
                user_book=recipient_book,
            )
        return proposal


class TradeShipmentSerializer(serializers.ModelSerializer):
    sender = UserPublicProfileSerializer(read_only=True)
    receiver = UserPublicProfileSerializer(read_only=True)
    user_book = UserBookSerializer(read_only=True)

    class Meta:
        model = TradeShipment
        fields = [
            'id', 'sender', 'receiver', 'user_book',
            'tracking_number', 'shipping_method',
            'shipped_at', 'received_at', 'status', 'created_at',
        ]
        read_only_fields = fields


class TradeSerializer(serializers.ModelSerializer):
    shipments = TradeShipmentSerializer(many=True, read_only=True)
    partner_addresses = serializers.SerializerMethodField()

    class Meta:
        model = Trade
        fields = [
            'id', 'source_type', 'source_id', 'status',
            'shipments', 'partner_addresses',
            'created_at', 'updated_at', 'completed_at', 'auto_close_at',
            'rating_reminders_sent',
        ]
        read_only_fields = fields

    def get_partner_addresses(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        from apps.trading.services.trade_workflow import reveal_addresses
        return reveal_addresses(obj, request.user)


class MarkShippedSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(required=False, allow_blank=True, max_length=100)
    shipping_method = serializers.CharField(required=False, allow_blank=True, max_length=100)


class TradeRateSerializer(serializers.Serializer):
    rated_user_id = serializers.UUIDField()
    score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)
    book_condition_accurate = serializers.BooleanField()

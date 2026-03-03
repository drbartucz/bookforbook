from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer
from apps.books.serializers import BookSerializer
from apps.inventory.serializers import UserBookSerializer

from .models import Match, MatchLeg


class MatchLegSerializer(serializers.ModelSerializer):
    sender = UserPublicProfileSerializer(read_only=True)
    receiver = UserPublicProfileSerializer(read_only=True)
    user_book = UserBookSerializer(read_only=True)

    class Meta:
        model = MatchLeg
        fields = [
            'id', 'sender', 'receiver', 'user_book',
            'position', 'status',
        ]
        read_only_fields = fields


class MatchSerializer(serializers.ModelSerializer):
    legs = MatchLegSerializer(many=True, read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'match_type', 'status', 'detected_at',
            'expires_at', 'updated_at', 'legs',
        ]
        read_only_fields = fields

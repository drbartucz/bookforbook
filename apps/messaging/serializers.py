from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer

from .models import TradeMessage


class TradeMessageSerializer(serializers.ModelSerializer):
    sender = UserPublicProfileSerializer(read_only=True)

    class Meta:
        model = TradeMessage
        fields = [
            'id', 'trade', 'sender', 'message_type',
            'content', 'metadata', 'created_at', 'read_at',
        ]
        read_only_fields = ['id', 'trade', 'sender', 'created_at', 'read_at']


class TradeMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeMessage
        fields = ['message_type', 'content', 'metadata']

    def validate_content(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError('Message content cannot be empty.')
        return value

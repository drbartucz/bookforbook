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
            "id",
            "sender",
            "receiver",
            "user_book",
            "position",
            "status",
        ]
        read_only_fields = fields


class MatchSerializer(serializers.ModelSerializer):
    legs = MatchLegSerializer(many=True, read_only=True)
    trade_id = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "match_type",
            "status",
            "detected_at",
            "expires_at",
            "updated_at",
            "legs",
            "trade_id",
        ]
        read_only_fields = fields

    def get_trade_id(self, obj):
        # Only COMPLETED matches have an associated trade.
        if obj.status != Match.Status.COMPLETED:
            return None

        # Use preloaded mapping from context when available (avoids N+1 on list).
        trade_ids = self.context.get("trade_ids")
        if trade_ids is not None:
            return str(trade_id) if (trade_id := trade_ids.get(obj.id)) else None

        # Fallback: single DB query (used for detail / accept views).
        from apps.trading.models import Trade

        trade_id = (
            Trade.objects.filter(
                source_type=Trade.SourceType.MATCH,
                source_id=obj.id,
            )
            .values_list("id", flat=True)
            .first()
        )
        return str(trade_id) if trade_id else None


class DiscoveryPartnerSerializer(serializers.Serializer):
    user = UserPublicProfileSerializer(read_only=True)
    they_want = UserBookSerializer(many=True, read_only=True)
    they_offer = UserBookSerializer(many=True, read_only=True)

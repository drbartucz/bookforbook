from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView


class _MessageCreateThrottle(UserRateThrottle):
    scope = "message_create"

from apps.trading.models import Trade

from .models import TradeMessage
from .serializers import TradeMessageCreateSerializer, TradeMessageSerializer


class TradeMessageListView(APIView):
    """
    GET /api/v1/trades/:pk/messages/ — list messages for a trade
    POST /api/v1/trades/:pk/messages/ — send a message
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [_MessageCreateThrottle()]
        return super().get_throttles()

    def _get_trade_and_verify_party(self, request, pk):
        trade = get_object_or_404(Trade, pk=pk)
        is_party = (
            trade.shipments.filter(sender=request.user).exists()
            or trade.shipments.filter(receiver=request.user).exists()
        )
        if not is_party:
            return None, None
        return trade, True

    def get(self, request, pk):
        trade, is_party = self._get_trade_and_verify_party(request, pk)
        if not is_party:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        messages = TradeMessage.objects.filter(
            trade=trade
        ).select_related('sender').order_by('created_at')

        # Mark unread messages as read
        now = timezone.now()
        TradeMessage.objects.filter(
            trade=trade,
            read_at__isnull=True,
        ).exclude(sender=request.user).update(read_at=now)

        return Response(TradeMessageSerializer(messages, many=True).data)

    def post(self, request, pk):
        trade, is_party = self._get_trade_and_verify_party(request, pk)
        if not is_party:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow messaging in active trades
        if trade.status in [Trade.Status.COMPLETED, Trade.Status.AUTO_CLOSED]:
            return Response(
                {'detail': 'Cannot send messages on a completed trade.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TradeMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(trade=trade, sender=request.user)

        return Response(
            TradeMessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )

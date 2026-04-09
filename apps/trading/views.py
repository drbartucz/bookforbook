import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Trade, TradeProposal, TradeShipment
from .serializers import (
    MarkShippedSerializer,
    TradeProposalCreateSerializer,
    TradeProposalSerializer,
    TradeRateSerializer,
    TradeSerializer,
)

logger = logging.getLogger(__name__)


class ProposalListCreateView(APIView):
    """
    GET  /api/v1/proposals/ — user's proposals (sent and received).
    POST /api/v1/proposals/ — create a new trade proposal.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        proposals = TradeProposal.objects.filter(
            Q(proposer=request.user) | Q(recipient=request.user)
        ).select_related('proposer', 'recipient').prefetch_related(
            'items__user_book__book'
        ).order_by('-created_at')
        return Response(TradeProposalSerializer(proposals, many=True).data)

    def post(self, request):
        serializer = TradeProposalCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        proposal = serializer.save()

        # Notify recipient
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=proposal.recipient,
                notification_type='proposal_received',
                title='New trade proposal',
                body=f'{proposal.proposer.username} has sent you a trade proposal.',
                metadata={'proposal_id': str(proposal.pk)},
            )
        except Exception:
            logger.exception('Failed to notify recipient of proposal %s', proposal.pk)

        return Response(
            TradeProposalSerializer(proposal).data,
            status=status.HTTP_201_CREATED,
        )


class ProposalDetailView(APIView):
    """GET /api/v1/proposals/:id/"""
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, pk):
        proposal = get_object_or_404(TradeProposal, pk=pk)
        if proposal.proposer != request.user and proposal.recipient != request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied
        return proposal

    def get(self, request, pk):
        proposal = self.get_object(request, pk)
        return Response(TradeProposalSerializer(proposal).data)


class ProposalAcceptView(APIView):
    """POST /api/v1/proposals/:id/accept/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        proposal = get_object_or_404(
            TradeProposal, pk=pk, recipient=request.user, status=TradeProposal.Status.PENDING
        )

        with transaction.atomic():
            proposal.status = TradeProposal.Status.ACCEPTED
            proposal.save(update_fields=['status'])

            try:
                from apps.trading.services.trade_workflow import create_trade_from_proposal
                trade = create_trade_from_proposal(proposal)
                proposal.status = TradeProposal.Status.COMPLETED
                proposal.save(update_fields=['status'])
                return Response({
                    'detail': 'Proposal accepted.',
                    'trade': TradeSerializer(trade, context={'request': request}).data,
                })
            except Exception:
                logger.exception('Failed to create trade from proposal %s', proposal.pk)
                return Response(
                    {'detail': 'Failed to create trade. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


class ProposalDeclineView(APIView):
    """POST /api/v1/proposals/:id/decline/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        proposal = get_object_or_404(
            TradeProposal, pk=pk, recipient=request.user, status=TradeProposal.Status.PENDING
        )
        proposal.status = TradeProposal.Status.DECLINED
        proposal.save(update_fields=['status'])

        # Notify proposer
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=proposal.proposer,
                notification_type='proposal_declined',
                title='Trade proposal declined',
                body=f'{proposal.recipient.username} has declined your trade proposal.',
                metadata={'proposal_id': str(proposal.pk)},
            )
        except Exception:
            logger.exception('Failed to notify proposer of declined proposal %s', proposal.pk)

        return Response({'detail': 'Proposal declined.'})


class ProposalCounterView(APIView):
    """POST /api/v1/proposals/:id/counter/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        original = get_object_or_404(
            TradeProposal, pk=pk, recipient=request.user,
            status__in=[TradeProposal.Status.PENDING, TradeProposal.Status.COUNTERED],
        )
        # Mark original as countered
        original.status = TradeProposal.Status.COUNTERED
        original.save(update_fields=['status'])

        # Create new counter proposal (swap proposer/recipient)
        counter_data = {
            'recipient_id': str(original.proposer.id),
            'proposer_book_id': request.data.get('proposer_book_id'),
            'recipient_book_id': request.data.get('recipient_book_id'),
            'message': request.data.get('message', ''),
            'origin_match_id': str(original.origin_match_id) if original.origin_match_id else None,
        }
        serializer = TradeProposalCreateSerializer(
            data=counter_data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        counter_proposal = serializer.save()

        return Response(
            TradeProposalSerializer(counter_proposal).data,
            status=status.HTTP_201_CREATED,
        )


class TradeListView(APIView):
    """GET /api/v1/trades/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        # Find trades where user is a sender or receiver in a shipment
        from apps.trading.models import TradeShipment
        trade_ids = TradeShipment.objects.filter(
            sender=user
        ).values_list('trade_id', flat=True).union(
            TradeShipment.objects.filter(
                receiver=user
            ).values_list('trade_id', flat=True)
        )
        trades = Trade.objects.filter(
            id__in=trade_ids
        ).prefetch_related(
            'shipments__sender', 'shipments__receiver', 'shipments__user_book__book'
        ).order_by('-created_at')
        return Response(TradeSerializer(trades, many=True, context={'request': request}).data)


class TradeDetailView(APIView):
    """GET /api/v1/trades/:id/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        trade = get_object_or_404(
            Trade.objects.prefetch_related(
                'shipments__sender', 'shipments__receiver', 'shipments__user_book__book'
            ),
            pk=pk,
        )
        # Verify user is a party
        is_party = trade.shipments.filter(sender=user).exists() or \
                   trade.shipments.filter(receiver=user).exists()
        if not is_party:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(TradeSerializer(trade, context={'request': request}).data)


class TradeMarkShippedView(APIView):
    """POST /api/v1/trades/:id/mark-shipped/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        trade = get_object_or_404(Trade, pk=pk)
        serializer = MarkShippedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Find the sender's shipment
        try:
            shipment = trade.shipments.get(sender=request.user, status=TradeShipment.Status.PENDING)
        except TradeShipment.DoesNotExist:
            return Response(
                {'detail': 'No pending shipment found for you in this trade.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.trading.services.trade_workflow import mark_shipped
        mark_shipped(
            shipment,
            tracking=serializer.validated_data.get('tracking_number', ''),
            method=serializer.validated_data.get('shipping_method', ''),
        )
        return Response(TradeSerializer(trade, context={'request': request}).data)


class TradeMarkReceivedView(APIView):
    """POST /api/v1/trades/:id/mark-received/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        trade = get_object_or_404(Trade, pk=pk)

        # Find the receiver's shipment
        try:
            shipment = trade.shipments.get(
                receiver=request.user,
                status=TradeShipment.Status.SHIPPED,
            )
        except TradeShipment.DoesNotExist:
            return Response(
                {'detail': 'No shipped shipment found for you in this trade.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.trading.services.trade_workflow import mark_received
        mark_received(shipment)
        trade.refresh_from_db()
        return Response(TradeSerializer(trade, context={'request': request}).data)


class TradeRateView(APIView):
    """POST /api/v1/trades/:id/rate/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        trade = get_object_or_404(Trade, pk=pk)

        # Verify user is a party
        is_party = trade.shipments.filter(sender=request.user).exists() or \
                   trade.shipments.filter(receiver=request.user).exists()
        if not is_party:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Trade must be at a ratable status
        if trade.status not in [
            Trade.Status.SHIPPING,
            Trade.Status.ONE_RECEIVED,
            Trade.Status.COMPLETED,
            Trade.Status.AUTO_CLOSED,
        ]:
            return Response(
                {'detail': 'This trade is not in a ratable state.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TradeRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.accounts.models import User
        try:
            rated_user = User.objects.get(pk=serializer.validated_data['rated_user_id'])
        except User.DoesNotExist:
            return Response({'detail': 'Rated user not found.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify rated_user is also a party to this trade
        is_rated_party = trade.shipments.filter(sender=rated_user).exists() or \
                         trade.shipments.filter(receiver=rated_user).exists()
        if not is_rated_party:
            return Response({'detail': 'That user is not part of this trade.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.ratings.models import Rating
        if Rating.objects.filter(trade=trade, rater=request.user).exists():
            return Response({'detail': 'You have already rated this trade.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            rating = Rating.objects.create(
                trade=trade,
                rater=request.user,
                rated=rated_user,
                score=serializer.validated_data['score'],
                comment=serializer.validated_data.get('comment', ''),
                book_condition_accurate=serializer.validated_data['book_condition_accurate'],
            )

            # Recompute rolling average
            try:
                from apps.ratings.services.rolling_average import recompute_rating_average
                recompute_rating_average(rated_user)
            except Exception:
                logger.exception('Failed to recompute rating for user %s', rated_user.pk)

            # Check if both parties have rated → complete
            all_rater_ids = set(
                str(uid) for uid in trade.shipments.values_list('sender_id', flat=True)
            ) | set(
                str(uid) for uid in trade.shipments.values_list('receiver_id', flat=True)
            )
            rated_ids = set(
                str(uid) for uid in Rating.objects.filter(trade=trade).values_list('rater_id', flat=True)
            )
            if rated_ids >= all_rater_ids and trade.status != Trade.Status.COMPLETED:
                trade.status = Trade.Status.COMPLETED
                trade.completed_at = timezone.now()
                trade.save(update_fields=['status', 'completed_at'])

        from apps.ratings.serializers import RatingSerializer
        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)

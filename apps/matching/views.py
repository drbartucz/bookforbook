import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import EmailVerifiedPermission
from apps.accounts.views import user_has_verified_shipping_address
from apps.inventory.models import UserBook, WishlistItem

from .models import Match, MatchLeg
from .serializers import DiscoveryPartnerSerializer, MatchSerializer

logger = logging.getLogger(__name__)


class MatchListView(APIView):
    """GET /api/v1/matches/ — current user's pending/active matches."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        # Find all matches where the user is a sender or receiver in any leg
        match_ids = (
            MatchLeg.objects.filter(
                sender=user,
                match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
            )
            .values_list("match_id", flat=True)
            .union(
                MatchLeg.objects.filter(
                    receiver=user,
                    match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
                ).values_list("match_id", flat=True)
            )
        )
        matches = (
            Match.objects.filter(id__in=match_ids)
            .prefetch_related("legs__sender", "legs__receiver", "legs__user_book__book")
            .order_by("-detected_at")
        )
        return Response(MatchSerializer(matches, many=True).data)


class MatchDetailView(APIView):
    """GET /api/v1/matches/:id/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        try:
            match = Match.objects.prefetch_related(
                "legs__sender", "legs__receiver", "legs__user_book__book"
            ).get(pk=pk)
        except Match.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Verify user is a participant
        is_participant = (
            match.legs.filter(sender=user).exists()
            or match.legs.filter(receiver=user).exists()
        )
        if not is_participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(MatchSerializer(match).data)


class MatchAcceptView(APIView):
    """POST /api/v1/matches/:id/accept/"""

    permission_classes = [permissions.IsAuthenticated, EmailVerifiedPermission]

    def post(self, request, pk):
        user = request.user
        try:
            match = Match.objects.prefetch_related("legs").get(
                pk=pk,
                status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
            )
        except Match.DoesNotExist:
            return Response(
                {"detail": "Match not found or not active."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Find the user's leg (as sender)
        try:
            leg = match.legs.get(sender=user)
        except MatchLeg.DoesNotExist:
            return Response(
                {"detail": "You are not a sender in this match."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user_has_verified_shipping_address(user):
            return Response(
                {
                    "detail": "You need a USPS-verified shipping address before accepting a match.",
                    "code": "address_verification_required",
                },
                status=status.HTTP_409_CONFLICT,
            )

        if leg.status == MatchLeg.Status.ACCEPTED:
            return Response({"detail": "You have already accepted this match."})

        with transaction.atomic():
            leg.status = MatchLeg.Status.ACCEPTED
            leg.save(update_fields=["status"])

            # Use a fresh DB-backed check to avoid stale prefetched leg states.
            if not match.legs.exclude(status=MatchLeg.Status.ACCEPTED).exists():
                match.status = Match.Status.COMPLETED
                match.save(update_fields=["status"])

                # Create the trade
                try:
                    from apps.trading.services.trade_workflow import (
                        create_trade_from_match,
                    )

                    trade = create_trade_from_match(match)
                    logger.info("Trade %s created from match %s", trade.pk, match.pk)
                except Exception:
                    logger.exception("Failed to create trade from match %s", match.pk)

        return Response(MatchSerializer(match).data)


class MatchDeclineView(APIView):
    """POST /api/v1/matches/:id/decline/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        try:
            match = Match.objects.prefetch_related("legs").get(
                pk=pk,
                status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
            )
        except Match.DoesNotExist:
            return Response(
                {"detail": "Match not found or not active."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            leg = match.legs.get(sender=user)
        except MatchLeg.DoesNotExist:
            return Response(
                {"detail": "You are not a sender in this match."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            leg.status = MatchLeg.Status.DECLINED
            leg.save(update_fields=["status"])

            match.status = Match.Status.EXPIRED
            match.save(update_fields=["status"])

            # For ring matches, attempt retry
            if match.match_type == Match.MatchType.RING:

                def _enqueue_ring_retry():
                    try:
                        from django_q.tasks import async_task

                        async_task(
                            "apps.matching.tasks.retry_ring_after_decline_task",
                            str(match.pk),
                            str(user.pk),
                        )
                    except Exception:
                        logger.exception(
                            "Failed to queue ring retry after decline for match %s",
                            match.pk,
                        )

                transaction.on_commit(_enqueue_ring_retry)
            else:
                _notify_match_cancelled(match)

        return Response({"detail": "Match declined."})


def _notify_ring_cancelled(match: Match, declining_user):
    """Notify ring participants that the ring was cancelled and could not be reformed."""
    participant_ids = list(
        match.legs.exclude(sender=declining_user)
        .values_list("sender_id", flat=True)
        .distinct()
    )
    for uid in participant_ids:
        try:
            from apps.notifications.models import Notification
            from apps.accounts.models import User

            participant = User.objects.get(pk=uid)
            Notification.objects.create(
                user=participant,
                notification_type="ring_cancelled",
                title="Exchange ring cancelled",
                body=(
                    f"An exchange ring you were part of could not be completed. "
                    f"Your books are available for new matches."
                ),
            )
        except Exception:
            logger.exception(
                "Failed to notify participant %s of ring cancellation", uid
            )


def _notify_match_cancelled(match: Match):
    """Notify all participants that a match was cancelled."""
    participant_ids = list(match.legs.values_list("sender_id", flat=True).distinct())
    for uid in participant_ids:
        try:
            from apps.notifications.models import Notification
            from apps.accounts.models import User

            participant = User.objects.get(pk=uid)
            Notification.objects.create(
                user=participant,
                notification_type="match_cancelled",
                title="Match cancelled",
                body="A match you were part of was declined.",
            )
        except Exception:
            logger.exception(
                "Failed to notify participant %s of match cancellation", uid
            )


class ReverseDiscoveryView(APIView):
    """
    GET /api/v1/matches/discovery/reverse/
    Find users who want books you have available, but where no direct match exists.
    Returns a list of partners with the books they want from you and the books they offer.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. Get current user's available books
        my_available_books = UserBook.objects.filter(
            user=user, status=UserBook.Status.AVAILABLE
        ).select_related("book")
        if not my_available_books.exists():
            return Response([])

        my_book_ids = list(my_available_books.values_list("book_id", flat=True))

        # 2. Find other users who want these books
        other_wants = (
            WishlistItem.objects.filter(
                book_id__in=my_book_ids, is_active=True, user__is_active=True
            )
            .exclude(user=user)
            .select_related("user")
        )

        # 3. Identify partners with existing active matches to exclude
        active_match_partner_ids = set(
            MatchLeg.objects.filter(
                match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
                sender=user,
            ).values_list("receiver_id", flat=True)
        ) | set(
            MatchLeg.objects.filter(
                match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
                receiver=user,
            ).values_list("sender_id", flat=True)
        )

        # 4. Filter my wishlist to exclude books I already want from "they_offer"
        my_wishlist_book_ids = set(
            WishlistItem.objects.filter(user=user, is_active=True).values_list(
                "book_id", flat=True
            )
        )

        # 5. Group by user and build response
        # Index my available books by book_id for O(1) lookup
        my_books_by_id: dict = {}
        for ub in my_available_books:
            my_books_by_id.setdefault(ub.book_id, []).append(ub)

        partner_map = {}
        for want in other_wants:
            partner = want.user
            if partner.id in active_match_partner_ids:
                continue

            if partner.id not in partner_map:
                partner_map[partner.id] = {
                    "user": partner,
                    "they_want_books": [],
                }

            # O(1) lookup instead of scanning all my available books
            partner_map[partner.id]["they_want_books"].extend(
                my_books_by_id.get(want.book_id, [])
            )

        # 6. Populate "they_offer" for these potential partners
        final_results = []
        for partner_id, data in partner_map.items():
            partner = data["user"]
            # Get their available books, excluding what I already have in my wishlist
            # (If it's in my wishlist, it's a potential direct match or ring leg,
            # which the automatic matcher should handle).
            partner_offers = list(
                UserBook.objects.filter(
                    user=partner,
                    status=UserBook.Status.AVAILABLE,
                )
                .exclude(book_id__in=my_wishlist_book_ids)
                .select_related("book")
                .order_by("-created_at")[:10]  # Limit to 10 for discovery preview
            )

            if partner_offers:
                final_results.append(
                    {
                        "user": partner,
                        "they_want": data["they_want_books"],
                        "they_offer": partner_offers,
                    }
                )

        # Sort by partners who want the most of my books
        final_results.sort(key=lambda x: len(x["they_want"]), reverse=True)

        serializer = DiscoveryPartnerSerializer(final_results, many=True)
        return Response(serializer.data)

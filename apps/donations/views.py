import logging

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView


class _DonationCreateThrottle(UserRateThrottle):
    scope = "donation_create"

from apps.accounts.permissions import EmailVerifiedPermission

from .models import Donation
from .serializers import DonationCreateSerializer, DonationSerializer

logger = logging.getLogger(__name__)


class DonationListCreateView(APIView):
    """
    GET  /api/v1/donations/ — user's donations as donor or recipient.
    POST /api/v1/donations/ — offer a donation/gift.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [_DonationCreateThrottle()]
        return super().get_throttles()

    def get(self, request):
        from django.db.models import Q

        user = request.user
        direction = request.query_params.get("direction", "")

        qs = Donation.objects.select_related("donor", "recipient", "user_book__book")

        if direction == "offered":
            qs = qs.filter(donor=user)
        elif direction == "received":
            qs = qs.filter(recipient=user)
        else:
            qs = qs.filter(Q(donor=user) | Q(recipient=user))

        qs = qs.order_by("-created_at")
        return Response(
            DonationSerializer(qs, many=True, context={"request": request}).data
        )

    def post(self, request):
        serializer = DonationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        donation = serializer.save()

        recipient = donation.recipient
        is_institutional = recipient.is_institutional
        verb = "donate" if is_institutional else "gift"
        display_name = getattr(recipient, 'institution_name', None) or recipient.username

        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=recipient,
                notification_type="donation_offered",
                title="Gift offer received" if not is_institutional else "Donation offer received",
                body=f"{donation.donor.username} would like to {verb} {donation.user_book.book.title} to you.",
                metadata={"donation_id": str(donation.pk)},
            )
        except Exception:
            logger.exception(
                "Failed to notify recipient of donation offer %s", donation.pk
            )

        return Response(
            DonationSerializer(donation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DonationAcceptView(APIView):
    """POST /api/v1/donations/:id/accept/ — recipient accepts a donation/gift."""

    permission_classes = [permissions.IsAuthenticated, EmailVerifiedPermission]

    def post(self, request, pk):
        with transaction.atomic():
            donation = (
                Donation.objects.select_for_update()
                .filter(pk=pk, recipient=request.user, status=Donation.Status.OFFERED)
                .first()
            )
            if not donation:
                raise Http404

            from apps.inventory.models import UserBook

            user_book = (
                UserBook.objects.select_for_update()
                .filter(pk=donation.user_book_id)
                .first()
            )
            if not user_book:
                raise Http404

            donation.status = Donation.Status.ACCEPTED
            donation.save(update_fields=["status"])

            user_book.status = UserBook.Status.RESERVED
            user_book.save(update_fields=["status"])

            from apps.trading.models import Trade, TradeShipment

            trade = Trade.objects.create(
                source_type=Trade.SourceType.DONATION,
                source_id=donation.pk,
                status=Trade.Status.CONFIRMED,
            )
            TradeShipment.objects.create(
                trade=trade,
                sender=donation.donor,
                receiver=donation.recipient,
                user_book=donation.user_book,
            )

            recipient = donation.recipient
            is_institutional = recipient.is_institutional
            display_name = getattr(recipient, 'institution_name', None) or recipient.username
            noun = "donation" if is_institutional else "gift"

            try:
                from apps.notifications.models import Notification

                Notification.objects.create(
                    user=donation.donor,
                    notification_type="donation_accepted",
                    title=f"{noun.capitalize()} accepted!",
                    body=(
                        f"{display_name} has accepted your {noun} of "
                        f"{donation.user_book.book.title}. "
                        f"Shipping address is now available."
                    ),
                    metadata={"donation_id": str(donation.pk)},
                )
            except Exception:
                logger.exception(
                    "Failed to notify donor of donation acceptance %s", donation.pk
                )

        return Response(DonationSerializer(donation, context={"request": request}).data)


class DonationDeclineView(APIView):
    """POST /api/v1/donations/:id/decline/ — recipient declines a donation/gift."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            donation = (
                Donation.objects.select_for_update()
                .filter(pk=pk, recipient=request.user, status=Donation.Status.OFFERED)
                .first()
            )
            if not donation:
                raise Http404

            donation.status = Donation.Status.CANCELLED
            donation.save(update_fields=["status"])

        recipient = donation.recipient
        is_institutional = recipient.is_institutional
        display_name = getattr(recipient, 'institution_name', None) or recipient.username
        noun = "donation" if is_institutional else "gift"

        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=donation.donor,
                notification_type="donation_declined",
                title=f"{noun.capitalize()} declined",
                body=f"{display_name} has declined your {noun} offer.",
                metadata={"donation_id": str(donation.pk)},
            )
        except Exception:
            logger.exception(
                "Failed to notify donor of donation decline %s", donation.pk
            )

        return Response({"detail": "Offer declined."})

import logging

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Donation
from .serializers import DonationCreateSerializer, DonationSerializer

logger = logging.getLogger(__name__)


class DonationListCreateView(APIView):
    """
    GET  /api/v1/donations/ — user's donations as donor or institution.
    POST /api/v1/donations/ — offer a donation.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Q

        user = request.user
        donations = (
            Donation.objects.filter(Q(donor=user) | Q(institution=user))
            .select_related("donor", "institution", "user_book__book")
            .order_by("-created_at")
        )
        return Response(
            DonationSerializer(donations, many=True, context={"request": request}).data
        )

    def post(self, request):
        serializer = DonationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        donation = serializer.save()

        # Notify institution
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=donation.institution,
                notification_type="donation_offered",
                title="Donation offer received",
                body=f"{donation.donor.username} would like to donate {donation.user_book.book.title}.",
                metadata={"donation_id": str(donation.pk)},
            )
        except Exception:
            logger.exception(
                "Failed to notify institution of donation offer %s", donation.pk
            )

        return Response(
            DonationSerializer(donation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DonationAcceptView(APIView):
    """POST /api/v1/donations/:id/accept/ — institution accepts a donation."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            # Lock the donation row for update
            donation = (
                Donation.objects.select_for_update()
                .filter(pk=pk, institution=request.user, status=Donation.Status.OFFERED)
                .first()
            )
            if not donation:
                raise Http404

            # Lock the user_book row for update
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

            # Reserve the book
            user_book.status = UserBook.Status.RESERVED
            user_book.save(update_fields=["status"])

            # Create a Trade record — must succeed for the accept to be valid
            from apps.trading.models import Trade, TradeShipment

            trade = Trade.objects.create(
                source_type=Trade.SourceType.DONATION,
                source_id=donation.pk,
                status=Trade.Status.CONFIRMED,
            )
            TradeShipment.objects.create(
                trade=trade,
                sender=donation.donor,
                receiver=donation.institution,
                user_book=donation.user_book,
            )

            # Notify donor
            try:
                from apps.notifications.models import Notification

                Notification.objects.create(
                    user=donation.donor,
                    notification_type="donation_accepted",
                    title="Donation accepted!",
                    body=(
                        f"{donation.institution.institution_name or donation.institution.username} "
                        f"has accepted your donation of {donation.user_book.book.title}. "
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
    """POST /api/v1/donations/:id/decline/ — institution declines a donation."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        donation = get_object_or_404(
            Donation, pk=pk, institution=request.user, status=Donation.Status.OFFERED
        )
        donation.status = Donation.Status.CANCELLED
        donation.save(update_fields=["status"])

        # Notify donor
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=donation.donor,
                notification_type="donation_declined",
                title="Donation declined",
                body=(
                    f"{donation.institution.institution_name or donation.institution.username} "
                    f"has declined your donation offer."
                ),
                metadata={"donation_id": str(donation.pk)},
            )
        except Exception:
            logger.exception(
                "Failed to notify donor of donation decline %s", donation.pk
            )

        return Response({"detail": "Donation offer declined."})

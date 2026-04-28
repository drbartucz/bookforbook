"""
Tests for donations API.
"""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inventory.models import UserBook
from apps.notifications.models import Notification
from apps.ratings.models import Rating
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory
from apps.donations.models import Donation
from apps.trading.models import Trade, TradeShipment


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(api_client, user):
    resp = api_client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')
    return api_client


def _make_institution():
    inst = UserFactory(
        account_type=User.AccountType.LIBRARY,
        is_verified=True,
        institution_name="City Library",
    )
    return inst


def _offer_donation(client, user_book, institution):
    return client.post(
        reverse("donation-list-create"),
        {"institution_id": str(institution.id), "user_book_id": str(user_book.id)},
        format="json",
    )


# ---------------------------------------------------------------------------
# Offer a donation
# ---------------------------------------------------------------------------


class TestDonationOffer:
    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get(reverse("donation-list-create"))
        assert resp.status_code == 401

    def test_offer_donation_success(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        resp = _offer_donation(client, user_book, institution)

        assert resp.status_code == 201
        assert resp.data["status"] == "offered"
        assert resp.data["donor"]["id"] == str(donor.id)

    def test_offer_to_non_institution_rejected(self, api_client):
        donor = UserFactory()
        regular_user = UserFactory()  # account_type='individual'
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        resp = _offer_donation(client, user_book, regular_user)
        assert resp.status_code == 400

    def test_offer_unavailable_book_rejected(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(
            user=donor, book=BookFactory(), status=UserBook.Status.RESERVED
        )

        client = _auth(api_client, donor)
        resp = _offer_donation(client, user_book, institution)
        assert resp.status_code == 400

    def test_list_own_donations(self, api_client):
        donor = UserFactory()
        inst = _make_institution()
        book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        _offer_donation(client, book, inst)

        resp = client.get(reverse("donation-list-create"))
        assert resp.status_code == 200
        assert len(resp.data) == 1


# ---------------------------------------------------------------------------
# Institution accepts
# ---------------------------------------------------------------------------


class TestDonationAccept:
    def test_institution_accepts_creates_trade(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        # Offer
        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        # Accept
        client = _auth(api_client, institution)
        resp = client.post(
            reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
        )

        assert resp.status_code == 200
        assert resp.data["status"] == "accepted"

        # Trade should have been created
        assert Trade.objects.filter(source_type=Trade.SourceType.DONATION).exists()

        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.RESERVED

    def test_trade_creation_failure_rolls_back_acceptance(self, api_client):
        """If trade creation raises, the whole transaction must roll back (no silent 200)."""
        from unittest.mock import patch

        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        client = _auth(api_client, institution)
        # Allow Django to return 500 instead of re-raising the exception in the test runner
        client.raise_request_exception = False
        with patch(
            "apps.trading.models.Trade.objects.create",
            side_effect=Exception("DB error"),
        ):
            resp = client.post(
                reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
            )

        # Must not silently succeed
        assert resp.status_code == 500

        # Donation status must still be OFFERED (rolled back)
        donation = Donation.objects.get(pk=donation_id)
        assert donation.status == Donation.Status.OFFERED

        # Book must still be AVAILABLE (rolled back)
        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.AVAILABLE

    def test_donor_cannot_accept_own_donation(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        # Donor tries to accept — should 404
        resp = client.post(
            reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
        )
        assert resp.status_code == 404

    def test_institution_address_revealed_after_acceptance(self, api_client):
        donor = UserFactory(
            address_line_1="123 Donor St", city="Portland", state="OR", zip_code="97201"
        )
        institution = _make_institution()
        # Give institution an address
        institution.address_line_1 = "456 Library Ave"
        institution.city = "Seattle"
        institution.state = "WA"
        institution.zip_code = "98101"
        institution.save()

        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        # Accept
        client_inst = _auth(api_client, institution)
        client_inst.post(reverse("donation-accept", kwargs={"pk": donation_id}))

        # Donor should now see institution address
        client_donor = _auth(api_client, donor)
        detail = client_donor.get(reverse("donation-list-create"))
        donation = next(d for d in detail.data if d["id"] == donation_id)
        assert donation["institution_address"] is not None


# ---------------------------------------------------------------------------
# Institution declines
# ---------------------------------------------------------------------------


class TestDonationDecline:
    def test_institution_declines(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        client = _auth(api_client, institution)
        resp = client.post(
            reverse("donation-decline", kwargs={"pk": donation_id}), format="json"
        )

        assert resp.status_code == 200
        donation = Donation.objects.get(pk=donation_id)
        assert donation.status == Donation.Status.CANCELLED

        # Book should remain available
        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.AVAILABLE

    def test_donor_cannot_decline_own_donation(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        offer_resp = _offer_donation(client, user_book, institution)
        donation_id = offer_resp.data["id"]

        resp = client.post(
            reverse("donation-decline", kwargs={"pk": donation_id}), format="json"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Notification side-effects
# ---------------------------------------------------------------------------


class TestDonationNotifications:
    def test_offering_notifies_institution(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        _offer_donation(client, user_book, institution)

        assert Notification.objects.filter(
            user=institution, notification_type="donation_offered"
        ).exists()

    def test_accepting_notifies_donor(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client_donor = _auth(api_client, donor)
        offer_resp = _offer_donation(client_donor, user_book, institution)
        donation_id = offer_resp.data["id"]

        client_inst = _auth(api_client, institution)
        client_inst.post(
            reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
        )

        assert Notification.objects.filter(
            user=donor, notification_type="donation_accepted"
        ).exists()

    def test_declining_notifies_donor(self, api_client):
        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client_donor = _auth(api_client, donor)
        offer_resp = _offer_donation(client_donor, user_book, institution)
        donation_id = offer_resp.data["id"]

        client_inst = _auth(api_client, institution)
        client_inst.post(
            reverse("donation-decline", kwargs={"pk": donation_id}), format="json"
        )

        assert Notification.objects.filter(
            user=donor, notification_type="donation_declined"
        ).exists()


# ---------------------------------------------------------------------------
# Notification exception resilience
# ---------------------------------------------------------------------------


class TestDonationNotificationExceptions:
    """Notification failures must be silenced — the main action must still succeed."""

    def test_offer_notification_exception_still_returns_201(self, api_client):
        """Lines 55-56: exception in notification for donation offer."""
        from unittest.mock import patch

        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client = _auth(api_client, donor)
        with patch(
            "apps.notifications.models.Notification.objects.create",
            side_effect=Exception("notification DB error"),
        ):
            resp = _offer_donation(client, user_book, institution)

        assert resp.status_code == 201
        # The donation itself was created even though the notification failed
        from apps.donations.models import Donation

        assert Donation.objects.filter(donor=donor, institution=institution).exists()

    def test_accept_notification_exception_still_returns_200(self, api_client):
        """Lines 117-118: exception in notification for donation acceptance."""
        from unittest.mock import patch

        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client_donor = _auth(api_client, donor)
        offer_resp = _offer_donation(client_donor, user_book, institution)
        donation_id = offer_resp.data["id"]

        client_inst = _auth(api_client, institution)
        with patch(
            "apps.notifications.models.Notification.objects.create",
            side_effect=Exception("notification DB error"),
        ):
            resp = client_inst.post(
                reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
            )

        assert resp.status_code == 200
        assert resp.data["status"] == "accepted"

    def test_decline_notification_exception_still_returns_200(self, api_client):
        """Lines 151-152: exception in notification for donation decline."""
        from unittest.mock import patch

        donor = UserFactory()
        institution = _make_institution()
        user_book = UserBookFactory(user=donor, book=BookFactory())

        client_donor = _auth(api_client, donor)
        offer_resp = _offer_donation(client_donor, user_book, institution)
        donation_id = offer_resp.data["id"]

        client_inst = _auth(api_client, institution)
        with patch(
            "apps.notifications.models.Notification.objects.create",
            side_effect=Exception("notification DB error"),
        ):
            resp = client_inst.post(
                reverse("donation-decline", kwargs={"pk": donation_id}), format="json"
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Donation trade lifecycle (shipping / receipt / rating after acceptance)
# ---------------------------------------------------------------------------


def _setup_accepted_donation(api_client):
    """Return (client_donor, client_inst, trade, donation, donor, institution, user_book)."""
    from rest_framework.test import APIClient

    donor = UserFactory()
    institution = _make_institution()
    institution.full_name = "City Library"
    institution.address_line_1 = "1 Library Plaza"
    institution.city = "Portland"
    institution.state = "OR"
    institution.zip_code = "97201"
    institution.address_verification_status = User.AddressVerificationStatus.VERIFIED
    institution.save()

    user_book = UserBookFactory(user=donor, book=BookFactory())

    client_donor = APIClient()
    client_donor.force_authenticate(user=donor)
    client_inst = APIClient()
    client_inst.force_authenticate(user=institution)

    offer_resp = client_donor.post(
        reverse("donation-list-create"),
        {"institution_id": str(institution.id), "user_book_id": str(user_book.id)},
        format="json",
    )
    donation_id = offer_resp.data["id"]

    client_inst.post(
        reverse("donation-accept", kwargs={"pk": donation_id}), format="json"
    )

    trade = Trade.objects.get(source_type=Trade.SourceType.DONATION)
    donation = Donation.objects.get(pk=donation_id)
    return client_donor, client_inst, trade, donation, donor, institution, user_book


class TestDonationTradePipeline:
    """Post-acceptance lifecycle: shipping, receipt, and rating for donation-sourced trades."""

    def test_donor_can_mark_book_shipped(self, api_client):
        """Donor (the sender) can mark the single donation shipment as shipped."""
        client_donor, _client_inst, trade, _donation, _donor, _inst, _book = (
            _setup_accepted_donation(api_client)
        )

        resp = client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-001", "shipping_method": "USPS"},
            format="json",
        )

        assert resp.status_code == 200
        trade.refresh_from_db()
        assert trade.status == Trade.Status.SHIPPING

        shipment = trade.shipments.get()
        assert shipment.status == TradeShipment.Status.SHIPPED

    def test_institution_can_mark_book_received_completes_trade(self, api_client):
        """Institution (receiver) marks received → trade COMPLETED, book TRADED."""
        client_donor, client_inst, trade, _donation, _donor, _inst, user_book = (
            _setup_accepted_donation(api_client)
        )

        client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-002"},
            format="json",
        )

        resp = client_inst.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )

        assert resp.status_code == 200
        trade.refresh_from_db()
        # Single-shipment donation: all received → COMPLETED immediately
        assert trade.status == Trade.Status.COMPLETED

        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.TRADED

    def test_donor_total_trades_incremented_on_completion(self, api_client):
        """donor.total_trades increments when the donation trade completes."""
        client_donor, client_inst, trade, _donation, donor, _inst, _book = (
            _setup_accepted_donation(api_client)
        )

        client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-003"},
            format="json",
        )
        client_inst.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )

        donor.refresh_from_db()
        assert donor.total_trades == 1

    def test_donor_can_rate_institution_after_completion(self, api_client):
        """Donor can submit a rating for the institution once the trade is completed."""
        client_donor, client_inst, trade, _donation, _donor, institution, _book = (
            _setup_accepted_donation(api_client)
        )

        client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-004"},
            format="json",
        )
        client_inst.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )

        resp = client_donor.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(institution.id),
                "score": 5,
                "comment": "Great library!",
                "book_condition_accurate": True,
            },
            format="json",
        )

        assert resp.status_code == 201
        assert Rating.objects.filter(trade=trade, rated=institution).count() == 1
        institution.refresh_from_db()
        assert institution.avg_recent_rating is not None

    def test_institution_can_rate_donor_after_completion(self, api_client):
        """Institution can submit a rating for the donor once the trade is completed."""
        client_donor, client_inst, trade, _donation, donor, _inst, _book = (
            _setup_accepted_donation(api_client)
        )

        client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-005"},
            format="json",
        )
        client_inst.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )

        resp = client_inst.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(donor.id),
                "score": 4,
                "comment": "Nice donation, thank you!",
                "book_condition_accurate": True,
            },
            format="json",
        )

        assert resp.status_code == 201
        assert Rating.objects.filter(trade=trade, rated=donor).count() == 1

    def test_full_donation_pipeline_offer_to_mutual_ratings(self, api_client):
        """End-to-end: offer → accept → ship → receive → both parties rate."""
        client_donor, client_inst, trade, donation, donor, institution, user_book = (
            _setup_accepted_donation(api_client)
        )

        assert donation.status == Donation.Status.ACCEPTED
        assert trade.status == Trade.Status.CONFIRMED

        resp = client_donor.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "USPS-DON-E2E"},
            format="json",
        )
        assert resp.status_code == 200

        resp = client_inst.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 200

        trade.refresh_from_db()
        assert trade.status == Trade.Status.COMPLETED

        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.TRADED

        resp = client_donor.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(institution.id),
                "score": 5,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp.status_code == 201

        resp = client_inst.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(donor.id),
                "score": 5,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp.status_code == 201

        assert Rating.objects.filter(trade=trade).count() == 2
        donor.refresh_from_db()
        institution.refresh_from_db()
        assert donor.rating_count == 1
        assert institution.rating_count == 1

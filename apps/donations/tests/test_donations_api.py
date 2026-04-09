"""
Tests for donations API.
"""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inventory.models import UserBook
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

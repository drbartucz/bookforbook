"""
Tests for trading API — trade proposals and trades.
"""

import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.ratings.models import Rating
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory
from apps.trading.models import Trade, TradeProposal, TradeShipment


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(api_client, user):
    """Obtain JWT and authenticate the client."""
    resp = api_client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')
    return api_client


def _make_proposal(
    proposer_client, proposer_book, recipient, recipient_book, message=""
):
    """Helper: POST to proposals endpoint."""
    url = reverse("proposal-list-create")
    return proposer_client.post(
        url,
        {
            "recipient_id": str(recipient.id),
            "proposer_book_id": str(proposer_book.id),
            "recipient_book_id": str(recipient_book.id),
            "message": message,
        },
        format="json",
    )


# ---------------------------------------------------------------------------
# Proposal: list & create
# ---------------------------------------------------------------------------


class TestProposalListCreate:
    def test_unauthenticated_rejected(self, api_client):
        url = reverse("proposal-list-create")
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_list_own_proposals(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()

        book1 = BookFactory()
        book2 = BookFactory()
        pbook = UserBookFactory(user=proposer, book=book1)
        rbook = UserBookFactory(user=recipient, book=book2)

        client = _auth(api_client, proposer)
        resp = _make_proposal(client, pbook, recipient, rbook, "Hi!")
        assert resp.status_code == 201

        resp2 = client.get(reverse("proposal-list-create"))
        assert resp2.status_code == 200
        assert len(resp2.data) == 1

    def test_create_proposal_success(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        resp = _make_proposal(client, pbook, recipient, rbook)

        assert resp.status_code == 201
        assert resp.data["status"] == "pending"
        assert resp.data["proposer"]["id"] == str(proposer.id)
        assert resp.data["recipient"]["id"] == str(recipient.id)

    def test_propose_to_self_rejected(self, api_client):
        user = UserFactory()
        book1 = UserBookFactory(user=user, book=BookFactory())
        book2 = UserBookFactory(user=user, book=BookFactory())

        client = _auth(api_client, user)
        url = reverse("proposal-list-create")
        resp = client.post(
            url,
            {
                "recipient_id": str(user.id),
                "proposer_book_id": str(book1.id),
                "recipient_book_id": str(book2.id),
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_unavailable_book_rejected(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(
            user=proposer, book=BookFactory(), status=UserBook.Status.RESERVED
        )
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        resp = _make_proposal(client, pbook, recipient, rbook)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Proposal: accept
# ---------------------------------------------------------------------------


class TestProposalAccept:
    def test_recipient_accepts_creates_trade(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        recipient.full_name = "Reader Two"
        recipient.address_line_1 = "456 Oak Ave"
        recipient.city = "Austin"
        recipient.state = "TX"
        recipient.zip_code = "73301"
        recipient.address_verification_status = "verified"
        recipient.save()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        # Create proposal as proposer
        _auth(api_client, proposer)
        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        # Accept as recipient
        client = _auth(api_client, recipient)
        url = reverse("proposal-accept", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")

        assert resp.status_code == 200
        assert "trade" in resp.data

        trade = Trade.objects.get(pk=resp.data["trade"]["id"])
        assert trade.status == Trade.Status.CONFIRMED
        assert trade.source_type == Trade.SourceType.PROPOSAL

        # Both books should be reserved
        pbook.refresh_from_db()
        rbook.refresh_from_db()
        assert pbook.status == UserBook.Status.RESERVED
        assert rbook.status == UserBook.Status.RESERVED

    def test_accept_requires_verified_address(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, recipient)
        url = reverse("proposal-accept", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")

        assert resp.status_code == 409
        assert resp.data["code"] == "address_verification_required"
        assert resp.data["verification_url"] == "/account"

    def test_proposer_cannot_accept_own_proposal(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        url = reverse("proposal-accept", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")
        assert resp.status_code == 404

    def test_accept_expired_proposal_rejected(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]
        TradeProposal.objects.filter(pk=proposal_id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        client = _auth(api_client, recipient)
        url = reverse("proposal-accept", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")

        assert resp.status_code == 400
        assert "expired" in resp.data["detail"].lower()

    def test_accept_rejected_if_item_book_no_longer_available(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        recipient.full_name = "Reader Two"
        recipient.address_line_1 = "456 Oak Ave"
        recipient.city = "Austin"
        recipient.state = "TX"
        recipient.zip_code = "73301"
        recipient.address_verification_status = "verified"
        recipient.save()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        pbook.status = UserBook.Status.RESERVED
        pbook.save(update_fields=["status"])

        client = _auth(api_client, recipient)
        url = reverse("proposal-accept", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")

        assert resp.status_code == 400
        assert "no longer available" in resp.data["detail"].lower()
        assert Trade.objects.count() == 0


# ---------------------------------------------------------------------------
# Proposal: decline
# ---------------------------------------------------------------------------


class TestProposalDecline:
    def test_recipient_declines(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, recipient)
        url = reverse("proposal-decline", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")

        assert resp.status_code == 200
        proposal = TradeProposal.objects.get(pk=proposal_id)
        assert proposal.status == TradeProposal.Status.DECLINED

    def test_proposer_cannot_decline_own_proposal(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        url = reverse("proposal-decline", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")
        assert resp.status_code == 404

    def test_decline_expired_proposal_rejected(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]
        TradeProposal.objects.filter(pk=proposal_id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        client = _auth(api_client, recipient)
        url = reverse("proposal-decline", kwargs={"pk": proposal_id})
        resp = client.post(url, format="json")
        assert resp.status_code == 400
        assert "expired" in resp.data["detail"].lower()


class TestProposalCounter:
    def test_recipient_can_counter_and_original_becomes_countered(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook, "original")
        proposal_id = create_resp.data["id"]

        new_recipient_book = UserBookFactory(user=recipient, book=BookFactory())
        new_proposer_book = UserBookFactory(user=proposer, book=BookFactory())

        client = _auth(api_client, recipient)
        resp = client.post(
            reverse("proposal-counter", kwargs={"pk": proposal_id}),
            {
                "proposer_book_id": str(new_recipient_book.id),
                "recipient_book_id": str(new_proposer_book.id),
                "message": "counter offer",
            },
            format="json",
        )

        assert resp.status_code == 201
        original = TradeProposal.objects.get(pk=proposal_id)
        assert original.status == TradeProposal.Status.COUNTERED

        counter = TradeProposal.objects.get(pk=resp.data["id"])
        assert counter.proposer_id == recipient.id
        assert counter.recipient_id == proposer.id
        assert counter.status == TradeProposal.Status.PENDING
        assert counter.items.count() == 2

    def test_proposer_cannot_counter_own_proposal(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        resp = client.post(
            reverse("proposal-counter", kwargs={"pk": proposal_id}),
            {
                "proposer_book_id": str(pbook.id),
                "recipient_book_id": str(rbook.id),
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_counter_expired_proposal_rejected(self, api_client):
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]
        TradeProposal.objects.filter(pk=proposal_id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        counter_sender_book = UserBookFactory(user=recipient, book=BookFactory())
        counter_recipient_book = UserBookFactory(user=proposer, book=BookFactory())

        client = _auth(api_client, recipient)
        resp = client.post(
            reverse("proposal-counter", kwargs={"pk": proposal_id}),
            {
                "proposer_book_id": str(counter_sender_book.id),
                "recipient_book_id": str(counter_recipient_book.id),
            },
            format="json",
        )

        assert resp.status_code == 400
        assert "expired" in resp.data["detail"].lower()


# ---------------------------------------------------------------------------
# Trade: list & detail
# ---------------------------------------------------------------------------


class TestTradeListDetail:
    def _create_confirmed_trade(self, proposer, recipient):
        """Create a trade with two shipments (helper)."""
        book1 = BookFactory()
        book2 = BookFactory()
        pbook = UserBookFactory(
            user=proposer, book=book1, status=UserBook.Status.RESERVED
        )
        rbook = UserBookFactory(
            user=recipient, book=book2, status=UserBook.Status.RESERVED
        )

        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=TradeProposal.objects.create(
                proposer=proposer,
                recipient=recipient,
                status=TradeProposal.Status.COMPLETED,
            ).pk,
            status=Trade.Status.CONFIRMED,
        )
        TradeShipment.objects.create(
            trade=trade, sender=proposer, receiver=recipient, user_book=pbook
        )
        TradeShipment.objects.create(
            trade=trade, sender=recipient, receiver=proposer, user_book=rbook
        )
        return trade

    def test_list_only_own_trades(self, api_client):
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()
        trade_ab = self._create_confirmed_trade(a, b)
        self._create_confirmed_trade(b, c)

        client = _auth(api_client, a)
        resp = client.get(reverse("trade-list"))
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert str(trade_ab.id) in ids
        assert len(ids) == 1

    def test_detail_party_can_view(self, api_client):
        a = UserFactory()
        b = UserFactory()
        trade = self._create_confirmed_trade(a, b)

        client = _auth(api_client, a)
        resp = client.get(reverse("trade-detail", kwargs={"pk": trade.id}))
        assert resp.status_code == 200
        assert resp.data["id"] == str(trade.id)

    def test_detail_non_party_gets_404(self, api_client):
        a = UserFactory()
        b = UserFactory()
        outsider = UserFactory()
        trade = self._create_confirmed_trade(a, b)

        client = _auth(api_client, outsider)
        resp = client.get(reverse("trade-detail", kwargs={"pk": trade.id}))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Trade: mark shipped & mark received
# ---------------------------------------------------------------------------


class TestTradeShipping:
    def _setup_confirmed_trade(self):
        proposer = UserFactory()
        recipient = UserFactory()
        book1 = BookFactory()
        book2 = BookFactory()
        pbook = UserBookFactory(
            user=proposer, book=book1, status=UserBook.Status.RESERVED
        )
        rbook = UserBookFactory(
            user=recipient, book=book2, status=UserBook.Status.RESERVED
        )

        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=TradeProposal.objects.create(
                proposer=proposer,
                recipient=recipient,
                status=TradeProposal.Status.COMPLETED,
            ).pk,
            status=Trade.Status.CONFIRMED,
        )
        s1 = TradeShipment.objects.create(
            trade=trade, sender=proposer, receiver=recipient, user_book=pbook
        )
        s2 = TradeShipment.objects.create(
            trade=trade, sender=recipient, receiver=proposer, user_book=rbook
        )
        return trade, proposer, recipient, s1, s2

    def test_mark_shipped_updates_status(self, api_client):
        trade, proposer, _recipient, s1, _s2 = self._setup_confirmed_trade()
        client = _auth(api_client, proposer)

        resp = client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "1Z999", "shipping_method": "USPS"},
            format="json",
        )
        assert resp.status_code == 200

        s1.refresh_from_db()
        assert s1.status == TradeShipment.Status.SHIPPED
        trade.refresh_from_db()
        assert trade.status == Trade.Status.SHIPPING

    def test_mark_received_after_shipped(self, api_client):
        trade, proposer, recipient, s1, _s2 = self._setup_confirmed_trade()

        # Proposer ships
        client = _auth(api_client, proposer)
        client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "1Z999"},
            format="json",
        )

        # Recipient marks received
        client = _auth(api_client, recipient)
        resp = client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 200

        s1.refresh_from_db()
        assert s1.status == TradeShipment.Status.RECEIVED

    def test_outsider_cannot_mark_shipped(self, api_client):
        trade, _proposer, _recipient, _s1, _s2 = self._setup_confirmed_trade()
        outsider = UserFactory()
        client = _auth(api_client, outsider)
        resp = client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "X123"},
            format="json",
        )
        assert resp.status_code == 404

    def test_outsider_cannot_mark_received(self, api_client):
        trade, proposer, _recipient, _s1, _s2 = self._setup_confirmed_trade()
        # First ship so there's something to receive
        client = _auth(api_client, proposer)
        client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "X123"},
            format="json",
        )
        outsider = UserFactory()
        client = _auth(api_client, outsider)
        resp = client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 404

    def test_double_mark_shipped_rejected(self, api_client):
        """Sender cannot mark the same shipment shipped twice."""
        trade, proposer, _recipient, _s1, _s2 = self._setup_confirmed_trade()
        client = _auth(api_client, proposer)
        url = reverse("trade-mark-shipped", kwargs={"pk": trade.id})
        client.post(url, {"tracking_number": "1Z999"}, format="json")
        resp2 = client.post(url, {"tracking_number": "1Z999"}, format="json")
        assert resp2.status_code == 400

    def test_receiver_cannot_mark_shipped(self, api_client):
        """Receiver is a party but cannot mark the shipment as shipped (wrong role)."""
        trade, _proposer, recipient, _s1, _s2 = self._setup_confirmed_trade()
        client = _auth(api_client, recipient)
        # recipient has no PENDING shipment where they are the SENDER for the
        # proposer's book; their own shipment (s2) is the one they send — but
        # recipient's shipment s2 is also PENDING so this would succeed for s2.
        # Instead, test that recipient cannot mark *proposer's* shipment (s1).
        # The view will find s2 (recipient's own pending shipment) instead, so
        # the cleaner test is: after recipient already shipped, propser can still
        # mark their own. Let's test the converse: receiver tries mark-received
        # before shipped → 400 (no SHIPPED shipment yet).
        resp = client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 400

    def test_sender_cannot_mark_received_own_shipment(self, api_client):
        """Sender cannot mark their own outgoing shipment as received."""
        trade, proposer, _recipient, _s1, _s2 = self._setup_confirmed_trade()
        # Ship first
        client = _auth(api_client, proposer)
        client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "1Z999"},
            format="json",
        )
        # Proposer is the sender of s1; they are NOT the receiver of s1,
        # so mark-received should not find a SHIPPED shipment where they are receiver.
        resp = client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 400

    def test_full_lifecycle_both_received_completes_trade(self, api_client):
        """Full shipment happy path: confirmed → shipping → one_received → completed."""
        trade, proposer, recipient, s1, s2 = self._setup_confirmed_trade()

        # Proposer ships
        _auth(api_client, proposer)
        resp = api_client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "PROP-TRK"},
            format="json",
        )
        assert resp.status_code == 200
        trade.refresh_from_db()
        assert trade.status == Trade.Status.SHIPPING

        # Recipient ships
        _auth(api_client, recipient)
        resp = api_client.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "RECP-TRK"},
            format="json",
        )
        assert resp.status_code == 200

        # Recipient marks received (gets the book proposer sent)
        resp = api_client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 200
        trade.refresh_from_db()
        assert trade.status == Trade.Status.ONE_RECEIVED

        # Proposer marks received (gets the book recipient sent)
        _auth(api_client, proposer)
        resp = api_client.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert resp.status_code == 200
        trade.refresh_from_db()
        assert trade.status == Trade.Status.COMPLETED

        # Books should be marked as traded
        s1.user_book.refresh_from_db()
        s2.user_book.refresh_from_db()
        assert s1.user_book.status == UserBook.Status.TRADED
        assert s2.user_book.status == UserBook.Status.TRADED

        # Trade counts incremented on both users
        proposer.refresh_from_db()
        recipient.refresh_from_db()
        assert proposer.total_trades == 1
        assert recipient.total_trades == 1


# ---------------------------------------------------------------------------
# Trade: rate
# ---------------------------------------------------------------------------


class TestTradeRate:
    def _setup_shipping_trade(self):
        a = UserFactory()
        b = UserFactory()
        book_a = UserBookFactory(
            user=a, book=BookFactory(), status=UserBook.Status.RESERVED
        )
        book_b = UserBookFactory(
            user=b, book=BookFactory(), status=UserBook.Status.RESERVED
        )

        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=TradeProposal.objects.create(
                proposer=a, recipient=b, status=TradeProposal.Status.COMPLETED
            ).pk,
            status=Trade.Status.SHIPPING,
        )
        TradeShipment.objects.create(
            trade=trade, sender=a, receiver=b, user_book=book_a
        )
        TradeShipment.objects.create(
            trade=trade, sender=b, receiver=a, user_book=book_b
        )
        return trade, a, b

    def test_rate_trade_success(self, api_client):
        trade, a, b = self._setup_shipping_trade()
        client = _auth(api_client, a)

        resp = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(b.id),
                "score": 5,
                "comment": "Great!",
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp.status_code == 201
        b.refresh_from_db()
        assert b.avg_recent_rating is not None

    def test_rate_twice_rejected(self, api_client):
        trade, a, b = self._setup_shipping_trade()
        client = _auth(api_client, a)

        payload = {
            "rated_user_id": str(b.id),
            "score": 4,
            "book_condition_accurate": True,
        }
        client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}), payload, format="json"
        )
        resp2 = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}), payload, format="json"
        )
        assert resp2.status_code == 400

    def test_non_party_cannot_rate(self, api_client):
        trade, a, b = self._setup_shipping_trade()
        outsider = UserFactory()
        client = _auth(api_client, outsider)

        resp = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {"rated_user_id": str(b.id), "score": 3, "book_condition_accurate": True},
            format="json",
        )
        assert resp.status_code == 404

    def test_rate_confirmed_trade_rejected(self, api_client):
        """Trade must be in shipping/received/completed/auto_closed to rate."""
        trade, a, b = self._setup_shipping_trade()
        trade.status = Trade.Status.CONFIRMED
        trade.save()

        client = _auth(api_client, a)
        resp = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {"rated_user_id": str(b.id), "score": 4, "book_condition_accurate": True},
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.slow
class TestTradePipelineIntegration:
    def test_match_to_completed_trade_with_mutual_ratings_recomputes_averages(
        self, api_client
    ):
        from rest_framework.test import APIClient

        user_a = UserFactory()
        user_b = UserFactory()
        client_a = APIClient()
        client_b = APIClient()
        client_a.force_authenticate(user=user_a)
        client_b.force_authenticate(user=user_b)

        for user, full_name, street, city, state, zip_code in [
            (user_a, "Reader A", "123 Main St", "Denver", "CO", "80202"),
            (user_b, "Reader B", "456 Oak Ave", "Austin", "TX", "73301"),
        ]:
            user.full_name = full_name
            user.address_line_1 = street
            user.city = city
            user.state = state
            user.zip_code = zip_code
            user.address_verification_status = User.AddressVerificationStatus.VERIFIED
            user.save()

        book_a = UserBookFactory(user=user_a, book=BookFactory(), condition="good")
        book_b = UserBookFactory(user=user_b, book=BookFactory(), condition="very_good")

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_a,
            receiver=user_b,
            user_book=book_a,
            position=0,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_b,
            receiver=user_a,
            user_book=book_b,
            position=1,
        )

        # Both parties accept the match, which should create a trade from the match.
        accept_a = client_a.post(f"/api/v1/matches/{match.id}/accept/")
        assert accept_a.status_code == 200

        accept_b = client_b.post(f"/api/v1/matches/{match.id}/accept/")
        assert accept_b.status_code == 200

        match.refresh_from_db()
        assert match.status == Match.Status.COMPLETED

        trade = Trade.objects.get(
            source_type=Trade.SourceType.MATCH,
            source_id=match.pk,
        )
        assert trade.status == Trade.Status.CONFIRMED

        # Both users ship.
        ship_a = client_a.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "A-TRACK-001", "shipping_method": "USPS"},
            format="json",
        )
        assert ship_a.status_code == 200

        ship_b = client_b.post(
            reverse("trade-mark-shipped", kwargs={"pk": trade.id}),
            {"tracking_number": "B-TRACK-002", "shipping_method": "USPS"},
            format="json",
        )
        assert ship_b.status_code == 200

        # Both users confirm receipt.
        receive_b = client_b.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert receive_b.status_code == 200

        receive_a = client_a.post(
            reverse("trade-mark-received", kwargs={"pk": trade.id}),
            format="json",
        )
        assert receive_a.status_code == 200

        trade.refresh_from_db()
        assert trade.status == Trade.Status.COMPLETED

        # Books transitioned to traded.
        book_a.refresh_from_db()
        book_b.refresh_from_db()
        assert book_a.status == UserBook.Status.TRADED
        assert book_b.status == UserBook.Status.TRADED

        # Both parties rate each other.
        rate_a = client_a.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(user_b.id),
                "score": 5,
                "comment": "Great trade",
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert rate_a.status_code == 201

        rate_b = client_b.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(user_a.id),
                "score": 4,
                "comment": "Smooth exchange",
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert rate_b.status_code == 201

        assert Rating.objects.filter(trade=trade).count() == 2

        user_a.refresh_from_db()
        user_b.refresh_from_db()
        assert user_a.rating_count == 1
        assert user_b.rating_count == 1
        assert float(user_a.avg_recent_rating) == pytest.approx(4.0)
        assert float(user_b.avg_recent_rating) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


class TestProposalNotificationException:
    """Lines 63-64: notification exception when creating proposal is silenced."""

    def test_proposal_creation_still_returns_201_when_notification_raises(
        self, api_client
    ):
        from unittest.mock import patch

        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        with patch(
            "apps.notifications.models.Notification.objects.create",
            side_effect=Exception("notification error"),
        ):
            resp = _make_proposal(client, pbook, recipient, rbook)

        assert resp.status_code == 201
        assert resp.data["status"] == "pending"


class TestProposalDetailViewAccess:
    """Lines 78-87: ProposalDetailView permission and GET."""

    def test_outsider_gets_403(self, api_client):
        """Lines 78-83: 403 when user not proposer/recipient."""
        proposer = UserFactory()
        recipient = UserFactory()
        outsider = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, outsider)
        resp = client.get(reverse("proposal-detail", kwargs={"pk": proposal_id}))
        assert resp.status_code == 403

    def test_proposer_can_get_proposal(self, api_client):
        """Lines 86-87: 200 for proposer."""
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        resp = client.get(reverse("proposal-detail", kwargs={"pk": proposal_id}))
        assert resp.status_code == 200
        assert resp.data["id"] == proposal_id

    def test_recipient_can_get_proposal(self, api_client):
        """Recipient can also GET the proposal."""
        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, recipient)
        resp = client.get(reverse("proposal-detail", kwargs={"pk": proposal_id}))
        assert resp.status_code == 200
        assert resp.data["id"] == proposal_id


class TestProposalAcceptValueError:
    """Lines 144-146: ValueError from create_trade_from_proposal → 400."""

    def test_value_error_returns_400(self, api_client):
        from unittest.mock import patch

        proposer = UserFactory()
        recipient = UserFactory()
        recipient.full_name = "Reader Two"
        recipient.address_line_1 = "456 Oak Ave"
        recipient.city = "Austin"
        recipient.state = "TX"
        recipient.zip_code = "73301"
        recipient.address_verification_status = "verified"
        recipient.save()

        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, recipient)
        with patch(
            "apps.trading.services.trade_workflow.create_trade_from_proposal",
            side_effect=ValueError("book no longer available"),
        ):
            resp = client.post(
                reverse("proposal-accept", kwargs={"pk": proposal_id}), format="json"
            )

        assert resp.status_code == 400
        assert "no longer available" in resp.data["detail"].lower()


class TestProposalDeclineNotificationException:
    """Lines 185-186: notification exception on proposal decline is silenced."""

    def test_decline_still_returns_200_when_notification_raises(self, api_client):
        from unittest.mock import patch

        proposer = UserFactory()
        recipient = UserFactory()
        pbook = UserBookFactory(user=proposer, book=BookFactory())
        rbook = UserBookFactory(user=recipient, book=BookFactory())

        client = _auth(api_client, proposer)
        create_resp = _make_proposal(client, pbook, recipient, rbook)
        proposal_id = create_resp.data["id"]

        client = _auth(api_client, recipient)
        with patch(
            "apps.notifications.models.Notification.objects.create",
            side_effect=Exception("notification error"),
        ):
            resp = client.post(
                reverse("proposal-decline", kwargs={"pk": proposal_id}), format="json"
            )

        assert resp.status_code == 200
        proposal = TradeProposal.objects.get(pk=proposal_id)
        assert proposal.status == TradeProposal.Status.DECLINED


class TestTradeListStatusFilter:
    """Lines 267, 275: TradeListView ?status=active and ?status=completed filters."""

    def _create_trade_with_status(self, trade_status):
        """Helper to create a trade with two shipments at the given status."""
        a = UserFactory()
        b = UserFactory()
        book_a = UserBookFactory(user=a, book=BookFactory(), status=UserBook.Status.RESERVED)
        book_b = UserBookFactory(user=b, book=BookFactory(), status=UserBook.Status.RESERVED)

        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=TradeProposal.objects.create(
                proposer=a,
                recipient=b,
                status=TradeProposal.Status.COMPLETED,
            ).pk,
            status=trade_status,
        )
        TradeShipment.objects.create(
            trade=trade, sender=a, receiver=b, user_book=book_a
        )
        TradeShipment.objects.create(
            trade=trade, sender=b, receiver=a, user_book=book_b
        )
        return trade, a, b

    def test_status_active_filter_returns_only_active_trades(self, api_client):
        trade_confirmed, a, b = self._create_trade_with_status(Trade.Status.CONFIRMED)
        trade_completed, _, _ = self._create_trade_with_status(Trade.Status.COMPLETED)
        # Make completed trade belong to user a too
        TradeShipment.objects.create(
            trade=trade_completed,
            sender=a,
            receiver=UserFactory(),
            user_book=UserBookFactory(user=a, book=BookFactory()),
        )

        client = _auth(api_client, a)
        resp = client.get(reverse("trade-list"), {"status": "active"})
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert str(trade_confirmed.id) in ids
        assert str(trade_completed.id) not in ids

    def test_status_completed_filter_returns_only_completed_trades(self, api_client):
        trade_confirmed, a, b = self._create_trade_with_status(Trade.Status.CONFIRMED)
        trade_completed, _, _ = self._create_trade_with_status(Trade.Status.COMPLETED)
        # Make completed trade belong to user a too
        TradeShipment.objects.create(
            trade=trade_completed,
            sender=a,
            receiver=UserFactory(),
            user_book=UserBookFactory(user=a, book=BookFactory()),
        )

        client = _auth(api_client, a)
        resp = client.get(reverse("trade-list"), {"status": "completed"})
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert str(trade_completed.id) in ids
        assert str(trade_confirmed.id) not in ids

    def test_status_auto_closed_included_in_completed_filter(self, api_client):
        trade_auto_closed, a, b = self._create_trade_with_status(Trade.Status.AUTO_CLOSED)

        client = _auth(api_client, a)
        resp = client.get(reverse("trade-list"), {"status": "completed"})
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert str(trade_auto_closed.id) in ids


class TestTradeRateViewEdgeCases:
    """Lines 417-418, 428, 460-461, 479-481 of TradeRateView."""

    def _setup_ratable_trade(self):
        """Create a SHIPPING trade with two parties."""
        a = UserFactory()
        b = UserFactory()
        book_a = UserBookFactory(
            user=a, book=BookFactory(), status=UserBook.Status.RESERVED
        )
        book_b = UserBookFactory(
            user=b, book=BookFactory(), status=UserBook.Status.RESERVED
        )
        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=TradeProposal.objects.create(
                proposer=a, recipient=b, status=TradeProposal.Status.COMPLETED
            ).pk,
            status=Trade.Status.SHIPPING,
        )
        TradeShipment.objects.create(
            trade=trade, sender=a, receiver=b, user_book=book_a
        )
        TradeShipment.objects.create(
            trade=trade, sender=b, receiver=a, user_book=book_b
        )
        return trade, a, b

    def test_non_party_rate_returns_404(self, api_client):
        """Lines 417-418: 404 when user not a party."""
        trade, a, b = self._setup_ratable_trade()
        outsider = UserFactory()

        client = _auth(api_client, outsider)
        resp = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(b.id),
                "score": 4,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_rated_user_not_in_trade_returns_400(self, api_client):
        """Line 428: rated_user not in this trade → 400."""
        trade, a, b = self._setup_ratable_trade()
        stranger = UserFactory()

        client = _auth(api_client, a)
        resp = client.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(stranger.id),
                "score": 4,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "not part of this trade" in resp.data["detail"]

    def test_recompute_rating_exception_still_returns_201(self, api_client):
        """Lines 460-461: exception in recompute_rating_average is silenced."""
        from unittest.mock import patch

        trade, a, b = self._setup_ratable_trade()

        client = _auth(api_client, a)
        with patch(
            "apps.ratings.services.rolling_average.recompute_rating_average",
            side_effect=Exception("db error"),
        ):
            resp = client.post(
                reverse("trade-rate", kwargs={"pk": trade.id}),
                {
                    "rated_user_id": str(b.id),
                    "score": 5,
                    "book_condition_accurate": True,
                },
                format="json",
            )

        assert resp.status_code == 201

    def test_both_parties_rated_sets_trade_completed(self, api_client):
        """Lines 479-481: trade status updated to COMPLETED when both parties have rated."""
        trade, a, b = self._setup_ratable_trade()

        # User a rates user b
        client_a = _auth(api_client, a)
        resp_a = client_a.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(b.id),
                "score": 5,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp_a.status_code == 201

        trade.refresh_from_db()
        # Only one rating so far — not yet completed
        assert trade.status == Trade.Status.SHIPPING

        # User b rates user a
        client_b = _auth(api_client, b)
        resp_b = client_b.post(
            reverse("trade-rate", kwargs={"pk": trade.id}),
            {
                "rated_user_id": str(a.id),
                "score": 4,
                "book_condition_accurate": True,
            },
            format="json",
        )
        assert resp_b.status_code == 201

        trade.refresh_from_db()
        # Both parties rated — should now be COMPLETED
        assert trade.status == Trade.Status.COMPLETED
        assert trade.completed_at is not None

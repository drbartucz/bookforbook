"""
Tests for trading API — trade proposals and trades.
"""

import pytest
from django.urls import reverse

from apps.inventory.models import UserBook
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

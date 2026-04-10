"""
Tests for the messaging app:
  - TradeMessage model constraints
  - TradeMessageListView GET (list + auto read-marking)
  - TradeMessageListView POST (create message)
  - Access control: only trade parties can read/write
  - Blocking messages on completed/auto_closed trades
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.messaging.models import TradeMessage
from apps.tests.factories import (
    TradeFactory,
    TradeMessageFactory,
    TradeShipmentFactory,
    UserBookFactory,
    UserFactory,
)
from apps.trading.models import Trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trade_with_parties(user_a, user_b):
    """Create a confirmed Trade with two shipments so user_a and user_b are trade parties."""
    book_a = UserBookFactory(user=user_a)
    book_b = UserBookFactory(user=user_b)
    trade = TradeFactory(status=Trade.Status.CONFIRMED)
    TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b, user_book=book_a)
    TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a, user_book=book_b)
    return trade


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def messages_url(trade_pk):
    return f"/api/v1/trades/{trade_pk}/messages/"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTradeMessageModel:
    def test_str_representation(self):
        msg = TradeMessageFactory()
        assert msg.sender.username in str(msg)
        assert msg.message_type in str(msg)

    def test_ordering_is_chronological(self):
        trade = TradeFactory()
        sender = UserFactory()
        m1 = TradeMessageFactory(trade=trade, sender=sender)
        m2 = TradeMessageFactory(trade=trade, sender=sender)
        qs = list(TradeMessage.objects.filter(trade=trade))
        assert qs[0].pk == m1.pk
        assert qs[1].pk == m2.pk

    def test_read_at_is_null_by_default(self):
        msg = TradeMessageFactory()
        assert msg.read_at is None

    def test_metadata_defaults_to_none(self):
        msg = TradeMessageFactory()
        assert msg.metadata is None

    def test_all_message_types_are_valid(self):
        valid_types = [c[0] for c in TradeMessage.MessageType.choices]
        assert "shipping_update" in valid_types
        assert "question" in valid_types
        assert "issue_report" in valid_types
        assert "general_note" in valid_types
        assert "delay_notice" in valid_types


# ---------------------------------------------------------------------------
# GET /api/v1/trades/:pk/messages/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTradeMessageListGet:
    def test_party_can_list_messages(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        TradeMessageFactory(trade=trade, sender=user_b, content="Hey!")

        resp = auth_client(user_a).get(messages_url(trade.pk))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]["content"] == "Hey!"

    def test_non_party_gets_404(self):
        user_a = UserFactory()
        user_b = UserFactory()
        outsider = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        resp = auth_client(outsider).get(messages_url(trade.pk))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_gets_401(self):
        trade = TradeFactory()
        resp = APIClient().get(messages_url(trade.pk))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_messages_ordered_chronologically(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        m1 = TradeMessageFactory(trade=trade, sender=user_a, content="First")
        m2 = TradeMessageFactory(trade=trade, sender=user_b, content="Second")

        resp = auth_client(user_a).get(messages_url(trade.pk))
        assert resp.data[0]["id"] == str(m1.pk)
        assert resp.data[1]["id"] == str(m2.pk)

    def test_get_marks_others_messages_as_read(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        msg = TradeMessageFactory(trade=trade, sender=user_b)
        assert msg.read_at is None

        auth_client(user_a).get(messages_url(trade.pk))

        msg.refresh_from_db()
        assert msg.read_at is not None

    def test_get_does_not_mark_own_messages_as_read(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        own_msg = TradeMessageFactory(trade=trade, sender=user_a)

        auth_client(user_a).get(messages_url(trade.pk))

        own_msg.refresh_from_db()
        assert own_msg.read_at is None

    def test_empty_trade_returns_empty_list(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        resp = auth_client(user_a).get(messages_url(trade.pk))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []


# ---------------------------------------------------------------------------
# POST /api/v1/trades/:pk/messages/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTradeMessageCreate:
    def test_party_can_send_message(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {"message_type": "general_note", "content": "Books are packed!"}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["content"] == "Books are packed!"
        assert resp.data["sender"]["username"] == user_a.username
        assert TradeMessage.objects.filter(trade=trade).count() == 1

    def test_non_party_cannot_send_message(self):
        user_a = UserFactory()
        user_b = UserFactory()
        outsider = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {"message_type": "general_note", "content": "Sneaky!"}
        resp = auth_client(outsider).post(
            messages_url(trade.pk), payload, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert TradeMessage.objects.count() == 0

    def test_message_with_metadata(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {
            "message_type": "shipping_update",
            "content": "Shipped via USPS.",
            "metadata": {"tracking_number": "9400111899220123456789"},
        }
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["metadata"]["tracking_number"] == "9400111899220123456789"

    def test_blank_content_is_rejected(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {"message_type": "general_note", "content": "   "}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_message_type_is_rejected(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {"content": "Missing type"}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_message_on_completed_trade(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        trade.status = Trade.Status.COMPLETED
        trade.save(update_fields=["status"])

        payload = {"message_type": "general_note", "content": "Too late!"}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "completed" in resp.data["detail"].lower()

    def test_cannot_message_on_auto_closed_trade(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)
        trade.status = Trade.Status.AUTO_CLOSED
        trade.save(update_fields=["status"])

        payload = {"message_type": "general_note", "content": "Hello?"}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_message_type_is_rejected(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = make_trade_with_parties(user_a, user_b)

        payload = {"message_type": "spam", "content": "Bad type"}
        resp = auth_client(user_a).post(messages_url(trade.pk), payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

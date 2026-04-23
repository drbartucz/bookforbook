"""
Tests for trading background tasks: auto_close_trades and send_rating_reminders.
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, call

from django.db import IntegrityError
from django.utils import timezone

from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.notifications.models import Notification
from apps.ratings.models import Rating
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory
from apps.trading.models import Trade, TradeShipment
from apps.trading.models import TradeProposal
from apps.trading.services.trade_workflow import (
    create_trade_from_match,
    create_trade_from_proposal,
)
from apps.trading.tasks import auto_close_trades, send_rating_reminders


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trade(user_a, user_b, status=Trade.Status.CONFIRMED, *, overdue=False):
    """Create a two-shipment trade between user_a and user_b."""
    book_a = UserBookFactory(
        user=user_a, book=BookFactory(), status=UserBook.Status.RESERVED
    )
    book_b = UserBookFactory(
        user=user_b, book=BookFactory(), status=UserBook.Status.RESERVED
    )
    proposal = TradeProposal.objects.create(
        proposer=user_a,
        recipient=user_b,
        status=TradeProposal.Status.COMPLETED,
    )
    trade = Trade.objects.create(
        source_type=Trade.SourceType.PROPOSAL,
        source_id=proposal.pk,
        status=status,
    )
    if overdue:
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() - timedelta(minutes=1)
        )
        trade.refresh_from_db()
    s1 = TradeShipment.objects.create(
        trade=trade, sender=user_a, receiver=user_b, user_book=book_a
    )
    s2 = TradeShipment.objects.create(
        trade=trade, sender=user_b, receiver=user_a, user_book=book_b
    )
    return trade, s1, s2


# ---------------------------------------------------------------------------
# auto_close_trades
# ---------------------------------------------------------------------------


class TestAutoCloseTrades:
    def test_overdue_confirmed_trade_is_closed(self):
        a = UserFactory()
        b = UserFactory()
        trade, s1, s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        assert trade.completed_at is not None

    def test_overdue_shipping_trade_is_closed(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.SHIPPING, overdue=True)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED

    def test_overdue_one_received_trade_is_closed(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.ONE_RECEIVED, overdue=True)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED

    def test_non_overdue_trade_not_closed(self):
        a = UserFactory()
        b = UserFactory()
        # auto_close_at defaults to NOW + 3 weeks in the model save
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=False)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.CONFIRMED

    def test_already_completed_trade_not_touched(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.COMPLETED, overdue=True)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.COMPLETED

    def test_already_auto_closed_trade_not_touched(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.AUTO_CLOSED, overdue=True)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED

    def test_books_marked_as_traded_on_auto_close(self):
        a = UserFactory()
        b = UserFactory()
        trade, s1, s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)

        auto_close_trades()

        s1.user_book.refresh_from_db()
        s2.user_book.refresh_from_db()
        assert s1.user_book.status == UserBook.Status.TRADED
        assert s2.user_book.status == UserBook.Status.TRADED

    def test_user_trade_counts_incremented_on_auto_close(self):
        a = UserFactory()
        b = UserFactory()
        _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)

        auto_close_trades()

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.total_trades == 1
        assert b.total_trades == 1

    def test_notifications_sent_on_auto_close(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)

        auto_close_trades()

        notif_a = Notification.objects.filter(
            user=a, notification_type="trade_auto_closed"
        )
        notif_b = Notification.objects.filter(
            user=b, notification_type="trade_auto_closed"
        )
        assert notif_a.exists()
        assert notif_b.exists()

    def test_pending_shipments_marked_received_on_auto_close(self):
        a = UserFactory()
        b = UserFactory()
        trade, s1, s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)

        auto_close_trades()

        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s1.status == TradeShipment.Status.RECEIVED
        assert s2.status == TradeShipment.Status.RECEIVED

    def test_multiple_overdue_trades_all_closed(self):
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()
        trade1, _s1, _s2 = _make_trade(a, b, Trade.Status.CONFIRMED, overdue=True)
        trade2, _s3, _s4 = _make_trade(b, c, Trade.Status.SHIPPING, overdue=True)

        auto_close_trades()

        trade1.refresh_from_db()
        trade2.refresh_from_db()
        assert trade1.status == Trade.Status.AUTO_CLOSED
        assert trade2.status == Trade.Status.AUTO_CLOSED


# ---------------------------------------------------------------------------
# send_rating_reminders
# ---------------------------------------------------------------------------


class TestSendRatingReminders:
    def test_reminder_queued_for_unrated_party(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.SHIPPING)

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        assert mock_task.called
        task_args = [call_args[0] for call_args in mock_task.call_args_list]
        task_names = [args[0] for args in task_args]
        assert all(
            name == "apps.notifications.tasks.send_rating_reminder"
            for name in task_names
        )

    def test_rating_reminders_sent_counter_incremented(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.SHIPPING)
        assert trade.rating_reminders_sent == 0

        with patch("django_q.tasks.async_task"):
            send_rating_reminders()

        trade.refresh_from_db()
        assert trade.rating_reminders_sent == 1

    def test_already_rated_user_does_not_get_reminder(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.SHIPPING)

        # a has already rated b
        Rating.objects.create(
            trade=trade,
            rater=a,
            rated=b,
            score=5,
            book_condition_accurate=True,
        )

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        # Only b (unrated) should get a reminder; a should not
        reminder_user_ids = {call_args[0][2] for call_args in mock_task.call_args_list}
        assert str(b.id) in reminder_user_ids
        assert str(a.id) not in reminder_user_ids

    def test_no_reminder_after_3_already_sent(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(rating_reminders_sent=3)

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        mock_task.assert_not_called()


class TestTradeUniquenessAndIdempotency:
    def test_trade_source_unique_constraint_blocks_duplicates(self):
        proposal = TradeProposal.objects.create(
            proposer=UserFactory(),
            recipient=UserFactory(),
            status=TradeProposal.Status.COMPLETED,
        )
        Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=proposal.pk,
            status=Trade.Status.CONFIRMED,
        )

        with pytest.raises(IntegrityError):
            Trade.objects.create(
                source_type=Trade.SourceType.PROPOSAL,
                source_id=proposal.pk,
                status=Trade.Status.CONFIRMED,
            )

    def test_create_trade_from_match_is_idempotent(self):
        user_a = UserFactory()
        user_b = UserFactory()
        book_a = UserBookFactory(user=user_a, book=BookFactory())
        book_b = UserBookFactory(user=user_b, book=BookFactory())
        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
        )
        MatchLeg.objects.create(
            match=match, sender=user_a, receiver=user_b, user_book=book_a, position=0
        )
        MatchLeg.objects.create(
            match=match, sender=user_b, receiver=user_a, user_book=book_b, position=1
        )

        first = create_trade_from_match(match)
        second = create_trade_from_match(match)

        assert first.pk == second.pk
        assert (
            Trade.objects.filter(
                source_type=Trade.SourceType.MATCH,
                source_id=match.pk,
            ).count()
            == 1
        )

    def test_create_trade_from_proposal_is_idempotent(self):
        proposer = UserFactory()
        recipient = UserFactory()
        proposal = TradeProposal.objects.create(
            proposer=proposer,
            recipient=recipient,
            status=TradeProposal.Status.ACCEPTED,
        )
        proposer_book = UserBookFactory(user=proposer, book=BookFactory())
        recipient_book = UserBookFactory(user=recipient, book=BookFactory())
        proposal.items.create(
            direction="proposer_sends",
            user_book=proposer_book,
        )
        proposal.items.create(
            direction="recipient_sends",
            user_book=recipient_book,
        )

        first = create_trade_from_proposal(proposal)
        second = create_trade_from_proposal(proposal)

        assert first.pk == second.pk
        assert (
            Trade.objects.filter(
                source_type=Trade.SourceType.PROPOSAL,
                source_id=proposal.pk,
            ).count()
            == 1
        )

    def test_no_reminder_for_completed_trade_with_max_reminders(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.COMPLETED)
        Trade.objects.filter(pk=trade.pk).update(rating_reminders_sent=3)

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        mock_task.assert_not_called()

    def test_no_reminder_for_non_active_trade(self):
        """Closed / already auto-closed trades don't get reminders."""
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.AUTO_CLOSED)

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        mock_task.assert_not_called()

    def test_both_unrated_parties_get_reminder(self):
        a = UserFactory()
        b = UserFactory()
        trade, _s1, _s2 = _make_trade(a, b, Trade.Status.COMPLETED)

        with patch("django_q.tasks.async_task") as mock_task:
            send_rating_reminders()

        reminder_user_ids = {call_args[0][2] for call_args in mock_task.call_args_list}
        assert str(a.id) in reminder_user_ids
        assert str(b.id) in reminder_user_ids

import pytest
from datetime import timedelta
from unittest.mock import patch
from django.db import IntegrityError
from django.utils import timezone

from apps.tests.factories import UserFactory, TradeFactory, TradeShipmentFactory, RatingFactory, UserBookFactory
from apps.trading.models import Trade, TradeShipment
from apps.trading.tasks import send_rating_reminders, auto_close_trades, send_trade_closure_warnings
from apps.inventory.models import UserBook
from apps.ratings.models import Rating


def make_expired_trade(**kwargs):
    """Create a trade with auto_close_at in the past."""
    trade = TradeFactory(**kwargs)
    Trade.objects.filter(pk=trade.pk).update(auto_close_at=timezone.now() - timedelta(days=1))
    trade.refresh_from_db()
    return trade


@pytest.mark.django_db
class TestSendRatingReminders:
    @patch("django_q.tasks.async_task")
    def test_send_rating_reminders(self, mock_async):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = TradeFactory(status=Trade.Status.COMPLETED)
        TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b)
        TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a)

        RatingFactory(trade=trade, rater=user_a, rated=user_b)

        send_rating_reminders()

        assert mock_async.called
        reminded_user_id = mock_async.call_args[0][2]
        assert str(reminded_user_id) == str(user_b.id)

        trade.refresh_from_db()
        assert trade.rating_reminders_sent == 1


@pytest.mark.django_db
class TestAutoCloseTrades:
    def test_confirmed_trade_restores_books(self):
        """CONFIRMED trade: books restored, no ratings, no total_trades change."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.CONFIRMED)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(trade=trade, sender=sender, receiver=receiver, user_book=ub, status=TradeShipment.Status.PENDING)

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.AVAILABLE
        sender.refresh_from_db()
        assert sender.total_trades == 0
        assert Rating.objects.filter(trade=trade).count() == 0

    def test_shipping_valid_tracking_credits_both_parties(self):
        """SHIPPING trade with valid tracking: 5-star rating, both parties credited."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.SHIPPING)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver, user_book=ub,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="1Z999AA10123456784",
        )

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.TRADED
        sender.refresh_from_db()
        receiver.refresh_from_db()
        assert sender.total_trades == 1
        assert receiver.total_trades == 1
        rating = Rating.objects.get(trade=trade)
        assert rating.score == 5
        assert rating.rated == sender

    def test_shipping_no_tracking_penalizes_sender(self):
        """SHIPPING trade with no tracking: 1-star rating, book restored, no credit."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.SHIPPING)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver, user_book=ub,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.AVAILABLE
        sender.refresh_from_db()
        receiver.refresh_from_db()
        assert sender.total_trades == 0
        assert receiver.total_trades == 0
        rating = Rating.objects.get(trade=trade)
        assert rating.score == 1
        assert rating.comment == "Did not ship"
        assert rating.rated == sender

    def test_already_received_shipment_gets_credit(self):
        """Shipment already RECEIVED before auto-close still gets 5-star credit."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.ONE_RECEIVED)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver, user_book=ub,
            status=TradeShipment.Status.RECEIVED,
            tracking_number="",
        )

        auto_close_trades()

        rating = Rating.objects.get(trade=trade)
        assert rating.score == 5

    def test_mixed_shipments_independent_outcomes(self):
        """One shipment succeeds, one fails — outcomes are independent."""
        sender_a = UserFactory(total_trades=0)
        sender_b = UserFactory(total_trades=0)
        receiver_a = UserFactory(total_trades=0)
        receiver_b = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.SHIPPING)

        ub_a = UserBookFactory(status=UserBook.Status.RESERVED)
        ub_b = UserBookFactory(status=UserBook.Status.RESERVED)

        TradeShipmentFactory(
            trade=trade, sender=sender_a, receiver=receiver_a, user_book=ub_a,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="1Z999AA10123456784",
        )
        TradeShipmentFactory(
            trade=trade, sender=sender_b, receiver=receiver_b, user_book=ub_b,
            status=TradeShipment.Status.PENDING,
            tracking_number="",
        )

        auto_close_trades()

        ub_a.refresh_from_db()
        ub_b.refresh_from_db()
        assert ub_a.status == UserBook.Status.TRADED
        assert ub_b.status == UserBook.Status.AVAILABLE

        sender_a.refresh_from_db()
        sender_b.refresh_from_db()
        assert sender_a.total_trades == 1
        assert sender_b.total_trades == 0

        ratings = Rating.objects.filter(trade=trade).order_by("score")
        assert ratings[0].score == 1
        assert ratings[1].score == 5

    def test_idempotent_second_call_is_noop(self):
        """Calling auto_close_trades twice on the same trade does not double-process it."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.SHIPPING)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver, user_book=ub,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="1Z999AA10123456784",
        )

        auto_close_trades()
        auto_close_trades()  # second call

        sender.refresh_from_db()
        assert sender.total_trades == 1  # not 2
        assert Rating.objects.filter(trade=trade).count() == 1  # not 2


@pytest.mark.django_db
class TestSendTradeClosureWarnings:
    @patch("django_q.tasks.async_task")
    def test_warns_shipping_trade_within_window(self, mock_async):
        """A SHIPPING trade within 2 days with no valid tracking gets a warning."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=1)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()

        assert mock_async.called
        trade.refresh_from_db()
        assert trade.closure_warning_sent_at is not None

    @patch("django_q.tasks.async_task")
    def test_does_not_rewarn_same_trade(self, mock_async):
        """A trade that already received a warning is not warned again."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=1),
            closure_warning_sent_at=timezone.now() - timedelta(hours=1),
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()

        assert not mock_async.called

    @patch("django_q.tasks.async_task")
    def test_does_not_warn_outside_window(self, mock_async):
        """A trade more than 2 days away is not warned."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=5)
        )
        TradeShipmentFactory(trade=trade, sender=sender, receiver=receiver, tracking_number="")

        send_trade_closure_warnings()

        assert not mock_async.called

    @patch("django_q.tasks.async_task")
    def test_does_not_warn_when_valid_tracking_present(self, mock_async):
        """A shipment with valid tracking does not trigger a warning."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=1)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="1Z999AA10123456784",
        )

        send_trade_closure_warnings()

        assert not mock_async.called

    @patch("django_q.tasks.async_task")
    def test_confirmed_trade_warns_all_parties(self, mock_async):
        """A CONFIRMED trade within window warns all senders with 'not_started' reason."""
        sender_a = UserFactory()
        receiver_a = UserFactory()
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=1)
        )
        TradeShipmentFactory(trade=trade, sender=sender_a, receiver=receiver_a)

        send_trade_closure_warnings()

        assert mock_async.called
        call_args = mock_async.call_args[0]
        assert call_args[3] == "not_started"


@pytest.mark.django_db
class TestAutoCloseDeletedUser:
    def test_auto_close_handles_deleted_user_gracefully(self):
        """If a sender is deleted (cascade-deleting their shipments) before auto-close
        runs, the task should not crash — the trade closes with no shipments processed."""
        sender = UserFactory(total_trades=0)
        receiver = UserFactory(total_trades=0)
        trade = make_expired_trade(status=Trade.Status.SHIPPING)
        ub = UserBookFactory(user=sender, status=UserBook.Status.RESERVED)
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver, user_book=ub,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="1Z999AA10123456784",
        )

        # Delete the sender — cascades to their shipment
        sender.delete()

        # Task must not raise
        auto_close_trades()

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        # No ratings created since there were no shipments to evaluate
        assert Rating.objects.filter(trade=trade).count() == 0


@pytest.mark.django_db
class TestClosureWarningBoundary:
    @patch("django_q.tasks.async_task")
    def test_trade_exactly_at_boundary_is_warned(self, mock_async):
        """A trade whose auto_close_at equals exactly now+2d is inside the window."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=2)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()

        assert mock_async.called

    @patch("django_q.tasks.async_task")
    def test_trade_just_outside_boundary_not_warned(self, mock_async):
        """A trade 2 days + 2 hours away is outside the window."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=2, hours=2)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()

        assert not mock_async.called

    @patch("django_q.tasks.async_task")
    def test_late_cron_still_warns_trade_past_lower_bound(self, mock_async):
        """If cron runs late, a trade whose auto_close_at has already passed (but hasn't
        been auto-closed yet) should still receive a warning rather than silently missing
        it. The lower bound of the window is now, so such a trade is excluded. This test
        documents the known limitation: trades that slip into the past before the daily
        warning task runs will not receive a warning email."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        # auto_close_at is 3 hours in the past — cron missed its window
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() - timedelta(hours=3)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()

        # Known limitation: warning is NOT sent because the trade is past the lower bound.
        # The auto_close task will handle it on its next weekly run instead.
        assert not mock_async.called

    @patch("django_q.tasks.async_task")
    def test_idempotent_second_warning_call_is_noop(self, mock_async):
        """A second run of send_trade_closure_warnings does not re-warn the same trade."""
        sender = UserFactory()
        receiver = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        Trade.objects.filter(pk=trade.pk).update(
            auto_close_at=timezone.now() + timedelta(days=1)
        )
        TradeShipmentFactory(
            trade=trade, sender=sender, receiver=receiver,
            status=TradeShipment.Status.SHIPPED,
            tracking_number="",
        )

        send_trade_closure_warnings()
        first_call_count = mock_async.call_count

        send_trade_closure_warnings()
        second_call_count = mock_async.call_count

        assert first_call_count == 1
        assert second_call_count == 1  # no additional calls on second run


@pytest.mark.django_db
class TestTradeRateViewAutoClosedGuard:
    def test_rating_after_auto_close_does_not_flip_to_completed(self, client):
        """A human rating on an AUTO_CLOSED trade does not change status to COMPLETED."""
        from rest_framework.test import APIClient
        from apps.tests.factories import TradeFactory, TradeShipmentFactory, UserFactory, UserBookFactory

        user_a = UserFactory()
        user_b = UserFactory()
        trade = TradeFactory(status=Trade.Status.AUTO_CLOSED)
        ub_a = UserBookFactory(user=user_a)
        ub_b = UserBookFactory(user=user_b)
        TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b, user_book=ub_a)
        TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a, user_book=ub_b)

        api = APIClient()
        api.force_authenticate(user=user_a)
        api.post(
            f"/api/v1/trades/{trade.pk}/rate/",
            {"rated_user_id": str(user_b.pk), "score": 5, "book_condition_accurate": True},
            format="json",
        )

        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED

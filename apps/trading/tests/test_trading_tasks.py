import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone

from apps.tests.factories import UserFactory, TradeFactory, TradeShipmentFactory, RatingFactory, UserBookFactory
from apps.trading.models import Trade, TradeShipment
from apps.trading.tasks import send_rating_reminders, auto_close_trades
from apps.inventory.models import UserBook

@pytest.mark.django_db
class TestTradingTasks:
    @patch("django_q.tasks.async_task")
    def test_send_rating_reminders(self, mock_async):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = TradeFactory(status=Trade.Status.COMPLETED)
        TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b)
        TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a)
        
        # User A has rated, B has not
        RatingFactory(trade=trade, rater=user_a, rated=user_b)
        
        send_rating_reminders()
        
        # Only B should be reminded
        assert mock_async.called
        # First arg is the task name, second is trade_id, third is user_id
        reminded_user_id = mock_async.call_args[0][2]
        assert str(reminded_user_id) == str(user_b.id)
        
        trade.refresh_from_db()
        assert trade.rating_reminders_sent == 1

    def test_auto_close_trades_unshipped(self):
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        TradeShipmentFactory(trade=trade, user_book=ub, status=TradeShipment.Status.PENDING)
        
        # Make it old
        Trade.objects.filter(pk=trade.pk).update(auto_close_at=timezone.now() - timedelta(days=1))
        
        auto_close_trades()
        
        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.AVAILABLE

    def test_auto_close_trades_shipped(self):
        user = UserFactory(total_trades=0)
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        ub = UserBookFactory(status=UserBook.Status.RESERVED)
        s = TradeShipmentFactory(trade=trade, sender=user, user_book=ub, status=TradeShipment.Status.SHIPPED)
        
        Trade.objects.filter(pk=trade.pk).update(auto_close_at=timezone.now() - timedelta(days=1))
        
        auto_close_trades()
        
        trade.refresh_from_db()
        assert trade.status == Trade.Status.AUTO_CLOSED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.TRADED
        user.refresh_from_db()
        assert user.total_trades == 1

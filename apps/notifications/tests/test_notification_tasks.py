import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.core import mail

from apps.tests.factories import (
    UserFactory, 
    MatchFactory, 
    MatchLegFactory, 
    TradeFactory, 
    TradeShipmentFactory,
    UserBookFactory,
    WishlistItemFactory
)
from apps.notifications.tasks import (
    send_verification_email,
    send_password_reset_email,
    send_match_notification,
    send_trade_confirmed_notification,
    send_rating_reminder,
    send_inactivity_warning_1m,
    send_books_delisted_notification,
    finalize_scheduled_account_deletions,
    check_inactivity,
    reconcile_inventory_user_ownership
)
from apps.notifications.models import Notification
from apps.inventory.models import UserBook, WishlistItem

@pytest.mark.django_db
class TestNotificationTasks:
    @patch("apps.notifications.email.send_verification_email")
    def test_send_verification_email_task(self, mock_send):
        user = UserFactory()
        send_verification_email(str(user.pk), "uid", "token")
        mock_send.assert_called_once_with(user, "uid", "token")

    @patch("apps.notifications.email.send_password_reset_email")
    def test_send_password_reset_email_task(self, mock_send):
        user = UserFactory()
        send_password_reset_email(str(user.pk), "uid", "token")
        mock_send.assert_called_once_with(user, "uid", "token")

    @patch("apps.notifications.email.send_match_notification_email")
    def test_send_match_notification_task(self, mock_email):
        user_a = UserFactory()
        user_b = UserFactory()
        match = MatchFactory()
        MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        MatchLegFactory(match=match, sender=user_b, receiver=user_a)
        
        send_match_notification(str(match.pk))
        
        assert Notification.objects.filter(user=user_a, notification_type="new_match").exists()
        assert Notification.objects.filter(user=user_b, notification_type="new_match").exists()
        assert mock_email.call_count == 2

    @patch("apps.notifications.email.send_trade_confirmed_email")
    def test_send_trade_confirmed_notification_task(self, mock_email):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = TradeFactory()
        TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b)
        TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a)
        
        send_trade_confirmed_notification(str(trade.pk))
        assert mock_email.call_count == 2

    @patch("apps.notifications.email.send_inactivity_warning_1m_email")
    def test_send_inactivity_warning_1m_task(self, mock_send):
        user = UserFactory()
        send_inactivity_warning_1m(str(user.pk))
        user.refresh_from_db()
        assert user.inactivity_warned_1m is not None
        mock_send.assert_called_once_with(user)

    @patch("apps.notifications.email.send_books_delisted_email")
    def test_send_books_delisted_notification_task(self, mock_send):
        user = UserFactory()
        send_books_delisted_notification(str(user.pk))
        assert Notification.objects.filter(user=user, notification_type="books_delisted").exists()
        mock_send.assert_called_once_with(user)

    def test_finalize_scheduled_account_deletions(self):
        user = UserFactory(
            is_active=False, 
            deletion_requested_at=timezone.now() - timedelta(days=31),
            full_name="PII Name",
            address_line_1="PII Address"
        )
        ub = UserBookFactory(user=user)
        wish = WishlistItemFactory(user=user)
        
        finalize_scheduled_account_deletions(grace_days=30)
        
        user.refresh_from_db()
        assert user.deletion_completed_at is not None
        assert user.full_name == ""
        assert user.email.endswith("@deleted.local")
        assert not UserBook.objects.filter(user=user).exists()
        assert not WishlistItem.objects.filter(user=user).exists()

    def test_check_inactivity_task(self):
        now = timezone.now()
        
        # 1. To delist (>90 days)
        u1 = UserFactory()
        u1.last_active_at = now - timedelta(days=95)
        u1.save()
        ub1 = UserBookFactory(user=u1, status=UserBook.Status.AVAILABLE)
        
        # 2. To warn 2m (>60 days)
        u2 = UserFactory()
        u2.last_active_at = now - timedelta(days=65)
        u2.inactivity_warned_1m = now - timedelta(days=30)
        u2.save()
        
        # 3. To warn 1m (>30 days)
        u3 = UserFactory()
        u3.last_active_at = now - timedelta(days=35)
        u3.save()
        
        # We need to mock async_task at the point of call inside the function
        # But wait, maybe the error was it was not available to patch because it was a local import
        # Let's try patching it where it would be if it were at the top level, 
        # or better, just mock the django_q.tasks version which it's imported FROM.
        with patch("django_q.tasks.async_task") as mock_async:
            check_inactivity()
            
            # Verify u1 books were delisted
            ub1.refresh_from_db()
            assert ub1.status == UserBook.Status.DELISTED
            
            u1.refresh_from_db()
            assert u1.books_delisted_at is not None
            
            # Verify tasks enqueued
            calls = [call[0][0] for call in mock_async.call_args_list]
            assert "apps.notifications.tasks.send_books_delisted_notification" in calls
            assert "apps.notifications.tasks.send_inactivity_warning_2m" in calls
            assert "apps.notifications.tasks.send_inactivity_warning_1m" in calls

    def test_reconcile_inventory_user_ownership(self):
        active_user = UserFactory(is_active=True)
        inactive_user = UserFactory(is_active=False)
        
        # Inactive user's book should be delisted
        ub1 = UserBookFactory(user=inactive_user, status=UserBook.Status.AVAILABLE)
        # Active user's book should stay
        ub2 = UserBookFactory(user=active_user, status=UserBook.Status.AVAILABLE)
        
        # Inactive user's wishlist should be deactivated
        wish = WishlistItemFactory(user=inactive_user, is_active=True)
        
        reconcile_inventory_user_ownership()
        
        ub1.refresh_from_db()
        assert ub1.status == UserBook.Status.DELISTED
        ub2.refresh_from_db()
        assert ub2.status == UserBook.Status.AVAILABLE
        wish.refresh_from_db()
        assert wish.is_active is False

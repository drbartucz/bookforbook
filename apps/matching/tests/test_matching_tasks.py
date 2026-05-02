import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.tests.factories import UserFactory, UserBookFactory, WishlistItemFactory, MatchFactory, MatchLegFactory
from apps.matching.models import Match
from apps.matching.tasks import (
    run_matching_for_new_item,
    run_matching_for_relisted_books,
    run_periodic_matching,
    expire_old_matches,
    retry_ring_after_decline_task
)

@pytest.mark.django_db
class TestMatchingTasks:
    @patch("apps.matching.services.direct_matcher.run_direct_matching")
    def test_run_matching_for_new_item_user_book(self, mock_direct):
        ub = UserBookFactory()
        run_matching_for_new_item(user_book_id=str(ub.pk))
        mock_direct.assert_called_once_with(user_book=ub)

    @patch("apps.matching.services.direct_matcher.run_direct_matching")
    def test_run_matching_for_new_item_wishlist(self, mock_direct):
        wish = WishlistItemFactory()
        # Create a book that matches the wishlist item
        ub = UserBookFactory(book=wish.book)
        
        run_matching_for_new_item(wishlist_item_id=str(wish.pk))
        # It should call direct_matcher for the available book
        assert mock_direct.called

    @patch("apps.matching.services.direct_matcher.run_direct_matching")
    def test_run_matching_for_relisted_books(self, mock_direct):
        user = UserFactory()
        UserBookFactory(user=user)
        run_matching_for_relisted_books(str(user.pk))
        assert mock_direct.called

    @patch("apps.matching.services.direct_matcher.run_direct_matching")
    @patch("apps.matching.services.ring_detector.run_ring_detection")
    def test_run_periodic_matching(self, mock_ring, mock_direct):
        run_periodic_matching()
        assert mock_direct.called
        assert mock_ring.called

    def test_expire_old_matches(self):
        m1 = MatchFactory(status=Match.Status.PENDING, expires_at=timezone.now() - timedelta(hours=1))
        m2 = MatchFactory(status=Match.Status.PROPOSED, expires_at=timezone.now() + timedelta(hours=1))
        
        expire_old_matches()
        
        m1.refresh_from_db()
        m2.refresh_from_db()
        assert m1.status == Match.Status.EXPIRED
        assert m2.status == Match.Status.PROPOSED

    @patch("apps.matching.services.ring_detector.retry_ring_after_decline")
    def test_retry_ring_after_decline_task_failure(self, mock_retry):
        user = UserFactory()
        match = MatchFactory(match_type=Match.MatchType.RING)
        MatchLegFactory(match=match, sender=UserFactory(), receiver=user)
        
        mock_retry.return_value = None # Failed to reform
        
        retry_ring_after_decline_task(str(match.pk), str(user.pk))
        
        # Should create notifications for remaining participants
        from apps.notifications.models import Notification
        assert Notification.objects.filter(notification_type="ring_cancelled").exists()

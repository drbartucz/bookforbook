import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.matching.models import Match
from apps.matching.tasks import (
    expire_old_matches,
    run_matching_for_new_item,
    run_periodic_matching,
)
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


@pytest.mark.django_db
class TestMatchingTasks:
    def test_replaying_user_book_task_does_not_create_duplicate_match(self):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        user_book = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        run_matching_for_new_item(user_book_id=user_book.pk)
        run_matching_for_new_item(user_book_id=user_book.pk)

        matches = Match.objects.filter(
            match_type=Match.MatchType.DIRECT,
            status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        )
        assert matches.count() == 1

    def test_replaying_wishlist_task_does_not_create_duplicate_match(self):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        user_book = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        wishlist_item = WishlistItemFactory(
            user=user_b,
            book=book_for_b,
            min_condition="acceptable",
        )
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        run_matching_for_new_item(wishlist_item_id=wishlist_item.pk)
        run_matching_for_new_item(wishlist_item_id=wishlist_item.pk)

        matches = Match.objects.filter(
            match_type=Match.MatchType.DIRECT,
            status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        )
        assert matches.count() == 1
        assert matches.first().legs.filter(user_book=user_book).exists()

    def test_periodic_matching_runs_ring_even_if_direct_fails(self):
        with patch(
            "apps.matching.services.direct_matcher.run_direct_matching",
            side_effect=RuntimeError("direct failed"),
        ), patch(
            "apps.matching.services.ring_detector.run_ring_detection",
            return_value=[],
        ) as mock_ring:
            run_periodic_matching()

        mock_ring.assert_called_once_with()

    def test_periodic_matching_runs_direct_even_if_ring_fails(self):
        with patch(
            "apps.matching.services.direct_matcher.run_direct_matching",
            return_value=[],
        ) as mock_direct, patch(
            "apps.matching.services.ring_detector.run_ring_detection",
            side_effect=RuntimeError("ring failed"),
        ):
            run_periodic_matching()

        mock_direct.assert_called_once_with()

    def test_expire_old_matches_only_updates_active_expired_rows(self):
        now = timezone.now()
        expired_pending = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
            expires_at=now - timedelta(minutes=1),
        )
        expired_proposed = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
            expires_at=now - timedelta(minutes=1),
        )
        future_pending = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
            expires_at=now + timedelta(hours=1),
        )
        already_completed = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.COMPLETED,
            expires_at=now - timedelta(hours=2),
        )

        expire_old_matches()

        expired_pending.refresh_from_db()
        expired_proposed.refresh_from_db()
        future_pending.refresh_from_db()
        already_completed.refresh_from_db()

        assert expired_pending.status == Match.Status.EXPIRED
        assert expired_proposed.status == Match.Status.EXPIRED
        assert future_pending.status == Match.Status.PENDING
        assert already_completed.status == Match.Status.COMPLETED

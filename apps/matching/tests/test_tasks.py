import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.matching.models import Match
from apps.matching.tasks import (
    expire_old_matches,
    retry_ring_after_decline_task,
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
    @pytest.fixture(autouse=True)
    def _zero_age_gate(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 0

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

    def test_retry_ring_after_decline_task_queues_notification_when_reformed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        book = BookFactory()
        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        leg = UserBookFactory(user=user_a, book=book)
        from apps.matching.models import MatchLeg

        MatchLeg.objects.create(
            match=ring,
            sender=user_a,
            receiver=user_b,
            user_book=leg,
        )

        replacement = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.PROPOSED,
        )

        with patch(
            "apps.matching.services.ring_detector.retry_ring_after_decline",
            return_value=replacement,
        ), patch("django_q.tasks.async_task") as mock_async_task:
            retry_ring_after_decline_task(str(ring.pk), str(user_a.pk))

        mock_async_task.assert_called_once_with(
            "apps.notifications.tasks.send_match_notification",
            str(replacement.pk),
        )

    def test_retry_ring_after_decline_task_notifies_when_not_reformed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        leg_a = UserBookFactory(user=user_a, book=book_a)
        leg_b = UserBookFactory(user=user_b, book=book_b)
        from apps.matching.models import MatchLeg

        MatchLeg.objects.create(
            match=ring,
            sender=user_a,
            receiver=user_b,
            user_book=leg_a,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=user_b,
            receiver=user_a,
            user_book=leg_b,
        )

        with patch(
            "apps.matching.services.ring_detector.retry_ring_after_decline",
            return_value=None,
        ):
            retry_ring_after_decline_task(str(ring.pk), str(user_a.pk))

        from apps.notifications.models import Notification

        assert Notification.objects.filter(
            user=user_b,
            notification_type="ring_cancelled",
        ).exists()


@pytest.mark.django_db
class TestMatchingTaskEdgeCases:
    """Covers missed lines: DoesNotExist handlers, run_matching_for_relisted_books,
    and retry_ring_after_decline_task error branches."""

    @pytest.fixture(autouse=True)
    def _zero_age_gate(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 0

    # ------------------------------------------------------------------
    # run_matching_for_new_item: DoesNotExist branches
    # ------------------------------------------------------------------

    def test_run_matching_for_new_item_userbook_not_found_is_silent(self):
        """Lines 28-29: UserBook.DoesNotExist is caught and logged without raising."""
        import uuid
        # Should not raise even if the UserBook doesn't exist.
        run_matching_for_new_item(user_book_id=uuid.uuid4())

    def test_run_matching_for_new_item_wishlist_item_not_found_is_silent(self):
        """Lines 53-54: WishlistItem.DoesNotExist is caught and logged without raising."""
        import uuid
        run_matching_for_new_item(wishlist_item_id=uuid.uuid4())

    # ------------------------------------------------------------------
    # run_matching_for_relisted_books
    # ------------------------------------------------------------------

    def test_run_matching_for_relisted_books_runs_for_available_books(self):
        """Lines 62-75: function iterates available books and runs direct matching."""
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        UserBookFactory(user=user_a, book=book_for_b, condition="good")
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        from apps.matching.tasks import run_matching_for_relisted_books

        # Should run without errors and create a match.
        run_matching_for_relisted_books(str(user_a.id))

        assert Match.objects.filter(
            match_type=Match.MatchType.DIRECT,
            status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        ).exists()

    def test_run_matching_for_relisted_books_no_books_is_silent(self):
        """Lines 62-75: user with no available books produces no errors."""
        from apps.matching.tasks import run_matching_for_relisted_books

        user = UserFactory()
        run_matching_for_relisted_books(str(user.id))
        # No match created and no exception.
        assert not Match.objects.filter(match_type=Match.MatchType.DIRECT).exists()

    # ------------------------------------------------------------------
    # retry_ring_after_decline_task: Match.DoesNotExist
    # ------------------------------------------------------------------

    def test_retry_ring_after_decline_task_match_not_found_is_silent(self):
        """Lines 132-134: Match.DoesNotExist exits early without raising."""
        import uuid
        user = UserFactory()
        # Should not raise.
        retry_ring_after_decline_task(str(uuid.uuid4()), str(user.pk))

    # ------------------------------------------------------------------
    # retry_ring_after_decline_task: non-ring match exits early
    # ------------------------------------------------------------------

    def test_retry_ring_after_decline_task_direct_match_is_skipped(self):
        """Lines 136-137: direct match type returns early."""
        user_a = UserFactory()
        user_b = UserFactory()
        book = BookFactory()
        direct = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
        )
        ub = UserBookFactory(user=user_a, book=book)
        from apps.matching.models import MatchLeg

        MatchLeg.objects.create(
            match=direct,
            sender=user_a,
            receiver=user_b,
            user_book=ub,
        )
        # Should return early (no exception).
        retry_ring_after_decline_task(str(direct.pk), str(user_a.pk))

    # ------------------------------------------------------------------
    # retry_ring_after_decline_task: User.DoesNotExist
    # ------------------------------------------------------------------

    def test_retry_ring_after_decline_task_user_not_found_is_silent(self):
        """Lines 142-146: User.DoesNotExist exits early without raising."""
        import uuid

        user_a = UserFactory()
        user_b = UserFactory()
        book = BookFactory()
        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        ub = UserBookFactory(user=user_a, book=book)
        from apps.matching.models import MatchLeg

        MatchLeg.objects.create(
            match=ring,
            sender=user_a,
            receiver=user_b,
            user_book=ub,
        )
        # Pass a non-existent user UUID.
        retry_ring_after_decline_task(str(ring.pk), str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # retry_ring_after_decline_task: service call raises exception
    # ------------------------------------------------------------------

    def test_retry_ring_after_decline_task_service_exception_is_caught(self):
        """Lines 160-164: exception in retry_ring_after_decline is logged and swallowed."""
        user_a = UserFactory()
        user_b = UserFactory()
        book = BookFactory()
        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        ub = UserBookFactory(user=user_a, book=book)
        from apps.matching.models import MatchLeg

        MatchLeg.objects.create(
            match=ring,
            sender=user_a,
            receiver=user_b,
            user_book=ub,
        )

        with patch(
            "apps.matching.services.ring_detector.retry_ring_after_decline",
            side_effect=RuntimeError("service boom"),
        ):
            # Should not raise.
            retry_ring_after_decline_task(str(ring.pk), str(user_a.pk))

    # ------------------------------------------------------------------
    # retry_ring_after_decline_task: Notification.objects.bulk_create raises
    # ------------------------------------------------------------------

    def test_retry_ring_after_decline_task_bulk_create_exception_is_caught(self):
        """Lines 190-191: exception in bulk_create is logged and swallowed."""
        user_a = UserFactory()
        user_b = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        leg_a = UserBookFactory(user=user_a, book=book_a)
        leg_b = UserBookFactory(user=user_b, book=book_b)
        from apps.matching.models import MatchLeg
        from apps.notifications.models import Notification

        MatchLeg.objects.create(
            match=ring,
            sender=user_a,
            receiver=user_b,
            user_book=leg_a,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=user_b,
            receiver=user_a,
            user_book=leg_b,
        )

        with patch(
            "apps.matching.services.ring_detector.retry_ring_after_decline",
            return_value=None,
        ), patch.object(
            Notification.objects,
            "bulk_create",
            side_effect=Exception("db write failed"),
        ):
            # Should not raise.
            retry_ring_after_decline_task(str(ring.pk), str(user_a.pk))

"""
Tests for the minimum account age eligibility gate in match detection.

Covers:
- user_is_match_eligible_by_age() helper
- Direct matcher: user_a and user_b age gates
- Ring detector: _build_trade_graph() age filter
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.matching.models import Match
from apps.matching.services.direct_matcher import (
    run_direct_matching,
    user_is_match_eligible_by_age,
)
from apps.matching.services.ring_detector import _build_trade_graph
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


# ---------------------------------------------------------------------------
# Unit tests — user_is_match_eligible_by_age helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUserIsMatchEligibleByAge:
    def test_old_account_is_eligible(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        user = UserFactory()
        user.created_at = timezone.now() - timedelta(hours=49)
        user.save(update_fields=["created_at"])
        assert user_is_match_eligible_by_age(user) is True

    def test_new_account_is_not_eligible(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        user = UserFactory()
        # created_at is auto_now_add — brand new account
        assert user_is_match_eligible_by_age(user) is False

    def test_exactly_past_boundary_is_eligible(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        user = UserFactory()
        user.created_at = timezone.now() - timedelta(hours=48, seconds=1)
        user.save(update_fields=["created_at"])
        assert user_is_match_eligible_by_age(user) is True

    def test_zero_hour_threshold_allows_all(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 0
        user = UserFactory()
        assert user_is_match_eligible_by_age(user) is True


# ---------------------------------------------------------------------------
# Direct matcher integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDirectMatcherAccountAgeGate:
    def _setup_pair(self, user_a_old=True, user_b_old=True):
        """Create a direct-match-eligible pair; control account age per user."""
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        if user_a_old:
            user_a.created_at = timezone.now() - timedelta(hours=49)
            user_a.save(update_fields=["created_at"])
        if user_b_old:
            user_b.created_at = timezone.now() - timedelta(hours=49)
            user_b.save(update_fields=["created_at"])

        ub_a = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")
        return ub_a

    def test_both_old_accounts_produce_match(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        ub_a = self._setup_pair(user_a_old=True, user_b_old=True)
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        assert matches[0].match_type == Match.MatchType.DIRECT

    def test_new_user_a_is_skipped(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        ub_a = self._setup_pair(user_a_old=False, user_b_old=True)
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_new_user_b_is_skipped(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        ub_a = self._setup_pair(user_a_old=True, user_b_old=False)
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_both_new_accounts_produce_no_match(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        ub_a = self._setup_pair(user_a_old=False, user_b_old=False)
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# Ring detector integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRingDetectorAccountAgeGate:
    def test_new_account_excluded_from_trade_graph(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        new_user = UserFactory()
        book = BookFactory()
        UserBookFactory(user=new_user, book=book, condition="good")
        WishlistItemFactory(
            user=new_user, book=BookFactory(), min_condition="acceptable"
        )

        graph, _ = _build_trade_graph()
        assert str(new_user.pk) not in graph

    def test_old_account_included_in_trade_graph(self, settings):
        settings.MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = 48
        old_user = UserFactory()
        old_user.created_at = timezone.now() - timedelta(hours=49)
        old_user.save(update_fields=["created_at"])

        other_user = UserFactory()
        other_user.created_at = timezone.now() - timedelta(hours=49)
        other_user.save(update_fields=["created_at"])

        book_a = BookFactory()
        UserBookFactory(user=old_user, book=book_a, condition="good")
        WishlistItemFactory(
            user=other_user, book=book_a, min_condition="acceptable"
        )

        graph, _ = _build_trade_graph()
        assert str(old_user.pk) in graph

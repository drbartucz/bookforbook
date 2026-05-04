import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import override_settings

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, WishlistItemFactory, MatchFactory, MatchLegFactory
from apps.matching.services.direct_matcher import run_direct_matching, count_active_matches_for_user, user_at_match_limit
from apps.matching.models import Match
from apps.inventory.models import UserBook, ConditionChoices

@pytest.mark.django_db
class TestDirectMatcher:
    def test_direct_match_success(self):
        # User A has Book 1, wants Book 2
        user_a = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        book_1 = BookFactory()
        book_2 = BookFactory()
        ub_a = UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE, condition=ConditionChoices.LIKE_NEW)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        
        # User B has Book 2, wants Book 1
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        ub_b = UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE, condition=ConditionChoices.LIKE_NEW)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        matches = run_direct_matching()
        assert len(matches) == 1
        match = matches[0]
        assert match.legs.count() == 2
        assert match.legs.filter(sender=user_a, receiver=user_b, user_book=ub_a).exists()
        assert match.legs.filter(sender=user_b, receiver=user_a, user_book=ub_b).exists()

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=48)
    def test_user_too_young_skipped(self):
        user_a = UserFactory(created_at=timezone.now()) # New account
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        
        book_1 = BookFactory()
        book_2 = BookFactory()
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        matches = run_direct_matching()
        assert len(matches) == 0

    def test_match_limit_enforced(self):
        user_a = UserFactory(created_at=timezone.now() - timedelta(days=3), rating_count=0)
        # Default capacity is min(max(rating_count, 2), 10) = 2
        
        m1 = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=m1, sender=user_a)
        m2 = MatchFactory(status=Match.Status.PENDING)
        MatchLegFactory(match=m2, sender=user_a)
        
        # Verify user A is at limit
        assert count_active_matches_for_user(user_a) == 2
        assert user_at_match_limit(user_a) is True
        
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        book_1 = BookFactory()
        book_2 = BookFactory()
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        matches = run_direct_matching()
        assert len(matches) == 0

    def test_institutional_skipped(self):
        user_a = UserFactory(account_type='library', created_at=timezone.now() - timedelta(days=3))
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3))
        
        book_1 = BookFactory()
        book_2 = BookFactory()
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        matches = run_direct_matching()
        assert len(matches) == 0

    def test_condition_not_met_skipped(self):
        user_a = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        
        book_1 = BookFactory()
        book_2 = BookFactory()
        
        # User A has book_1 in ACCEPTABLE
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE, condition=ConditionChoices.ACCEPTABLE)
        # User B wants book_1 in GOOD or better
        WishlistItemFactory(user=user_b, book=book_1, is_active=True, min_condition=ConditionChoices.GOOD)
        
        # User B has book_2
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        
        matches = run_direct_matching()
        assert len(matches) == 0

    def test_focused_matching_single_book(self):
        user_a = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        user_b = UserFactory(created_at=timezone.now() - timedelta(days=3), email_verified=True)
        book_1 = BookFactory()
        book_2 = BookFactory()
        ub_a = UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True)
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        # Only scan for matches involving ub_a
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        
        # If ub_a is reserved, should find nothing
        ub_a.status = UserBook.Status.RESERVED
        ub_a.save()
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

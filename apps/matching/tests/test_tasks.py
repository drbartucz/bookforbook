import pytest

from apps.matching.models import Match
from apps.matching.tasks import run_matching_for_new_item
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

import pytest
from apps.inventory.models import ConditionChoices, condition_meets_minimum, UserBook, WishlistItem
from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, WishlistItemFactory

def test_condition_meets_minimum():
    assert condition_meets_minimum(ConditionChoices.LIKE_NEW, ConditionChoices.GOOD) is True
    assert condition_meets_minimum(ConditionChoices.GOOD, ConditionChoices.LIKE_NEW) is False
    assert condition_meets_minimum(ConditionChoices.GOOD, ConditionChoices.GOOD) is True
    assert condition_meets_minimum("invalid", ConditionChoices.GOOD) is False

@pytest.mark.django_db
class TestInventoryModels:
    def test_user_book_str(self):
        user = UserFactory(username="testuser")
        book = BookFactory(title="Test Title")
        ub = UserBookFactory(user=user, book=book, condition=ConditionChoices.GOOD, status=UserBook.Status.AVAILABLE)
        assert "testuser — Test Title [good] (available)" in str(ub)

    def test_wishlist_item_str(self):
        user = UserFactory(username="testuser")
        book = BookFactory(title="Test Title")
        wish = WishlistItemFactory(user=user, book=book, min_condition=ConditionChoices.VERY_GOOD)
        assert "testuser wants Test Title (min: very_good)" in str(wish)

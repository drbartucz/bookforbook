import pytest
from apps.matching.services.preference_filters import (
    normalize_title,
    extract_author_tokens,
    normalize_format,
    is_abridged,
    wishlist_allows_book
)
from apps.inventory.models import WishlistItem
from apps.tests.factories import BookFactory, WishlistItemFactory, UserFactory

def test_normalize_title():
    assert normalize_title("The Great Gatsby: A Novel") == "the great gatsby"
    assert normalize_title("Crème Brûlée") == "creme brulee"
    assert normalize_title("Hello!!!   World") == "hello world"
    assert normalize_title("") == ""

def test_extract_author_tokens():
    assert extract_author_tokens(["F. Scott Fitzgerald"]) == {"f. scott fitzgerald"}
    assert extract_author_tokens(" Fitzgerald ") == {"fitzgerald"}
    assert extract_author_tokens(None) == set()

def test_normalize_format():
    assert normalize_format("Trade Paperback") == "paperback"
    assert normalize_format("Cloth Bound Hardcover") == "hardcover"
    assert normalize_format("Mass Market") == "mass_market"
    assert normalize_format("Unknown") is None

@pytest.mark.django_db
def test_is_abridged():
    b1 = BookFactory(title="Abridged Edition")
    assert is_abridged(b1) is True
    b2 = BookFactory(title="Unabridged Abridgement")
    assert is_abridged(b2) is False

@pytest.mark.django_db
class TestWishlistAllowsBook:
    def test_exact_match(self):
        book = BookFactory()
        wish = WishlistItemFactory(book=book, edition_preference=WishlistItem.EditionPreference.EXACT)
        assert wishlist_allows_book(wish, book) is True
        assert wishlist_allows_book(wish, BookFactory()) is False

    def test_related_edition_title_mismatch(self):
        book1 = BookFactory(title="Title One")
        book2 = BookFactory(title="Title Two")
        wish = WishlistItemFactory(book=book1, edition_preference=WishlistItem.EditionPreference.SAME_LANGUAGE)
        assert wishlist_allows_book(wish, book2) is False

    def test_related_edition_author_check(self):
        book1 = BookFactory(title="Same Title", authors=["Author A"])
        book2 = BookFactory(title="Same Title", authors=["Author B"])
        
        wish = WishlistItemFactory(
            book=book1, 
            edition_preference=WishlistItem.EditionPreference.SAME_LANGUAGE,
            allow_translations=False
        )
        # DIFFERENT authors, same title -> False
        assert wishlist_allows_book(wish, book2) is False
        
        # Change to ANY_LANGUAGE allows more flexibility
        wish.edition_preference = WishlistItem.EditionPreference.ANY_LANGUAGE
        assert wishlist_allows_book(wish, book2) is True

    def test_format_preferences(self):
        book_hard = BookFactory(title="Book", physical_format="Hardcover")
        book_paper = BookFactory(title="Book", physical_format="Paperback")
        wish = WishlistItemFactory(
            book=book_hard,
            edition_preference=WishlistItem.EditionPreference.SAME_LANGUAGE,
            format_preferences=["hardcover"]
        )
        assert wishlist_allows_book(wish, book_hard) is True
        assert wishlist_allows_book(wish, book_paper) is False

    def test_unknown_format_not_rejected(self):
        # A book whose physical_format maps to None (e.g. "spiral-bound") should
        # not be rejected when the wishlist has format preferences — the format
        # is simply unknown, not wrong.
        book_known = BookFactory(title="Book", physical_format="Hardcover")
        book_unknown = BookFactory(title="Book", physical_format="spiral-bound")
        wish = WishlistItemFactory(
            book=book_known,
            edition_preference=WishlistItem.EditionPreference.SAME_LANGUAGE,
            format_preferences=["hardcover"],
        )
        assert wishlist_allows_book(wish, book_unknown) is True

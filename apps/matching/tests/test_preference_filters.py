import pytest

from apps.matching.services.preference_filters import wishlist_allows_book
from apps.tests.factories import BookFactory, WishlistItemFactory


pytestmark = pytest.mark.django_db


class TestWishlistAllowsBook:
    def test_accented_titles_match_under_related_edition_preferences(self):
        wanted = BookFactory(title="Les Miserables", authors=["Victor Hugo"])
        offered = BookFactory(title="Les Miserables", authors=["Victor Hugo"])
        wanted.title = "Les Misérables"
        wanted.save(update_fields=["title"])

        wish = WishlistItemFactory(
            book=wanted,
            edition_preference="same_language",
            allow_translations=False,
        )

        assert wishlist_allows_book(wish, offered)

    def test_not_abridged_phrase_does_not_trigger_abridged_rejection(self):
        wanted = BookFactory(title="War and Peace", authors=["Leo Tolstoy"])
        offered = BookFactory(
            title="War and Peace: NOT abridged edition",
            authors=["Leo Tolstoy"],
            description="This printing is NOT abridged.",
        )

        wish = WishlistItemFactory(
            book=wanted,
            edition_preference="same_language",
            exclude_abridged=True,
        )

        assert wishlist_allows_book(wish, offered)

    def test_unabridged_title_does_not_trigger_abridged_rejection(self):
        wanted = BookFactory(title="War and Peace", authors=["Leo Tolstoy"])
        offered = BookFactory(
            title="War and Peace: Unabridged edition",
            authors=["Leo Tolstoy"],
            description="Complete and unabridged text.",
        )

        wish = WishlistItemFactory(
            book=wanted,
            edition_preference="same_language",
            exclude_abridged=True,
        )

        assert wishlist_allows_book(wish, offered)

    def test_mixed_case_author_names_still_match(self):
        wanted = BookFactory(title="Dune", authors=["Frank Herbert"])
        offered = BookFactory(title="Dune", authors=["FRANK HERBERT"])

        wish = WishlistItemFactory(
            book=wanted,
            edition_preference="same_language",
            allow_translations=False,
        )

        assert wishlist_allows_book(wish, offered)

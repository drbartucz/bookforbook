"""
API tests for inventory: my-books (have-list) and wishlist (want-list).
"""

import pytest
from rest_framework import status

from apps.inventory.models import UserBook, WishlistItem
from apps.tests.factories import BookFactory, UserBookFactory, WishlistItemFactory


@pytest.mark.django_db
class TestMyBooksView:
    url = "/api/v1/my-books/"

    def test_requires_auth(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_requires_email_verified(self, api_client, user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_user_books(self, auth_api_client, user_book):
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        # Response should be paginated with 'results' and 'count'
        assert "results" in resp.data
        assert "count" in resp.data
        assert len(resp.data["results"]) == 1
        assert resp.data["count"] == 1

    def test_add_book(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "condition": "good",
                },
            )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["condition"] == "good"

    def test_add_book_and_appears_in_list(self, auth_api_client, book):
        """Test the full flow: add a book to have-list and verify it appears in the list."""
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            # Add the book
            add_resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "condition": "good",
                },
            )
        assert add_resp.status_code == status.HTTP_201_CREATED

        # Now list the books
        list_resp = auth_api_client.get(self.url)
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] == 1
        assert len(list_resp.data["results"]) == 1

        # Verify the item has the correct data
        item = list_resp.data["results"][0]
        assert item["book"]["isbn_13"] == book.isbn_13
        assert item["condition"] == "good"
        assert item["status"] == "available"

    def test_add_book_invalid_condition(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "condition": "terrible",
                },
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_removed_books_excluded_from_list(
        self, auth_api_client, verified_user, book
    ):
        UserBookFactory(user=verified_user, book=book, status=UserBook.Status.REMOVED)
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 0
        assert len(resp.data["results"]) == 0

    def test_patch_condition(self, auth_api_client, user_book):
        resp = auth_api_client.patch(
            f"{self.url}{user_book.id}/", {"condition": "like_new"}
        )
        assert resp.status_code == status.HTTP_200_OK
        user_book.refresh_from_db()
        assert user_book.condition == "like_new"

    def test_delete_available_book(self, auth_api_client, user_book):
        resp = auth_api_client.delete(f"{self.url}{user_book.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.REMOVED

    def test_delete_reserved_book_rejected(self, auth_api_client, verified_user, book):
        reserved = UserBookFactory(
            user=verified_user, book=book, status=UserBook.Status.RESERVED
        )
        resp = auth_api_client.delete(f"{self.url}{reserved.id}/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_access_another_users_book(self, auth_api_client, db):
        other_book = UserBookFactory()
        resp = auth_api_client.get(f"{self.url}{other_book.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_sort_by_title(self, auth_api_client, verified_user, book):
        """Test sorting books by title."""
        from apps.tests.factories import BookFactory

        book_a = BookFactory(title="Alpha Book")
        book_b = BookFactory(title="Beta Book")

        UserBookFactory(user=verified_user, book=book_a)
        UserBookFactory(user=verified_user, book=book_b)

        # Sort ascending (A to Z)
        resp = auth_api_client.get(self.url, {"sort_by": "title", "sort_order": "asc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "Alpha Book"
        assert resp.data["results"][1]["book"]["title"] == "Beta Book"

        # Sort descending (Z to A)
        resp = auth_api_client.get(self.url, {"sort_by": "title", "sort_order": "desc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "Beta Book"
        assert resp.data["results"][1]["book"]["title"] == "Alpha Book"

    def test_sort_by_author(self, auth_api_client, verified_user):
        """Test sorting books by author last name."""
        from apps.tests.factories import BookFactory

        # Last names are Adams and Brown, regardless of first-name ordering.
        book_a = BookFactory(title="A Book", authors=["Zoe Adams"])
        book_b = BookFactory(title="B Book", authors=["Amy Brown"])

        UserBookFactory(user=verified_user, book=book_a)
        UserBookFactory(user=verified_user, book=book_b)

        # Sort ascending by last name
        resp = auth_api_client.get(self.url, {"sort_by": "author", "sort_order": "asc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "A Book"
        assert resp.data["results"][1]["book"]["title"] == "B Book"

        # Sort descending by last name
        resp = auth_api_client.get(
            self.url, {"sort_by": "author", "sort_order": "desc"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "B Book"
        assert resp.data["results"][1]["book"]["title"] == "A Book"

    def test_sort_by_date_added(self, auth_api_client, verified_user, book):
        """Test sorting books by date added (default)."""
        from apps.tests.factories import BookFactory

        book_a = BookFactory(title="Old Book")
        book_b = BookFactory(title="New Book")

        old = UserBookFactory(user=verified_user, book=book_a)
        new = UserBookFactory(user=verified_user, book=book_b)

        # Sort descending (newest first, the default)
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        # Since 'new' was created after 'old', it should appear first
        assert resp.data["results"][0]["id"] == str(new.id)
        assert resp.data["results"][1]["id"] == str(old.id)


@pytest.mark.django_db
class TestWishlistView:
    url = "/api/v1/wishlist/"

    def test_requires_email_verified(self, api_client, user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(self.url, {})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_wishlist_paginated(self, auth_api_client, wishlist_item):
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        # Response should be paginated with 'results' and 'count'
        assert "results" in resp.data
        assert "count" in resp.data
        assert len(resp.data["results"]) == 1
        assert resp.data["count"] == 1

    def test_add_wishlist_item(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "min_condition": "good",
                },
            )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_add_wishlist_item_and_appears_in_list(self, auth_api_client, book):
        """Test the full flow: add an item to wishlist and verify it appears in the list."""
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            # Add the book to wishlist
            add_resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "min_condition": "good",
                },
            )
        assert add_resp.status_code == status.HTTP_201_CREATED

        # Now list the wishlist
        list_resp = auth_api_client.get(self.url)
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] == 1
        assert len(list_resp.data["results"]) == 1

        # Verify the item has the correct data
        item = list_resp.data["results"][0]
        assert item["book"]["isbn_13"] == book.isbn_13
        assert item["min_condition"] == "good"
        assert item["edition_preference"] == "same_language"
        assert item["allow_translations"] is False
        assert item["exclude_abridged"] is True
        assert item["format_preferences"] == []
        assert item["is_active"] is True

    def test_add_wishlist_item_with_custom_edition_preferences(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "min_condition": "good",
                    "edition_preference": "custom",
                    "allow_translations": True,
                    "exclude_abridged": True,
                    "format_preferences": ["hardcover", "paperback"],
                },
            )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["edition_preference"] == "custom"
        assert resp.data["allow_translations"] is True
        assert resp.data["exclude_abridged"] is True
        assert resp.data["format_preferences"] == ["hardcover", "paperback"]

    def test_duplicate_wishlist_item_rejected(self, auth_api_client, wishlist_item):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book",
            return_value=wishlist_item.book,
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn",
            return_value=wishlist_item.book.isbn_13,
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": wishlist_item.book.isbn_13,
                    "min_condition": "acceptable",
                },
            )
        # Should fail — unique_together constraint
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_wishlist_item(self, auth_api_client, wishlist_item):
        resp = auth_api_client.delete(f"{self.url}{wishlist_item.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not WishlistItem.objects.filter(pk=wishlist_item.id).exists()

    def test_patch_min_condition(self, auth_api_client, wishlist_item):
        resp = auth_api_client.patch(
            f"{self.url}{wishlist_item.id}/", {"min_condition": "very_good"}
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_patch_edition_preferences(self, auth_api_client, wishlist_item):
        resp = auth_api_client.patch(
            f"{self.url}{wishlist_item.id}/",
            {
                "edition_preference": "custom",
                "allow_translations": True,
                "exclude_abridged": False,
                "format_preferences": ["paperback", "audiobook"],
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["edition_preference"] == "custom"
        assert resp.data["allow_translations"] is True
        assert resp.data["exclude_abridged"] is False
        assert resp.data["format_preferences"] == ["paperback", "audiobook"]

    def test_sort_wishlist_by_title(self, auth_api_client, verified_user):
        """Test sorting wishlist items by title."""
        from apps.tests.factories import BookFactory

        book_a = BookFactory(title="Alpha Book")
        book_b = BookFactory(title="Beta Book")

        WishlistItemFactory(user=verified_user, book=book_a)
        WishlistItemFactory(user=verified_user, book=book_b)

        # Sort ascending (A to Z)
        resp = auth_api_client.get(self.url, {"sort_by": "title", "sort_order": "asc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "Alpha Book"
        assert resp.data["results"][1]["book"]["title"] == "Beta Book"

        # Sort descending (Z to A)
        resp = auth_api_client.get(self.url, {"sort_by": "title", "sort_order": "desc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "Beta Book"
        assert resp.data["results"][1]["book"]["title"] == "Alpha Book"

    def test_sort_wishlist_by_author_last_name(self, auth_api_client, verified_user):
        """Test sorting wishlist items by author last name."""
        from apps.tests.factories import BookFactory

        # Last names are Adams and Brown, regardless of first-name ordering.
        book_a = BookFactory(title="A Wish", authors=["Zoe Adams"])
        book_b = BookFactory(title="B Wish", authors=["Amy Brown"])

        WishlistItemFactory(user=verified_user, book=book_a)
        WishlistItemFactory(user=verified_user, book=book_b)

        resp = auth_api_client.get(self.url, {"sort_by": "author", "sort_order": "asc"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "A Wish"
        assert resp.data["results"][1]["book"]["title"] == "B Wish"

        resp = auth_api_client.get(
            self.url, {"sort_by": "author", "sort_order": "desc"}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["book"]["title"] == "B Wish"
        assert resp.data["results"][1]["book"]["title"] == "A Wish"

    def test_sort_wishlist_by_date_added(self, auth_api_client, verified_user):
        """Test sorting wishlist items by date added (default)."""
        from apps.tests.factories import BookFactory

        book_a = BookFactory(title="Old Book")
        book_b = BookFactory(title="New Book")

        old = WishlistItemFactory(user=verified_user, book=book_a)
        new = WishlistItemFactory(user=verified_user, book=book_b)

        # Sort descending (newest first, the default)
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 2
        assert resp.data["results"][0]["id"] == str(new.id)
        assert resp.data["results"][1]["id"] == str(old.id)


@pytest.mark.django_db
class TestBrowseAvailableView:
    url = "/api/v1/browse/available/"

    def test_browse_public_anonymous(self, api_client, user_book):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) >= 1

    def test_browse_excludes_non_available(self, api_client, verified_user, book):
        UserBookFactory(user=verified_user, book=book, status=UserBook.Status.TRADED)
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        for item in resp.data["results"]:
            assert item["status"] == "available"

    def test_browse_filter_by_query(self, api_client, db):
        b1 = BookFactory(title="Dune")
        b2 = BookFactory(title="Foundation")
        UserBookFactory(book=b1, status=UserBook.Status.AVAILABLE)
        UserBookFactory(book=b2, status=UserBook.Status.AVAILABLE)
        resp = api_client.get(self.url, {"q": "Dune"})
        assert resp.status_code == status.HTTP_200_OK
        titles = [r["book"]["title"] for r in resp.data["results"]]
        assert "Dune" in titles
        assert "Foundation" not in titles

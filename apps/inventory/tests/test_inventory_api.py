"""
API tests for inventory: my-books (have-list) and wishlist (want-list).
"""

import uuid

import pytest
from rest_framework import status

from apps.inventory.models import UserBook, WishlistItem
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)
from apps.trading.models import Trade, TradeShipment


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

    def test_add_book_enqueues_matching_task_once(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ), patch(
            "django_q.tasks.async_task"
        ) as mock_async_task:
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "condition": "good",
                },
            )

        assert resp.status_code == status.HTTP_201_CREATED
        mock_async_task.assert_called_once()
        args, kwargs = mock_async_task.call_args
        assert args == ("apps.matching.tasks.run_matching_for_new_item",)
        assert kwargs == {"user_book_id": resp.data["id"]}

    def test_first_offer_listing_sets_address_prompt_header(
        self, auth_api_client, book
    ):
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
        assert resp["X-Address-Prompt"] == "add_now"

    def test_second_listing_does_not_repeat_address_prompt_header(
        self, auth_api_client, verified_user
    ):
        from unittest.mock import patch

        book1 = BookFactory()
        book2 = BookFactory()

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book1
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book1.isbn_13
        ):
            first_resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book1.isbn_13,
                    "condition": "good",
                },
            )
        assert first_resp.status_code == status.HTTP_201_CREATED
        assert first_resp["X-Address-Prompt"] == "add_now"

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book2
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book2.isbn_13
        ):
            second_resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book2.isbn_13,
                    "condition": "good",
                },
            )
        assert second_resp.status_code == status.HTTP_201_CREATED
        assert "X-Address-Prompt" not in second_resp

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

    def test_invalid_book_submission_does_not_enqueue_matching_task(
        self, auth_api_client, book
    ):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ), patch(
            "django_q.tasks.async_task"
        ) as mock_async_task:
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "condition": "terrible",
                },
            )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        mock_async_task.assert_not_called()

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

    def test_add_wishlist_item_enqueues_matching_task_once(self, auth_api_client, book):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ), patch(
            "django_q.tasks.async_task"
        ) as mock_async_task:
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": book.isbn_13,
                    "min_condition": "good",
                },
            )

        assert resp.status_code == status.HTTP_201_CREATED
        mock_async_task.assert_called_once()
        args, kwargs = mock_async_task.call_args
        assert args == ("apps.matching.tasks.run_matching_for_new_item",)
        assert kwargs == {"wishlist_item_id": resp.data["id"]}

    def test_first_wishlist_listing_sets_address_prompt_header(
        self, auth_api_client, book
    ):
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
        assert resp["X-Address-Prompt"] == "add_now"

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

    def test_add_wishlist_item_with_custom_edition_preferences(
        self, auth_api_client, book
    ):
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

    def test_duplicate_wishlist_item_does_not_enqueue_matching_task(
        self, auth_api_client, wishlist_item
    ):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book",
            return_value=wishlist_item.book,
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn",
            return_value=wishlist_item.book.isbn_13,
        ), patch(
            "django_q.tasks.async_task"
        ) as mock_async_task:
            resp = auth_api_client.post(
                self.url,
                {
                    "isbn": wishlist_item.book.isbn_13,
                    "min_condition": "acceptable",
                },
            )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        mock_async_task.assert_not_called()

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


@pytest.mark.django_db
class TestPartnerBooksView:
    def test_confirmed_trade_partner_can_browse_books(self, verified_user):
        from rest_framework.test import APIClient

        partner = UserFactory(email_verified=True)
        outsider = UserFactory(email_verified=True)

        visible_book = UserBookFactory(
            user=partner,
            status=UserBook.Status.AVAILABLE,
        )
        shipment_book = UserBookFactory(
            user=partner,
            status=UserBook.Status.RESERVED,
        )
        UserBookFactory(
            user=partner,
            status=UserBook.Status.REMOVED,
        )
        UserBookFactory(
            user=outsider,
            status=UserBook.Status.AVAILABLE,
        )

        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=uuid.uuid4(),
            status=Trade.Status.CONFIRMED,
        )
        TradeShipment.objects.create(
            trade=trade,
            sender=partner,
            receiver=verified_user,
            user_book=shipment_book,
        )

        client = APIClient()
        client.force_authenticate(user=verified_user)

        resp = client.get(f"/api/v1/browse/partner/{partner.id}/books/")

        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]["id"] == str(visible_book.id)

    def test_outsider_cannot_browse_partner_books(self, verified_user):
        from rest_framework.test import APIClient

        partner = UserFactory(email_verified=True)
        UserBookFactory(user=partner, status=UserBook.Status.AVAILABLE)

        client = APIClient()
        client.force_authenticate(user=verified_user)

        resp = client.get(f"/api/v1/browse/partner/{partner.id}/books/")

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "confirmed trade partners" in resp.data["detail"]


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNoAddressPromptWhenUserAlreadyHasAddress:
    """Line 29: _should_prompt_for_address returns False when user has address."""

    url = "/api/v1/my-books/"

    def test_no_address_prompt_when_user_has_shipping_address(self, api_client):
        from unittest.mock import patch

        from apps.tests.factories import BookFactory, UserFactory

        # Create a user with all address fields filled in (has_shipping_address == True)
        user = UserFactory(
            email_verified=True,
            full_name="John Doe",
            address_line_1="123 Main St",
            city="Denver",
            state="CO",
            zip_code="80202",
            address_verification_status="verified",
        )
        book = BookFactory()

        client = api_client
        client.force_authenticate(user=user)

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ):
            resp = client.post(
                self.url,
                {"isbn": book.isbn_13, "condition": "good"},
            )

        assert resp.status_code == status.HTTP_201_CREATED
        # User already has address — prompt must NOT appear
        assert "X-Address-Prompt" not in resp


@pytest.mark.django_db
class TestMyBooksSortByAuthorSQLiteFallback:
    """Lines 88-97: SQLite fallback author sort in apply_book_sorting."""

    url = "/api/v1/my-books/"

    def test_sort_by_author_list_authors(self, auth_api_client, verified_user):
        """Authors stored as lists; SQLite fallback sorts by last name correctly."""
        from apps.tests.factories import BookFactory, UserBookFactory

        # 'Zoe Adams' last name 'adams' < 'Amy Brown' last name 'brown'
        book_a = BookFactory(title="First Book", authors=["Zoe Adams", "Co Author"])
        book_b = BookFactory(title="Second Book", authors=["Amy Brown"])

        UserBookFactory(user=verified_user, book=book_a)
        UserBookFactory(user=verified_user, book=book_b)

        resp = auth_api_client.get(self.url, {"sort_by": "author", "sort_order": "asc"})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["results"]
        assert len(results) == 2
        # Adams before Brown
        assert results[0]["book"]["title"] == "First Book"
        assert results[1]["book"]["title"] == "Second Book"

    def test_sort_by_author_desc_list_authors(self, auth_api_client, verified_user):
        """Descending author sort via SQLite fallback."""
        from apps.tests.factories import BookFactory, UserBookFactory

        book_a = BookFactory(title="First Book", authors=["Zoe Adams"])
        book_b = BookFactory(title="Second Book", authors=["Amy Brown"])

        UserBookFactory(user=verified_user, book=book_a)
        UserBookFactory(user=verified_user, book=book_b)

        resp = auth_api_client.get(self.url, {"sort_by": "author", "sort_order": "desc"})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["results"]
        assert len(results) == 2
        # Brown before Adams in descending order
        assert results[0]["book"]["title"] == "Second Book"
        assert results[1]["book"]["title"] == "First Book"


@pytest.mark.django_db
class TestAsyncTaskExceptionSilenced:
    """Lines 152-153 and 231-232: exception when async_task raises is swallowed."""

    def test_book_post_still_returns_201_when_async_task_raises(
        self, auth_api_client, book
    ):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ), patch(
            "django_q.tasks.async_task", side_effect=Exception("queue down")
        ):
            resp = auth_api_client.post(
                "/api/v1/my-books/",
                {"isbn": book.isbn_13, "condition": "good"},
            )

        # Even though async_task raised, we still get 201
        assert resp.status_code == status.HTTP_201_CREATED

    def test_wishlist_post_still_returns_201_when_async_task_raises(
        self, auth_api_client, book
    ):
        from unittest.mock import patch

        with patch(
            "apps.books.services.openlibrary.get_or_create_book", return_value=book
        ), patch(
            "apps.books.services.openlibrary.normalize_isbn", return_value=book.isbn_13
        ), patch(
            "django_q.tasks.async_task", side_effect=Exception("queue down")
        ):
            resp = auth_api_client.post(
                "/api/v1/wishlist/",
                {"isbn": book.isbn_13, "min_condition": "good"},
            )

        assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestMyBookDetailViewGet:
    """Line 173: MyBookDetailView.get — GET single book by pk."""

    def test_get_single_book(self, auth_api_client, user_book):
        resp = auth_api_client.get(f"/api/v1/my-books/{user_book.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == str(user_book.id)

    def test_get_other_users_book_returns_404(self, auth_api_client):
        other_book = UserBookFactory()
        resp = auth_api_client.get(f"/api/v1/my-books/{other_book.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWishlistItemDetailViewGet:
    """Lines 251-252: WishlistItemDetailView.get — GET single wishlist item."""

    def test_get_single_wishlist_item(self, auth_api_client, wishlist_item):
        resp = auth_api_client.get(f"/api/v1/wishlist/{wishlist_item.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == str(wishlist_item.id)

    def test_get_other_users_wishlist_item_returns_404(self, auth_api_client):
        other_item = WishlistItemFactory()
        resp = auth_api_client.get(f"/api/v1/wishlist/{other_item.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestBrowseConditionFilter:
    """Line 297: BrowseAvailableView with ?condition= filter."""

    url = "/api/v1/browse/available/"

    def test_filter_by_condition(self, api_client):
        from apps.tests.factories import BookFactory, UserBookFactory

        book_good = BookFactory(title="Good Condition Book")
        book_new = BookFactory(title="Like New Book")

        UserBookFactory(
            book=book_good,
            status=UserBook.Status.AVAILABLE,
            condition="good",
        )
        UserBookFactory(
            book=book_new,
            status=UserBook.Status.AVAILABLE,
            condition="like_new",
        )

        resp = api_client.get(self.url, {"condition": "good"})
        assert resp.status_code == status.HTTP_200_OK
        conditions = [r["condition"] for r in resp.data["results"]]
        assert all(c == "good" for c in conditions)
        titles = [r["book"]["title"] for r in resp.data["results"]]
        assert "Good Condition Book" in titles
        assert "Like New Book" not in titles

    def test_filter_by_condition_like_new(self, api_client):
        from apps.tests.factories import BookFactory, UserBookFactory

        book_good = BookFactory(title="Good Book")
        book_new = BookFactory(title="New Book")

        UserBookFactory(
            book=book_good,
            status=UserBook.Status.AVAILABLE,
            condition="good",
        )
        UserBookFactory(
            book=book_new,
            status=UserBook.Status.AVAILABLE,
            condition="like_new",
        )

        resp = api_client.get(self.url, {"condition": "like_new"})
        assert resp.status_code == status.HTTP_200_OK
        titles = [r["book"]["title"] for r in resp.data["results"]]
        assert "New Book" in titles
        assert "Good Book" not in titles


@pytest.mark.django_db
class TestShippingEstimateView:
    """Lines 368-376: ShippingEstimateView."""

    def test_shipping_estimate_returns_200(self, api_client, book):
        resp = api_client.get(f"/api/v1/browse/shipping-estimate/{book.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["book_id"] == str(book.id)
        assert "low" in resp.data
        assert "high" in resp.data
        assert "display" in resp.data
        assert "disclaimer" in resp.data

    def test_shipping_estimate_with_page_count(self, api_client):
        from apps.tests.factories import BookFactory

        book = BookFactory()
        book.page_count = 300
        book.save(update_fields=["page_count"])

        resp = api_client.get(f"/api/v1/browse/shipping-estimate/{book.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["page_count"] == 300
        assert resp.data["title"] == book.title

    def test_shipping_estimate_nonexistent_book_returns_404(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/browse/shipping-estimate/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

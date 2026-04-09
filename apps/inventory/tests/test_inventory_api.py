"""
API tests for inventory: my-books (have-list) and wishlist (want-list).
"""
import pytest
from rest_framework import status

from apps.inventory.models import UserBook, WishlistItem
from apps.tests.factories import BookFactory, UserBookFactory, WishlistItemFactory


@pytest.mark.django_db
class TestMyBooksView:
    url = '/api/v1/my-books/'

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
        assert len(resp.data) == 1

    def test_add_book(self, auth_api_client, book):
        from unittest.mock import patch
        with patch('apps.books.services.openlibrary.get_or_create_book', return_value=book), \
             patch('apps.books.services.openlibrary.normalize_isbn', return_value=book.isbn_13):
            resp = auth_api_client.post(self.url, {
                'isbn': book.isbn_13,
                'condition': 'good',
            })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['condition'] == 'good'

    def test_add_book_invalid_condition(self, auth_api_client, book):
        from unittest.mock import patch
        with patch('apps.books.services.openlibrary.get_or_create_book', return_value=book), \
             patch('apps.books.services.openlibrary.normalize_isbn', return_value=book.isbn_13):
            resp = auth_api_client.post(self.url, {
                'isbn': book.isbn_13,
                'condition': 'terrible',
            })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_removed_books_excluded_from_list(self, auth_api_client, verified_user, book):
        UserBookFactory(user=verified_user, book=book, status=UserBook.Status.REMOVED)
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_patch_condition(self, auth_api_client, user_book):
        resp = auth_api_client.patch(f'{self.url}{user_book.id}/', {'condition': 'like_new'})
        assert resp.status_code == status.HTTP_200_OK
        user_book.refresh_from_db()
        assert user_book.condition == 'like_new'

    def test_delete_available_book(self, auth_api_client, user_book):
        resp = auth_api_client.delete(f'{self.url}{user_book.id}/')
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        user_book.refresh_from_db()
        assert user_book.status == UserBook.Status.REMOVED

    def test_delete_reserved_book_rejected(self, auth_api_client, verified_user, book):
        reserved = UserBookFactory(user=verified_user, book=book, status=UserBook.Status.RESERVED)
        resp = auth_api_client.delete(f'{self.url}{reserved.id}/')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_access_another_users_book(self, auth_api_client, db):
        other_book = UserBookFactory()
        resp = auth_api_client.get(f'{self.url}{other_book.id}/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWishlistView:
    url = '/api/v1/wishlist/'

    def test_requires_email_verified(self, api_client, user):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(self.url, {})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_wishlist(self, auth_api_client, wishlist_item):
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1

    def test_add_wishlist_item(self, auth_api_client, book):
        from unittest.mock import patch
        with patch('apps.books.services.openlibrary.get_or_create_book', return_value=book), \
             patch('apps.books.services.openlibrary.normalize_isbn', return_value=book.isbn_13):
            resp = auth_api_client.post(self.url, {
                'isbn': book.isbn_13,
                'min_condition': 'good',
            })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_duplicate_wishlist_item_rejected(self, auth_api_client, wishlist_item):
        from unittest.mock import patch
        with patch('apps.books.services.openlibrary.get_or_create_book', return_value=wishlist_item.book), \
             patch('apps.books.services.openlibrary.normalize_isbn', return_value=wishlist_item.book.isbn_13):
            resp = auth_api_client.post(self.url, {
                'isbn': wishlist_item.book.isbn_13,
                'min_condition': 'acceptable',
            })
        # Should fail — unique_together constraint
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_wishlist_item(self, auth_api_client, wishlist_item):
        resp = auth_api_client.delete(f'{self.url}{wishlist_item.id}/')
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not WishlistItem.objects.filter(pk=wishlist_item.id).exists()

    def test_patch_min_condition(self, auth_api_client, wishlist_item):
        resp = auth_api_client.patch(f'{self.url}{wishlist_item.id}/', {'min_condition': 'very_good'})
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestBrowseAvailableView:
    url = '/api/v1/browse/available/'

    def test_browse_public_anonymous(self, api_client, user_book):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data['results']) >= 1

    def test_browse_excludes_non_available(self, api_client, verified_user, book):
        UserBookFactory(user=verified_user, book=book, status=UserBook.Status.TRADED)
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        for item in resp.data['results']:
            assert item['status'] == 'available'

    def test_browse_filter_by_query(self, api_client, db):
        b1 = BookFactory(title='Dune')
        b2 = BookFactory(title='Foundation')
        UserBookFactory(book=b1, status=UserBook.Status.AVAILABLE)
        UserBookFactory(book=b2, status=UserBook.Status.AVAILABLE)
        resp = api_client.get(self.url, {'q': 'Dune'})
        assert resp.status_code == status.HTTP_200_OK
        titles = [r['book']['title'] for r in resp.data['results']]
        assert 'Dune' in titles
        assert 'Foundation' not in titles

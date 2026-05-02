import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, WishlistItemFactory, TradeFactory, TradeShipmentFactory
from apps.inventory.models import UserBook, ConditionChoices

@pytest.mark.django_db
class TestInventoryViews:
    def test_my_books_list(self, api_client):
        user = UserFactory(email_verified=True)
        api_client.force_authenticate(user=user)
        
        UserBookFactory(user=user, status=UserBook.Status.AVAILABLE)
        UserBookFactory(user=user, status=UserBook.Status.REMOVED)
        
        url = reverse('my-books-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    @patch("apps.books.services.openlibrary.get_or_create_book")
    @patch("apps.books.services.openlibrary.normalize_isbn")
    def test_my_books_add_with_address_prompt(self, mock_normalize, mock_get_book, api_client):
        user = UserFactory(email_verified=True, address_line_1="")
        api_client.force_authenticate(user=user)
        book = BookFactory(isbn_13="9780141036144")
        mock_get_book.return_value = book
        mock_normalize.return_value = book.isbn_13
        
        url = reverse('my-books-list')
        data = {"isbn": book.isbn_13, "condition": "good"}
        
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.get('X-Address-Prompt') == 'add_now'

    def test_my_book_detail_and_update(self, api_client):
        user = UserFactory(email_verified=True)
        api_client.force_authenticate(user=user)
        ub = UserBookFactory(user=user, condition="good")
        
        url = reverse('my-book-detail', kwargs={'pk': ub.pk})
        
        # Get
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Patch
        response = api_client.patch(url, {"condition": "like_new"})
        assert response.status_code == status.HTTP_200_OK
        ub.refresh_from_db()
        assert ub.condition == "like_new"

    def test_my_book_delete_restricted(self, api_client):
        user = UserFactory(email_verified=True)
        api_client.force_authenticate(user=user)
        ub = UserBookFactory(user=user, status=UserBook.Status.RESERVED)
        
        url = reverse('my-book-detail', kwargs={'pk': ub.pk})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.books.services.openlibrary.get_or_create_book")
    @patch("apps.books.services.openlibrary.normalize_isbn")
    def test_wishlist_list_and_add(self, mock_normalize, mock_get_book, api_client):
        user = UserFactory(email_verified=True)
        api_client.force_authenticate(user=user)
        book = BookFactory(isbn_13="9780141036145")
        mock_get_book.return_value = book
        mock_normalize.return_value = book.isbn_13
        
        url = reverse('wishlist-list')
        data = {"isbn": book.isbn_13, "min_condition": "good"}
        
        # Add
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        
        # List
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    def test_browse_available(self, api_client):
        user = UserFactory(is_active=True)
        book = BookFactory(title="Unique Book")
        UserBookFactory(book=book, user=user, status=UserBook.Status.AVAILABLE)
        
        url = reverse('browse-available')
        response = api_client.get(url, {"q": "Unique"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_partner_books_view_denied(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)
        
        url = reverse('browse-partner-books', kwargs={'user_id': other.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_shipping_estimate_view(self, api_client):
        book = BookFactory(page_count=500)
        url = reverse('shipping-estimate', kwargs={'book_id': book.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'display' in response.data

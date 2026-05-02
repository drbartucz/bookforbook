import pytest
import io
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
from PIL import Image

from apps.tests.factories import UserFactory, BookFactory
from apps.books.models import Book

@pytest.mark.django_db
class TestBooksViews:
    def test_book_lookup_success(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        book = BookFactory(isbn_13="9780141036144")
        
        url = reverse('book-lookup')
        with patch("apps.books.services.openlibrary.get_or_create_book", return_value=book):
            response = api_client.post(url, {"isbn": "9780141036144"})
            assert response.status_code == status.HTTP_200_OK
            assert response.data['isbn_13'] == "9780141036144"

    def test_book_lookup_invalid(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        url = reverse('book-lookup')
        with patch("apps.books.services.openlibrary.get_or_create_book", side_effect=ValueError("Invalid ISBN")):
            response = api_client.post(url, {"isbn": "invalid"})
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_image_barcode_success(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        # Create a dummy image
        file = io.BytesIO()
        image = Image.new('RGB', (100, 100))
        image.save(file, 'jpeg')
        file.name = 'test.jpg'
        file.seek(0)
        
        url = reverse('book-from-image')
        with patch("apps.books.services.barcode.extract_isbn_from_image", return_value="9780141036144"):
            response = api_client.post(url, {"image": file}, format='multipart')
            assert response.status_code == status.HTTP_200_OK
            assert response.data['isbn'] == "9780141036144"

    def test_book_detail(self, api_client):
        book = BookFactory()
        url = reverse('book-detail', kwargs={'id': book.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == book.title

    def test_book_search(self, api_client):
        BookFactory(title="Searchable Book")
        BookFactory(title="Other")
        
        url = reverse('book-search')
        response = api_client.get(url, {"q": "Searchable"})
        assert response.status_code == status.HTTP_200_OK
        # results is a list inside the response data
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == "Searchable Book"

"""
API tests for books: lookup, detail, search.
"""
import pytest
from rest_framework import status
from unittest.mock import patch

from apps.books.models import Book
from apps.tests.factories import BookFactory


@pytest.mark.django_db
class TestBookLookupView:
    url = '/api/v1/books/lookup/'

    def test_lookup_requires_auth(self, api_client):
        resp = api_client.post(self.url, {'isbn': '9780201616224'})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_lookup_cached_book(self, auth_api_client, db):
        book = BookFactory(isbn_13='9780201616224', title='The Pragmatic Programmer')
        with patch('apps.books.services.openlibrary.get_or_create_book', return_value=book) as mock:
            resp = auth_api_client.post(self.url, {'isbn': '9780201616224'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['isbn_13'] == '9780201616224'
        mock.assert_called_once()

    def test_lookup_invalid_isbn_returns_400(self, auth_api_client):
        with patch('apps.books.services.openlibrary.get_or_create_book', side_effect=ValueError('Invalid ISBN')):
            resp = auth_api_client.post(self.url, {'isbn': 'invalid'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_lookup_service_error_returns_503(self, auth_api_client):
        with patch('apps.books.services.openlibrary.get_or_create_book', side_effect=Exception('network error')):
            resp = auth_api_client.post(self.url, {'isbn': '9780201616224'})
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.django_db
class TestBookDetailView:
    def test_get_book_anonymous(self, api_client, book):
        resp = api_client.get(f'/api/v1/books/{book.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['id'] == str(book.id)

    def test_get_book_not_found(self, api_client):
        import uuid
        resp = api_client.get(f'/api/v1/books/{uuid.uuid4()}/')
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestBookSearchView:
    url = '/api/v1/books/search/'

    def test_search_returns_matching_books(self, api_client, db):
        b1 = BookFactory(title='Python Crash Course', authors=['Eric Matthes'])
        b2 = BookFactory(title='Django for Beginners', authors=['William Vincent'])
        resp = api_client.get(self.url, {'q': 'Python'})
        assert resp.status_code == status.HTTP_200_OK
        titles = [r['title'] for r in resp.data['results']]
        assert 'Python Crash Course' in titles
        assert 'Django for Beginners' not in titles

    def test_search_empty_query_returns_nothing(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['results'] == []

    def test_search_by_isbn(self, api_client, db):
        book = BookFactory(isbn_13='9780596007645')
        resp = api_client.get(self.url, {'q': '9780596007645'})
        assert resp.status_code == status.HTTP_200_OK
        assert any(r['isbn_13'] == '9780596007645' for r in resp.data['results'])

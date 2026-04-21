import pytest

from django.contrib.auth import get_user_model

from apps.books.models import Book
from apps.tests.factories import BookFactory


@pytest.mark.django_db
def test_books_admin_changelist_renders_for_superuser(client):
    BookFactory(title="Admin Test Book", authors=["Tester"], isbn_13="9780000001234")

    superuser = get_user_model().objects.create_superuser(
        email="admin@example.com",
        username="admin",
        password="adminpass123",
    )
    client.force_login(superuser)

    response = client.get("/admin/books/book/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_books_admin_search_renders_for_superuser(client):
    BookFactory(
        title="Django Admin Search Book", authors=["Tester"], isbn_13="9780000001235"
    )

    superuser = get_user_model().objects.create_superuser(
        email="admin2@example.com",
        username="admin2",
        password="adminpass123",
    )
    client.force_login(superuser)

    response = client.get("/admin/books/book/", {"q": "Django"})

    assert response.status_code == 200


@pytest.mark.django_db
def test_books_admin_changelist_handles_non_list_authors(client):
    Book.objects.create(
        isbn_13="9780000001236",
        title="Malformed Authors Book",
        authors={"primary": "Someone"},
    )

    superuser = get_user_model().objects.create_superuser(
        email="admin3@example.com",
        username="admin3",
        password="adminpass123",
    )
    client.force_login(superuser)

    response = client.get("/admin/books/book/")

    assert response.status_code == 200

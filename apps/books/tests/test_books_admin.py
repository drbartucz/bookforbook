import pytest

from django.contrib.auth import get_user_model

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

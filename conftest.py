import pytest

from apps.accounts.models import User
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def user(db) -> User:
    return UserFactory(email_verified=False)


@pytest.fixture
def verified_user(db) -> User:
    return UserFactory(email_verified=True)


@pytest.fixture
def auth_api_client(verified_user: User):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=verified_user)
    return client


@pytest.fixture
def book(db):
    return BookFactory()


@pytest.fixture
def user_book(verified_user, book):
    return UserBookFactory(user=verified_user, book=book)


@pytest.fixture
def wishlist_item(verified_user, book):
    return WishlistItemFactory(user=verified_user, book=book)

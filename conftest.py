import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Python 3.14 compatibility: object gained __copy__ / __deepcopy__ methods.
# Calling super().__copy__() inside BaseContext.__copy__ now returns the super
# proxy rather than the actual instance, causing an AttributeError.
# This patch replaces the broken method with an equivalent that works on all
# supported Python versions.  It can be removed once Django ships the fix in
# the 5.1.x series.
# ---------------------------------------------------------------------------
if sys.version_info >= (3, 14):
    from django.template.context import BaseContext

    def _patched_base_context_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _patched_base_context_copy

from apps.accounts.models import User
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


@pytest.fixture(scope="session", autouse=True)
def ensure_staticfiles_dir():
    # Keep tests quiet when WhiteNoise middleware checks STATIC_ROOT.
    Path("staticfiles").mkdir(exist_ok=True)


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

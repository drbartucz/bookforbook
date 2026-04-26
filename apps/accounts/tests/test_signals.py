"""
Tests for accounts.signals — on_user_login signal handler.
"""

import pytest
from unittest.mock import patch

from django.test import RequestFactory

from apps.inventory.models import UserBook
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory


pytestmark = pytest.mark.django_db


def _simulate_login(user):
    """Fire the user_logged_in signal for the given user."""
    from django.contrib.auth.signals import user_logged_in
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user
    user_logged_in.send(sender=user.__class__, request=request, user=user)


class TestOnUserLogin:
    def test_updates_last_active_at(self):
        user = UserFactory(email_verified=True)
        original = user.last_active_at
        _simulate_login(user)
        user.refresh_from_db()
        assert user.last_active_at != original or original is None

    def test_no_delisted_books_skips_relist(self):
        user = UserFactory(email_verified=True, books_delisted_at=None)
        book = UserBookFactory(user=user, book=BookFactory(), status=UserBook.Status.AVAILABLE)

        _simulate_login(user)

        book.refresh_from_db()
        assert book.status == UserBook.Status.AVAILABLE

    def test_relists_delisted_books_on_login(self):
        from django.utils import timezone
        user = UserFactory(email_verified=True, books_delisted_at=timezone.now())
        book = UserBookFactory(user=user, book=BookFactory(), status=UserBook.Status.DELISTED)

        with patch("django_q.tasks.async_task") as mock_task:
            _simulate_login(user)

        book.refresh_from_db()
        assert book.status == UserBook.Status.AVAILABLE

        user.refresh_from_db()
        assert user.books_delisted_at is None
        assert user.inactivity_warned_1m is None
        assert user.inactivity_warned_2m is None

    def test_queues_matching_for_relisted_books(self):
        from django.utils import timezone
        user = UserFactory(email_verified=True, books_delisted_at=timezone.now())
        UserBookFactory(user=user, book=BookFactory(), status=UserBook.Status.DELISTED)

        with patch("django_q.tasks.async_task") as mock_task:
            _simulate_login(user)

        mock_task.assert_called_once()
        call_args = mock_task.call_args
        assert "run_matching_for_relisted_books" in call_args[0][0]

    def test_delisted_but_no_books_skips_matching_queue(self):
        """books_delisted_at set but no DELISTED books → no async_task called."""
        from django.utils import timezone
        user = UserFactory(email_verified=True, books_delisted_at=timezone.now())
        # No delisted books — relist query returns 0

        with patch("django_q.tasks.async_task") as mock_task:
            _simulate_login(user)

        mock_task.assert_not_called()
        user.refresh_from_db()
        assert user.books_delisted_at is None  # still cleared

    def test_async_task_exception_does_not_propagate(self):
        """If async_task raises (e.g., worker offline), login must still succeed."""
        from django.utils import timezone
        user = UserFactory(email_verified=True, books_delisted_at=timezone.now())
        UserBookFactory(user=user, book=BookFactory(), status=UserBook.Status.DELISTED)

        with patch("django_q.tasks.async_task", side_effect=Exception("q down")):
            _simulate_login(user)  # must not raise

        user.refresh_from_db()
        assert user.books_delisted_at is None

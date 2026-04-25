"""
Tests for notifications tasks — email helpers and async tasks.
All outbound email is intercepted by Django's locmem backend.
django_q.tasks.async_task is patched so no worker is needed.
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, call

from django.core import mail
from django.utils import timezone

from apps.notifications.email import (
    send_email,
    send_verification_email,
    send_match_notification_email,
    send_inactivity_warning_1m_email,
    send_inactivity_warning_2m_email,
    send_books_delisted_email,
    send_account_deletion_email,
    send_rating_reminder_email,
    send_trade_confirmed_email,
)
from apps.notifications.models import Notification
from apps.tests.factories import (
    TradeFactory,
    TradeMessageFactory,
    TradeShipmentFactory,
    UserBookFactory,
    UserFactory,
)
from apps.inventory.models import UserBook


# ---------------------------------------------------------------------------
# send_email helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendEmailHelper:
    def test_sends_plain_text_email(self, settings):
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        result = send_email("user@example.com", "Subject", "Hello!")
        assert result is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Subject"
        assert mail.outbox[0].to == ["user@example.com"]

    def test_sends_html_email_with_alternative(self, settings):
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        result = send_email("user@example.com", "Sub", "text", "<b>html</b>")
        assert result is True
        assert len(mail.outbox) == 1
        # EmailMultiAlternatives stores alternatives
        msg = mail.outbox[0]
        assert any("html" in alt[1] for alt in msg.alternatives)

    def test_returns_false_on_exception(self, settings):
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        with patch(
            "apps.notifications.email.send_mail", side_effect=Exception("SMTP down")
        ):
            result = send_email("user@example.com", "Sub", "text")
        assert result is False


# ---------------------------------------------------------------------------
# Email template functions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmailTemplateFunctions:
    def test_send_verification_email_contains_link(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="verify@example.com", username="alice")
        result = send_verification_email(user, "someuid", "sometoken")
        assert result is True
        assert len(mail.outbox) == 1
        assert "verify-email" in mail.outbox[0].body
        assert "someuid" in mail.outbox[0].body
        assert "sometoken" in mail.outbox[0].body

    def test_send_verification_email_escapes_html_in_username(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(
            email="xss@example.com", username="<script>alert(1)</script>"
        )

        result = send_verification_email(user, "someuid", "sometoken")

        assert result is True
        assert len(mail.outbox) == 1
        html_alternatives = [alt[0] for alt in mail.outbox[0].alternatives]
        assert html_alternatives
        html_body = html_alternatives[0]
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_body
        assert "<script>alert(1)</script>" not in html_body

    def test_send_match_notification_email_direct(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="match@example.com")
        match = MagicMock()
        match.pk = "abc123"
        match.match_type = "direct"
        match.legs.all.return_value = [MagicMock(), MagicMock()]
        result = send_match_notification_email(user, match)
        assert result is True
        assert "match" in mail.outbox[0].body.lower()

    def test_send_match_notification_email_ring(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="ring@example.com")
        match = MagicMock()
        match.pk = "ring999"
        match.match_type = "ring"
        match.legs.all.return_value = [MagicMock(), MagicMock(), MagicMock()]
        result = send_match_notification_email(user, match)
        assert result is True
        assert "3" in mail.outbox[0].body

    def test_send_inactivity_warning_1m_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="inactive1@example.com")
        result = send_inactivity_warning_1m_email(user)
        assert result is True
        assert mail.outbox[0].to == ["inactive1@example.com"]

    def test_send_inactivity_warning_2m_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="inactive2@example.com")
        result = send_inactivity_warning_2m_email(user)
        assert result is True
        assert (
            "removed" in mail.outbox[0].body.lower()
            or "delist" in mail.outbox[0].body.lower()
        )

    def test_send_books_delisted_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="delisted@example.com")
        result = send_books_delisted_email(user)
        assert result is True
        assert "delisted" in mail.outbox[0].subject.lower()

    def test_send_account_deletion_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="delete@example.com")
        result = send_account_deletion_email(user)
        assert result is True
        assert "deletion" in mail.outbox[0].subject.lower()

    def test_send_rating_reminder_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="rate@example.com")
        trade = TradeFactory()
        result = send_rating_reminder_email(user, trade)
        assert result is True
        assert "rate" in mail.outbox[0].body.lower()

    def test_send_trade_confirmed_email(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="confirmed@example.com")
        trade = TradeFactory()
        result = send_trade_confirmed_email(user, trade)
        assert result is True
        assert "confirmed" in mail.outbox[0].subject.lower()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

from unittest.mock import (
    MagicMock,
)  # noqa: E402 (already imported above, ensure accessible)


@pytest.mark.django_db
class TestSendVerificationEmailTask:
    def test_sends_email_via_task(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory(email="task@example.com")
        from apps.notifications.tasks import send_verification_email as task_fn

        task_fn(str(user.pk), "uid123", "tok456")
        assert len(mail.outbox) == 1
        assert "uid123" in mail.outbox[0].body


@pytest.mark.django_db
class TestSendMatchNotificationTask:
    def test_creates_in_app_notifications_for_all_participants(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"

        from apps.matching.models import Match, MatchLeg

        user_a = UserFactory()
        user_b = UserFactory()
        book_a = UserBookFactory(user=user_a)
        book_b = UserBookFactory(user=user_b)
        match = Match.objects.create(match_type="direct", status="pending")
        MatchLeg.objects.create(
            match=match, sender=user_a, receiver=user_b, user_book=book_a, position=0
        )
        MatchLeg.objects.create(
            match=match, sender=user_b, receiver=user_a, user_book=book_b, position=1
        )

        from apps.notifications.tasks import send_match_notification

        send_match_notification(str(match.pk))

        assert Notification.objects.filter(notification_type="new_match").count() == 2
        assert len(mail.outbox) == 2

    def test_notification_body_mentions_ring(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"

        from apps.matching.models import Match, MatchLeg

        users = [UserFactory() for _ in range(3)]
        books = [UserBookFactory(user=u) for u in users]
        match = Match.objects.create(match_type="ring", status="pending")
        for i, (u, b) in enumerate(zip(users, books)):
            MatchLeg.objects.create(
                match=match,
                sender=u,
                receiver=users[(i + 1) % 3],
                user_book=b,
                position=i,
            )

        from apps.notifications.tasks import send_match_notification

        send_match_notification(str(match.pk))

        notif = Notification.objects.filter(notification_type="new_match").first()
        assert "ring" in notif.body.lower()


@pytest.mark.django_db
class TestSendInactivityWarning1mTask:
    def test_stamps_inactivity_warned_1m_on_user(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory()
        assert user.inactivity_warned_1m is None

        from apps.notifications.tasks import send_inactivity_warning_1m

        send_inactivity_warning_1m(str(user.pk))

        user.refresh_from_db()
        assert user.inactivity_warned_1m is not None
        assert len(mail.outbox) == 1


@pytest.mark.django_db
class TestSendInactivityWarning2mTask:
    def test_stamps_inactivity_warned_2m_on_user(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory()

        from apps.notifications.tasks import send_inactivity_warning_2m

        send_inactivity_warning_2m(str(user.pk))

        user.refresh_from_db()
        assert user.inactivity_warned_2m is not None
        assert len(mail.outbox) == 1


@pytest.mark.django_db
class TestSendBooksDelistedNotificationTask:
    def test_creates_in_app_notification(self, settings):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"
        user = UserFactory()

        from apps.notifications.tasks import send_books_delisted_notification

        send_books_delisted_notification(str(user.pk))

        assert (
            Notification.objects.filter(
                user=user, notification_type="books_delisted"
            ).count()
            == 1
        )
        assert len(mail.outbox) == 1


@pytest.mark.django_db
class TestAccountDeletionTasks:
    def test_send_account_deletion_initiated_sends_confirmation_and_export(
        self, settings
    ):
        settings.FRONTEND_URL = "https://app.bookforbook.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@bookforbook.com"

        user = UserFactory(email="gdpr@example.com")
        UserBookFactory(user=user)

        from apps.notifications.tasks import send_account_deletion_initiated

        send_account_deletion_initiated(str(user.pk))

        assert len(mail.outbox) == 2
        assert "deletion" in mail.outbox[0].subject.lower()
        assert "export" in mail.outbox[1].subject.lower()
        assert any(
            (getattr(att, "filename", att[0]) == "bookforbook-data-export.json")
            for att in mail.outbox[1].attachments
        )

    def test_finalize_scheduled_account_deletions_anonymizes_profile(self):
        user = UserFactory(
            is_active=False,
            deletion_requested_at=timezone.now() - timedelta(days=31),
        )
        UserBookFactory(user=user)

        from apps.notifications.tasks import finalize_scheduled_account_deletions

        finalize_scheduled_account_deletions()

        user.refresh_from_db()
        assert user.deletion_completed_at is not None
        assert user.email.endswith("@deleted.local")
        assert user.username.startswith("deleted-")
        assert user.full_name == ""
        assert user.address_line_1 == ""
        assert UserBook.objects.filter(user=user).count() == 0


# ---------------------------------------------------------------------------
# check_inactivity task
# ---------------------------------------------------------------------------


def _set_last_active(user, days_ago):
    """Bypass auto_now_add on last_active_at via a direct UPDATE."""
    from apps.accounts.models import User as UserModel

    UserModel.objects.filter(pk=user.pk).update(
        last_active_at=timezone.now() - timedelta(days=days_ago)
    )
    user.refresh_from_db()


@pytest.mark.django_db
class TestCheckInactivityTask:
    """Exercises the three inactivity pipeline stages without needing a Q worker."""

    @patch("django_q.tasks.async_task")
    def test_warns_users_inactive_over_1_month(self, mock_async):
        user = UserFactory(inactivity_warned_1m=None, books_delisted_at=None)
        _set_last_active(user, 35)
        from apps.notifications.tasks import check_inactivity

        check_inactivity()
        mock_async.assert_any_call(
            "apps.notifications.tasks.send_inactivity_warning_1m", str(user.pk)
        )

    @patch("django_q.tasks.async_task")
    def test_institutional_users_do_not_get_1m_warning(self, mock_async):
        library_user = UserFactory(
            account_type="library",
            inactivity_warned_1m=None,
            books_delisted_at=None,
        )
        _set_last_active(library_user, 35)
        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        calls_str = str(mock_async.call_args_list)
        assert "send_inactivity_warning_1m" not in calls_str

    @patch("django_q.tasks.async_task")
    def test_does_not_warn_recently_active_user(self, mock_async):
        user = UserFactory(inactivity_warned_1m=None)
        # last_active_at defaults to now() via auto_now_add — no update needed
        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        calls = [str(c) for c in mock_async.call_args_list]
        assert not any("send_inactivity_warning_1m" in c for c in calls)

    @patch("django_q.tasks.async_task")
    def test_warns_users_inactive_over_2_months(self, mock_async):
        user = UserFactory(
            inactivity_warned_1m=timezone.now() - timedelta(days=35),
            inactivity_warned_2m=None,
            books_delisted_at=None,
        )
        _set_last_active(user, 65)
        from apps.notifications.tasks import check_inactivity

        check_inactivity()
        mock_async.assert_any_call(
            "apps.notifications.tasks.send_inactivity_warning_2m", str(user.pk)
        )

    @patch("django_q.tasks.async_task")
    def test_institutional_users_do_not_get_2m_warning(self, mock_async):
        bookstore_user = UserFactory(
            account_type="bookstore",
            inactivity_warned_1m=timezone.now() - timedelta(days=35),
            inactivity_warned_2m=None,
            books_delisted_at=None,
        )
        _set_last_active(bookstore_user, 65)
        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        calls_str = str(mock_async.call_args_list)
        assert "send_inactivity_warning_2m" not in calls_str

    @patch("django_q.tasks.async_task")
    def test_delists_books_after_3_months_inactive(self, mock_async):
        user = UserFactory(
            inactivity_warned_1m=timezone.now() - timedelta(days=65),
            inactivity_warned_2m=timezone.now() - timedelta(days=35),
            books_delisted_at=None,
        )
        _set_last_active(user, 95)
        book = UserBookFactory(user=user, status=UserBook.Status.AVAILABLE)

        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        book.refresh_from_db()
        assert book.status == UserBook.Status.DELISTED
        user.refresh_from_db()
        assert user.books_delisted_at is not None
        mock_async.assert_any_call(
            "apps.notifications.tasks.send_books_delisted_notification", str(user.pk)
        )

    @patch("django_q.tasks.async_task")
    def test_does_not_delist_twice(self, mock_async):
        """User already delisted should not be processed again."""
        user = UserFactory(
            inactivity_warned_1m=timezone.now() - timedelta(days=65),
            inactivity_warned_2m=timezone.now() - timedelta(days=35),
            books_delisted_at=timezone.now() - timedelta(days=5),
        )
        _set_last_active(user, 95)
        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        calls_str = str(mock_async.call_args_list)
        assert "send_books_delisted_notification" not in calls_str

    @patch("django_q.tasks.async_task")
    def test_delists_user_who_never_received_2m_warning(self, mock_async):
        """User inactive 3+ months is delisted even if the 2m warning was never sent."""
        user = UserFactory(
            inactivity_warned_1m=None,
            inactivity_warned_2m=None,
            books_delisted_at=None,
        )
        _set_last_active(user, 95)
        book = UserBookFactory(user=user, status=UserBook.Status.AVAILABLE)

        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        book.refresh_from_db()
        assert book.status == UserBook.Status.DELISTED
        mock_async.assert_any_call(
            "apps.notifications.tasks.send_books_delisted_notification", str(user.pk)
        )

    @patch("django_q.tasks.async_task")
    def test_institutional_users_are_excluded_from_inactivity_pipeline(
        self, mock_async
    ):
        """Institutional accounts should never receive inactivity warnings or delisting."""
        library_user = UserFactory(
            account_type="library",
            inactivity_warned_1m=None,
            inactivity_warned_2m=None,
            books_delisted_at=None,
        )
        _set_last_active(library_user, 95)
        book = UserBookFactory(user=library_user, status=UserBook.Status.AVAILABLE)

        from apps.notifications.tasks import check_inactivity

        check_inactivity()

        calls_str = str(mock_async.call_args_list)
        assert "send_inactivity_warning_1m" not in calls_str
        assert "send_inactivity_warning_2m" not in calls_str
        assert "send_books_delisted_notification" not in calls_str

        book.refresh_from_db()
        library_user.refresh_from_db()
        assert book.status == UserBook.Status.AVAILABLE
        assert library_user.books_delisted_at is None

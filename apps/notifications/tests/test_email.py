import pytest
from django.core import mail
from apps.tests.factories import UserFactory, MatchFactory, TradeFactory
from apps.notifications.email import (
    send_verification_email,
    send_password_reset_email,
    send_match_notification_email,
    send_trade_confirmed_email,
    send_rating_reminder_email,
    send_inactivity_warning_1m_email,
    send_books_delisted_email,
    send_account_deletion_email,
    send_account_deletion_export_email
)

@pytest.mark.django_db
class TestEmailHelpers:
    def test_send_verification_email(self):
        user = UserFactory()
        send_verification_email(user, "uid", "token")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Verify your BookForBook email address"
        assert user.email in mail.outbox[0].to

    def test_send_password_reset_email(self):
        user = UserFactory()
        send_password_reset_email(user, "uid", "token")
        assert len(mail.outbox) == 1
        assert "Reset your BookForBook password" in mail.outbox[0].subject

    def test_send_match_notification_email(self):
        user = UserFactory()
        match = MatchFactory(match_type="direct")
        send_match_notification_email(user, match)
        assert len(mail.outbox) == 1
        assert "new book match" in mail.outbox[0].subject

    def test_send_trade_confirmed_email(self):
        user = UserFactory()
        trade = TradeFactory()
        send_trade_confirmed_email(user, trade)
        assert len(mail.outbox) == 1
        assert "confirmed" in mail.outbox[0].subject.lower()

    def test_send_rating_reminder_email(self):
        user = UserFactory()
        trade = TradeFactory()
        send_rating_reminder_email(user, trade)
        assert len(mail.outbox) == 1
        assert "rate your" in mail.outbox[0].subject.lower()

    def test_send_inactivity_warning_1m_email(self):
        user = UserFactory()
        send_inactivity_warning_1m_email(user)
        assert len(mail.outbox) == 1
        assert "miss you" in mail.outbox[0].subject.lower()

    def test_send_books_delisted_email(self):
        user = UserFactory()
        send_books_delisted_email(user)
        assert len(mail.outbox) == 1
        assert "delisted" in mail.outbox[0].subject.lower()

    def test_send_account_deletion_email(self):
        user = UserFactory()
        send_account_deletion_email(user)
        assert len(mail.outbox) == 1
        assert "deletion initiated" in mail.outbox[0].subject.lower()

    def test_send_account_deletion_export_email(self):
        user = UserFactory()
        export_data = {"books": ["book1", "book2"]}
        send_account_deletion_export_email(user, export_data)
        assert len(mail.outbox) == 1
        assert len(mail.outbox[0].attachments) == 1
        assert mail.outbox[0].attachments[0][0] == "bookforbook-data-export.json"

from django.test import override_settings
from unittest.mock import patch
import pytest

from apps.accounts.services.admin_alerts import (
    notify_admin_on_email_verified,
    notify_admin_on_postal_verified,
    notify_admin_on_registration,
)
from apps.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


def _prepare_verified_user():
    user = UserFactory(email="member@bookforbook.com", username="member1")
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


@override_settings(
    ADMIN_ACCOUNT_ALERTS_ENABLED=True,
    ADMIN_ACCOUNT_ALERT_EMAIL="john@bookforbook.com",
    ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS=True,
    ADMIN_ACCOUNT_ALERT_TEST_DOMAINS=["example.com"],
)
def test_registration_alert_skips_test_domain():
    with patch("apps.accounts.services.admin_alerts.send_email") as send_email:
        user = UserFactory(email="user99@example.com", username="user99")

        sent = notify_admin_on_registration(user)

    assert sent is False
    send_email.assert_not_called()


@override_settings(
    ADMIN_ACCOUNT_ALERTS_ENABLED=True,
    ADMIN_ACCOUNT_ALERT_EMAIL="john@bookforbook.com",
    ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS=False,
)
def test_registration_alert_sends_for_non_test_user():
    with patch(
        "apps.accounts.services.admin_alerts.send_email", return_value=True
    ) as send_email:
        user = UserFactory(email="realuser@bookforbook.com", username="realuser")

        sent = notify_admin_on_registration(user)

    assert sent is True
    send_email.assert_called_once()


@override_settings(
    ADMIN_ACCOUNT_ALERTS_ENABLED=True,
    ADMIN_ACCOUNT_ALERT_EMAIL="john@bookforbook.com",
    ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS=False,
)
def test_email_verified_alert_sends():
    with patch(
        "apps.accounts.services.admin_alerts.send_email", return_value=True
    ) as send_email:
        user = _prepare_verified_user()

        sent = notify_admin_on_email_verified(user)

    assert sent is True
    send_email.assert_called_once()


@override_settings(
    ADMIN_ACCOUNT_ALERTS_ENABLED=True,
    ADMIN_ACCOUNT_ALERT_EMAIL="john@bookforbook.com",
    ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS=False,
)
def test_postal_verified_alert_includes_full_name_and_address():
    with patch(
        "apps.accounts.services.admin_alerts.send_email", return_value=True
    ) as send_email:
        user = _prepare_verified_user()
        user.full_name = "Reader One"
        user.address_line_1 = "123 MAIN ST"
        user.address_line_2 = "APT 2"
        user.city = "DENVER"
        user.state = "CO"
        user.zip_code = "80202-1234"
        user.save(
            update_fields=[
                "full_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "zip_code",
            ]
        )

        sent = notify_admin_on_postal_verified(user)

    assert sent is True
    send_email.assert_called_once()
    _, _, body = send_email.call_args[0]
    assert "Reader One" in body
    assert "123 MAIN ST" in body
    assert "DENVER, CO 80202-1234" in body

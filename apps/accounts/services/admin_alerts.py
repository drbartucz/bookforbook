import logging

from django.conf import settings

from apps.notifications.email import send_email

logger = logging.getLogger(__name__)


def _clean_values(values):
    return {value.strip().lower() for value in values if value and value.strip()}


def _is_test_account(user) -> bool:
    if not getattr(settings, "ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS", True):
        return False

    email = (user.email or "").strip().lower()
    username = (user.username or "").strip().lower()
    local_part, _, domain = email.partition("@")

    test_domains = _clean_values(
        getattr(settings, "ADMIN_ACCOUNT_ALERT_TEST_DOMAINS", [])
    )
    test_prefixes = _clean_values(
        getattr(settings, "ADMIN_ACCOUNT_ALERT_TEST_PREFIXES", [])
    )

    if domain and domain in test_domains:
        return True
    if any(local_part.startswith(prefix) for prefix in test_prefixes):
        return True
    if any(username.startswith(prefix) for prefix in test_prefixes):
        return True

    # Convenience fallback for common test aliases.
    return "+test" in local_part or local_part.startswith("test+")


def _send_admin_alert(user, subject: str, lines: list[str]) -> bool:
    if not getattr(settings, "ADMIN_ACCOUNT_ALERTS_ENABLED", True):
        return False

    recipient = getattr(settings, "ADMIN_ACCOUNT_ALERT_EMAIL", "")
    if not recipient:
        return False

    if _is_test_account(user):
        logger.info("Skipping admin account alert for test user %s", user.pk)
        return False

    return send_email(recipient, subject, "\n".join(lines))


def notify_admin_on_registration(user) -> bool:
    subject = f"[BookForBook] New registration: {user.email}"
    return _send_admin_alert(
        user,
        subject,
        [
            "A new user account has been registered.",
            "",
            f"User ID: {user.pk}",
            f"Email: {user.email}",
            f"Username: {user.username}",
            f"Account type: {user.account_type}",
            f"Institution name: {user.institution_name or '(none)'}",
            f"Institution URL: {user.institution_url or '(none)'}",
            f"Created at: {user.created_at.isoformat() if user.created_at else '(unknown)'}",
        ],
    )


def notify_admin_on_email_verified(user) -> bool:
    subject = f"[BookForBook] Email verified: {user.email}"
    return _send_admin_alert(
        user,
        subject,
        [
            "A user has verified their email address.",
            "",
            f"User ID: {user.pk}",
            f"Email: {user.email}",
            f"Username: {user.username}",
            f"Email verified at: {user.email_verified_at.isoformat() if user.email_verified_at else '(unknown)'}",
        ],
    )


def notify_admin_on_postal_verified(user) -> bool:
    subject = f"[BookForBook] USPS address verified: {user.email}"

    address_lines = [user.address_line_1]
    if user.address_line_2:
        address_lines.append(user.address_line_2)
    address_lines.append(f"{user.city}, {user.state} {user.zip_code}")

    return _send_admin_alert(
        user,
        subject,
        [
            "A user has verified their postal address with USPS.",
            "",
            f"User ID: {user.pk}",
            f"Email: {user.email}",
            f"Username: {user.username}",
            f"Full name: {user.full_name or '(none)'}",
            "Verified address:",
            *address_lines,
            f"Address verified at: {user.address_verified_at.isoformat() if user.address_verified_at else '(unknown)'}",
        ],
    )

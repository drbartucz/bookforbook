"""
Tasks for notifications — email + in-app.
"""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def send_verification_email(user_id: str, uid: str, token: str):
    """Send email verification link to a newly registered user."""
    logger.info("send_verification_email: starting for user_id=%s", user_id)
    from apps.accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_verification_email skipped: user %s not found", user_id
        )
        return
    from apps.notifications.email import send_verification_email as _send

    success = _send(user, uid, token)
    if success:
        logger.info("send_verification_email: sent to %s", user.email)
    else:
        logger.error("send_verification_email: failed for %s", user.email)


def send_password_reset_email(user_id: str, uid: str, token: str):
    """Send password reset email."""
    from apps.accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_password_reset_email skipped: user %s not found", user_id
        )
        return
    from apps.notifications.email import send_password_reset_email as _send

    _send(user, uid, token)


def send_admin_registration_alert(user_id: str):
    """Send admin alert when a new account is registered."""
    from apps.accounts.models import User
    from apps.accounts.services.admin_alerts import notify_admin_on_registration

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_admin_registration_alert skipped: user %s not found", user_id
        )
        return
    notify_admin_on_registration(user)


def send_admin_email_verified_alert(user_id: str):
    """Send admin alert when a user verifies email."""
    from apps.accounts.models import User
    from apps.accounts.services.admin_alerts import notify_admin_on_email_verified

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_admin_email_verified_alert skipped: user %s not found", user_id
        )
        return
    notify_admin_on_email_verified(user)


def send_admin_postal_verified_alert(user_id: str):
    """Send admin alert when a user verifies postal address with USPS."""
    from apps.accounts.models import User
    from apps.accounts.services.admin_alerts import notify_admin_on_postal_verified

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_admin_postal_verified_alert skipped: user %s not found", user_id
        )
        return
    notify_admin_on_postal_verified(user)


def send_match_notification(match_id: str):
    """Email + in-app notification for all participants in a new match."""
    from apps.matching.models import Match
    from apps.notifications.models import Notification

    try:
        match = Match.objects.prefetch_related("legs__sender", "legs__receiver").get(
            pk=match_id
        )
    except Match.DoesNotExist:
        logger.warning("send_match_notification skipped: match %s not found", match_id)
        return

    # Collect unique senders (they need to accept)
    participants = set()
    for leg in match.legs.all():
        participants.add(leg.sender)

    for user in participants:
        # In-app notification
        Notification.objects.create(
            user=user,
            notification_type="new_match",
            title="New book match!",
            body=(
                "You have a new book match. Log in to accept or decline."
                if match.match_type == "direct"
                else f"You are part of a {match.legs.count()}-way exchange ring!"
            ),
            metadata={"match_id": str(match.pk)},
        )

        # Email
        from apps.notifications.email import send_match_notification_email

        send_match_notification_email(user, match)


def send_trade_confirmed_notification(trade_id: str):
    """Email all parties when a trade is confirmed."""
    from apps.trading.models import Trade

    try:
        trade = Trade.objects.prefetch_related(
            "shipments__sender", "shipments__receiver"
        ).get(pk=trade_id)
    except Trade.DoesNotExist:
        logger.warning(
            "send_trade_confirmed_notification skipped: trade %s not found", trade_id
        )
        return

    parties = set()
    for shipment in trade.shipments.all():
        parties.add(shipment.sender)
        parties.add(shipment.receiver)

    for user in parties:
        from apps.notifications.email import send_trade_confirmed_email

        send_trade_confirmed_email(user, trade)


def send_rating_reminder(trade_id: str, user_id: str):
    """Send a weekly rating reminder to a specific user for a trade."""
    from apps.accounts.models import User
    from apps.trading.models import Trade

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_rating_reminder skipped: user %s not found", user_id)
        return

    try:
        trade = Trade.objects.get(pk=trade_id)
    except Trade.DoesNotExist:
        logger.warning("send_rating_reminder skipped: trade %s not found", trade_id)
        return
    from apps.notifications.email import send_rating_reminder_email

    send_rating_reminder_email(user, trade)


def send_inactivity_warning_1m(user_id: str):
    """Send 1-month inactivity warning."""
    from apps.accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_inactivity_warning_1m skipped: user %s not found", user_id)
        return
    from apps.notifications.email import send_inactivity_warning_1m_email

    send_inactivity_warning_1m_email(user)
    user.inactivity_warned_1m = timezone.now()
    user.save(update_fields=["inactivity_warned_1m"])


def send_inactivity_warning_2m(user_id: str):
    """Send 2-month inactivity warning."""
    from apps.accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_inactivity_warning_2m skipped: user %s not found", user_id)
        return
    from apps.notifications.email import send_inactivity_warning_2m_email

    send_inactivity_warning_2m_email(user)
    user.inactivity_warned_2m = timezone.now()
    user.save(update_fields=["inactivity_warned_2m"])


def send_books_delisted_notification(user_id: str):
    """Send notification that books have been delisted."""
    from apps.accounts.models import User
    from apps.notifications.models import Notification

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_books_delisted_notification skipped: user %s not found", user_id
        )
        return
    from apps.notifications.email import send_books_delisted_email

    send_books_delisted_email(user)
    Notification.objects.create(
        user=user,
        notification_type="books_delisted",
        title="Your books have been delisted",
        body="Your books have been temporarily removed due to inactivity. Log in to re-list them.",
    )


def send_account_deletion_initiated(user_id: str):
    """Send account deletion confirmation email and GDPR export."""
    from apps.accounts.models import User
    from apps.accounts.views import _build_user_export
    from apps.notifications.email import (
        send_account_deletion_email,
        send_account_deletion_export_email,
    )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_account_deletion_initiated skipped: user %s not found", user_id
        )
        return
    export_data = _build_user_export(user)

    send_account_deletion_email(user)
    send_account_deletion_export_email(user, export_data)


def finalize_scheduled_account_deletions(grace_days: int = 30):
    """Finalize pending deletions by anonymizing personal data after grace period."""
    from apps.accounts.models import User
    from apps.inventory.models import UserBook, WishlistItem

    users = User.objects.filter(
        is_active=False,
        deletion_requested_at__isnull=False,
        deletion_requested_at__lte=timezone.now() - timedelta(days=grace_days),
        deletion_completed_at__isnull=True,
    )

    for user in users:
        user.set_unusable_password()
        user.email = f"deleted-{user.pk}@deleted.local"
        user.username = f"deleted-{str(user.pk).replace('-', '')[:12]}"
        user.email_verified = False
        user.email_verified_at = None

        # Remove personally identifiable profile/address data.
        user.full_name = ""
        user.address_line_1 = ""
        user.address_line_2 = ""
        user.city = ""
        user.state = ""
        user.zip_code = ""
        user.institution_name = ""
        user.institution_url = ""
        user.address_verification_status = User.AddressVerificationStatus.UNVERIFIED
        user.address_verified_at = None

        # Remove active listing/wishlist data tied to the deleted account.
        UserBook.objects.filter(user=user).delete()
        WishlistItem.objects.filter(user=user).delete()

        user.deletion_completed_at = timezone.now()
        user.save(
            update_fields=[
                "password",
                "email",
                "username",
                "email_verified",
                "email_verified_at",
                "full_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "zip_code",
                "institution_name",
                "institution_url",
                "address_verification_status",
                "address_verified_at",
                "deletion_completed_at",
                "updated_at",
            ]
        )


def check_inactivity():
    """
    Daily task: scan all users and send inactivity warnings / delist books.

    Timeline:
    - 1 month inactive → send warning email (if not yet sent)
    - 2 months inactive → send "delist soon" email (if 1m warning was sent)
    - 3 months inactive → delist books (if 2m warning was sent)
    """
    from apps.accounts.models import User
    from apps.inventory.models import UserBook
    from datetime import timedelta
    from django_q.tasks import async_task

    now = timezone.now()
    one_month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)
    three_months_ago = now - timedelta(days=90)

    # Users inactive for 3+ months → delist (regardless of whether warning emails were sent)
    to_delist = User.objects.filter(
        is_active=True,
        account_type=User.AccountType.INDIVIDUAL,
        last_active_at__lt=three_months_ago,
        books_delisted_at__isnull=True,
    )
    for user in to_delist:
        UserBook.objects.filter(user=user, status=UserBook.Status.AVAILABLE).update(
            status=UserBook.Status.DELISTED
        )
        user.books_delisted_at = now
        user.save(update_fields=["books_delisted_at"])
        async_task(
            "apps.notifications.tasks.send_books_delisted_notification", str(user.pk)
        )
        logger.info("Delisted books for inactive user %s", user.pk)

    # Users inactive for 2+ months with 1m warning sent → send 2m warning
    to_warn_2m = User.objects.filter(
        is_active=True,
        account_type=User.AccountType.INDIVIDUAL,
        last_active_at__lt=two_months_ago,
        inactivity_warned_1m__isnull=False,
        inactivity_warned_2m__isnull=True,
        books_delisted_at__isnull=True,
    )
    for user in to_warn_2m:
        async_task("apps.notifications.tasks.send_inactivity_warning_2m", str(user.pk))
        logger.info("Sent 2m inactivity warning to user %s", user.pk)

    # Users inactive for 1+ month with no warning sent → send 1m warning
    to_warn_1m = User.objects.filter(
        is_active=True,
        account_type=User.AccountType.INDIVIDUAL,
        last_active_at__lt=one_month_ago,
        inactivity_warned_1m__isnull=True,
        books_delisted_at__isnull=True,
    )
    for user in to_warn_1m:
        async_task("apps.notifications.tasks.send_inactivity_warning_1m", str(user.pk))
        logger.info("Sent 1m inactivity warning to user %s", user.pk)


def reconcile_inventory_user_ownership():
    """
    Nightly maintenance for inventory ownership consistency.

    - Delist AVAILABLE user books that belong to inactive users.
    - Deactivate active wishlist items that belong to inactive users.
    - Delete orphaned user books/wishlist rows whose user_id no longer exists.
      (Should be rare because FKs use CASCADE, but this keeps data healthy
      if rows were imported outside normal ORM constraints.)
    """
    from apps.accounts.models import User
    from apps.inventory.models import UserBook, WishlistItem

    valid_user_ids = User.objects.values_list("id", flat=True)

    orphaned_user_books_qs = UserBook.objects.exclude(user_id__in=valid_user_ids)
    orphaned_wishlist_qs = WishlistItem.objects.exclude(user_id__in=valid_user_ids)

    orphaned_user_books_deleted = orphaned_user_books_qs.count()
    orphaned_wishlist_deleted = orphaned_wishlist_qs.count()

    # count() first so logs reflect row counts rather than Django's delete tuple
    if orphaned_user_books_deleted:
        orphaned_user_books_qs.delete()
    if orphaned_wishlist_deleted:
        orphaned_wishlist_qs.delete()

    delisted_books = UserBook.objects.filter(
        user__is_active=False,
        status=UserBook.Status.AVAILABLE,
    ).update(status=UserBook.Status.DELISTED)

    deactivated_wishlist = WishlistItem.objects.filter(
        user__is_active=False,
        is_active=True,
    ).update(is_active=False)

    logger.info(
        (
            "Inventory ownership reconcile complete: delisted_books=%s, "
            "deactivated_wishlist=%s, orphaned_user_books_deleted=%s, "
            "orphaned_wishlist_deleted=%s"
        ),
        delisted_books,
        deactivated_wishlist,
        orphaned_user_books_deleted,
        orphaned_wishlist_deleted,
    )

    return {
        "delisted_books": delisted_books,
        "deactivated_wishlist": deactivated_wishlist,
        "orphaned_user_books_deleted": orphaned_user_books_deleted,
        "orphaned_wishlist_deleted": orphaned_wishlist_deleted,
    }

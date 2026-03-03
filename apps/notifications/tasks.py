"""
Celery tasks for notifications — email + in-app.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id: str, uid: str, token: str):
    """Send email verification link to a newly registered user."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_verification_email as _send
        _send(user, uid, token)
    except Exception as exc:
        logger.exception('send_verification_email failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: str, uid: str, token: str):
    """Send password reset email."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_password_reset_email as _send
        _send(user, uid, token)
    except Exception as exc:
        logger.exception('send_password_reset_email failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_match_notification(self, match_id: str):
    """Email + in-app notification for all participants in a new match."""
    try:
        from apps.matching.models import Match
        from apps.notifications.models import Notification

        match = Match.objects.prefetch_related('legs__sender', 'legs__receiver').get(pk=match_id)

        # Collect unique senders (they need to accept)
        participants = set()
        for leg in match.legs.all():
            participants.add(leg.sender)

        for user in participants:
            # In-app notification
            Notification.objects.create(
                user=user,
                notification_type='new_match',
                title='New book match!',
                body=(
                    'You have a new book match. Log in to accept or decline.'
                    if match.match_type == 'direct'
                    else f'You are part of a {match.legs.count()}-way exchange ring!'
                ),
                metadata={'match_id': str(match.pk)},
            )

            # Email
            from apps.notifications.email import send_match_notification_email
            send_match_notification_email(user, match)

    except Exception as exc:
        logger.exception('send_match_notification failed for match %s', match_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_trade_confirmed_notification(self, trade_id: str):
    """Email all parties when a trade is confirmed."""
    try:
        from apps.trading.models import Trade
        trade = Trade.objects.prefetch_related('shipments__sender', 'shipments__receiver').get(pk=trade_id)

        parties = set()
        for shipment in trade.shipments.all():
            parties.add(shipment.sender)
            parties.add(shipment.receiver)

        for user in parties:
            from apps.notifications.email import send_trade_confirmed_email
            send_trade_confirmed_email(user, trade)

    except Exception as exc:
        logger.exception('send_trade_confirmed_notification failed for trade %s', trade_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def send_rating_reminder(self, trade_id: str, user_id: str):
    """Send a weekly rating reminder to a specific user for a trade."""
    try:
        from apps.accounts.models import User
        from apps.trading.models import Trade
        user = User.objects.get(pk=user_id)
        trade = Trade.objects.get(pk=trade_id)
        from apps.notifications.email import send_rating_reminder_email
        send_rating_reminder_email(user, trade)
    except Exception as exc:
        logger.exception('send_rating_reminder failed for trade %s, user %s', trade_id, user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inactivity_warning_1m(self, user_id: str):
    """Send 1-month inactivity warning."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_inactivity_warning_1m_email
        send_inactivity_warning_1m_email(user)
        user.inactivity_warned_1m = timezone.now()
        user.save(update_fields=['inactivity_warned_1m'])
    except Exception as exc:
        logger.exception('send_inactivity_warning_1m failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inactivity_warning_2m(self, user_id: str):
    """Send 2-month inactivity warning."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_inactivity_warning_2m_email
        send_inactivity_warning_2m_email(user)
        user.inactivity_warned_2m = timezone.now()
        user.save(update_fields=['inactivity_warned_2m'])
    except Exception as exc:
        logger.exception('send_inactivity_warning_2m failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_books_delisted_notification(self, user_id: str):
    """Send notification that books have been delisted."""
    try:
        from apps.accounts.models import User
        from apps.notifications.models import Notification
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_books_delisted_email
        send_books_delisted_email(user)
        Notification.objects.create(
            user=user,
            notification_type='books_delisted',
            title='Your books have been delisted',
            body='Your books have been temporarily removed due to inactivity. Log in to re-list them.',
        )
    except Exception as exc:
        logger.exception('send_books_delisted_notification failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_account_deletion_initiated(self, user_id: str):
    """Send account deletion confirmation email with data export."""
    try:
        from apps.accounts.models import User
        user = User.objects.get(pk=user_id)
        from apps.notifications.email import send_account_deletion_email
        send_account_deletion_email(user)
    except Exception as exc:
        logger.exception('send_account_deletion_initiated failed for user %s', user_id)
        raise self.retry(exc=exc)


@shared_task
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

    now = timezone.now()
    one_month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)
    three_months_ago = now - timedelta(days=90)

    # Users inactive for 3+ months with 2m warning sent → delist
    to_delist = User.objects.filter(
        is_active=True,
        last_active_at__lt=three_months_ago,
        inactivity_warned_2m__isnull=False,
        books_delisted_at__isnull=True,
    )
    for user in to_delist:
        UserBook.objects.filter(user=user, status=UserBook.Status.AVAILABLE).update(
            status=UserBook.Status.DELISTED
        )
        user.books_delisted_at = now
        user.save(update_fields=['books_delisted_at'])
        send_books_delisted_notification.delay(str(user.pk))
        logger.info('Delisted books for inactive user %s', user.pk)

    # Users inactive for 2+ months with 1m warning sent → send 2m warning
    to_warn_2m = User.objects.filter(
        is_active=True,
        last_active_at__lt=two_months_ago,
        inactivity_warned_1m__isnull=False,
        inactivity_warned_2m__isnull=True,
        books_delisted_at__isnull=True,
    )
    for user in to_warn_2m:
        send_inactivity_warning_2m.delay(str(user.pk))
        logger.info('Sent 2m inactivity warning to user %s', user.pk)

    # Users inactive for 1+ month with no warning sent → send 1m warning
    to_warn_1m = User.objects.filter(
        is_active=True,
        last_active_at__lt=one_month_ago,
        inactivity_warned_1m__isnull=True,
        books_delisted_at__isnull=True,
    )
    for user in to_warn_1m:
        send_inactivity_warning_1m.delay(str(user.pk))
        logger.info('Sent 1m inactivity warning to user %s', user.pk)

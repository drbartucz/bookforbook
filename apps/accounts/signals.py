import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    """
    Update last_active_at and re-list delisted books when a user logs in.
    Also clear inactivity warning timestamps.
    """
    from apps.inventory.models import UserBook

    now = timezone.now()
    update_fields = ['last_active_at']

    # Re-list delisted books if any
    if user.books_delisted_at:
        relisted_count = UserBook.objects.filter(
            user=user, status=UserBook.Status.DELISTED
        ).update(status=UserBook.Status.AVAILABLE)

        if relisted_count > 0:
            logger.info(
                'Re-listed %d books for user %s after login',
                relisted_count,
                user.pk,
            )
            # Trigger matching scan for newly available books
            try:
                from django_q.tasks import async_task
                async_task('apps.matching.tasks.run_matching_for_relisted_books', str(user.pk))
            except Exception:
                logger.exception('Failed to queue matching for relisted books, user %s', user.pk)

        user.books_delisted_at = None
        user.inactivity_warned_1m = None
        user.inactivity_warned_2m = None
        update_fields += ['books_delisted_at', 'inactivity_warned_1m', 'inactivity_warned_2m']

    user.last_active_at = now
    user.save(update_fields=update_fields)

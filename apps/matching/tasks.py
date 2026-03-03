import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_matching_for_new_item(self, user_book_id=None, wishlist_item_id=None):
    """
    Triggered when a new UserBook or WishlistItem is added.
    Runs direct matching (and optionally ring detection) for the new item.
    """
    try:
        from apps.matching.services.direct_matcher import run_direct_matching

        if user_book_id:
            from apps.inventory.models import UserBook
            try:
                user_book = UserBook.objects.select_related('user', 'book').get(pk=user_book_id)
                matches = run_direct_matching(user_book=user_book)
                logger.info('Direct matching for UserBook %s found %d match(es)', user_book_id, len(matches))
            except UserBook.DoesNotExist:
                logger.warning('UserBook %s not found for matching', user_book_id)

        elif wishlist_item_id:
            from apps.inventory.models import WishlistItem
            try:
                item = WishlistItem.objects.get(pk=wishlist_item_id)
                # Find books available that this user wants
                from apps.inventory.models import UserBook
                available = UserBook.objects.filter(
                    book=item.book,
                    status=UserBook.Status.AVAILABLE,
                ).select_related('user', 'book')
                total = 0
                for ub in available:
                    matches = run_direct_matching(user_book=ub)
                    total += len(matches)
                logger.info('Direct matching for WishlistItem %s found %d match(es)', wishlist_item_id, total)
            except WishlistItem.DoesNotExist:
                logger.warning('WishlistItem %s not found for matching', wishlist_item_id)

    except Exception as exc:
        logger.exception('Error in run_matching_for_new_item')
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_matching_for_relisted_books(self, user_id: str):
    """
    Triggered when a user logs back in after being delisted.
    Runs matching for all their newly available books.
    """
    try:
        from apps.inventory.models import UserBook
        from apps.matching.services.direct_matcher import run_direct_matching

        books = UserBook.objects.filter(
            user_id=user_id,
            status=UserBook.Status.AVAILABLE,
        ).select_related('user', 'book')

        total = 0
        for ub in books:
            matches = run_direct_matching(user_book=ub)
            total += len(matches)

        logger.info('Relisted-books matching for user %s found %d match(es)', user_id, total)
    except Exception as exc:
        logger.exception('Error in run_matching_for_relisted_books')
        raise self.retry(exc=exc)


@shared_task
def run_periodic_matching():
    """
    Periodic full scan — runs every 6 hours.
    Runs both direct matching and ring detection.
    """
    logger.info('Starting periodic matching scan')
    try:
        from apps.matching.services.direct_matcher import run_direct_matching
        direct_matches = run_direct_matching()
        logger.info('Periodic direct matching found %d new match(es)', len(direct_matches))
    except Exception:
        logger.exception('Error in periodic direct matching')

    try:
        from apps.matching.services.ring_detector import run_ring_detection
        ring_matches = run_ring_detection()
        logger.info('Periodic ring detection found %d new ring match(es)', len(ring_matches))
    except Exception:
        logger.exception('Error in periodic ring detection')


@shared_task
def expire_old_matches():
    """
    Periodic task — expire pending/proposed matches past their expiry time.
    """
    from apps.matching.models import Match

    now = timezone.now()
    expired_count = Match.objects.filter(
        status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        expires_at__lt=now,
    ).update(status=Match.Status.EXPIRED)

    if expired_count:
        logger.info('Expired %d match(es)', expired_count)

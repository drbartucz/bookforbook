import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def run_matching_for_new_item(user_book_id=None, wishlist_item_id=None):
    """
    Triggered when a new UserBook or WishlistItem is added.
    Runs direct matching (and optionally ring detection) for the new item.
    """
    from apps.matching.services.direct_matcher import run_direct_matching

    if user_book_id:
        from apps.inventory.models import UserBook

        try:
            user_book = UserBook.objects.select_related("user", "book").get(
                pk=user_book_id
            )
            matches = run_direct_matching(user_book=user_book)
            logger.info(
                "Direct matching for UserBook %s found %d match(es)",
                user_book_id,
                len(matches),
            )
        except UserBook.DoesNotExist:
            logger.warning("UserBook %s not found for matching", user_book_id)

    elif wishlist_item_id:
        from apps.inventory.models import WishlistItem

        try:
            item = WishlistItem.objects.get(pk=wishlist_item_id)
            from apps.inventory.models import UserBook
            from apps.matching.services.preference_filters import wishlist_allows_book

            available = UserBook.objects.filter(
                status=UserBook.Status.AVAILABLE,
            ).select_related("user", "book")

            available = [ub for ub in available if wishlist_allows_book(item, ub.book)]
            total = 0
            for ub in available:
                matches = run_direct_matching(user_book=ub)
                total += len(matches)
            logger.info(
                "Direct matching for WishlistItem %s found %d match(es)",
                wishlist_item_id,
                total,
            )
        except WishlistItem.DoesNotExist:
            logger.warning("WishlistItem %s not found for matching", wishlist_item_id)


def run_matching_for_relisted_books(user_id: str):
    """
    Triggered when a user logs back in after being delisted.
    Runs matching for all their newly available books.
    """
    from apps.inventory.models import UserBook
    from apps.matching.services.direct_matcher import run_direct_matching

    books = UserBook.objects.filter(
        user_id=user_id,
        status=UserBook.Status.AVAILABLE,
    ).select_related("user", "book")

    total = 0
    for ub in books:
        matches = run_direct_matching(user_book=ub)
        total += len(matches)

    logger.info(
        "Relisted-books matching for user %s found %d match(es)", user_id, total
    )


def run_periodic_matching():
    """
    Periodic full scan — runs every 6 hours.
    Runs both direct matching and ring detection.
    """
    logger.info("Starting periodic matching scan")
    try:
        from apps.matching.services.direct_matcher import run_direct_matching

        direct_matches = run_direct_matching()
        logger.info(
            "Periodic direct matching found %d new match(es)", len(direct_matches)
        )
    except Exception:
        logger.exception("Error in periodic direct matching")

    try:
        from apps.matching.services.ring_detector import run_ring_detection

        ring_matches = run_ring_detection()
        logger.info(
            "Periodic ring detection found %d new ring match(es)", len(ring_matches)
        )
    except Exception:
        logger.exception("Error in periodic ring detection")


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
        logger.info("Expired %d match(es)", expired_count)


def retry_ring_after_decline_task(match_id: str, declining_user_id: str):
    """
    Async job: attempt to reform a ring after a decline and notify participants.
    """
    from apps.accounts.models import User
    from apps.matching.models import Match

    try:
        match = Match.objects.prefetch_related("legs").get(pk=match_id)
    except Match.DoesNotExist:
        logger.warning("Ring retry skipped: match %s not found", match_id)
        return

    if match.match_type != Match.MatchType.RING:
        logger.info("Ring retry skipped: match %s is not a ring", match_id)
        return

    try:
        declining_user = User.objects.get(pk=declining_user_id)
    except User.DoesNotExist:
        logger.warning(
            "Ring retry skipped: declining user %s not found", declining_user_id
        )
        return

    try:
        from apps.matching.services.ring_detector import retry_ring_after_decline

        new_match = retry_ring_after_decline(match, declining_user)
        if new_match:
            from django_q.tasks import async_task

            async_task(
                "apps.notifications.tasks.send_match_notification",
                str(new_match.pk),
            )
            return
    except Exception:
        logger.exception(
            "Error during async ring retry after decline for match %s", match.pk
        )
        return

    participant_ids = list(
        match.legs.exclude(sender=declining_user)
        .values_list("sender_id", flat=True)
        .distinct()
    )
    participants = User.objects.filter(pk__in=participant_ids)

    try:
        from apps.notifications.models import Notification

        notifications = [
            Notification(
                user=participant,
                notification_type="ring_cancelled",
                title="Exchange ring cancelled",
                body=(
                    "An exchange ring you were part of could not be completed. "
                    "Your books are available for new matches."
                ),
            )
            for participant in participants
        ]
        if notifications:
            Notification.objects.bulk_create(notifications)
    except Exception:
        logger.exception(
            "Failed to notify ring participants after decline for match %s", match.pk
        )

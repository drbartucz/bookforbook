"""
Direct match detection service.

A direct match: User A has a book User B wants, AND User B has a book User A wants.
Both books must meet the minimum condition requirement.
"""

import logging
from typing import Optional

from django.db import transaction
from django.db.models import Q

from apps.inventory.models import UserBook, WishlistItem, condition_meets_minimum
from apps.matching.models import Match, MatchLeg
from apps.matching.services.prioritization import priority_ordered_wishlist_entries
from apps.matching.services.preference_filters import wishlist_allows_book

logger = logging.getLogger(__name__)


def count_active_matches_for_user(user) -> int:
    """Count the number of active (pending/proposed) matches a user is involved in."""
    match_count = (
        MatchLeg.objects.filter(
            sender=user,
            match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        )
        .values("match")
        .distinct()
        .count()
    )

    proposal_count = 0
    try:
        from apps.trading.models import TradeProposal

        proposal_count = (
            TradeProposal.objects.filter(
                proposer=user,
                status__in=["pending", "accepted"],
            ).count()
            + TradeProposal.objects.filter(
                recipient=user,
                status__in=["pending", "accepted"],
            ).count()
        )
    except Exception:
        pass

    return match_count + proposal_count


def user_at_match_limit(user) -> bool:
    """Return True if the user has reached their active match limit."""
    return count_active_matches_for_user(user) >= user.max_active_matches


def _active_match_exists_for_user_book(user_book_id) -> bool:
    """Check if the given UserBook is already in an active match."""
    return MatchLeg.objects.filter(
        user_book_id=user_book_id,
        match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
    ).exists()


def _lock_user_books(*book_ids: int) -> dict[int, UserBook]:
    """Lock user-book rows in deterministic order and return by id."""
    unique_ids = sorted(set(book_ids))
    locked_books = (
        UserBook.objects.select_for_update()
        .select_related("user", "book")
        .filter(pk__in=unique_ids)
    )
    return {book.pk: book for book in locked_books}


def run_direct_matching(user_book: Optional[UserBook] = None) -> list[Match]:
    """
    Run direct match detection.

    If user_book is provided, only scan for matches involving that specific book.
    Otherwise, scan all available books for matches.

    Returns a list of newly created Match objects.
    """
    created_matches = []

    if user_book is not None:
        # Focused scan: find matches for this specific book
        candidates = (
            [user_book] if user_book.status == UserBook.Status.AVAILABLE else []
        )
    else:
        # Full scan: all available books
        candidates = list(
            UserBook.objects.filter(
                status=UserBook.Status.AVAILABLE,
            ).select_related("user", "book")
        )

    logger.info("Running direct matching over %d candidate books", len(candidates))

    for book_a in candidates:
        user_a = book_a.user

        # Skip institutional users (they don't trade)
        if user_a.is_institutional:
            continue

        # Skip if book is already in an active match
        if _active_match_exists_for_user_book(book_a.pk):
            continue

        # Skip if user is at their match limit
        if user_at_match_limit(user_a):
            continue

        # Find users who want book_a (condition met)
        wishlist_entries = (
            WishlistItem.objects.filter(
                is_active=True,
                user__email_verified=True,
                user__is_active=True,
            )
            .filter(
                Q(
                    edition_preference=WishlistItem.EditionPreference.EXACT,
                    book=book_a.book,
                )
                | ~Q(edition_preference=WishlistItem.EditionPreference.EXACT)
            )
            .select_related("user", "book")
            .exclude(user=user_a)
        )
        wishlist_entries = priority_ordered_wishlist_entries(wishlist_entries)

        for wish_b in wishlist_entries:
            user_b = wish_b.user

            if not wishlist_allows_book(wish_b, book_a.book):
                continue

            # Skip institutional users
            if user_b.is_institutional:
                continue

            # Check if book_a meets user_b's minimum condition
            if not condition_meets_minimum(book_a.condition, wish_b.min_condition):
                continue

            # Skip if user_b is at their match limit
            if user_at_match_limit(user_b):
                continue

            # Find books that user_a wants that user_b has available
            match_book_b = _find_book_for_trade(user_a=user_a, user_b=user_b)
            if match_book_b is None:
                continue

            # Create the direct match under row locks to avoid races across workers.
            match = _create_direct_match_with_locks(
                user_a, user_b, book_a, match_book_b
            )
            if match:
                created_matches.append(match)
                logger.info(
                    "Created direct match %s: %s ↔ %s",
                    match.pk,
                    user_a.username,
                    user_b.username,
                )

                # Notify asynchronously
                try:
                    from django_q.tasks import async_task

                    async_task(
                        "apps.notifications.tasks.send_match_notification",
                        str(match.pk),
                    )
                except Exception:
                    logger.exception(
                        "Failed to queue match notification for %s", match.pk
                    )

                # book_a is now committed to this match — stop looking for
                # further recipients so one copy is never double-matched.
                break

    return created_matches


def _find_book_for_trade(user_a, user_b) -> Optional[UserBook]:
    """
    Find an available book that user_b has and user_a wants.
    Returns the first qualifying UserBook, or None.
    """
    wishlist_a = WishlistItem.objects.filter(
        user=user_a,
        is_active=True,
    ).select_related("book")
    wishlist_a = priority_ordered_wishlist_entries(wishlist_a)

    candidates = UserBook.objects.filter(
        user=user_b,
        status=UserBook.Status.AVAILABLE,
    ).select_related("book")

    for wish in wishlist_a:
        for candidate in candidates:
            if not wishlist_allows_book(wish, candidate.book):
                continue
            if condition_meets_minimum(candidate.condition, wish.min_condition):
                return candidate

    return None


def _duplicate_match_exists(user_a, user_b, book_a: UserBook, book_b: UserBook) -> bool:
    """Check if an equivalent active direct match already exists."""
    existing = MatchLeg.objects.filter(
        match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
        match__match_type=Match.MatchType.DIRECT,
        user_book=book_a,
        sender=user_a,
        receiver=user_b,
    ).exists()
    return existing


@transaction.atomic
def _create_direct_match_with_locks(
    user_a, user_b, book_a: UserBook, book_b: UserBook
) -> Optional[Match]:
    """Re-check and create a direct match while holding row locks on both books."""
    locked_books = _lock_user_books(book_a.pk, book_b.pk)
    locked_book_a = locked_books.get(book_a.pk)
    locked_book_b = locked_books.get(book_b.pk)

    if not locked_book_a or not locked_book_b:
        return None

    if (
        locked_book_a.status != UserBook.Status.AVAILABLE
        or locked_book_b.status != UserBook.Status.AVAILABLE
    ):
        return None

    if _active_match_exists_for_user_book(locked_book_a.pk):
        return None

    if _active_match_exists_for_user_book(locked_book_b.pk):
        return None

    if _duplicate_match_exists(user_a, user_b, locked_book_a, locked_book_b):
        return None

    if user_at_match_limit(user_a) or user_at_match_limit(user_b):
        return None

    return _create_direct_match(user_a, user_b, locked_book_a, locked_book_b)


@transaction.atomic
def _create_direct_match(
    user_a, user_b, book_a: UserBook, book_b: UserBook
) -> Optional[Match]:
    """Create a direct Match with two MatchLegs."""
    try:
        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        # Leg 0: A sends book_a to B
        MatchLeg.objects.create(
            match=match,
            sender=user_a,
            receiver=user_b,
            user_book=book_a,
            position=0,
        )
        # Leg 1: B sends book_b to A
        MatchLeg.objects.create(
            match=match,
            sender=user_b,
            receiver=user_a,
            user_book=book_b,
            position=1,
        )
        return match
    except Exception:
        logger.exception(
            "Failed to create direct match between %s and %s", user_a.pk, user_b.pk
        )
        return None

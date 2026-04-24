"""
Exchange ring detection using DFS-based cycle finding.

A ring match: A→B→C→A (3-5 participants), where each sends a book the next wants.
"""

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import UserBook, WishlistItem, condition_meets_minimum
from apps.matching.models import Match, MatchLeg
from apps.matching.services.direct_matcher import (
    _active_match_exists_for_user_book,
    user_at_match_limit,
)
from apps.matching.services.prioritization import (
    condition_priority_value,
    priority_ordered_wishlist_entries,
)
from apps.matching.services.preference_filters import wishlist_allows_book

logger = logging.getLogger(__name__)

MIN_RING_SIZE = 3
MAX_RING_SIZE = 5


def _get_age_cutoff():
    """Return the earliest created_at timestamp that qualifies for matching."""
    hours = getattr(settings, "MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS", 48)
    return timezone.now() - timedelta(hours=hours)


def _build_trade_graph() -> tuple[dict, dict]:
    """
    Build a directed graph where edge A→B means A has a book that B wants.

    Returns:
        graph: dict mapping user_id → list of (user_id, user_book_id, wishlist_item_id)
        user_books: dict mapping user_id → list of available UserBook objects
    """
    cutoff = _get_age_cutoff()

    # Fetch all active wishlists (excluding institutional users and new accounts)
    wishlist_items = WishlistItem.objects.filter(
        is_active=True,
        user__email_verified=True,
        user__is_active=True,
        user__account_type="individual",
        user__created_at__lte=cutoff,
    ).select_related("user", "book")
    wishlist_items = priority_ordered_wishlist_entries(wishlist_items)

    # Build a per-user list of active wishlist items.
    wants: dict[str, list[WishlistItem]] = defaultdict(list)
    for w in wishlist_items:
        wants[str(w.user_id)].append(w)

    # Fetch all available books for individual users (excluding new accounts)
    available_books = UserBook.objects.filter(
        status=UserBook.Status.AVAILABLE,
        user__email_verified=True,
        user__is_active=True,
        user__account_type="individual",
        user__created_at__lte=cutoff,
    ).select_related("user", "book")

    # Index by user_id → list of UserBook
    user_books_map: dict[str, list[UserBook]] = defaultdict(list)
    for ub in available_books:
        user_books_map[str(ub.user_id)].append(ub)

    # Build directed graph: A→B if A has something B wants (condition met)
    graph: dict[str, list[tuple]] = defaultdict(list)

    for sender_id, books in user_books_map.items():
        sender_edges = []
        for ub in books:
            if _active_match_exists_for_user_book(ub.pk):
                continue
            for receiver_id, receiver_wants in wants.items():
                if receiver_id == sender_id:
                    continue
                for wish in receiver_wants:
                    if wishlist_allows_book(wish, ub.book) and condition_meets_minimum(
                        ub.condition, wish.min_condition
                    ):
                        priority_key = (
                            wish.created_at,
                            condition_priority_value(wish.min_condition),
                            str(wish.pk),
                            str(ub.pk),
                            receiver_id,
                        )
                        sender_edges.append((priority_key, receiver_id, str(ub.pk)))
                        break

        sender_edges.sort(key=lambda edge: edge[0])
        graph[sender_id].extend(
            (receiver_id, book_id) for _, receiver_id, book_id in sender_edges
        )

    return graph, user_books_map


def run_ring_detection() -> list[Match]:
    """
    Find exchange rings of length 3-5 among users.
    Creates Match records for each valid ring found.
    Returns list of created Match objects.
    """
    graph, user_books_map = _build_trade_graph()

    if len(graph) < MIN_RING_SIZE:
        logger.info("Not enough users for ring detection (%d users)", len(graph))
        return []

    created_matches = []
    seen_cycles: set[frozenset] = set()

    all_nodes = list(graph.keys())

    for start_node in all_nodes:
        cycles = _find_cycles_from(start_node, graph, MIN_RING_SIZE, MAX_RING_SIZE)
        for cycle in cycles:
            cycle_key = frozenset(cycle)
            if cycle_key in seen_cycles:
                continue
            seen_cycles.add(cycle_key)

            match = _try_create_ring_match(cycle, graph, user_books_map)
            if match:
                created_matches.append(match)
                logger.info(
                    "Created ring match %s with %d participants", match.pk, len(cycle)
                )
                try:
                    from django_q.tasks import async_task

                    async_task(
                        "apps.notifications.tasks.send_match_notification",
                        str(match.pk),
                    )
                except Exception:
                    logger.exception(
                        "Failed to queue ring match notification for %s", match.pk
                    )

    return created_matches


def _find_cycles_from(
    start: str,
    graph: dict,
    min_len: int,
    max_len: int,
) -> list[list[str]]:
    """
    DFS-based cycle detection starting from `start`.
    Returns cycles (lists of user_ids) of length min_len to max_len.
    """
    cycles = []
    path = [start]
    visited_in_path = {start}

    def dfs(current: str, depth: int):
        if depth > max_len:
            return
        for neighbor, _book_id in graph.get(current, []):
            if neighbor == start and depth >= min_len:
                # Found a valid cycle
                cycles.append(list(path))
            elif neighbor not in visited_in_path and depth < max_len:
                path.append(neighbor)
                visited_in_path.add(neighbor)
                dfs(neighbor, depth + 1)
                path.pop()
                visited_in_path.remove(neighbor)

    dfs(start, 1)
    return cycles


def _try_create_ring_match(
    cycle: list[str],
    graph: dict,
    user_books_map: dict,
) -> Optional[Match]:
    """
    Validate and create a ring match from a cycle of user IDs.
    Returns the created Match or None if invalid.
    """
    from apps.accounts.models import User

    users = {}
    try:
        user_qs = User.objects.filter(pk__in=cycle, is_active=True)
        for u in user_qs:
            users[str(u.pk)] = u
    except Exception:
        return None

    if len(users) != len(cycle):
        return None

    # Check match limits for all participants
    for uid in cycle:
        user = users.get(uid)
        if not user or user_at_match_limit(user):
            return None

    # Resolve the actual book for each leg: cycle[i] sends to cycle[i+1]
    legs = []
    for i, sender_id in enumerate(cycle):
        receiver_id = cycle[(i + 1) % len(cycle)]
        # Find the book that sender has that receiver wants
        book_id = _resolve_leg_book(sender_id, receiver_id, graph, user_books_map)
        if book_id is None:
            return None
        # Re-check that book is still available and not in another active match
        if _active_match_exists_for_user_book(book_id):
            return None
        legs.append((sender_id, receiver_id, book_id))

    return _create_ring_match(legs, users)


def _resolve_leg_book(
    sender_id: str,
    receiver_id: str,
    graph: dict,
    user_books_map: dict,
) -> Optional[str]:
    """Find the user_book_id that sender can send to receiver."""
    for neighbor_id, book_id in graph.get(sender_id, []):
        if neighbor_id == receiver_id:
            return book_id
    return None


@transaction.atomic
def _create_ring_match(
    legs: list[tuple],
    users: dict,
) -> Optional[Match]:
    """Create a ring Match and its MatchLegs."""
    try:
        match = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.PROPOSED,
        )
        for position, (sender_id, receiver_id, user_book_id) in enumerate(legs):
            MatchLeg.objects.create(
                match=match,
                sender=users[sender_id],
                receiver=users[receiver_id],
                user_book_id=user_book_id,
                position=position,
            )
        return match
    except Exception:
        logger.exception("Failed to create ring match")
        return None


def retry_ring_after_decline(match: Match, declining_user) -> Optional[Match]:
    """
    After a user declines a ring leg, attempt to re-form the ring
    without that user. Returns a new Match if successful, None otherwise.
    """
    remaining_user_ids = list(
        match.legs.exclude(sender=declining_user)
        .values_list("sender_id", flat=True)
        .distinct()
    )

    if len(remaining_user_ids) < MIN_RING_SIZE - 1:
        logger.info("Not enough users to retry ring after decline")
        return None

    graph, user_books_map = _build_trade_graph()

    # Try to find a valid cycle among remaining users (exclude declining user)
    for uid in remaining_user_ids:
        cycles = _find_cycles_from(str(uid), graph, MIN_RING_SIZE, MAX_RING_SIZE)
        for cycle in cycles:
            # Ensure the declining user is not in the new cycle
            if str(declining_user.pk) in cycle:
                continue
            new_match = _try_create_ring_match(cycle, graph, user_books_map)
            if new_match:
                logger.info(
                    "Found replacement ring match %s after %s declined",
                    new_match.pk,
                    declining_user.username,
                )
                return new_match

    return None

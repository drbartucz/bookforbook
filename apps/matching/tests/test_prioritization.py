"""
Tests for matching/services/prioritization.py.

Covers:
- condition_priority_value: mapping of condition strings to ordinal scores
- priority_ordered_wishlist_entries: deterministic allocation ordering
  (oldest first, stricter condition breaks ties, id is final tie-break)
"""

import pytest
from datetime import timedelta

from django.utils import timezone

from apps.inventory.models import WishlistItem
from apps.matching.services.prioritization import (
    condition_priority_value,
    priority_ordered_wishlist_entries,
)
from apps.tests.factories import BookFactory, UserFactory, WishlistItemFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# condition_priority_value
# ---------------------------------------------------------------------------


class TestConditionPriorityValue:
    def test_like_new_is_zero(self):
        assert condition_priority_value("like_new") == 0

    def test_very_good_is_one(self):
        assert condition_priority_value("very_good") == 1

    def test_good_is_two(self):
        assert condition_priority_value("good") == 2

    def test_acceptable_is_three(self):
        assert condition_priority_value("acceptable") == 3

    def test_unknown_condition_returns_four(self):
        assert condition_priority_value("mint") == 4
        assert condition_priority_value("") == 4
        assert condition_priority_value("LIKE_NEW") == 4  # case-sensitive

    def test_stricter_conditions_have_lower_priority_value(self):
        """Lower value = stricter requirement, so like_new < very_good < good < acceptable."""
        assert (
            condition_priority_value("like_new")
            < condition_priority_value("very_good")
            < condition_priority_value("good")
            < condition_priority_value("acceptable")
        )


# ---------------------------------------------------------------------------
# priority_ordered_wishlist_entries
# ---------------------------------------------------------------------------


def _make_wishlist_item(user, min_condition="acceptable", hours_ago=0):
    book = BookFactory()
    item = WishlistItemFactory(user=user, book=book, min_condition=min_condition)
    if hours_ago:
        WishlistItem.objects.filter(pk=item.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )
        item.refresh_from_db()
    return item


class TestPriorityOrderedWishlistEntries:
    def test_oldest_entry_comes_first(self):
        user = UserFactory()
        old = _make_wishlist_item(user, min_condition="acceptable", hours_ago=5)
        new = _make_wishlist_item(user, min_condition="acceptable", hours_ago=0)

        qs = WishlistItem.objects.filter(user=user)
        ordered = list(priority_ordered_wishlist_entries(qs))

        assert ordered[0].pk == old.pk
        assert ordered[1].pk == new.pk

    def test_stricter_condition_wins_same_created_at(self):
        """When created_at is equal, stricter min_condition (like_new) goes first."""
        user = UserFactory()
        fixed_ts = timezone.now() - timedelta(hours=1)

        strict = _make_wishlist_item(user, min_condition="like_new")
        lenient = _make_wishlist_item(user, min_condition="acceptable")
        # Pin both to the exact same timestamp
        WishlistItem.objects.filter(pk__in=[strict.pk, lenient.pk]).update(
            created_at=fixed_ts
        )

        qs = WishlistItem.objects.filter(user=user)
        ordered = list(priority_ordered_wishlist_entries(qs))

        assert ordered[0].pk == strict.pk
        assert ordered[1].pk == lenient.pk

    def test_all_four_conditions_ordered_correctly(self):
        user = UserFactory()
        fixed_ts = timezone.now() - timedelta(hours=1)

        conditions = ["acceptable", "good", "very_good", "like_new"]
        items = {c: _make_wishlist_item(user, min_condition=c) for c in conditions}
        WishlistItem.objects.filter(pk__in=[i.pk for i in items.values()]).update(
            created_at=fixed_ts
        )

        qs = WishlistItem.objects.filter(user=user)
        ordered = list(priority_ordered_wishlist_entries(qs))

        # Stricter first: like_new, very_good, good, acceptable
        assert ordered[0].pk == items["like_new"].pk
        assert ordered[1].pk == items["very_good"].pk
        assert ordered[2].pk == items["good"].pk
        assert ordered[3].pk == items["acceptable"].pk

    def test_empty_queryset_returns_empty(self):
        qs = WishlistItem.objects.none()
        assert list(priority_ordered_wishlist_entries(qs)) == []

    def test_returns_all_entries(self):
        user = UserFactory()
        for _ in range(5):
            _make_wishlist_item(user)

        qs = WishlistItem.objects.filter(user=user)
        assert len(list(priority_ordered_wishlist_entries(qs))) == 5

    def test_older_lenient_beats_newer_strict(self):
        """Age beats condition strictness: an older acceptable entry comes before a newer like_new."""
        user = UserFactory()
        old_lenient = _make_wishlist_item(user, min_condition="acceptable", hours_ago=10)
        new_strict = _make_wishlist_item(user, min_condition="like_new", hours_ago=0)

        qs = WishlistItem.objects.filter(user=user)
        ordered = list(priority_ordered_wishlist_entries(qs))

        assert ordered[0].pk == old_lenient.pk
        assert ordered[1].pk == new_strict.pk

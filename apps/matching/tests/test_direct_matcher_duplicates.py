import pytest

from apps.matching.models import DeclinedPairing, Match, MatchLeg
from apps.matching.services.direct_matcher import (
    _duplicate_match_exists,
    run_direct_matching,
)
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory, WishlistItemFactory


pytestmark = pytest.mark.django_db


class TestDuplicateMatchExists:
    def test_returns_true_for_existing_same_direction_match(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_a,
            receiver=user_b,
            user_book=ub_a,
            position=0,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_b,
            receiver=user_a,
            user_book=ub_b,
            position=1,
        )

        assert _duplicate_match_exists(user_a, user_b, ub_a, ub_b)

    def test_returns_true_when_users_and_books_are_reversed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_a,
            receiver=user_b,
            user_book=ub_a,
            position=0,
        )

        assert not _duplicate_match_exists(user_b, user_a, ub_b, ub_a)

        MatchLeg.objects.create(
            match=match,
            sender=user_b,
            receiver=user_a,
            user_book=ub_b,
            position=1,
        )

        assert _duplicate_match_exists(user_b, user_a, ub_b, ub_a)

    def test_returns_false_for_inactive_match(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.EXPIRED,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_a,
            receiver=user_b,
            user_book=ub_a,
            position=0,
        )
        MatchLeg.objects.create(
            match=match,
            sender=user_b,
            receiver=user_a,
            user_book=ub_b,
            position=1,
        )

        assert not _duplicate_match_exists(user_a, user_b, ub_a, ub_b)

    def test_returns_true_when_declined_pairing_exists(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)

        assert _duplicate_match_exists(user_a, user_b, ub_a, ub_b)

    def test_returns_true_when_declined_pairing_exists_reversed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)

        # Direction is irrelevant — canonical ordering means one row covers both
        assert _duplicate_match_exists(user_b, user_a, ub_b, ub_a)

    def test_periodic_scan_does_not_recreate_declined_match(self):
        book = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=book)
        ub_b = UserBookFactory(user=user_b, book=BookFactory())
        WishlistItemFactory(user=user_b, book=book)
        WishlistItemFactory(user=user_a, book=ub_b.book)

        first_run = run_direct_matching()
        assert len(first_run) == 1

        # Simulate decline: expire the match and record the pairing
        match = first_run[0]
        match.status = Match.Status.EXPIRED
        match.save(update_fields=["status"])
        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)

        second_run = run_direct_matching()
        assert len(second_run) == 0

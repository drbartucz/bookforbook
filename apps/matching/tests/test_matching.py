"""
Tests for the direct match detection service and matching API.
"""

import pytest

from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.matching.services.direct_matcher import (
    count_active_matches_for_user,
    run_direct_matching,
    user_at_match_limit,
)
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


@pytest.mark.django_db
class TestDirectMatcherService:
    def _setup_direct_pair(self):
        """Create a classic direct-match pair: A has what B wants, B has what A wants."""
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        ub_b = UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")
        return user_a, user_b, ub_a, ub_b

    def test_direct_match_created(self, db):
        user_a, user_b, ub_a, ub_b = self._setup_direct_pair()
        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        assert matches[0].match_type == Match.MatchType.DIRECT
        assert matches[0].legs.count() == 2

    def test_no_match_when_condition_not_met(self, db):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=book_for_b, condition="acceptable")
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        # B wants book_for_b but requires 'very_good' — 'acceptable' doesn't satisfy
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="very_good")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_no_match_for_institutional_user(self, db):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        lib = UserFactory(account_type="library")
        user_a = UserFactory()

        ub_a = UserBookFactory(user=lib, book=book_for_b, condition="good")
        UserBookFactory(user=user_a, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_a, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=lib, book=book_for_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_no_match_when_book_already_reserved(self, db):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(
            user=user_a,
            book=book_for_b,
            condition="good",
            status=UserBook.Status.RESERVED,
        )
        UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_user_at_match_limit_blocks_new_match(self, db):
        book_for_b = BookFactory()
        book_for_a = BookFactory()
        user_a = UserFactory(rating_count=0)  # max_active_matches = 1
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        ub_b = UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        # Create an existing match using up user_a's 1-slot capacity
        other_book = BookFactory()
        other_user = UserFactory()
        other_ub = UserBookFactory(user=user_a, book=other_book, condition="good")
        existing_match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=existing_match, sender=user_a, receiver=other_user, user_book=other_ub
        )

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_exact_preference_blocks_related_edition(self, db):
        wanted_by_b = BookFactory(
            title="The Pragmatic Programmer", authors=["Andrew Hunt"]
        )
        related_from_a = BookFactory(
            title="The Pragmatic Programmer", authors=["Andrew Hunt"]
        )
        wanted_by_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=related_from_a, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a, condition="good")
        WishlistItemFactory(
            user=user_b,
            book=wanted_by_b,
            min_condition="acceptable",
            edition_preference="exact",
        )
        WishlistItemFactory(user=user_a, book=wanted_by_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_same_language_preference_allows_related_edition(self, db):
        wanted_by_b = BookFactory(title="Refactoring", authors=["Martin Fowler"])
        related_from_a = BookFactory(title="Refactoring", authors=["Martin Fowler"])
        wanted_by_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=related_from_a, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a, condition="good")
        WishlistItemFactory(
            user=user_b,
            book=wanted_by_b,
            min_condition="acceptable",
            edition_preference="same_language",
        )
        WishlistItemFactory(user=user_a, book=wanted_by_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1

    def test_custom_format_preference_filters_related_edition(self, db):
        wanted_by_b = BookFactory(title="Clean Code", authors=["Robert C. Martin"])
        paperback_from_a = BookFactory(
            title="Clean Code",
            authors=["Robert C. Martin"],
            physical_format="Paperback",
        )
        wanted_by_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=paperback_from_a, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a, condition="good")
        WishlistItemFactory(
            user=user_b,
            book=wanted_by_b,
            min_condition="acceptable",
            edition_preference="custom",
            format_preferences=["hardcover"],
        )
        WishlistItemFactory(user=user_a, book=wanted_by_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0

    def test_exclude_abridged_blocks_related_edition(self, db):
        wanted_by_b = BookFactory(title="War and Peace", authors=["Leo Tolstoy"])
        abridged_from_a = BookFactory(
            title="War and Peace",
            authors=["Leo Tolstoy"],
            description="Abridged edition for students",
        )
        wanted_by_a = BookFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=abridged_from_a, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a, condition="good")
        WishlistItemFactory(
            user=user_b,
            book=wanted_by_b,
            min_condition="acceptable",
            edition_preference="same_language",
            exclude_abridged=True,
        )
        WishlistItemFactory(user=user_a, book=wanted_by_a, min_condition="acceptable")

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 0


@pytest.mark.django_db
class TestCountActiveMatches:
    def test_zero_when_no_active_matches(self, verified_user):
        assert count_active_matches_for_user(verified_user) == 0

    def test_counts_matches_as_sender(self, db):
        user = UserFactory()
        other = UserFactory()
        book = BookFactory()
        ub = UserBookFactory(user=user, book=book)
        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(match=match, sender=user, receiver=other, user_book=ub)
        assert count_active_matches_for_user(user) == 1


@pytest.mark.django_db
class TestMatchAPI:
    def test_accept_match_sets_leg_accepted(self, auth_api_client, verified_user, db):
        verified_user.full_name = "Reader One"
        verified_user.address_line_1 = "123 Main St"
        verified_user.city = "Denver"
        verified_user.state = "CO"
        verified_user.zip_code = "80202"
        verified_user.address_verification_status = "verified"
        verified_user.save()

        other = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ub_a = UserBookFactory(user=verified_user, book=book_a, condition="good")
        ub_b = UserBookFactory(user=other, book=book_b, condition="good")

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        leg_a = MatchLeg.objects.create(
            match=match, sender=verified_user, receiver=other, user_book=ub_a
        )
        leg_b = MatchLeg.objects.create(
            match=match, sender=other, receiver=verified_user, user_book=ub_b
        )

        resp = auth_api_client.post(f"/api/v1/matches/{match.id}/accept/")
        assert resp.status_code == 200
        leg_a.refresh_from_db()
        assert leg_a.status == MatchLeg.Status.ACCEPTED

    def test_accept_match_requires_verified_address(
        self, auth_api_client, verified_user, db
    ):
        other = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ub_a = UserBookFactory(user=verified_user, book=book_a, condition="good")
        ub_b = UserBookFactory(user=other, book=book_b, condition="good")

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=match, sender=verified_user, receiver=other, user_book=ub_a
        )
        MatchLeg.objects.create(
            match=match, sender=other, receiver=verified_user, user_book=ub_b
        )

        resp = auth_api_client.post(f"/api/v1/matches/{match.id}/accept/")
        assert resp.status_code == 409
        assert resp.data["code"] == "address_verification_required"

    def test_decline_match_sets_expired(self, auth_api_client, verified_user, db):
        other = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ub_a = UserBookFactory(user=verified_user, book=book_a, condition="good")
        ub_b = UserBookFactory(user=other, book=book_b, condition="good")

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=match, sender=verified_user, receiver=other, user_book=ub_a
        )
        MatchLeg.objects.create(
            match=match, sender=other, receiver=verified_user, user_book=ub_b
        )

        resp = auth_api_client.post(f"/api/v1/matches/{match.id}/decline/")
        assert resp.status_code == 200
        match.refresh_from_db()
        assert match.status == Match.Status.EXPIRED

    def test_non_participant_cannot_accept(self, auth_api_client, db):
        user_x = UserFactory()
        user_y = UserFactory()
        book = BookFactory()
        ub = UserBookFactory(user=user_x, book=book)
        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=match, sender=user_x, receiver=user_y, user_book=ub
        )

        resp = auth_api_client.post(f"/api/v1/matches/{match.id}/accept/")
        assert resp.status_code in (403, 404)

    def test_list_only_includes_users_matches(self, auth_api_client, verified_user, db):
        other_a = UserFactory()
        other_b = UserFactory()
        book = BookFactory()
        ub = UserBookFactory(user=other_a, book=book)
        unrelated_match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=unrelated_match, sender=other_a, receiver=other_b, user_book=ub
        )

        resp = auth_api_client.get("/api/v1/matches/")
        assert resp.status_code == 200
        assert all(
            any(
                leg["sender_id"] == str(verified_user.id)
                or leg["receiver_id"] == str(verified_user.id)
                for leg in m["legs"]
            )
            for m in resp.data
        )

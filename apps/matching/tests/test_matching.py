"""
Tests for the direct match detection service and matching API.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.matching.views import _notify_ring_cancelled
from apps.matching.services.preference_filters import normalize_title
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
        user_a = UserFactory(rating_count=0)  # max_active_matches = 2
        user_b = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=book_for_b, condition="good")
        ub_b = UserBookFactory(user=user_b, book=book_for_a, condition="good")
        WishlistItemFactory(user=user_b, book=book_for_b, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=book_for_a, min_condition="acceptable")

        # Create existing matches using up user_a's 2-slot capacity
        other_book_1 = BookFactory()
        other_user_1 = UserFactory()
        other_ub_1 = UserBookFactory(user=user_a, book=other_book_1, condition="good")
        existing_match_1 = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=existing_match_1,
            sender=user_a,
            receiver=other_user_1,
            user_book=other_ub_1,
        )

        other_book_2 = BookFactory()
        other_user_2 = UserFactory()
        other_ub_2 = UserBookFactory(user=user_a, book=other_book_2, condition="good")
        existing_match_2 = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        MatchLeg.objects.create(
            match=existing_match_2,
            sender=user_a,
            receiver=other_user_2,
            user_book=other_ub_2,
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

    def test_scarce_copy_prefers_oldest_wishlist(self, db):
        """When one copy can satisfy multiple users, oldest wishlist wins."""
        contested_book = BookFactory()
        wanted_by_a_1 = BookFactory()
        wanted_by_a_2 = BookFactory()

        user_a = UserFactory()
        user_b = UserFactory()
        user_c = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=contested_book, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a_1, condition="good")
        UserBookFactory(user=user_c, book=wanted_by_a_2, condition="good")

        # A can trade with either B or C
        WishlistItemFactory(user=user_a, book=wanted_by_a_1, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=wanted_by_a_2, min_condition="acceptable")

        wish_b = WishlistItemFactory(
            user=user_b, book=contested_book, min_condition="acceptable"
        )
        wish_c = WishlistItemFactory(
            user=user_c, book=contested_book, min_condition="acceptable"
        )

        older = timezone.now() - timedelta(days=2)
        newer = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=older)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=newer)

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        leg = matches[0].legs.get(sender=user_a)
        assert leg.receiver_id == user_b.id

    def test_scarce_copy_tie_break_prefers_stricter_condition(self, db):
        """With equal age, stricter min_condition is preferred."""
        contested_book = BookFactory()
        wanted_by_a_1 = BookFactory()
        wanted_by_a_2 = BookFactory()

        user_a = UserFactory()
        user_b = UserFactory()
        user_c = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=contested_book, condition="very_good")
        UserBookFactory(user=user_b, book=wanted_by_a_1, condition="good")
        UserBookFactory(user=user_c, book=wanted_by_a_2, condition="good")

        WishlistItemFactory(user=user_a, book=wanted_by_a_1, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=wanted_by_a_2, min_condition="acceptable")

        wish_b = WishlistItemFactory(
            user=user_b, book=contested_book, min_condition="acceptable"
        )
        wish_c = WishlistItemFactory(
            user=user_c, book=contested_book, min_condition="very_good"
        )

        same_time = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=same_time)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=same_time)

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        leg = matches[0].legs.get(sender=user_a)
        assert leg.receiver_id == user_c.id

    def test_scarce_copy_tie_break_prefers_lowest_wishlist_id(self, db):
        """With equal age and condition, stable tie-break is wishlist id."""
        contested_book = BookFactory()
        wanted_by_a_1 = BookFactory()
        wanted_by_a_2 = BookFactory()

        user_a = UserFactory()
        user_b = UserFactory()
        user_c = UserFactory()

        ub_a = UserBookFactory(user=user_a, book=contested_book, condition="good")
        UserBookFactory(user=user_b, book=wanted_by_a_1, condition="good")
        UserBookFactory(user=user_c, book=wanted_by_a_2, condition="good")

        WishlistItemFactory(user=user_a, book=wanted_by_a_1, min_condition="acceptable")
        WishlistItemFactory(user=user_a, book=wanted_by_a_2, min_condition="acceptable")

        lower_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        higher_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
        wish_b = WishlistItemFactory(
            id=lower_id,
            user=user_b,
            book=contested_book,
            min_condition="acceptable",
        )
        wish_c = WishlistItemFactory(
            id=higher_id,
            user=user_c,
            book=contested_book,
            min_condition="acceptable",
        )

        same_time = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=same_time)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=same_time)

        matches = run_direct_matching(user_book=ub_a)
        assert len(matches) == 1
        leg = matches[0].legs.get(sender=user_a)
        assert leg.receiver_id == user_b.id


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

    def test_accepted_proposal_with_trade_not_counted(self, db):
        from apps.trading.models import Trade, TradeProposal

        user = UserFactory()
        other = UserFactory()
        proposal = TradeProposal.objects.create(
            proposer=user,
            recipient=other,
            status=TradeProposal.Status.ACCEPTED,
        )
        Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=proposal.pk,
            status=Trade.Status.CONFIRMED,
        )

        assert count_active_matches_for_user(user) == 0

    def test_accepted_proposal_without_trade_is_counted(self, db):
        from apps.trading.models import TradeProposal

        user = UserFactory()
        other = UserFactory()
        TradeProposal.objects.create(
            proposer=user,
            recipient=other,
            status=TradeProposal.Status.ACCEPTED,
        )

        assert count_active_matches_for_user(user) == 1


@pytest.mark.django_db
class TestPreferenceFilters:
    def test_normalize_title_handles_accents(self):
        assert normalize_title("Les Misérables") == normalize_title("Les Miserables")


@pytest.mark.django_db
class TestMatchAPI:
    def test_accept_match_sets_leg_accepted(self, address_verified_user, db):
        from rest_framework.test import APIClient

        auth_api_client = APIClient()
        auth_api_client.force_authenticate(user=address_verified_user)

        other = UserFactory()
        book_a = BookFactory()
        book_b = BookFactory()
        ub_a = UserBookFactory(
            user=address_verified_user,
            book=book_a,
            condition="good",
        )
        ub_b = UserBookFactory(user=other, book=book_b, condition="good")

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING
        )
        leg_a = MatchLeg.objects.create(
            match=match,
            sender=address_verified_user,
            receiver=other,
            user_book=ub_a,
        )
        leg_b = MatchLeg.objects.create(
            match=match,
            sender=other,
            receiver=address_verified_user,
            user_book=ub_b,
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

    def test_accept_match_rejects_unverified_status_even_with_full_address(
        self, auth_api_client, verified_user, db
    ):
        verified_user.full_name = "Reader One"
        verified_user.address_line_1 = "123 Main St"
        verified_user.city = "Denver"
        verified_user.state = "CO"
        verified_user.zip_code = "80202"
        verified_user.address_verification_status = "unverified"
        verified_user.save()

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

    def test_accept_match_rejects_verified_status_with_incomplete_address(
        self, auth_api_client, verified_user, db
    ):
        verified_user.full_name = "Reader One"
        verified_user.address_line_1 = "123 Main St"
        verified_user.city = "Denver"
        verified_user.state = "CO"
        verified_user.zip_code = ""
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

    def test_decline_ring_queues_async_retry(self, auth_api_client, verified_user, db):
        other = UserFactory()
        book_a = BookFactory()
        ub_a = UserBookFactory(user=verified_user, book=book_a, condition="good")

        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=verified_user,
            receiver=other,
            user_book=ub_a,
        )

        with patch("django_q.tasks.async_task") as mock_async_task:
            with TestCase.captureOnCommitCallbacks(execute=True):
                resp = auth_api_client.post(f"/api/v1/matches/{ring.id}/decline/")

        assert resp.status_code == 200
        ring.refresh_from_db()
        assert ring.status == Match.Status.EXPIRED
        mock_async_task.assert_called_once_with(
            "apps.matching.tasks.retry_ring_after_decline_task",
            str(ring.pk),
            str(verified_user.pk),
        )

    def test_decline_ring_still_succeeds_when_retry_enqueue_fails(
        self, auth_api_client, verified_user, db
    ):
        other = UserFactory()
        book_a = BookFactory()
        ub_a = UserBookFactory(user=verified_user, book=book_a, condition="good")

        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=verified_user,
            receiver=other,
            user_book=ub_a,
        )

        with patch("django_q.tasks.async_task", side_effect=RuntimeError("queue down")):
            with TestCase.captureOnCommitCallbacks(execute=True):
                resp = auth_api_client.post(f"/api/v1/matches/{ring.id}/decline/")

        assert resp.status_code == 200
        ring.refresh_from_db()
        assert ring.status == Match.Status.EXPIRED

    def test_notify_ring_cancelled_excludes_declining_user(self, db):
        declining_user = UserFactory()
        participant_b = UserFactory()
        participant_c = UserFactory()

        book_a = BookFactory()
        book_b = BookFactory()
        book_c = BookFactory()
        ub_a = UserBookFactory(user=declining_user, book=book_a, condition="good")
        ub_b = UserBookFactory(user=participant_b, book=book_b, condition="good")
        ub_c = UserBookFactory(user=participant_c, book=book_c, condition="good")

        ring = Match.objects.create(
            match_type=Match.MatchType.RING,
            status=Match.Status.EXPIRED,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=declining_user,
            receiver=participant_b,
            user_book=ub_a,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=participant_b,
            receiver=participant_c,
            user_book=ub_b,
        )
        MatchLeg.objects.create(
            match=ring,
            sender=participant_c,
            receiver=declining_user,
            user_book=ub_c,
        )

        _notify_ring_cancelled(ring, declining_user)

        from apps.notifications.models import Notification

        assert Notification.objects.filter(
            user=participant_b,
            notification_type="ring_cancelled",
        ).exists()
        assert Notification.objects.filter(
            user=participant_c,
            notification_type="ring_cancelled",
        ).exists()
        assert not Notification.objects.filter(
            user=declining_user,
            notification_type="ring_cancelled",
        ).exists()

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

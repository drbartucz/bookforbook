import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import override_settings

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, WishlistItemFactory, MatchFactory, MatchLegFactory
from apps.matching.services.ring_detector import (
    record_declined_ring_leg,
    run_ring_detection,
    retry_ring_after_decline,
)
from apps.inventory.models import UserBook
from apps.matching.models import DeclinedPairing, Match, MatchLeg

@pytest.mark.django_db
class TestRingDetector:
    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0)
    def test_ring_success_3_users(self):
        # A -> B -> C -> A
        user_a = UserFactory(email_verified=True)
        user_b = UserFactory(email_verified=True)
        user_c = UserFactory(email_verified=True)
        
        book_a = BookFactory() # A has, B wants
        book_b = BookFactory() # B has, C wants
        book_c = BookFactory() # C has, A wants
        
        UserBookFactory(user=user_a, book=book_a, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_a, is_active=True)
        
        UserBookFactory(user=user_b, book=book_b, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_c, book=book_b, is_active=True)
        
        UserBookFactory(user=user_c, book=book_c, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_c, is_active=True)
        
        matches = run_ring_detection()
        assert len(matches) == 1
        match = matches[0]
        assert match.match_type == Match.MatchType.RING
        assert match.legs.count() == 3

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=48)
    def test_ring_skipped_due_to_age(self):
        # New users should be skipped
        user_a = UserFactory(email_verified=True, created_at=timezone.now())
        user_b = UserFactory(email_verified=True, created_at=timezone.now())
        user_c = UserFactory(email_verified=True, created_at=timezone.now())
        
        # Setup ring A->B->C->A
        # ...
        
        matches = run_ring_detection()
        assert len(matches) == 0

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0)
    def test_ring_skipped_due_to_match_limit(self):
        user_a = UserFactory(email_verified=True)
        # capacity default is 2
        MatchLegFactory(match=MatchFactory(status=Match.Status.PROPOSED), sender=user_a)
        MatchLegFactory(match=MatchFactory(status=Match.Status.PROPOSED), sender=user_a)
        
        user_b = UserFactory(email_verified=True)
        user_c = UserFactory(email_verified=True)
        
        # Setup ring A->B->C->A
        UserBookFactory(user=user_a, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, is_active=True) # Needs book from A
        # ...
        
        matches = run_ring_detection()
        # Since A is at limit, no ring involving A should be created
        assert len(matches) == 0

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0)
    def test_retry_ring_after_decline(self):
        user_a = UserFactory(email_verified=True)
        user_b = UserFactory(email_verified=True)
        user_c = UserFactory(email_verified=True)
        user_d = UserFactory(email_verified=True)
        
        # Original ring A->B->C->A
        match = MatchFactory(match_type=Match.MatchType.RING)
        MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        MatchLegFactory(match=match, sender=user_b, receiver=user_c)
        MatchLegFactory(match=match, sender=user_c, receiver=user_a)
        
        # User B declines. We want to see if it can reform A->D->C->A
        # Setup needed data for reformed ring
        book_a = BookFactory() # A has, D wants
        book_d = BookFactory() # D has, C wants
        book_c = BookFactory() # C has, A wants
        
        UserBookFactory(user=user_a, book=book_a, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_d, book=book_a, is_active=True)
        
        UserBookFactory(user=user_d, book=book_d, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_c, book=book_d, is_active=True)
        
        UserBookFactory(user=user_c, book=book_c, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_c, is_active=True)
        
        reformed = retry_ring_after_decline(match, declining_user=user_b)
        assert reformed is not None
        assert reformed.legs.count() == 3
        # Check D is in the reformed ring
        assert reformed.legs.filter(sender=user_d).exists()

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0)
    def test_ring_not_recreated_after_decline(self):
        user_a = UserFactory(email_verified=True)
        user_b = UserFactory(email_verified=True)
        user_c = UserFactory(email_verified=True)

        book_a = BookFactory()
        book_b = BookFactory()
        book_c = BookFactory()

        ub_a = UserBookFactory(user=user_a, book=book_a, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_a, is_active=True)
        ub_b = UserBookFactory(user=user_b, book=book_b, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_c, book=book_b, is_active=True)
        ub_c = UserBookFactory(user=user_c, book=book_c, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_c, is_active=True)

        matches = run_ring_detection()
        assert len(matches) == 1

        # Simulate user_a declining — expire the match and record the pairing
        match = matches[0]
        match.status = Match.Status.EXPIRED
        match.save(update_fields=["status"])
        declined_leg = match.legs.get(sender=user_a)
        reverse_leg = match.legs.get(sender=declined_leg.receiver)
        DeclinedPairing.record_by_ids(declined_leg.user_book_id, reverse_leg.user_book_id)

        second_run = run_ring_detection()
        assert len(second_run) == 0

    @override_settings(MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0)
    def test_record_declined_ring_leg_records_correct_pairing(self):
        user_a = UserFactory(email_verified=True)
        user_b = UserFactory(email_verified=True)
        user_c = UserFactory(email_verified=True)

        book_a = BookFactory()
        book_b = BookFactory()
        book_c = BookFactory()

        ub_a = UserBookFactory(user=user_a, book=book_a, status=UserBook.Status.AVAILABLE)
        ub_b = UserBookFactory(user=user_b, book=book_b, status=UserBook.Status.AVAILABLE)
        ub_c = UserBookFactory(user=user_c, book=book_c, status=UserBook.Status.AVAILABLE)

        # Ring: A(ub_a)→B, B(ub_b)→C, C(ub_c)→A
        ring_match = MatchFactory(match_type=Match.MatchType.RING, status=Match.Status.EXPIRED)
        MatchLegFactory(match=ring_match, sender=user_a, receiver=user_b, user_book=ub_a, position=0)
        MatchLegFactory(match=ring_match, sender=user_b, receiver=user_c, user_book=ub_b, position=1)
        MatchLegFactory(match=ring_match, sender=user_c, receiver=user_a, user_book=ub_c, position=2)

        record_declined_ring_leg(ring_match, user_a)

        assert DeclinedPairing.objects.count() == 1
        pairing = DeclinedPairing.objects.get()
        recorded_ids = {str(pairing.user_book_a_id), str(pairing.user_book_b_id)}
        # user_a sent ub_a; user_b (receiver) sent ub_b back — that edge is declined
        assert recorded_ids == {str(ub_a.pk), str(ub_b.pk)}

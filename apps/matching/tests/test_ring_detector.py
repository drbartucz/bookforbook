"""
Tests for the ring detection algorithm.

Covers:
- _find_cycles_from: pure graph traversal (no DB)
- _build_trade_graph: DB query layer building the adjacency list
- run_ring_detection: full end-to-end ring creation
- Edge cases: condition filtering, institutional users, match-limit checks,
  size limits (min 3, max 5), deduplication of duplicate cycles,
  books already in active matches, fewer than 3 eligible users.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.matching.services.ring_detector import (
    _build_trade_graph,
    _find_cycles_from,
    run_ring_detection,
)
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


# ---------------------------------------------------------------------------
# Pure unit tests — _find_cycles_from (no DB required)
# ---------------------------------------------------------------------------


class TestFindCyclesFrom:
    """Test the DFS cycle finder in isolation with hand-built graphs."""

    def test_simple_3_cycle(self):
        # A→B→C→A
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2")],
            "C": [("A", "ub3")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert len(cycles) == 1
        assert cycles[0] == ["A", "B", "C"]

    def test_simple_4_cycle(self):
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2")],
            "C": [("D", "ub3")],
            "D": [("A", "ub4")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert len(cycles) == 1
        assert cycles[0] == ["A", "B", "C", "D"]

    def test_simple_5_cycle(self):
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2")],
            "C": [("D", "ub3")],
            "D": [("E", "ub4")],
            "E": [("A", "ub5")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert len(cycles) == 1
        assert len(cycles[0]) == 5

    def test_6_cycle_exceeds_max_not_found(self):
        """Rings of 6 should not be returned (MAX_RING_SIZE = 5)."""
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2")],
            "C": [("D", "ub3")],
            "D": [("E", "ub4")],
            "E": [("F", "ub5")],
            "F": [("A", "ub6")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert cycles == []

    def test_2_cycle_below_min_not_found(self):
        """Direct pairs (length 2) should not be returned (MIN_RING_SIZE = 3)."""
        graph = {
            "A": [("B", "ub1")],
            "B": [("A", "ub2")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert cycles == []

    def test_no_cycle_in_graph(self):
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2")],
            # C has no outgoing edge back
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert cycles == []

    def test_multiple_cycles_from_same_start(self):
        # A→B→C→A and A→B→D→A both start at A
        graph = {
            "A": [("B", "ub1")],
            "B": [("C", "ub2"), ("D", "ub5")],
            "C": [("A", "ub3")],
            "D": [("A", "ub4")],
        }
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert len(cycles) == 2

    def test_empty_graph(self):
        cycles = _find_cycles_from("A", {}, 3, 5)
        assert cycles == []

    def test_node_not_in_graph(self):
        graph = {"B": [("C", "ub1")]}
        cycles = _find_cycles_from("A", graph, 3, 5)
        assert cycles == []


# ---------------------------------------------------------------------------
# DB integration tests — _build_trade_graph
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBuildTradeGraph:
    def test_basic_three_user_graph(self):
        """Three users forming a potential ring should all appear as graph nodes."""
        # A has book1 that B wants; B has book2 that C wants; C has book3 that A wants
        book1, book2, book3 = BookFactory(), BookFactory(), BookFactory()
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()

        UserBookFactory(user=a, book=book1, condition="good")
        UserBookFactory(user=b, book=book2, condition="good")
        UserBookFactory(user=c, book=book3, condition="good")

        WishlistItemFactory(user=b, book=book1, min_condition="acceptable")
        WishlistItemFactory(user=c, book=book2, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book3, min_condition="acceptable")

        graph, _ = _build_trade_graph()

        assert str(a.pk) in graph
        assert str(b.pk) in graph
        assert str(c.pk) in graph

    def test_condition_not_met_excludes_edge(self):
        """An edge should not exist if the book condition doesn't meet the wishlist minimum."""
        book1, book2 = BookFactory(), BookFactory()
        a = UserFactory()
        b = UserFactory()

        # a has book1 in 'acceptable' condition; b requires 'very_good'
        UserBookFactory(user=a, book=book1, condition="acceptable")
        UserBookFactory(user=b, book=book2, condition="good")
        WishlistItemFactory(user=b, book=book1, min_condition="very_good")
        WishlistItemFactory(user=a, book=book2, min_condition="acceptable")

        graph, _ = _build_trade_graph()

        # a→b edge should not exist
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert str(b.pk) not in neighbors_of_a

    def test_institutional_users_excluded(self):
        """Library/bookstore users should not appear as graph nodes."""
        book1 = BookFactory()
        lib = UserFactory(account_type="library")
        a = UserFactory()

        UserBookFactory(user=lib, book=book1, condition="good")
        WishlistItemFactory(user=a, book=book1, min_condition="acceptable")

        graph, _ = _build_trade_graph()
        assert str(lib.pk) not in graph

    def test_reserved_book_excluded(self):
        """Reserved books should not appear as graph edges."""
        book1, book2 = BookFactory(), BookFactory()
        a = UserFactory()
        b = UserFactory()

        UserBookFactory(
            user=a, book=book1, condition="good", status=UserBook.Status.RESERVED
        )
        UserBookFactory(user=b, book=book2, condition="good")
        WishlistItemFactory(user=b, book=book1, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book2, min_condition="acceptable")

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert str(b.pk) not in neighbors_of_a

    def test_unverified_user_excluded(self):
        """Users without a verified email should not appear in the graph."""
        book1, book2 = BookFactory(), BookFactory()
        a = UserFactory(email_verified=False)
        b = UserFactory()

        UserBookFactory(user=a, book=book1, condition="good")
        UserBookFactory(user=b, book=book2, condition="good")
        WishlistItemFactory(user=b, book=book1, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book2, min_condition="acceptable")

        graph, _ = _build_trade_graph()
        assert str(a.pk) not in graph

    def test_related_edition_preference_creates_edge(self):
        wanted = BookFactory(title="Domain-Driven Design", authors=["Eric Evans"])
        related = BookFactory(title="Domain-Driven Design", authors=["Eric Evans"])
        a = UserFactory()
        b = UserFactory()

        UserBookFactory(user=a, book=related, condition="good")
        WishlistItemFactory(
            user=b,
            book=wanted,
            min_condition="acceptable",
            edition_preference="same_language",
        )

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert str(b.pk) in neighbors_of_a

    def test_exact_preference_does_not_create_related_edge(self):
        wanted = BookFactory(
            title="Patterns of Enterprise Application Architecture",
            authors=["Martin Fowler"],
        )
        related = BookFactory(
            title="Patterns of Enterprise Application Architecture",
            authors=["Martin Fowler"],
        )
        a = UserFactory()
        b = UserFactory()

        UserBookFactory(user=a, book=related, condition="good")
        WishlistItemFactory(
            user=b,
            book=wanted,
            min_condition="acceptable",
            edition_preference="exact",
        )

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert str(b.pk) not in neighbors_of_a

    def test_edge_order_prefers_oldest_wishlist(self):
        contested = BookFactory()
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()

        UserBookFactory(user=a, book=contested, condition="good")

        wish_b = WishlistItemFactory(user=b, book=contested, min_condition="acceptable")
        wish_c = WishlistItemFactory(user=c, book=contested, min_condition="acceptable")

        older = timezone.now() - timedelta(days=2)
        newer = timezone.now() - timedelta(days=1)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=older)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=newer)

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert neighbors_of_a[0] == str(c.pk)

    def test_edge_order_tie_break_prefers_stricter_condition(self):
        contested = BookFactory()
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()

        UserBookFactory(user=a, book=contested, condition="very_good")

        wish_b = WishlistItemFactory(user=b, book=contested, min_condition="acceptable")
        wish_c = WishlistItemFactory(user=c, book=contested, min_condition="very_good")

        same_time = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=same_time)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=same_time)

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert neighbors_of_a[0] == str(c.pk)

    def test_edge_order_tie_break_prefers_lower_wishlist_id(self):
        contested = BookFactory()
        a = UserFactory()
        b = UserFactory()
        c = UserFactory()

        UserBookFactory(user=a, book=contested, condition="good")

        low_id = uuid.UUID("00000000-0000-0000-0000-000000000011")
        high_id = uuid.UUID("00000000-0000-0000-0000-000000000022")
        wish_b = WishlistItemFactory(
            id=low_id,
            user=b,
            book=contested,
            min_condition="acceptable",
        )
        wish_c = WishlistItemFactory(
            id=high_id,
            user=c,
            book=contested,
            min_condition="acceptable",
        )

        same_time = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=same_time)
        type(wish_c).objects.filter(pk=wish_c.pk).update(created_at=same_time)

        graph, _ = _build_trade_graph()
        neighbors_of_a = [n for n, _ in graph.get(str(a.pk), [])]
        assert neighbors_of_a[0] == str(b.pk)


# ---------------------------------------------------------------------------
# DB integration tests — run_ring_detection (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunRingDetection:
    def _setup_ring(self, size: int):
        """
        Create `size` users with books forming a clean ring:
        users[0]→users[1]→...→users[size-1]→users[0].
        Returns list of users and their outgoing UserBook objects.
        """
        books = [BookFactory() for _ in range(size)]
        users = [UserFactory() for _ in range(size)]
        user_books = []

        for i in range(size):
            # user[i] has books[i], which user[(i+1)%size] wants
            ub = UserBookFactory(user=users[i], book=books[i], condition="good")
            user_books.append(ub)
            WishlistItemFactory(
                user=users[(i + 1) % size],
                book=books[i],
                min_condition="acceptable",
            )

        return users, user_books

    def test_3_user_ring_detected(self):
        _users, _ubs = self._setup_ring(3)
        matches = run_ring_detection()

        assert len(matches) == 1
        m = matches[0]
        assert m.match_type == Match.MatchType.RING
        assert m.status == Match.Status.PROPOSED
        assert m.legs.count() == 3

    def test_4_user_ring_detected(self):
        _users, _ubs = self._setup_ring(4)
        matches = run_ring_detection()

        assert len(matches) == 1
        assert matches[0].legs.count() == 4

    def test_5_user_ring_detected(self):
        _users, _ubs = self._setup_ring(5)
        matches = run_ring_detection()

        assert len(matches) == 1
        assert matches[0].legs.count() == 5

    def test_ring_legs_have_correct_structure(self):
        """Each leg should have a valid sender→receiver→user_book chain."""
        users, user_books = self._setup_ring(3)
        matches = run_ring_detection()

        assert len(matches) == 1
        match = matches[0]
        legs = list(match.legs.order_by("position"))

        assert len(legs) == 3
        for leg in legs:
            assert leg.sender is not None
            assert leg.receiver is not None
            assert leg.user_book is not None
            # sender and receiver must be different
            assert leg.sender_id != leg.receiver_id

    def test_fewer_than_3_users_no_match(self):
        """Two users cannot form a ring (minimum is 3)."""
        book_a, book_b = BookFactory(), BookFactory()
        a, b = UserFactory(), UserFactory()
        UserBookFactory(user=a, book=book_a, condition="good")
        UserBookFactory(user=b, book=book_b, condition="good")
        WishlistItemFactory(user=b, book=book_a, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book_b, min_condition="acceptable")

        matches = run_ring_detection()
        assert matches == []

    def test_no_ring_when_chain_is_incomplete(self):
        """A→B→C where C does not want anything A has — no ring."""
        book_ab, book_bc, book_ca = BookFactory(), BookFactory(), BookFactory()
        a, b, c = UserFactory(), UserFactory(), UserFactory()

        UserBookFactory(user=a, book=book_ab, condition="good")
        UserBookFactory(user=b, book=book_bc, condition="good")
        UserBookFactory(user=c, book=book_ca, condition="good")

        WishlistItemFactory(user=b, book=book_ab, min_condition="acceptable")
        WishlistItemFactory(user=c, book=book_bc, min_condition="acceptable")
        # Deliberately NO wishlist entry for A wanting book_ca

        matches = run_ring_detection()
        assert matches == []

    def test_duplicate_cycle_not_created_twice(self):
        """The same ring should only create one Match, not one per starting node."""
        _users, _ubs = self._setup_ring(3)
        matches = run_ring_detection()
        assert len(matches) == 1
        assert Match.objects.filter(match_type=Match.MatchType.RING).count() == 1

    def test_ring_not_created_when_book_already_in_active_match(self):
        """If a book in the ring is already in an active match leg, skip the ring."""
        users, user_books = self._setup_ring(3)

        # Put user_books[0] into an existing active match
        existing_match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=existing_match,
            sender=users[0],
            receiver=users[1],
            user_book=user_books[0],
            position=0,
        )

        matches = run_ring_detection()
        assert matches == []

    def test_ring_not_created_when_user_at_match_limit(self):
        """If any participant is at their match limit, the ring is skipped."""
        users, user_books = self._setup_ring(3)

        # Give users[0] rating_count=0 → max_active_matches=2
        # Then put them in 2 existing active matches to saturate the limit
        users[0].rating_count = 0
        users[0].save(update_fields=["rating_count"])

        other_book_1 = BookFactory()
        other_user_1 = UserFactory()
        other_ub_1 = UserBookFactory(
            user=users[0],
            book=other_book_1,
            condition="good",
        )
        existing_match_1 = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=existing_match_1,
            sender=users[0],
            receiver=other_user_1,
            user_book=other_ub_1,
            position=0,
        )

        other_book_2 = BookFactory()
        other_user_2 = UserFactory()
        other_ub_2 = UserBookFactory(
            user=users[0],
            book=other_book_2,
            condition="good",
        )
        existing_match_2 = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PROPOSED,
        )
        MatchLeg.objects.create(
            match=existing_match_2,
            sender=users[0],
            receiver=other_user_2,
            user_book=other_ub_2,
            position=0,
        )

        matches = run_ring_detection()
        # users[0] is at limit, so the ring involving them should be skipped
        ring_matches = [m for m in matches if m.match_type == Match.MatchType.RING]
        assert ring_matches == []

    def test_condition_mismatch_prevents_ring(self):
        """A ring where one leg fails the condition check should not be created."""
        book1, book2, book3 = BookFactory(), BookFactory(), BookFactory()
        a, b, c = UserFactory(), UserFactory(), UserFactory()

        UserBookFactory(user=a, book=book1, condition="acceptable")  # too low for b
        UserBookFactory(user=b, book=book2, condition="good")
        UserBookFactory(user=c, book=book3, condition="good")

        WishlistItemFactory(
            user=b, book=book1, min_condition="very_good"
        )  # won't be met
        WishlistItemFactory(user=c, book=book2, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book3, min_condition="acceptable")

        matches = run_ring_detection()
        assert matches == []

    def test_independent_rings_both_created(self):
        """Two independent 3-user rings should each produce a separate Match."""
        self._setup_ring(3)
        self._setup_ring(3)

        matches = run_ring_detection()
        assert len(matches) == 2
        assert Match.objects.filter(match_type=Match.MatchType.RING).count() == 2

    def test_ring_books_not_marked_reserved_on_detection(self):
        """
        Books should remain AVAILABLE when a ring is first detected —
        they're only reserved after all participants accept.
        """
        users, user_books = self._setup_ring(3)
        run_ring_detection()

        for ub in user_books:
            ub.refresh_from_db()
            assert ub.status == UserBook.Status.AVAILABLE

    def test_competing_rings_sharing_same_book_create_only_one_ring(self):
        """
        If two candidate rings share one scarce outgoing book, only one ring
        can be created because that book is committed to the first active ring.
        """
        scarce = BookFactory()
        book_b = BookFactory()
        book_c = BookFactory()
        book_d = BookFactory()
        book_e = BookFactory()

        a = UserFactory()
        b = UserFactory()
        c = UserFactory()
        d = UserFactory()
        e = UserFactory()

        ub_a = UserBookFactory(user=a, book=scarce, condition="good")
        UserBookFactory(user=b, book=book_b, condition="good")
        UserBookFactory(user=c, book=book_c, condition="good")
        UserBookFactory(user=d, book=book_d, condition="good")
        UserBookFactory(user=e, book=book_e, condition="good")

        # Ring candidate 1: A -> B -> C -> A
        WishlistItemFactory(user=b, book=scarce, min_condition="acceptable")
        WishlistItemFactory(user=c, book=book_b, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book_c, min_condition="acceptable")

        # Ring candidate 2: A -> D -> E -> A (shares A's scarce book)
        WishlistItemFactory(user=d, book=scarce, min_condition="acceptable")
        WishlistItemFactory(user=e, book=book_d, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book_e, min_condition="acceptable")

        matches = run_ring_detection()

        assert len(matches) == 1
        ring = matches[0]
        legs = list(ring.legs.all())
        scarce_legs = [leg for leg in legs if leg.user_book_id == ub_a.pk]
        assert len(scarce_legs) == 1

    def test_competing_rings_produce_one_coherent_cycle_not_hybrid(self):
        """
        With two competing candidate rings sharing one scarce leg, ring detection
        should create one complete candidate cycle, not a mixed hybrid of both.
        """
        scarce = BookFactory()
        book_b = BookFactory()
        book_c = BookFactory()
        book_d = BookFactory()
        book_e = BookFactory()

        a = UserFactory()
        b = UserFactory()
        c = UserFactory()
        d = UserFactory()
        e = UserFactory()

        UserBookFactory(user=a, book=scarce, condition="good")
        UserBookFactory(user=b, book=book_b, condition="good")
        UserBookFactory(user=c, book=book_c, condition="good")
        UserBookFactory(user=d, book=book_d, condition="good")
        UserBookFactory(user=e, book=book_e, condition="good")

        # Candidate ring A -> B -> C -> A
        wish_b = WishlistItemFactory(user=b, book=scarce, min_condition="acceptable")
        WishlistItemFactory(user=c, book=book_b, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book_c, min_condition="acceptable")

        # Candidate ring A -> D -> E -> A
        wish_d = WishlistItemFactory(user=d, book=scarce, min_condition="acceptable")
        WishlistItemFactory(user=e, book=book_d, min_condition="acceptable")
        WishlistItemFactory(user=a, book=book_e, min_condition="acceptable")

        older = timezone.now() - timedelta(days=3)
        newer = timezone.now() - timedelta(days=1)
        type(wish_b).objects.filter(pk=wish_b.pk).update(created_at=older)
        type(wish_d).objects.filter(pk=wish_d.pk).update(created_at=newer)

        matches = run_ring_detection()

        assert len(matches) == 1
        participant_ids = {
            str(pid) for pid in matches[0].legs.values_list("sender_id", flat=True)
        }
        cycle_1 = {str(a.pk), str(b.pk), str(c.pk)}
        cycle_2 = {str(a.pk), str(d.pk), str(e.pk)}
        assert participant_ids in (cycle_1, cycle_2)

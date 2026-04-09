"""
Tests for the ratings rolling average service and uniqueness constraint.
"""

import pytest
from django.db import IntegrityError

from apps.tests.factories import BookFactory, UserBookFactory, UserFactory
from apps.trading.models import Trade, TradeShipment
from apps.trading.models import TradeProposal
from apps.inventory.models import UserBook
from apps.ratings.models import Rating
from apps.ratings.services.rolling_average import recompute_rating_average


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trade(a, b):
    """Create a minimal confirmed trade between users a and b."""
    book_a = UserBookFactory(
        user=a, book=BookFactory(), status=UserBook.Status.RESERVED
    )
    book_b = UserBookFactory(
        user=b, book=BookFactory(), status=UserBook.Status.RESERVED
    )
    proposal = TradeProposal.objects.create(
        proposer=a, recipient=b, status=TradeProposal.Status.COMPLETED
    )
    trade = Trade.objects.create(
        source_type=Trade.SourceType.PROPOSAL,
        source_id=proposal.pk,
        status=Trade.Status.SHIPPING,
    )
    TradeShipment.objects.create(trade=trade, sender=a, receiver=b, user_book=book_a)
    TradeShipment.objects.create(trade=trade, sender=b, receiver=a, user_book=book_b)
    return trade


def _make_rating(trade, rater, rated, score):
    return Rating.objects.create(
        trade=trade,
        rater=rater,
        rated=rated,
        score=score,
        book_condition_accurate=True,
    )


# ---------------------------------------------------------------------------
# recompute_rating_average
# ---------------------------------------------------------------------------


class TestRecomputeRatingAverage:
    def test_no_ratings_gives_none_and_zero_count(self):
        user = UserFactory()
        recompute_rating_average(user)
        user.refresh_from_db()
        assert user.avg_recent_rating is None
        assert user.rating_count == 0

    def test_single_rating(self):
        a = UserFactory()
        b = UserFactory()
        trade = _make_trade(a, b)
        _make_rating(trade, a, b, 4)

        recompute_rating_average(b)
        b.refresh_from_db()
        assert float(b.avg_recent_rating) == 4.0
        assert b.rating_count == 1

    def test_average_over_multiple_ratings(self):
        rater = UserFactory()
        rated = UserFactory()

        # Create 3 trades and 3 ratings with scores 1, 3, 5
        for score in (1, 3, 5):
            trade = _make_trade(rater, rated)
            _make_rating(trade, rater, rated, score)

        recompute_rating_average(rated)
        rated.refresh_from_db()
        assert float(rated.avg_recent_rating) == pytest.approx(3.0)
        assert rated.rating_count == 3

    def test_rolling_window_capped_at_10(self):
        """Only the last 10 ratings should be used for the average."""
        raters = [UserFactory() for _ in range(11)]
        rated = UserFactory()

        # 10 ratings of score 5
        for i in range(10):
            trade = _make_trade(raters[i], rated)
            _make_rating(trade, raters[i], rated, 5)

        # 1 rating of score 1 (should be included in rolling window, displacing oldest)
        last_trade = _make_trade(raters[10], rated)
        _make_rating(last_trade, raters[10], rated, 1)

        recompute_rating_average(rated)
        rated.refresh_from_db()

        # total_count = 11; rolling window is 10
        assert rated.rating_count == 11
        # The last 10: scores are 5,5,5,5,5,5,5,5,5,1 → avg = (9*5+1)/10 = 4.6
        assert float(rated.avg_recent_rating) == pytest.approx(4.6)


# ---------------------------------------------------------------------------
# Rating unique_together constraint
# ---------------------------------------------------------------------------


class TestRatingUnique:
    def test_cannot_rate_same_trade_twice(self):
        a = UserFactory()
        b = UserFactory()
        trade = _make_trade(a, b)
        _make_rating(trade, a, b, 5)

        with pytest.raises(IntegrityError):
            _make_rating(trade, a, b, 3)

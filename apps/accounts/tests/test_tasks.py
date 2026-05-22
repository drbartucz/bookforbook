import pytest

from apps.accounts.models import User
from apps.accounts.tasks import recalculate_karma_badges
from apps.tests.factories import UserFactory


@pytest.mark.django_db
class TestRecalculateKarmaBadges:
    def _make_user(self, gifts=0, trades=0):
        return UserFactory(
            account_type=User.AccountType.INDIVIDUAL,
            is_active=True,
            email_verified=True,
            gifts_given_count=gifts,
            total_trades=trades,
        )

    def test_no_users_runs_without_error(self):
        recalculate_karma_badges()

    def test_zero_gifts_gets_no_giver_badge(self):
        user = self._make_user(gifts=0, trades=5)
        recalculate_karma_badges()
        user.refresh_from_db()
        assert user.giver_badge is None

    def test_zero_trades_gets_no_trader_badge(self):
        user = self._make_user(gifts=5, trades=0)
        recalculate_karma_badges()
        user.refresh_from_db()
        assert user.trader_badge is None

    def test_top_10_giver_assigned(self):
        # Create 10 users; the one with the most gifts should be top_10.
        users = [self._make_user(gifts=i + 1) for i in range(10)]
        recalculate_karma_badges()
        users[9].refresh_from_db()
        assert users[9].giver_badge == User.BadgeChoices.TOP_10

    def test_top_25_giver_assigned(self):
        # 20 users: the 3rd-highest should be top_25 (rank ~10-25%).
        users = [self._make_user(gifts=i + 1) for i in range(20)]
        recalculate_karma_badges()
        # Rank 2 (0-indexed) = 10th percentile exactly → top_25
        users[17].refresh_from_db()
        assert users[17].giver_badge == User.BadgeChoices.TOP_25

    def test_top_10_trader_assigned(self):
        users = [self._make_user(trades=i + 1) for i in range(10)]
        recalculate_karma_badges()
        users[9].refresh_from_db()
        assert users[9].trader_badge == User.BadgeChoices.TOP_10

    def test_institutional_users_excluded(self):
        lib = UserFactory(
            account_type=User.AccountType.LIBRARY,
            is_active=True,
            email_verified=True,
            gifts_given_count=100,
            total_trades=100,
        )
        recalculate_karma_badges()
        lib.refresh_from_db()
        assert lib.giver_badge is None
        assert lib.trader_badge is None

    def test_inactive_users_excluded(self):
        inactive = UserFactory(
            account_type=User.AccountType.INDIVIDUAL,
            is_active=False,
            email_verified=True,
            gifts_given_count=100,
            total_trades=100,
        )
        recalculate_karma_badges()
        inactive.refresh_from_db()
        assert inactive.giver_badge is None
        assert inactive.trader_badge is None

    def test_badges_cleared_when_user_drops_to_zero(self):
        user = self._make_user(gifts=5, trades=5)
        user.giver_badge = User.BadgeChoices.TOP_10
        user.trader_badge = User.BadgeChoices.TOP_10
        user.gifts_given_count = 0
        user.total_trades = 0
        user.save(update_fields=["giver_badge", "trader_badge", "gifts_given_count", "total_trades"])

        recalculate_karma_badges()
        user.refresh_from_db()
        assert user.giver_badge is None
        assert user.trader_badge is None

    def test_badges_independent(self):
        # User has gifts but no trades.
        user = self._make_user(gifts=10, trades=0)
        recalculate_karma_badges()
        user.refresh_from_db()
        assert user.giver_badge == User.BadgeChoices.TOP_10
        assert user.trader_badge is None

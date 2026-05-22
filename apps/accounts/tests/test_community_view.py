import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.tests.factories import UserFactory, UserBookFactory
from apps.inventory.models import UserBook


@pytest.mark.django_db
class TestCommunityListView:
    URL = "community-list"

    def _make_individual(self, **kwargs):
        return UserFactory(
            account_type=User.AccountType.INDIVIDUAL,
            is_active=True,
            email_verified=True,
            **kwargs,
        )

    def test_returns_200_for_anonymous(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK

    def test_only_individual_active_verified_users_returned(self, api_client):
        individual = self._make_individual()
        library = UserFactory(account_type=User.AccountType.LIBRARY, is_verified=True)
        inactive = self._make_individual(is_active=False)
        unverified = self._make_individual(email_verified=False)

        response = api_client.get(reverse(self.URL))
        ids = [u["id"] for u in response.data["results"]]
        assert str(individual.id) in ids
        assert str(library.id) not in ids
        assert str(inactive.id) not in ids
        assert str(unverified.id) not in ids

    def test_karma_field_present(self, api_client):
        self._make_individual(total_trades=3, gifts_given_count=2)
        response = api_client.get(reverse(self.URL))
        user_data = response.data["results"][0]
        assert "karma" in user_data
        assert user_data["karma"] == 3 + 2 * 2

    def test_default_ordering_by_karma_desc(self, api_client):
        low = self._make_individual(total_trades=1, gifts_given_count=0)
        high = self._make_individual(total_trades=10, gifts_given_count=5)
        response = api_client.get(reverse(self.URL))
        ids = [u["id"] for u in response.data["results"]]
        assert ids.index(str(high.id)) < ids.index(str(low.id))

    def test_ordering_by_total_trades(self, api_client):
        low = self._make_individual(total_trades=1)
        high = self._make_individual(total_trades=50)
        response = api_client.get(reverse(self.URL), {"ordering": "-total_trades"})
        ids = [u["id"] for u in response.data["results"]]
        assert ids.index(str(high.id)) < ids.index(str(low.id))

    def test_ordering_by_gifts_given(self, api_client):
        low = self._make_individual(gifts_given_count=1)
        high = self._make_individual(gifts_given_count=20)
        response = api_client.get(reverse(self.URL), {"ordering": "-gifts_given_count"})
        ids = [u["id"] for u in response.data["results"]]
        assert ids.index(str(high.id)) < ids.index(str(low.id))

    def test_search_by_username(self, api_client):
        target = self._make_individual()
        other = self._make_individual()
        response = api_client.get(reverse(self.URL), {"search": target.username})
        ids = [u["id"] for u in response.data["results"]]
        assert str(target.id) in ids
        assert str(other.id) not in ids

    def test_giver_badge_filter(self, api_client):
        with_badge = self._make_individual(giver_badge=User.BadgeChoices.TOP_10)
        without_badge = self._make_individual(giver_badge=None)
        response = api_client.get(reverse(self.URL), {"giver_badge": "top_10"})
        ids = [u["id"] for u in response.data["results"]]
        assert str(with_badge.id) in ids
        assert str(without_badge.id) not in ids

    def test_trader_badge_filter(self, api_client):
        with_badge = self._make_individual(trader_badge=User.BadgeChoices.TOP_25)
        without_badge = self._make_individual(trader_badge=None)
        response = api_client.get(reverse(self.URL), {"trader_badge": "top_25"})
        ids = [u["id"] for u in response.data["results"]]
        assert str(with_badge.id) in ids
        assert str(without_badge.id) not in ids

    def test_has_books_filter(self, api_client):
        with_books = self._make_individual()
        UserBookFactory(user=with_books, status=UserBook.Status.AVAILABLE)
        without_books = self._make_individual()

        response = api_client.get(reverse(self.URL), {"has_books": "true"})
        ids = [u["id"] for u in response.data["results"]]
        assert str(with_books.id) in ids
        assert str(without_books.id) not in ids

    def test_pagination(self, api_client):
        for _ in range(5):
            self._make_individual()
        response = api_client.get(reverse(self.URL), {"page_size": 2})
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert "count" in response.data
        assert len(response.data["results"]) == 2

    def test_response_fields(self, api_client):
        self._make_individual(
            total_trades=2,
            gifts_given_count=1,
            giver_badge=User.BadgeChoices.TOP_10,
        )
        response = api_client.get(reverse(self.URL))
        user_data = response.data["results"][0]
        for field in ["id", "username", "karma", "total_trades", "gifts_given_count",
                      "avg_recent_rating", "giver_badge", "trader_badge", "created_at"]:
            assert field in user_data, f"Missing field: {field}"

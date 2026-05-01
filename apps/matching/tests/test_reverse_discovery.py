import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.models import UserBook
from apps.matching.models import Match, MatchLeg
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)


@pytest.mark.django_db
class TestReverseDiscoveryView:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        user = UserFactory(email_verified=True)
        return user

    def test_reverse_discovery_basic(self, api_client, user):
        """Test that we find a partner who wants our book but we don't want theirs yet."""
        api_client.force_authenticate(user=user)

        # Current user has Book A available
        book_a = BookFactory(title="Book A")
        UserBookFactory(user=user, book=book_a, status=UserBook.Status.AVAILABLE)

        # Partner has Book B available and wants Book A
        partner = UserFactory(username="partner")
        book_b = BookFactory(title="Book B")
        UserBookFactory(user=partner, book=book_b, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=partner, book=book_a, is_active=True)

        url = "/api/v1/matches/discovery/reverse/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert len(data) == 1
        assert data[0]["user"]["username"] == "partner"
        assert data[0]["they_want"][0]["book"]["title"] == "Book A"
        assert data[0]["they_offer"][0]["book"]["title"] == "Book B"

    def test_reverse_discovery_excludes_active_matches(self, api_client, user):
        """Test that partners with whom we already have an active match are excluded."""
        api_client.force_authenticate(user=user)

        # Current user has Book A
        book_a = BookFactory(title="Book A")
        ub_a = UserBookFactory(user=user, book=book_a, status=UserBook.Status.AVAILABLE)

        # Partner has Book B and wants Book A
        partner = UserFactory(username="partner")
        book_b = BookFactory(title="Book B")
        ub_b = UserBookFactory(user=partner, book=book_b, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=partner, book=book_a, is_active=True)

        # Create an existing active match
        match = Match.objects.create(match_type=Match.MatchType.DIRECT, status=Match.Status.PENDING)
        MatchLeg.objects.create(match=match, sender=user, receiver=partner, user_book=ub_a, position=0)
        MatchLeg.objects.create(match=match, sender=partner, receiver=user, user_book=ub_b, position=1)

        url = "/api/v1/matches/discovery/reverse/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_reverse_discovery_excludes_items_already_in_wishlist(self, api_client, user):
        """Test that 'they_offer' excludes books already in the current user's wishlist."""
        api_client.force_authenticate(user=user)

        # Current user has Book A and wants Book B
        book_a = BookFactory(title="Book A")
        book_b = BookFactory(title="Book B")
        UserBookFactory(user=user, book=book_a, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user, book=book_b, is_active=True)

        # Partner wants Book A and has Book B AND Book C
        partner = UserFactory(username="partner")
        book_c = BookFactory(title="Book C")
        UserBookFactory(user=partner, book=book_b, status=UserBook.Status.AVAILABLE)
        UserBookFactory(user=partner, book=book_c, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=partner, book=book_a, is_active=True)

        url = "/api/v1/matches/discovery/reverse/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert len(data) == 1
        # Should only offer Book C because Book B is already in our wishlist
        assert len(data[0]["they_offer"]) == 1
        assert data[0]["they_offer"][0]["book"]["title"] == "Book C"

    def test_reverse_discovery_empty_for_no_books(self, api_client, user):
        api_client.force_authenticate(user=user)
        url = "/api/v1/matches/discovery/reverse/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

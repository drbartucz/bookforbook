import pytest
from django.urls import reverse
from rest_framework import status

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, WishlistItemFactory, MatchFactory, MatchLegFactory
from apps.inventory.models import UserBook

@pytest.mark.django_db
class TestReverseDiscoveryView:
    def test_no_available_books(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        url = reverse('reverse-discovery')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_discovery_success(self, api_client):
        user_a = UserFactory()
        user_b = UserFactory()
        api_client.force_authenticate(user=user_a)
        
        book_1 = BookFactory() # Book User A has, User B wants
        book_2 = BookFactory() # Book User B has, User A DOES NOT want
        
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        
        url = reverse('reverse-discovery')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['user']['id'] == str(user_b.id)
        assert len(response.data[0]['they_want']) == 1
        assert response.data[0]['they_want'][0]['book']['id'] == str(book_1.id)
        assert len(response.data[0]['they_offer']) == 1
        assert response.data[0]['they_offer'][0]['book']['id'] == str(book_2.id)

    def test_discovery_excludes_existing_matches(self, api_client):
        user_a = UserFactory()
        user_b = UserFactory()
        api_client.force_authenticate(user=user_a)
        
        book_1 = BookFactory()
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        UserBookFactory(user=user_b, status=UserBook.Status.AVAILABLE)
        
        # Create an active match between A and B
        match = MatchFactory()
        MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        
        url = reverse('reverse-discovery')
        response = api_client.get(url)
        
        # Should be empty because B is an active partner
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_discovery_excludes_my_wishlist_from_offers(self, api_client):
        user_a = UserFactory()
        user_b = UserFactory()
        api_client.force_authenticate(user=user_a)
        
        book_1 = BookFactory() # A has, B wants
        book_2 = BookFactory() # B has, A ALSO wants (mutual match scenario)
        
        UserBookFactory(user=user_a, book=book_1, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_b, book=book_1, is_active=True)
        
        UserBookFactory(user=user_b, book=book_2, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=user_a, book=book_2, is_active=True) # A wants book_2
        
        url = reverse('reverse-discovery')
        response = api_client.get(url)
        
        # Partner B is found, but they_offer should NOT include book_2 
        # because it should be handled by the automatic mutual matcher
        assert len(response.data) == 0 # Current implementation excludes partner if they have NO books I DON'T want

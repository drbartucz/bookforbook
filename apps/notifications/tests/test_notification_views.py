import pytest
from django.urls import reverse
from rest_framework import status

from apps.tests.factories import UserFactory, NotificationFactory, MatchFactory, MatchLegFactory, TradeProposalFactory

@pytest.mark.django_db
class TestNotificationViews:
    def test_notification_list(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        NotificationFactory(user=user)
        NotificationFactory(user=user)
        NotificationFactory() # Unrelated
        
        url = reverse('notification-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_pending_counts(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)
        
        # 1 Pending match
        match = MatchFactory()
        MatchLegFactory(match=match, sender=user, receiver=other)
        
        # 1 Pending proposal (recipient)
        TradeProposalFactory(proposer=other, recipient=user)
        
        # 2 Unread notifications
        NotificationFactory(user=user, is_read=False)
        NotificationFactory(user=user, is_read=False)
        
        url = reverse('notification-counts')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pending_matches'] == 1
        assert response.data['pending_proposals'] == 1
        assert response.data['unread_notifications'] == 2

    def test_mark_read(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        n = NotificationFactory(user=user, is_read=False)
        
        url = reverse('notification-read', kwargs={'pk': n.pk})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        n.refresh_from_db()
        assert n.is_read is True

    def test_mark_all_read(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        NotificationFactory(user=user, is_read=False)
        NotificationFactory(user=user, is_read=False)
        
        url = reverse('notifications-read-all')
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['detail'] == "2 notification(s) marked as read."

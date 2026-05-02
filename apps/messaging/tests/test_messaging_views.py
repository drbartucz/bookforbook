import pytest
from django.urls import reverse
from rest_framework import status

from apps.tests.factories import UserFactory, TradeFactory, TradeShipmentFactory, TradeMessageFactory
from apps.messaging.models import TradeMessage
from apps.trading.models import Trade

@pytest.mark.django_db
class TestMessagingViews:
    def test_message_list_participant(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory()
        TradeShipmentFactory(trade=trade, sender=user, receiver=other)
        
        TradeMessageFactory(trade=trade, sender=other, content="Hello", message_type=TradeMessage.MessageType.GENERAL_NOTE)
        TradeMessageFactory(trade=trade, sender=user, content="Hi", message_type=TradeMessage.MessageType.GENERAL_NOTE)
        
        url = reverse('trade-messages', kwargs={'pk': trade.pk})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        # Verify unread marking
        assert TradeMessage.objects.filter(trade=trade, sender=other, read_at__isnull=False).exists()

    def test_message_list_non_participant(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory() # Unrelated trade
        TradeShipmentFactory(trade=trade, sender=UserFactory(), receiver=UserFactory())
        
        url = reverse('trade-messages', kwargs={'pk': trade.pk})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_message_create_success(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        TradeShipmentFactory(trade=trade, sender=user, receiver=other)
        
        url = reverse('trade-messages', kwargs={'pk': trade.pk})
        data = {
            "content": "Test message",
            "message_type": TradeMessage.MessageType.GENERAL_NOTE
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert TradeMessage.objects.filter(trade=trade, sender=user, content="Test message").exists()

    def test_message_create_completed_trade(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory(status=Trade.Status.COMPLETED)
        TradeShipmentFactory(trade=trade, sender=user, receiver=UserFactory())
        
        url = reverse('trade-messages', kwargs={'pk': trade.pk})
        response = api_client.post(url, {
            "content": "too late",
            "message_type": TradeMessage.MessageType.GENERAL_NOTE
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

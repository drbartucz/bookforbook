import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

from apps.tests.factories import (
    UserFactory, 
    BookFactory, 
    UserBookFactory, 
    TradeFactory, 
    TradeShipmentFactory, 
    TradeProposalFactory,
    TradeProposalItemFactory
)
from apps.trading.models import Trade, TradeProposal, TradeShipment
from apps.inventory.models import UserBook
from apps.accounts.models import User

@pytest.mark.django_db
class TestTradingViews:
    def test_proposal_list(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        TradeProposalFactory(proposer=user)
        TradeProposalFactory(recipient=user)
        TradeProposalFactory() # Unrelated
        
        url = reverse('proposal-list-create')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_proposal_create(self, api_client):
        user = UserFactory(address_verification_status=User.AddressVerificationStatus.VERIFIED)
        recipient = UserFactory()
        ub_proposer = UserBookFactory(user=user, status=UserBook.Status.AVAILABLE)
        ub_recipient = UserBookFactory(user=recipient, status=UserBook.Status.AVAILABLE)
        
        api_client.force_authenticate(user=user)
        
        url = reverse('proposal-list-create')
        data = {
            "recipient_id": str(recipient.id),
            "proposer_book_id": str(ub_proposer.id),
            "recipient_book_id": str(ub_recipient.id),
            "message": "Let's trade!"
        }
        
        with patch("apps.notifications.models.Notification.objects.create") as mock_notify:
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_201_CREATED
            assert mock_notify.called
            assert TradeProposal.objects.filter(proposer=user, recipient=recipient).exists()

    def test_proposal_accept_success(self, api_client):
        user = UserFactory() # recipient
        proposer = UserFactory()
        api_client.force_authenticate(user=user)
        
        proposal = TradeProposalFactory(proposer=proposer, recipient=user)
        TradeProposalItemFactory(proposal=proposal)
        
        url = reverse('proposal-accept', kwargs={'pk': proposal.pk})
        
        with patch("apps.trading.views.user_has_verified_shipping_address", return_value=True):
            with patch("apps.trading.services.trade_workflow.create_trade_from_proposal") as mock_create:
                mock_create.return_value = TradeFactory()
                response = api_client.post(url)
                assert response.status_code == status.HTTP_200_OK
                proposal.refresh_from_db()
                assert proposal.status == TradeProposal.Status.COMPLETED

    def test_proposal_decline(self, api_client):
        user = UserFactory()
        proposal = TradeProposalFactory(recipient=user)
        api_client.force_authenticate(user=user)
        
        url = reverse('proposal-decline', kwargs={'pk': proposal.pk})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        proposal.refresh_from_db()
        assert proposal.status == TradeProposal.Status.DECLINED

    def test_trade_list(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory()
        TradeShipmentFactory(trade=trade, sender=user)
        
        url = reverse('trade-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_trade_mark_shipped(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        shipment = TradeShipmentFactory(trade=trade, sender=user, status=TradeShipment.Status.PENDING)
        
        url = reverse('trade-mark-shipped', kwargs={'pk': trade.pk})
        data = {"tracking_number": "123", "shipping_method": "USPS"}
        
        with patch("apps.trading.services.trade_workflow.mark_shipped") as mock_mark:
            response = api_client.post(url, data)
            assert response.status_code == status.HTTP_200_OK
            assert mock_mark.called

    def test_trade_mark_received(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        shipment = TradeShipmentFactory(trade=trade, receiver=user, status=TradeShipment.Status.SHIPPED)
        
        url = reverse('trade-mark-received', kwargs={'pk': trade.pk})
        
        with patch("apps.trading.services.trade_workflow.mark_received") as mock_mark:
            response = api_client.post(url)
            assert response.status_code == status.HTTP_200_OK
            assert mock_mark.called

    def test_trade_rate(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)
        
        trade = TradeFactory(status=Trade.Status.ONE_RECEIVED)
        TradeShipmentFactory(trade=trade, sender=user, receiver=other)
        TradeShipmentFactory(trade=trade, sender=other, receiver=user)
        
        url = reverse('trade-rate', kwargs={'pk': trade.pk})
        data = {
            "rated_user_id": str(other.id),
            "score": 5,
            "book_condition_accurate": True,
            "comment": "Great!"
        }
        
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        from apps.ratings.models import Rating
        assert Rating.objects.filter(trade=trade, rater=user).exists()

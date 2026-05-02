import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone

from apps.tests.factories import (
    UserFactory, 
    BookFactory, 
    UserBookFactory, 
    MatchFactory, 
    MatchLegFactory, 
    TradeFactory, 
    TradeShipmentFactory, 
    TradeProposalFactory,
    TradeProposalItemFactory
)
from apps.trading.models import Trade, TradeShipment, TradeProposal, TradeProposalItem
from apps.inventory.models import UserBook
from apps.trading.services.trade_workflow import (
    create_trade_from_match,
    create_trade_from_proposal,
    reveal_addresses,
    mark_shipped,
    mark_received,
    check_trade_completion
)

@pytest.mark.django_db
class TestTradeWorkflow:
    @patch("django_q.tasks.async_task")
    def test_create_trade_from_match(self, mock_async):
        user_a = UserFactory()
        user_b = UserFactory()
        match = MatchFactory()
        leg1 = MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        leg2 = MatchLegFactory(match=match, sender=user_b, receiver=user_a)
        
        trade = create_trade_from_match(match)
        
        assert trade.status == Trade.Status.CONFIRMED
        assert trade.shipments.count() == 2
        assert UserBook.objects.get(pk=leg1.user_book.pk).status == UserBook.Status.RESERVED
        assert mock_async.called

    @patch("django_q.tasks.async_task")
    def test_create_trade_from_proposal(self, mock_async):
        user_a = UserFactory()
        user_b = UserFactory()
        proposal = TradeProposalFactory(proposer=user_a, recipient=user_b)
        
        ub_a = UserBookFactory(user=user_a, status=UserBook.Status.AVAILABLE)
        ub_b = UserBookFactory(user=user_b, status=UserBook.Status.AVAILABLE)
        
        TradeProposalItemFactory(proposal=proposal, user_book=ub_a, direction=TradeProposalItem.Direction.PROPOSER_SENDS)
        TradeProposalItemFactory(proposal=proposal, user_book=ub_b, direction=TradeProposalItem.Direction.RECIPIENT_SENDS)
        
        trade = create_trade_from_proposal(proposal)
        
        assert trade.status == Trade.Status.CONFIRMED
        assert trade.shipments.count() == 2
        assert UserBook.objects.get(pk=ub_a.pk).status == UserBook.Status.RESERVED
        assert mock_async.called

    def test_reveal_addresses(self):
        user_a = UserFactory(username="user_a", address_line_1="Address A")
        user_b = UserFactory(username="user_b", address_line_1="Address B")
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b)
        TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a)
        
        # User A requests B's address
        addresses = reveal_addresses(trade, user_a)
        assert str(user_b.id) in addresses
        assert addresses[str(user_b.id)]['address_line_1'] == "Address B"
        
    def test_mark_shipped(self):
        user_a = UserFactory(username="sender")
        user_b = UserFactory(username="receiver")
        trade = TradeFactory(status=Trade.Status.CONFIRMED)
        shipment = TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b, status=TradeShipment.Status.PENDING)
        
        mark_shipped(shipment, "TRACK123", "USPS")
        
        shipment.refresh_from_db()
        assert shipment.status == TradeShipment.Status.SHIPPED
        assert shipment.tracking_number == "TRACK123"
        trade.refresh_from_db()
        assert trade.status == Trade.Status.SHIPPING

    def test_check_trade_completion(self):
        user_a = UserFactory()
        user_b = UserFactory()
        trade = TradeFactory(status=Trade.Status.SHIPPING)
        s1 = TradeShipmentFactory(trade=trade, sender=user_a, receiver=user_b, status=TradeShipment.Status.RECEIVED)
        s2 = TradeShipmentFactory(trade=trade, sender=user_b, receiver=user_a, status=TradeShipment.Status.SHIPPED)
        
        # Partially received
        check_trade_completion(trade)
        trade.refresh_from_db()
        assert trade.status == Trade.Status.ONE_RECEIVED
        
        # Fully received
        s2.status = TradeShipment.Status.RECEIVED
        s2.save()
        check_trade_completion(trade)
        trade.refresh_from_db()
        assert trade.status == Trade.Status.COMPLETED
        assert trade.completed_at is not None
        
        assert UserBook.objects.get(pk=s1.user_book.pk).status == UserBook.Status.TRADED
        user_a.refresh_from_db()
        assert user_a.total_trades == 1

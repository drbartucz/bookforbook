"""
Trade workflow service — handles creation and lifecycle of trades.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@transaction.atomic
def create_trade_from_match(match) -> 'Trade':
    """
    Create a Trade and TradeShipments from a confirmed Match.
    Marks all involved UserBooks as 'reserved'.
    """
    from apps.inventory.models import UserBook
    from apps.trading.models import Trade, TradeShipment

    trade = Trade.objects.create(
        source_type=Trade.SourceType.MATCH,
        source_id=match.pk,
        status=Trade.Status.CONFIRMED,
    )

    for leg in match.legs.select_related('sender', 'receiver', 'user_book').all():
        TradeShipment.objects.create(
            trade=trade,
            sender=leg.sender,
            receiver=leg.receiver,
            user_book=leg.user_book,
        )
        # Reserve the book
        UserBook.objects.filter(pk=leg.user_book_id).update(
            status=UserBook.Status.RESERVED
        )

    # Notify all parties
    try:
        from django_q.tasks import async_task
        async_task('apps.notifications.tasks.send_trade_confirmed_notification', str(trade.pk))
    except Exception:
        logger.exception('Failed to queue trade confirmed notification for trade %s', trade.pk)

    logger.info('Created trade %s from match %s', trade.pk, match.pk)
    return trade


@transaction.atomic
def create_trade_from_proposal(proposal) -> 'Trade':
    """
    Create a Trade and TradeShipments from an accepted TradeProposal.
    """
    from apps.inventory.models import UserBook
    from apps.trading.models import Trade, TradeProposalItem, TradeShipment

    trade = Trade.objects.create(
        source_type=Trade.SourceType.PROPOSAL,
        source_id=proposal.pk,
        status=Trade.Status.CONFIRMED,
    )

    for item in proposal.items.select_related('user_book__user', 'user_book__book').all():
        if item.direction == TradeProposalItem.Direction.PROPOSER_SENDS:
            sender = proposal.proposer
            receiver = proposal.recipient
        else:
            sender = proposal.recipient
            receiver = proposal.proposer

        TradeShipment.objects.create(
            trade=trade,
            sender=sender,
            receiver=receiver,
            user_book=item.user_book,
        )
        UserBook.objects.filter(pk=item.user_book_id).update(
            status=UserBook.Status.RESERVED
        )

    try:
        from django_q.tasks import async_task
        async_task('apps.notifications.tasks.send_trade_confirmed_notification', str(trade.pk))
    except Exception:
        logger.exception('Failed to queue trade confirmed notification for trade %s', trade.pk)

    logger.info('Created trade %s from proposal %s', trade.pk, proposal.pk)
    return trade


def reveal_addresses(trade, requesting_user) -> dict:
    """
    Return the decrypted address of the other party in a trade.
    Only callable if the trade is in confirmed+ status and requester is a party.
    """
    from apps.trading.models import Trade

    if trade.status not in [
        Trade.Status.CONFIRMED,
        Trade.Status.SHIPPING,
        Trade.Status.ONE_RECEIVED,
        Trade.Status.COMPLETED,
        Trade.Status.AUTO_CLOSED,
    ]:
        return {}

    # Get all parties in this trade
    shipments = trade.shipments.select_related('sender', 'receiver').all()
    parties = set()
    for s in shipments:
        parties.add(s.sender)
        parties.add(s.receiver)

    if requesting_user not in parties:
        return {}

    # Return addresses of all OTHER parties
    addresses = {}
    for party in parties:
        if party == requesting_user:
            continue
        addresses[str(party.id)] = {
            'username': party.username,
            'full_name': party.full_name,
            'address_line_1': party.address_line_1,
            'address_line_2': party.address_line_2,
            'city': party.city,
            'state': party.state,
            'zip_code': party.zip_code,
        }
    return addresses


def mark_shipped(shipment, tracking: str, method: str):
    """Mark a shipment as shipped with tracking info."""
    from apps.trading.models import Trade, TradeShipment

    shipment.tracking_number = tracking
    shipment.shipping_method = method
    shipment.shipped_at = timezone.now()
    shipment.status = TradeShipment.Status.SHIPPED
    shipment.save(update_fields=['tracking_number', 'shipping_method', 'shipped_at', 'status'])

    # Update trade status
    trade = shipment.trade
    all_shipments = list(trade.shipments.all())
    any_shipped = any(s.status == TradeShipment.Status.SHIPPED for s in all_shipments)

    if any_shipped and trade.status == Trade.Status.CONFIRMED:
        trade.status = Trade.Status.SHIPPING
        trade.save(update_fields=['status'])

    # Notify receiver
    try:
        from apps.notifications.models import Notification
        Notification.objects.create(
            user=shipment.receiver,
            notification_type='shipment_sent',
            title='Your book is on its way!',
            body=f'{shipment.sender.username} has shipped {shipment.user_book.book.title}.',
            metadata={'trade_id': str(trade.pk), 'tracking_number': tracking, 'method': method},
        )
    except Exception:
        logger.exception('Failed to create shipment notification')


def mark_received(shipment):
    """Mark a shipment as received. Check if trade is complete."""
    from apps.trading.models import TradeShipment

    shipment.received_at = timezone.now()
    shipment.status = TradeShipment.Status.RECEIVED
    shipment.save(update_fields=['received_at', 'status'])

    check_trade_completion(shipment.trade)


def check_trade_completion(trade):
    """
    Check if all shipments are received. If so, complete the trade.
    Updates UserBook statuses and user trade counts.
    """
    from apps.trading.models import Trade, TradeShipment
    from apps.inventory.models import UserBook

    # Refresh trade object
    trade.refresh_from_db()
    all_shipments = list(trade.shipments.all())

    received_count = sum(1 for s in all_shipments if s.status == TradeShipment.Status.RECEIVED)
    total_count = len(all_shipments)

    if received_count == 1 and total_count > 1 and trade.status == Trade.Status.SHIPPING:
        trade.status = Trade.Status.ONE_RECEIVED
        trade.save(update_fields=['status'])

    elif received_count == total_count:
        trade.status = Trade.Status.COMPLETED
        trade.completed_at = timezone.now()
        trade.save(update_fields=['status', 'completed_at'])

        # Mark all books as traded
        book_ids = [s.user_book_id for s in all_shipments]
        UserBook.objects.filter(pk__in=book_ids).update(status=UserBook.Status.TRADED)

        # Update trade counts for all unique users
        user_ids = set()
        for s in all_shipments:
            user_ids.add(s.sender_id)
            user_ids.add(s.receiver_id)

        from apps.accounts.models import User
        from django.db.models import F
        User.objects.filter(pk__in=user_ids).update(total_trades=F('total_trades') + 1)

        # Notify all parties
        try:
            from apps.notifications.models import Notification
            for uid in user_ids:
                Notification.objects.create(
                    user_id=uid,
                    notification_type='trade_completed',
                    title='Trade completed!',
                    body='Your trade has been completed. Please leave a rating.',
                    metadata={'trade_id': str(trade.pk)},
                )
        except Exception:
            logger.exception('Failed to create trade completion notifications for trade %s', trade.pk)

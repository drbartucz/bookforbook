import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_rating_reminders():
    """
    Weekly task: send rating reminders to users who haven't rated yet.
    Sends up to 3 reminders per trade, then gives up.
    """
    from apps.trading.models import Trade, TradeShipment
    from apps.ratings.models import Rating

    # Find completed/shipping trades that still need ratings
    active_statuses = [
        Trade.Status.COMPLETED,
        Trade.Status.SHIPPING,
        Trade.Status.ONE_RECEIVED,
    ]
    trades = Trade.objects.filter(
        status__in=active_statuses,
        rating_reminders_sent__lt=3,
    ).prefetch_related('shipments__sender', 'shipments__receiver')

    for trade in trades:
        # Get all parties
        user_ids = set()
        for shipment in trade.shipments.all():
            user_ids.add(str(shipment.sender_id))
            user_ids.add(str(shipment.receiver_id))

        # Find who hasn't rated yet
        rated_user_ids = set(
            str(uid) for uid in Rating.objects.filter(
                trade=trade
            ).values_list('rater_id', flat=True)
        )

        unrated_user_ids = user_ids - rated_user_ids

        for uid in unrated_user_ids:
            try:
                from apps.notifications.tasks import send_rating_reminder
                send_rating_reminder.delay(str(trade.pk), uid)
            except Exception:
                logger.exception('Failed to queue rating reminder for trade %s, user %s', trade.pk, uid)

        trade.rating_reminders_sent += 1
        trade.save(update_fields=['rating_reminders_sent'])


@shared_task
def auto_close_trades():
    """
    Weekly task: close trades that have passed their auto_close_at deadline.
    Marks books as traded, updates user counts, no rating recorded.
    """
    from apps.trading.models import Trade, TradeShipment
    from apps.inventory.models import UserBook
    from apps.accounts.models import User
    from django.db.models import F

    now = timezone.now()
    trades_to_close = Trade.objects.filter(
        status__in=[Trade.Status.CONFIRMED, Trade.Status.SHIPPING, Trade.Status.ONE_RECEIVED],
        auto_close_at__lt=now,
    ).prefetch_related('shipments')

    for trade in trades_to_close:
        try:
            all_shipments = list(trade.shipments.all())

            # Mark all pending/shipped shipments as received
            TradeShipment.objects.filter(
                trade=trade,
                status__in=[TradeShipment.Status.PENDING, TradeShipment.Status.SHIPPED],
            ).update(
                status=TradeShipment.Status.RECEIVED,
                received_at=now,
            )

            # Mark all books as traded
            book_ids = [s.user_book_id for s in all_shipments]
            UserBook.objects.filter(pk__in=book_ids).update(status=UserBook.Status.TRADED)

            # Update trade counts
            user_ids = set()
            for s in all_shipments:
                user_ids.add(s.sender_id)
                user_ids.add(s.receiver_id)

            User.objects.filter(pk__in=user_ids).update(total_trades=F('total_trades') + 1)

            # Close trade
            trade.status = Trade.Status.AUTO_CLOSED
            trade.completed_at = now
            trade.save(update_fields=['status', 'completed_at'])

            # Notify
            for uid in user_ids:
                try:
                    from apps.notifications.models import Notification
                    Notification.objects.create(
                        user_id=uid,
                        notification_type='trade_auto_closed',
                        title='Trade auto-closed',
                        body=(
                            'Your trade has been automatically closed after 3 weeks. '
                            'The book has been marked as received.'
                        ),
                        metadata={'trade_id': str(trade.pk)},
                    )
                except Exception:
                    logger.exception('Failed to notify user %s of auto-close', uid)

            logger.info('Auto-closed trade %s', trade.pk)
        except Exception:
            logger.exception('Failed to auto-close trade %s', trade.pk)

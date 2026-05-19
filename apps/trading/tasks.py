import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_trade_manager():
    from apps.accounts.models import User
    user, created = User.objects.get_or_create(
        username="trademanager",
        defaults={
            "email": "trademanager@system.internal",
            "is_active": False,
        },
    )
    if not created and user.is_active:
        user.is_active = False
        user.save(update_fields=["is_active"])
    return user


def send_rating_reminders():
    """
    Weekly task: send rating reminders to users who haven't rated yet.
    Sends up to 3 reminders per trade, then gives up.
    """
    from apps.trading.models import Trade
    from apps.ratings.models import Rating
    from django_q.tasks import async_task

    active_statuses = [
        Trade.Status.COMPLETED,
        Trade.Status.SHIPPING,
        Trade.Status.ONE_RECEIVED,
    ]
    trades = Trade.objects.filter(
        status__in=active_statuses,
        rating_reminders_sent__lt=3,
    ).prefetch_related("shipments__sender", "shipments__receiver")

    for trade in trades:
        user_ids = set()
        for shipment in trade.shipments.all():
            user_ids.add(str(shipment.sender_id))
            user_ids.add(str(shipment.receiver_id))

        rated_user_ids = set(
            str(uid)
            for uid in Rating.objects.filter(trade=trade).values_list(
                "rater_id", flat=True
            )
        )

        unrated_user_ids = user_ids - rated_user_ids

        queued_count = 0
        for uid in unrated_user_ids:
            try:
                async_task(
                    "apps.notifications.tasks.send_rating_reminder", str(trade.pk), uid
                )
                queued_count += 1
            except Exception:
                logger.exception(
                    "Failed to queue rating reminder for trade %s, user %s",
                    trade.pk,
                    uid,
                )

        if queued_count > 0:
            trade.rating_reminders_sent += 1
            trade.save(update_fields=["rating_reminders_sent"])


def auto_close_trades():
    """
    Weekly task: close trades that have passed their auto_close_at deadline.

    Per-shipment logic for SHIPPING / ONE_RECEIVED trades:
      - Valid tracking or already RECEIVED  → 5-star auto-rating, book TRADED, both parties credited
      - No valid tracking                   → 1-star auto-rating, book AVAILABLE, no credit
    CONFIRMED trades (nothing shipped at all) → books restored, no ratings, no credit.
    """
    from apps.trading.models import Trade, TradeShipment
    from apps.inventory.models import UserBook
    from apps.accounts.models import User
    from apps.ratings.models import Rating
    from apps.ratings.services.rolling_average import recompute_rating_average
    from apps.trading.utils import is_valid_tracking_number

    now = timezone.now()

    trades_to_close = (
        Trade.objects.select_for_update(skip_locked=True)
        .filter(
            status__in=[
                Trade.Status.CONFIRMED,
                Trade.Status.SHIPPING,
                Trade.Status.ONE_RECEIVED,
            ],
            auto_close_at__lt=now,
        )
        .prefetch_related("shipments__sender", "shipments__receiver", "shipments__user_book")
    )

    for trade in trades_to_close:
        try:
            all_shipments = list(trade.shipments.all())

            with transaction.atomic():
                if trade.status == Trade.Status.CONFIRMED:
                    # Nothing was shipped — restore books, no credit, no ratings
                    book_ids = [s.user_book_id for s in all_shipments]
                    UserBook.objects.filter(pk__in=book_ids).update(
                        status=UserBook.Status.AVAILABLE
                    )
                    _notify_confirmed_auto_close(trade, all_shipments)
                else:
                    # SHIPPING or ONE_RECEIVED — evaluate per shipment
                    trade_manager = _get_trade_manager()

                    for shipment in all_shipments:
                        shipped_ok = (
                            shipment.status == TradeShipment.Status.RECEIVED
                            or (
                                shipment.status
                                in (TradeShipment.Status.PENDING, TradeShipment.Status.SHIPPED)
                                and is_valid_tracking_number(shipment.tracking_number)
                            )
                        )

                        if shipped_ok:
                            if shipment.status != TradeShipment.Status.RECEIVED:
                                shipment.status = TradeShipment.Status.RECEIVED
                                shipment.received_at = now
                                shipment.save(update_fields=["status", "received_at"])

                            shipment.user_book.status = UserBook.Status.TRADED
                            shipment.user_book.save(update_fields=["status"])

                            User.objects.filter(
                                pk__in=[shipment.sender_id, shipment.receiver_id]
                            ).update(total_trades=F("total_trades") + 1)

                            Rating.objects.create(
                                trade=trade,
                                rater=trade_manager,
                                rated=shipment.sender,
                                score=5,
                                book_condition_accurate=True,
                            )
                            _notify_shipment_success(trade, shipment)
                        else:
                            shipment.status = TradeShipment.Status.NOT_RECEIVED
                            shipment.save(update_fields=["status"])

                            shipment.user_book.status = UserBook.Status.AVAILABLE
                            shipment.user_book.save(update_fields=["status"])

                            Rating.objects.create(
                                trade=trade,
                                rater=trade_manager,
                                rated=shipment.sender,
                                score=1,
                                comment="Did not ship",
                                book_condition_accurate=True,
                            )
                            _notify_shipment_failure(trade, shipment)

                    # Recompute rolling averages inside the transaction
                    for shipment in all_shipments:
                        try:
                            recompute_rating_average(shipment.sender)
                        except Exception:
                            logger.exception(
                                "Failed to recompute rating for user %s", shipment.sender_id
                            )

                trade.status = Trade.Status.AUTO_CLOSED
                trade.completed_at = now
                trade.save(update_fields=["status", "completed_at"])

            logger.info("Auto-closed trade %s", trade.pk)
        except Exception:
            logger.exception("Failed to auto-close trade %s", trade.pk)


def send_trade_closure_warnings():
    """
    Daily task: warn users whose trade is within 2 days of auto-close and
    who have not provided a valid tracking number.
    """
    from apps.trading.models import Trade, TradeShipment
    from apps.trading.utils import is_valid_tracking_number
    from django_q.tasks import async_task
    from datetime import timedelta

    now = timezone.now()
    warning_window_end = now + timedelta(days=2)

    trades = Trade.objects.filter(
        status__in=[
            Trade.Status.CONFIRMED,
            Trade.Status.SHIPPING,
            Trade.Status.ONE_RECEIVED,
        ],
        auto_close_at__range=(now, warning_window_end),
        closure_warning_sent_at__isnull=True,
    ).prefetch_related("shipments")

    for trade in trades:
        # Stamp the guard before queuing tasks so that a crash mid-loop
        # does not cause re-warnings on retry for this trade.
        updated = Trade.objects.filter(
            pk=trade.pk, closure_warning_sent_at__isnull=True
        ).update(closure_warning_sent_at=now)
        if not updated:
            # Another worker already claimed this trade.
            continue

        if trade.status == Trade.Status.CONFIRMED:
            # Nothing shipped at all — warn all senders
            for shipment in trade.shipments.all():
                try:
                    async_task(
                        "apps.notifications.tasks.send_closure_warning",
                        str(shipment.sender_id),
                        str(trade.pk),
                        "not_started",
                    )
                except Exception:
                    logger.exception(
                        "Failed to queue closure warning for trade %s, user %s",
                        trade.pk,
                        shipment.sender_id,
                    )
        else:
            # Warn only senders without valid tracking
            for shipment in trade.shipments.filter(
                status__in=[TradeShipment.Status.PENDING, TradeShipment.Status.SHIPPED]
            ):
                if not is_valid_tracking_number(shipment.tracking_number):
                    try:
                        async_task(
                            "apps.notifications.tasks.send_closure_warning",
                            str(shipment.sender_id),
                            str(trade.pk),
                            "no_tracking",
                        )
                    except Exception:
                        logger.exception(
                            "Failed to queue closure warning for trade %s, user %s",
                            trade.pk,
                            shipment.sender_id,
                        )

        logger.info("Queued closure warnings for trade %s", trade.pk)


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


def _notify_confirmed_auto_close(trade, shipments):
    sender_ids = {s.sender_id for s in shipments}
    receiver_ids = {s.receiver_id for s in shipments}
    all_ids = sender_ids | receiver_ids
    _create_notifications(
        trade,
        all_ids,
        "trade_auto_closed",
        "Trade auto-closed",
        "Your trade was auto-closed after 3 weeks. Neither party shipped, so your books have been returned to your available list.",
    )


def _notify_shipment_success(trade, shipment):
    from apps.notifications.models import Notification

    for user_id, msg in [
        (
            shipment.sender_id,
            "Your trade has been auto-closed. Your book was marked as received and you've been credited with a 5-star review.",
        ),
        (
            shipment.receiver_id,
            "Your trade has been auto-closed. Your partner's book was marked as received.",
        ),
    ]:
        try:
            Notification.objects.create(
                user_id=user_id,
                notification_type="trade_auto_closed",
                title="Trade auto-closed",
                body=msg,
                metadata={"trade_id": str(trade.pk)},
            )
        except Exception:
            logger.exception("Failed to notify user %s of auto-close", user_id)


def _notify_shipment_failure(trade, shipment):
    from apps.notifications.models import Notification

    msgs = {
        shipment.sender_id: (
            "Your trade has been auto-closed. No valid tracking number was found for your shipment. "
            "Your book has been returned to your available list and you have received a 1-star review."
        ),
        shipment.receiver_id: (
            "Your trade has been auto-closed. The other party did not ship their book. "
            "No trade credit has been recorded for that leg."
        ),
    }
    for user_id, body in msgs.items():
        try:
            Notification.objects.create(
                user_id=user_id,
                notification_type="trade_auto_closed",
                title="Trade auto-closed",
                body=body,
                metadata={"trade_id": str(trade.pk)},
            )
        except Exception:
            logger.exception("Failed to notify user %s of auto-close", user_id)


def _create_notifications(trade, user_ids, notification_type, title, body):
    from apps.notifications.models import Notification

    for uid in user_ids:
        try:
            Notification.objects.create(
                user_id=uid,
                notification_type=notification_type,
                title=title,
                body=body,
                metadata={"trade_id": str(trade.pk)},
            )
        except Exception:
            logger.exception("Failed to notify user %s", uid)

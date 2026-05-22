import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def recalculate_karma_badges() -> None:
    """
    Nightly task. Assigns giver_badge and trader_badge to individual users
    based on their percentile rank within active, email-verified individuals.
    Only users with at least 1 gift (for giver) or 1 trade (for trader) are eligible.
    """
    from .models import User

    users = list(
        User.objects.filter(
            account_type=User.AccountType.INDIVIDUAL,
            is_active=True,
            email_verified=True,
        ).values("id", "gifts_given_count", "total_trades")
    )

    all_ids = {u["id"] for u in users}

    def _assign_badges(users_list, metric_key, badge_giver_field):
        eligible = [u for u in users_list if u[metric_key] > 0]
        eligible.sort(key=lambda u: u[metric_key], reverse=True)

        n = len(eligible)
        top_10_ids = set()
        top_25_ids = set()
        no_badge_ids = set()

        for rank, u in enumerate(eligible):
            percentile = (rank / n) * 100 if n > 0 else 100
            if percentile < 10:
                top_10_ids.add(u["id"])
            elif percentile < 25:
                top_25_ids.add(u["id"])
            else:
                no_badge_ids.add(u["id"])

        ineligible_ids = all_ids - {u["id"] for u in eligible}
        clear_ids = no_badge_ids | ineligible_ids

        with transaction.atomic():
            User.objects.filter(pk__in=top_10_ids).update(
                **{badge_giver_field: User.BadgeChoices.TOP_10}
            )
            User.objects.filter(pk__in=top_25_ids).update(
                **{badge_giver_field: User.BadgeChoices.TOP_25}
            )
            User.objects.filter(pk__in=clear_ids).update(
                **{badge_giver_field: None}
            )

        logger.info(
            "Badge recalc [%s]: top_10=%d top_25=%d cleared=%d",
            badge_giver_field,
            len(top_10_ids),
            len(top_25_ids),
            len(clear_ids),
        )

    _assign_badges(users, "gifts_given_count", "giver_badge")
    _assign_badges(users, "total_trades", "trader_badge")

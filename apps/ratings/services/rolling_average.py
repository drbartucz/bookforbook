"""
Rolling average computation for user ratings.

Uses only the last 10 ratings to compute avg_recent_rating.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def recompute_rating_average(user) -> None:
    """
    Recompute the rolling average of the last 10 ratings for a user.
    Updates user.avg_recent_rating and user.rating_count in place.
    """
    from apps.ratings.models import Rating

    with transaction.atomic():
        # Use one cutoff so count and rolling average are computed from
        # the same logical rating set under concurrent inserts.
        cutoff = timezone.now()
        ratings_qs = Rating.objects.filter(rated=user, created_at__lte=cutoff)

        total_count = ratings_qs.count()
        recent_list = list(ratings_qs.order_by("-created_at")[:10])

        if not recent_list:
            user.avg_recent_rating = None
            user.rating_count = 0
        else:
            avg = sum(r.score for r in recent_list) / len(recent_list)
            user.avg_recent_rating = Decimal(str(round(avg, 2)))
            user.rating_count = total_count

        user.save(update_fields=["avg_recent_rating", "rating_count"])
    logger.debug(
        "Recomputed rating for user %s: avg=%.2f, count=%d",
        user.pk,
        float(user.avg_recent_rating or 0),
        user.rating_count,
    )

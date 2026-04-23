"""
Backup retention policy enforcement.

Retention rules:
  - 0–14 days:  Keep all daily backups
  - 14–60 days: Keep one per week (oldest from each week)
  - 60+ days:   Keep one per month (oldest from each month)
  - 1 year+:    Delete
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple

from django.utils import timezone as tz

logger = logging.getLogger(__name__)


class RetentionBucket(NamedTuple):
    """A group of backups belonging to a retention period."""

    period_name: str  # "daily", "weekly", "monthly"
    start_date: datetime
    end_date: datetime
    backups: list  # BackupRecord instances


def apply_retention_policy() -> None:
    """
    Scan all successful backups and delete those outside the retention policy.

    Keeps oldest backup from each period:
      - Daily: 0–14 days ago
      - Weekly: 14–60 days ago (one per calendar week)
      - Monthly: 60–365 days ago (one per calendar month)
      - Anything >365 days old is deleted
    """
    from apps.backups.models import BackupRecord
    from dbbackup.storage import get_storage

    storage = get_storage()
    now = tz.now()

    # Fetch all successful backups, newest first
    backups = list(
        BackupRecord.objects.filter(status=BackupRecord.Status.SUCCESS)
        .order_by("-created_at")
        .all()
    )

    if not backups:
        logger.info("No successful backups to evaluate for retention")
        return

    # Partition backups into retention buckets
    keep: set[str] = set()
    delete_set: set = set()

    daily_bucket = []
    weekly_buckets: dict = {}
    monthly_buckets: dict = {}

    for backup in backups:
        age = now - backup.created_at
        days_old = age.days

        if days_old < 14:
            daily_bucket.append(backup)
        elif days_old < 60:
            # Group by ISO week
            iso_cal = backup.created_at.isocalendar()
            week_key = (iso_cal[0], iso_cal[1])
            if week_key not in weekly_buckets:
                weekly_buckets[week_key] = []
            weekly_buckets[week_key].append(backup)
        elif days_old < 365:
            # Group by month
            month_key = (backup.created_at.year, backup.created_at.month)
            if month_key not in monthly_buckets:
                monthly_buckets[month_key] = []
            monthly_buckets[month_key].append(backup)
        else:
            # >1 year: delete all in this group
            delete_set.add(backup)

    # Keep: oldest from each daily, all dailies, oldest from each week, oldest from each month
    for backup in daily_bucket:
        if backup.file_name:
            keep.add(backup.file_name)

    for backups_in_week in weekly_buckets.values():
        # Keep only the oldest (most recent to first)
        oldest = min(backups_in_week, key=lambda b: b.created_at)
        if oldest.file_name:
            keep.add(oldest.file_name)

    for backups_in_month in monthly_buckets.values():
        oldest = min(backups_in_month, key=lambda b: b.created_at)
        if oldest.file_name:
            keep.add(oldest.file_name)

    # Now actually delete from storage and update records
    deleted_count = 0
    for backup in BackupRecord.objects.filter(status=BackupRecord.Status.SUCCESS).all():
        if backup.file_name and backup.file_name not in keep:
            try:
                storage.delete(backup.file_name)
                backup.delete()
                deleted_count += 1
                logger.info("Deleted backup per retention policy: %s", backup.file_name)
            except Exception as exc:
                logger.error("Failed to delete backup %s: %s", backup.file_name, exc)

    logger.info(
        "Retention policy applied: kept %d backups, deleted %d",
        len(keep),
        deleted_count,
    )

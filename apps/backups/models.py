import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class BackupSettings(models.Model):
    """Singleton configuration for backup notifications.

    Always use BackupSettings.get() rather than querying directly.
    """

    email_on_success = models.BooleanField(
        default=False,
        help_text="Send an email to the admin alert address whenever a backup succeeds.",
    )
    email_on_failure = models.BooleanField(
        default=True,
        help_text="Send an email to the admin alert address whenever a backup fails.",
    )

    class Meta:
        verbose_name = "Backup Settings"
        verbose_name_plural = "Backup Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> "BackupSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BackupRecord(models.Model):
    """Audit log for every database backup run (automatic or manual)."""

    class BackupType(models.TextChoices):
        DATABASE = "database", _("Database")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_type = models.CharField(
        max_length=20,
        choices=BackupType.choices,
        default=BackupType.DATABASE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    file_name = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    storage_backend = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    # True = scheduled nightly; False = manually triggered from admin.
    is_automatic = models.BooleanField(default=True)
    triggered_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggered_backups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Backup Record"
        verbose_name_plural = "Backup Records"

    def __str__(self) -> str:
        return (
            f"{self.get_backup_type_display()} backup "
            f"[{self.status}] @ {self.created_at:%Y-%m-%d %H:%M UTC}"
        )

    @property
    def file_size_mb(self) -> float | None:
        if self.file_size_bytes is not None:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return None

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at and self.created_at:
            return round((self.completed_at - self.created_at).total_seconds(), 1)
        return None

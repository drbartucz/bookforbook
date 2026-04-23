from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import BackupRecord


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    change_list_template = "admin/backups/backuprecord/change_list.html"

    list_display = [
        "created_at",
        "backup_type",
        "status_badge",
        "file_name",
        "file_size_display",
        "duration_display",
        "is_automatic",
        "triggered_by",
        "restore_button",
    ]
    list_filter = ["status", "backup_type", "is_automatic"]
    readonly_fields = [
        "id",
        "backup_type",
        "status",
        "file_name",
        "file_size_bytes",
        "error_message",
        "is_automatic",
        "triggered_by",
        "created_at",
        "completed_at",
    ]
    ordering = ["-created_at"]

    # ── Permissions ────────────────────────────────────────────────────────────

    def has_add_permission(self, request) -> bool:  # type: ignore[override]
        return False  # use the "Trigger Backup Now" button instead

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False  # records are immutable audit logs

    # ── Custom display columns ─────────────────────────────────────────────────

    @admin.display(description="Status")
    def status_badge(self, obj: BackupRecord) -> str:
        colours = {
            BackupRecord.Status.PENDING: "#888",
            BackupRecord.Status.RUNNING: "#0077cc",
            BackupRecord.Status.SUCCESS: "#2e7d32",
            BackupRecord.Status.FAILED: "#c62828",
        }
        colour = colours.get(obj.status, "#888")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Size")
    def file_size_display(self, obj: BackupRecord) -> str:
        if obj.file_size_mb is not None:
            return f"{obj.file_size_mb} MB"
        return "—"

    @admin.display(description="Duration")
    def duration_display(self, obj: BackupRecord) -> str:
        if obj.duration_seconds is not None:
            return f"{obj.duration_seconds}s"
        return "—"

    @admin.display(description="Restore")
    def restore_button(self, obj: BackupRecord) -> str:
        if obj.status != BackupRecord.Status.SUCCESS or not obj.file_name:
            return "—"
        url = reverse("admin:backups_restore", args=[str(obj.pk)])
        return format_html(
            '<a class="button" href="{}" style="background:#c62828;color:#fff;'
            "padding:3px 8px;border-radius:4px;text-decoration:none;"
            'font-size:12px;">Restore…</a>',
            url,
        )

    # ── Custom URLs ────────────────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "trigger-backup/",
                self.admin_site.admin_view(self.trigger_backup_view),
                name="backups_trigger",
            ),
            path(
                "<uuid:pk>/restore/",
                self.admin_site.admin_view(self.restore_view),
                name="backups_restore",
            ),
        ]
        return custom + urls

    # ── Custom views ───────────────────────────────────────────────────────────

    def trigger_backup_view(self, request):
        """POST-only: queue a manual backup and redirect back to the list."""
        if request.method != "POST":
            return redirect(reverse("admin:backups_backuprecord_changelist"))

        from apps.backups.services.backup_service import trigger_manual_backup

        record = trigger_manual_backup(user_id=str(request.user.pk))
        self.message_user(
            request,
            f"Backup queued (ID: {record.pk}). "
            "Refresh this page in a moment to see the result.",
            messages.SUCCESS,
        )
        return redirect(reverse("admin:backups_backuprecord_changelist"))

    def restore_view(self, request, pk):
        """GET: confirmation page. POST with CONFIRM text: execute restore."""
        record = get_object_or_404(BackupRecord, pk=pk)

        if request.method == "POST":
            confirmation = request.POST.get("confirmation", "").strip()
            if confirmation == "CONFIRM":
                try:
                    from apps.backups.services.backup_service import (
                        run_database_restore,
                    )

                    run_database_restore(record.file_name)
                    self.message_user(
                        request,
                        "Database restore completed successfully. "
                        "Please restart the application to ensure consistency.",
                        messages.WARNING,
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Restore failed: {exc}",
                        messages.ERROR,
                    )
            else:
                self.message_user(
                    request,
                    'Restore aborted — you must type exactly "CONFIRM" to proceed.',
                    messages.ERROR,
                )
            return redirect(reverse("admin:backups_backuprecord_changelist"))

        # GET: show the confirmation page.
        context = {
            **self.admin_site.each_context(request),
            "title": "Confirm database restore",
            "record": record,
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/backups/backuprecord/restore_confirm.html",
            context,
        )

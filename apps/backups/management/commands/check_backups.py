import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django_q.models import Schedule
from apps.backups.models import BackupRecord

class Command(BaseCommand):
    help = "Verify backup configuration and connection."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Backup System Check ---"))

        # 1. Storage Configuration
        storage_type = getattr(settings, "DBBACKUP_STORAGE", "Not set")
        self.stdout.write(f"Storage backend: {storage_type}")

        storage_opts = getattr(settings, "DBBACKUP_STORAGE_OPTIONS", {})
        if "s3boto3" in storage_type.lower():
            endpoint = storage_opts.get("endpoint_url", "Not set")
            bucket = storage_opts.get("bucket_name", "Not set")
            region = storage_opts.get("region_name", "Not set")
            self.stdout.write(f"  Endpoint: {endpoint}")
            self.stdout.write(f"  Bucket: {bucket}")
            self.stdout.write(f"  Region: {region}")

            if "f000.backblazeb2.com" in endpoint:
                self.stdout.write(self.style.WARNING("  WARNING: Using native B2 endpoint instead of S3 endpoint!"))
        elif "FileSystemStorage" in storage_type:
            self.stdout.write(self.style.WARNING(
                "  WARNING: Using local filesystem storage — backups will be lost on redeploy. "
                "Set B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, and B2_BUCKET_NAME to enable B2."
            ))

        # 2. Schedule Check
        backup_sched = Schedule.objects.filter(func="apps.backups.tasks.nightly_database_backup").first()
        if backup_sched:
            self.stdout.write(self.style.SUCCESS(f"Nightly backup schedule: FOUND (Next run: {backup_sched.next_run})"))
        else:
            self.stdout.write(self.style.ERROR("Nightly backup schedule: MISSING!"))

        retention_sched = Schedule.objects.filter(func="apps.backups.tasks.apply_backup_retention_policy").first()
        if retention_sched:
            self.stdout.write(self.style.SUCCESS(f"Retention policy schedule: FOUND (Next run: {retention_sched.next_run})"))
        else:
            self.stdout.write(self.style.ERROR("Retention policy schedule: MISSING!"))

        # 3. Connection Test (if S3)
        if "s3boto3" in storage_type.lower():
            self.stdout.write("Testing B2 connection...")
            try:
                import boto3
                s3 = boto3.client(
                    "s3",
                    aws_access_key_id=storage_opts.get("access_key"),
                    aws_secret_access_key=storage_opts.get("secret_key"),
                    endpoint_url=storage_opts.get("endpoint_url"),
                    region_name=storage_opts.get("region_name"),
                )
                s3.list_objects_v2(Bucket=storage_opts.get("bucket_name"), MaxKeys=1)
                self.stdout.write(self.style.SUCCESS("  B2 connection: SUCCESSFUL"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  B2 connection: FAILED - {str(e)}"))

        # 4. Recent Records
        recent = BackupRecord.objects.order_by("-created_at")[:5]
        if recent:
            self.stdout.write("Recent backup records:")
            for r in recent:
                status_color = self.style.SUCCESS if r.status == "success" else self.style.ERROR
                self.stdout.write(f"  - {r.created_at} [{r.status}]: {r.file_name or r.error_message}")
        else:
            self.stdout.write("No backup records found.")

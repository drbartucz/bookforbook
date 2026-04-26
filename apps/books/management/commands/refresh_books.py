"""
Management command to refresh book metadata from Open Library.

Usage:
    python manage.py refresh_books                        # refresh all books
    python manage.py refresh_books --isbn 9780141036144  # single book
    python manage.py refresh_books --missing-only        # only books with gaps
    python manage.py refresh_books --dry-run             # show what would change
    python manage.py refresh_books --delay 0.5           # seconds between requests
    python manage.py refresh_books --batch-size 50       # progress checkpoint interval
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.books.models import Book
from apps.books.services.openlibrary import fetch_from_open_library


REFRESHABLE_FIELDS = [
    "title",
    "authors",
    "publisher",
    "publish_year",
    "cover_image_url",
    "page_count",
    "physical_format",
    "subjects",
    "description",
    "open_library_key",
]


class Command(BaseCommand):
    help = "Refresh book metadata and cover URLs from Open Library"

    def add_arguments(self, parser):
        parser.add_argument(
            "--isbn",
            type=str,
            help="Refresh a single book by ISBN-13",
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Only refresh books that are missing authors or physical_format",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving anything",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Seconds to wait between Open Library requests (default: 0.5)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Log a progress line every N books (default: 50)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing non-empty fields (default: only fill gaps)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delay = options["delay"]
        batch_size = options["batch_size"]
        force = options["force"]
        isbn = options.get("isbn")
        missing_only = options["missing_only"]
        verbosity = options["verbosity"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved"))

        queryset = self._build_queryset(isbn, missing_only)
        total = queryset.count()

        if total == 0:
            self.stdout.write("No books to refresh.")
            return

        self.stdout.write(f"Refreshing {total} book(s)...")

        updated = 0
        skipped = 0
        errors = 0

        for i, book in enumerate(queryset.iterator(), start=1):
            try:
                changed = self._refresh_book(book, force=force, dry_run=dry_run, verbosity=verbosity)
                if changed:
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    f"  ERROR {book.isbn_13} ({book.title[:40]}): {exc}"
                )

            if i % batch_size == 0:
                self.stdout.write(
                    f"  Progress: {i}/{total} — "
                    f"{updated} updated, {skipped} skipped, {errors} errors"
                )

            if i < total and delay > 0:
                time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {updated} updated, {skipped} skipped, {errors} errors "
                f"({'dry run' if dry_run else 'saved'})"
            )
        )

    def _build_queryset(self, isbn, missing_only):
        if isbn:
            return Book.objects.filter(isbn_13=isbn)
        qs = Book.objects.all().order_by("created_at")
        if missing_only:
            qs = qs.filter(
                Q(authors=[]) | Q(authors__isnull=True) | Q(physical_format__isnull=True)
            )
        return qs

    def _refresh_book(self, book, force, dry_run, verbosity=1):
        """
        Fetch fresh data from Open Library and update the book.
        Returns True if any fields changed, False otherwise.
        """
        data = fetch_from_open_library(book.isbn_13)
        if not data:
            return False

        updates = {}
        for field in REFRESHABLE_FIELDS:
            new_value = data.get(field)
            old_value = getattr(book, field)

            if new_value in (None, "", []):
                continue
            if not force and old_value not in (None, "", [], "Unknown Title"):
                continue
            if new_value == old_value:
                continue

            updates[field] = new_value

        if not updates:
            if verbosity >= 2:
                reasons = []
                for field in REFRESHABLE_FIELDS:
                    new_value = data.get(field)
                    old_value = getattr(book, field)
                    if new_value in (None, "", []):
                        reasons.append(f"{field}=<empty from API>")
                    elif new_value == old_value:
                        reasons.append(f"{field}=<unchanged>")
                self.stdout.write(
                    f"  SKIPPED {book.isbn_13} ({book.title[:40]}): "
                    + (", ".join(reasons) if reasons else "no changes")
                )
            return False

        if dry_run:
            self.stdout.write(
                f"  WOULD UPDATE {book.isbn_13} ({book.title[:40]}): "
                f"{', '.join(updates.keys())}"
            )
            return True

        for field, value in updates.items():
            setattr(book, field, value)

        book.save(update_fields=list(updates.keys()) + ["updated_at"])
        self.stdout.write(
            f"  Updated {book.isbn_13} ({book.title[:40]}): "
            f"{', '.join(updates.keys())}"
        )
        return True

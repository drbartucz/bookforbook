"""
Management command: e2e_seed_trade_flow

Seeds a fresh pending direct match between alice_e2e and bob_e2e
using two books dedicated to the full trade flow E2E spec:

  The Stranger (Camus, 9780679720201)         — alice has, bob wants
  Crime and Punishment (Dostoevsky, 9780140449136) — bob has, alice wants

Matching is run synchronously so no background worker is required.
Safe to run multiple times — tears down and recreates relevant records each run.
"""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

STRANGER_ISBN = "9780679720201"
CRIME_ISBN = "9780140449136"


class Command(BaseCommand):
    help = "Seed the full-trade-flow E2E test data for alice_e2e and bob_e2e."

    def handle(self, *args, **options):
        if "production" in os.environ.get("DJANGO_SETTINGS_MODULE", ""):
            raise CommandError(
                "e2e_seed_trade_flow may only be run outside of production."
            )

        User = get_user_model()
        try:
            alice = User.objects.get(email="alice@e2e.test")
            bob = User.objects.get(email="bob@e2e.test")
        except User.DoesNotExist as exc:
            raise CommandError(
                f"E2E user not found: {exc}. Run 'manage.py seed_e2e' first."
            )

        with transaction.atomic():
            self._teardown(alice, bob)
            stranger, crime = self._ensure_books()
            alice_ub, _bob_ub = self._setup_inventory(alice, bob, stranger, crime)
            match_count = self._run_matching(alice_ub)

        if match_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No match was created — check that both wishlist items exist "
                    "and that matching conditions are met."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"e2e_seed_trade_flow complete: {match_count} match(es) created. "
                    "Alice has 'The Stranger', Bob has 'Crime and Punishment'."
                )
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _teardown(self, alice, bob):
        from apps.books.models import Book
        from apps.inventory.models import UserBook, WishlistItem
        from apps.matching.models import Match

        flow_books = Book.objects.filter(isbn_13__in=[STRANGER_ISBN, CRIME_ISBN])
        if not flow_books.exists():
            return

        flow_ubs = UserBook.objects.filter(
            user__in=[alice, bob], book__in=flow_books
        )
        # Cascade deletes legs too, but be explicit for clarity.
        Match.objects.filter(legs__user_book__in=flow_ubs).distinct().delete()
        WishlistItem.objects.filter(
            user__in=[alice, bob], book__in=flow_books
        ).delete()
        flow_ubs.delete()
        self.stdout.write("  Existing flow-test data cleared.")

    def _ensure_books(self):
        from apps.books.models import Book

        stranger, _ = Book.objects.get_or_create(
            isbn_13=STRANGER_ISBN,
            defaults={
                "title": "The Stranger",
                "authors": ["Albert Camus"],
                "publish_year": 1942,
                "physical_format": "Paperback",
            },
        )
        crime, _ = Book.objects.get_or_create(
            isbn_13=CRIME_ISBN,
            defaults={
                "title": "Crime and Punishment",
                "authors": ["Fyodor Dostoevsky"],
                "publish_year": 1866,
                "physical_format": "Paperback",
            },
        )
        self.stdout.write(f"  Books: '{stranger.title}', '{crime.title}'")
        return stranger, crime

    def _setup_inventory(self, alice, bob, stranger, crime):
        from apps.inventory.models import ConditionChoices, UserBook, WishlistItem

        alice_ub = UserBook.objects.create(
            user=alice,
            book=stranger,
            condition=ConditionChoices.GOOD,
            status=UserBook.Status.AVAILABLE,
        )
        bob_ub = UserBook.objects.create(
            user=bob,
            book=crime,
            condition=ConditionChoices.GOOD,
            status=UserBook.Status.AVAILABLE,
        )
        WishlistItem.objects.create(
            user=alice,
            book=crime,
            min_condition=ConditionChoices.ACCEPTABLE,
            is_active=True,
        )
        WishlistItem.objects.create(
            user=bob,
            book=stranger,
            min_condition=ConditionChoices.ACCEPTABLE,
            is_active=True,
        )
        self.stdout.write("  Inventory and wishlist items created.")
        return alice_ub, bob_ub

    def _run_matching(self, alice_ub):
        from apps.matching.services.direct_matcher import run_direct_matching

        matches = run_direct_matching(user_book=alice_ub)
        self.stdout.write(f"  Direct matching: {len(matches)} match(es) found.")
        return len(matches)

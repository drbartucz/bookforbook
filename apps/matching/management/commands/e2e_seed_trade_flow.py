"""
Management command: e2e_seed_trade_flow

Seeds a direct match (status=PROPOSED) between alice_e2e and bob_e2e
using two books dedicated to the full trade flow E2E specs:

  The Stranger (Camus, 9780679720201)              — alice has, bob wants
  Crime and Punishment (Dostoevsky, 9780140449136) — bob has, alice wants

Matching is run synchronously so no background worker is required.
Safe to run multiple times — tears down and recreates relevant records each run.

Flags
-----
(no flag)       Full setup: teardown → books → inventory/wishlists → matching.
--books-only    Teardown then create only the Book catalog entries (no UserBooks,
                WishlistItems, or matching). Use this before a UI-driven spec that
                adds inventory through the browser so the backend does not need to
                contact Open Library.
--match-only    Re-run direct matching for Alice's existing "The Stranger" UserBook
                without touching any other data. Use after a UI-driven spec has added
                the books and wishlists via the browser.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

STRANGER_ISBN = "9780679720201"
CRIME_ISBN = "9780140449136"


class Command(BaseCommand):
    help = "Seed the full-trade-flow E2E test data for alice_e2e and bob_e2e."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--books-only",
            action="store_true",
            help="Teardown existing flow data then create only Book catalog entries.",
        )
        group.add_argument(
            "--match-only",
            action="store_true",
            help="Run direct matching for Alice's existing 'The Stranger' UserBook only.",
        )

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

        if options["books_only"]:
            self._run_books_only(alice, bob)
        elif options["match_only"]:
            self._run_match_only(alice)
        else:
            self._run_full(alice, bob)

    # ── modes ─────────────────────────────────────────────────────────────────

    def _run_full(self, alice, bob):
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
                    f"e2e_seed_trade_flow complete: {match_count} proposed match(es) created. "
                    "Alice has 'The Stranger', Bob has 'Crime and Punishment'."
                )
            )

    def _run_books_only(self, alice, bob):
        with transaction.atomic():
            self._teardown(alice, bob)
            stranger, crime = self._ensure_books()
        self.stdout.write(
            self.style.SUCCESS(
                f"Books seeded: '{stranger.title}', '{crime.title}'. "
                "Add inventory and wishlists via the UI."
            )
        )

    def _run_match_only(self, alice):
        from apps.inventory.models import UserBook
        from apps.books.models import Book

        try:
            stranger = Book.objects.get(isbn_13=STRANGER_ISBN)
            alice_ub = UserBook.objects.get(
                user=alice, book=stranger, status=UserBook.Status.AVAILABLE
            )
        except (Book.DoesNotExist, UserBook.DoesNotExist) as exc:
            raise CommandError(
                f"Could not find Alice's 'The Stranger' UserBook: {exc}. "
                "Run the UI steps first or use the default mode."
            )

        match_count = self._run_matching(alice_ub)
        if match_count == 0:
            self.stdout.write(
                self.style.WARNING("No match created — verify Bob's wishlist and inventory exist.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Matching complete: {match_count} proposed match(es) created.")
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _teardown(self, alice, bob):
        from apps.books.models import Book
        from apps.inventory.models import UserBook, WishlistItem
        from apps.matching.models import Match
        from apps.trading.models import Trade

        flow_books = Book.objects.filter(isbn_13__in=[STRANGER_ISBN, CRIME_ISBN])
        if not flow_books.exists():
            return

        flow_ubs = UserBook.objects.filter(user__in=[alice, bob], book__in=flow_books)

        # Remove trades whose shipments reference these UserBooks; deleting the
        # UserBooks would cascade-delete the shipments and leave orphan Trade rows.
        Trade.objects.filter(
            shipments__user_book__in=flow_ubs
        ).distinct().delete()

        Match.objects.filter(legs__user_book__in=flow_ubs).distinct().delete()
        WishlistItem.objects.filter(user__in=[alice, bob], book__in=flow_books).delete()
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
        self.stdout.write(f"  Direct matching: {len(matches)} proposed match(es) found.")
        return len(matches)

"""
Management command: seed_e2e

Creates deterministic test data for the Playwright E2E suite.
Safe to run multiple times — uses get_or_create throughout.

Usage:
    python manage.py seed_e2e
    python manage.py seed_e2e --reset   # drops and recreates all e2e data
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.books.models import Book
from apps.donations.models import Donation
from apps.inventory.models import ConditionChoices, UserBook, WishlistItem
from apps.matching.models import Match, MatchLeg
from apps.trading.models import Trade, TradeProposal, TradeProposalItem, TradeShipment

User = get_user_model()

# ── Deterministic credentials ─────────────────────────────────────────────────
E2E_PASSWORD = "E2eTestPass1!"

USERS = {
    "alice": dict(
        email="alice@e2e.test",
        username="alice_e2e",
        account_type=User.AccountType.INDIVIDUAL,
        email_verified=True,
        address_verified=True,
        full_name="Alice Tester",
        address_line_1="100 E Main St",
        city="Denver",
        state="CO",
        zip_code="80203",
    ),
    "bob": dict(
        email="bob@e2e.test",
        username="bob_e2e",
        account_type=User.AccountType.INDIVIDUAL,
        email_verified=True,
        address_verified=True,
        full_name="Bob Tester",
        address_line_1="200 W 5th Ave",
        city="Portland",
        state="OR",
        zip_code="97204",
    ),
    "carol": dict(
        email="carol@e2e.test",
        username="carol_e2e",
        account_type=User.AccountType.INDIVIDUAL,
        email_verified=True,
        address_verified=False,
        full_name="",
        address_line_1="",
        city="",
        state="",
        zip_code="",
    ),
    "library": dict(
        email="library@e2e.test",
        username="library_e2e",
        account_type=User.AccountType.LIBRARY,
        email_verified=True,
        address_verified=True,
        is_verified=True,
        institution_name="E2E Public Library",
        institution_url="https://e2e-library.example.com",
        full_name="E2E Library",
        address_line_1="1 Library Way",
        city="Chicago",
        state="IL",
        zip_code="60601",
    ),
}

# ── Book catalogue ────────────────────────────────────────────────────────────
BOOKS = {
    "orwell": dict(
        isbn_13="9780451524935",
        title="Nineteen Eighty-Four",
        authors=["George Orwell"],
        publish_year=1949,
        physical_format="Paperback",
    ),
    "gatsby": dict(
        isbn_13="9780743273565",
        title="The Great Gatsby",
        authors=["F. Scott Fitzgerald"],
        publish_year=1925,
        physical_format="Paperback",
    ),
    "hemingway": dict(
        isbn_13="9780684801469",
        title="A Farewell to Arms",
        authors=["Ernest Hemingway"],
        publish_year=1929,
        physical_format="Hardcover",
    ),
    "dickens": dict(
        isbn_13="9780141439563",
        title="Great Expectations",
        authors=["Charles Dickens"],
        publish_year=1861,
        physical_format="Paperback",
    ),
    "austen": dict(
        isbn_13="9780141439518",
        title="Pride and Prejudice",
        authors=["Jane Austen"],
        publish_year=1813,
        physical_format="Paperback",
    ),
    "twain": dict(
        isbn_13="9780143107330",
        title="Adventures of Huckleberry Finn",
        authors=["Mark Twain"],
        publish_year=1884,
        physical_format="Paperback",
    ),
}


class Command(BaseCommand):
    help = "Seed deterministic test data for the Playwright E2E suite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing E2E data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        users = self._seed_users()
        books = self._seed_books()
        self._seed_inventory(users, books)
        self._seed_match(users, books)
        self._seed_proposal(users, books)
        self._seed_trade(users, books)
        self._seed_donation(users, books)

        self.stdout.write(self.style.SUCCESS("E2E seed complete."))
        self._print_summary(users)

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset(self):
        emails = [u["email"] for u in USERS.values()]
        e2e_users = User.objects.filter(email__in=emails)

        # Cascade handles most related objects; explicit cleanup for safety.
        Trade.objects.filter(shipments__sender__in=e2e_users).delete()
        TradeProposal.objects.filter(proposer__in=e2e_users).delete()
        Match.objects.filter(legs__sender__in=e2e_users).delete()
        Donation.objects.filter(donor__in=e2e_users).delete()
        WishlistItem.objects.filter(user__in=e2e_users).delete()
        UserBook.objects.filter(user__in=e2e_users).delete()
        e2e_users.delete()
        self.stdout.write("E2E data cleared.")

    # ── Users ─────────────────────────────────────────────────────────────────

    def _seed_users(self):
        created = {}
        for key, spec in USERS.items():
            address_verified = spec.pop("address_verified", False)
            is_verified = spec.pop("is_verified", False)
            full_name = spec.pop("full_name", "")
            address_line_1 = spec.pop("address_line_1", "")
            city = spec.pop("city", "")
            state = spec.pop("state", "")
            zip_code = spec.pop("zip_code", "")
            institution_name = spec.pop("institution_name", None)
            institution_url = spec.pop("institution_url", None)

            user, was_created = User.objects.get_or_create(
                email=spec["email"],
                defaults={"username": spec["username"]},
            )
            user.set_password(E2E_PASSWORD)
            user.email_verified = spec.get("email_verified", True)
            user.account_type = spec.get("account_type", User.AccountType.INDIVIDUAL)
            user.is_verified = is_verified
            user.full_name = full_name
            user.address_line_1 = address_line_1
            user.city = city
            user.state = state
            user.zip_code = zip_code
            if institution_name:
                user.institution_name = institution_name
            if institution_url:
                user.institution_url = institution_url

            if address_verified:
                user.address_verification_status = (
                    User.AddressVerificationStatus.VERIFIED
                )
                if not user.address_verified_at:
                    user.address_verified_at = timezone.now() - timedelta(days=10)
            else:
                user.address_verification_status = (
                    User.AddressVerificationStatus.UNVERIFIED
                )

            user.save()
            created[key] = user
            action = "created" if was_created else "updated"
            self.stdout.write(f"  User {spec['email']} {action}.")

        return created

    # ── Books ─────────────────────────────────────────────────────────────────

    def _seed_books(self):
        created = {}
        for key, spec in BOOKS.items():
            book, was_created = Book.objects.get_or_create(
                isbn_13=spec["isbn_13"],
                defaults={
                    "title": spec["title"],
                    "authors": spec["authors"],
                    "publish_year": spec.get("publish_year"),
                    "physical_format": spec.get("physical_format"),
                },
            )
            created[key] = book
            action = "created" if was_created else "exists"
            self.stdout.write(f"  Book '{book.title}' {action}.")
        return created

    # ── Inventory ─────────────────────────────────────────────────────────────

    def _seed_inventory(self, users, books):
        """
        Scenario:
          alice has: Orwell (for match), Hemingway (for proposal), Austen (for donation)
          alice wants: Gatsby (for match)
          bob   has: Gatsby (for match), Dickens (for proposal)
          bob   wants: Orwell (for match)
          carol wants: Twain (tests wishlist UI only)
        """
        inventory = {}

        inventory["alice_orwell"] = self._get_or_create_user_book(
            users["alice"],
            books["orwell"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )
        inventory["alice_hemingway"] = self._get_or_create_user_book(
            users["alice"],
            books["hemingway"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )
        inventory["alice_austen"] = self._get_or_create_user_book(
            users["alice"],
            books["austen"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )

        inventory["bob_gatsby"] = self._get_or_create_user_book(
            users["bob"],
            books["gatsby"],
            ConditionChoices.VERY_GOOD,
            UserBook.Status.AVAILABLE,
        )
        inventory["bob_dickens"] = self._get_or_create_user_book(
            users["bob"],
            books["dickens"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )

        # Wishlist items
        WishlistItem.objects.get_or_create(
            user=users["alice"],
            book=books["gatsby"],
            defaults={"min_condition": ConditionChoices.ACCEPTABLE, "is_active": True},
        )
        WishlistItem.objects.get_or_create(
            user=users["bob"],
            book=books["orwell"],
            defaults={"min_condition": ConditionChoices.ACCEPTABLE, "is_active": True},
        )
        WishlistItem.objects.get_or_create(
            user=users["carol"],
            book=books["twain"],
            defaults={"min_condition": ConditionChoices.ACCEPTABLE, "is_active": True},
        )

        self.stdout.write("  Inventory seeded.")
        return inventory

    def _get_or_create_user_book(self, user, book, condition, status):
        ub, _ = UserBook.objects.get_or_create(
            user=user,
            book=book,
            defaults={"condition": condition, "status": status},
        )
        return ub

    # ── Match ─────────────────────────────────────────────────────────────────

    def _seed_match(self, users, books):
        """
        Pending direct match: alice sends Orwell to bob; bob sends Gatsby to alice.
        We look for an existing match first to stay idempotent.
        """
        alice = users["alice"]
        bob = users["bob"]
        alice_ub = UserBook.objects.filter(user=alice, book=books["orwell"]).first()
        bob_ub = UserBook.objects.filter(user=bob, book=books["gatsby"]).first()
        if not alice_ub or not bob_ub:
            self.stdout.write(
                self.style.WARNING("  Match skipped — inventory missing.")
            )
            return

        # Check if an existing pending match already exists
        existing = Match.objects.filter(
            status=Match.Status.PENDING,
            legs__sender=alice,
            legs__user_book=alice_ub,
        ).first()
        if existing:
            self.stdout.write("  Match exists — skipped.")
            return

        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
            expires_at=timezone.now() + timedelta(hours=48),
        )
        MatchLeg.objects.create(
            match=match, sender=alice, receiver=bob, user_book=alice_ub, position=0
        )
        MatchLeg.objects.create(
            match=match, sender=bob, receiver=alice, user_book=bob_ub, position=1
        )
        self.stdout.write("  Match created.")

    # ── Proposal ──────────────────────────────────────────────────────────────

    def _seed_proposal(self, users, books):
        """
        Pending proposal: bob proposes to alice.
          bob sends Dickens → alice
          alice sends Hemingway → bob
        """
        alice = users["alice"]
        bob = users["bob"]
        alice_ub = UserBook.objects.filter(user=alice, book=books["hemingway"]).first()
        bob_ub = UserBook.objects.filter(user=bob, book=books["dickens"]).first()
        if not alice_ub or not bob_ub:
            self.stdout.write(
                self.style.WARNING("  Proposal skipped — inventory missing.")
            )
            return

        existing = TradeProposal.objects.filter(
            proposer=bob, recipient=alice, status=TradeProposal.Status.PENDING
        ).first()
        if existing:
            self.stdout.write("  Proposal exists — skipped.")
            return

        proposal = TradeProposal.objects.create(
            proposer=bob,
            recipient=alice,
            status=TradeProposal.Status.PENDING,
            message="Happy to trade!",
            expires_at=timezone.now() + timedelta(hours=72),
        )
        TradeProposalItem.objects.create(
            proposal=proposal,
            direction=TradeProposalItem.Direction.PROPOSER_SENDS,
            user_book=bob_ub,
        )
        TradeProposalItem.objects.create(
            proposal=proposal,
            direction=TradeProposalItem.Direction.RECIPIENT_SENDS,
            user_book=alice_ub,
        )
        self.stdout.write("  Proposal created.")

    # ── Trade ─────────────────────────────────────────────────────────────────

    def _seed_trade(self, users, books):
        """
        Pre-staged CONFIRMED trade so mark-shipped tests don't need to
        accept a match first.  Uses the Twain / Austen books.
        """
        alice = users["alice"]
        bob = users["bob"]
        alice_ub = UserBook.objects.filter(user=alice, book=books["austen"]).first()
        bob_ub = UserBook.objects.filter(user=bob, book=books["dickens"]).first()
        if not alice_ub or not bob_ub:
            self.stdout.write(
                self.style.WARNING("  Trade skipped — inventory missing.")
            )
            return

        # Use a stable source_id derived from user PKs so it's idempotent
        source_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"e2e-trade-{alice.pk}-{bob.pk}")

        trade, was_created = Trade.objects.get_or_create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=source_id,
            defaults={"status": Trade.Status.CONFIRMED},
        )

        if was_created:
            TradeShipment.objects.get_or_create(
                trade=trade,
                sender=alice,
                receiver=bob,
                user_book=alice_ub,
                defaults={"status": TradeShipment.Status.PENDING},
            )
            TradeShipment.objects.get_or_create(
                trade=trade,
                sender=bob,
                receiver=alice,
                user_book=bob_ub,
                defaults={"status": TradeShipment.Status.PENDING},
            )
            self.stdout.write(f"  Trade created (id={trade.id}).")
        else:
            self.stdout.write("  Trade exists — skipped.")

    # ── Donation ──────────────────────────────────────────────────────────────

    def _seed_donation(self, users, books):
        """
        Pending donation: alice offers Austen to the library.
        """
        alice = users["alice"]
        library = users["library"]
        alice_ub = UserBook.objects.filter(user=alice, book=books["austen"]).first()
        if not alice_ub:
            self.stdout.write(
                self.style.WARNING("  Donation skipped — inventory missing.")
            )
            return

        existing = Donation.objects.filter(
            donor=alice,
            institution=library,
            user_book=alice_ub,
            status=Donation.Status.OFFERED,
        ).first()
        if existing:
            self.stdout.write("  Donation exists — skipped.")
            return

        Donation.objects.create(
            donor=alice,
            institution=library,
            user_book=alice_ub,
            status=Donation.Status.OFFERED,
            message="Hope this helps your collection!",
        )
        self.stdout.write("  Donation created.")

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self, users):
        self.stdout.write("\n── E2E Test Users ───────────────────────────────────────")
        for key, user in users.items():
            self.stdout.write(f"  {key:10s}  {user.email}  /  {E2E_PASSWORD}")
        self.stdout.write("────────────────────────────────────────────────────────\n")

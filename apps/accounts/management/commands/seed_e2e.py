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
    # dave exists solely for account-deletion E2E tests; deleted during the suite run.
    "dave": dict(
        email="dave@e2e.test",
        username="dave_e2e",
        account_type=User.AccountType.INDIVIDUAL,
        email_verified=True,
        address_verified=True,
        full_name="Dave Tester",
        address_line_1="300 N Oak St",
        city="Austin",
        state="TX",
        zip_code="78701",
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
    "tolstoy": dict(
        isbn_13="9780140447934",
        title="War and Peace",
        authors=["Leo Tolstoy"],
        publish_year=1869,
        physical_format="Paperback",
    ),
    "chekhov": dict(
        isbn_13="9780140447484",
        title="The Cherry Orchard",
        authors=["Anton Chekhov"],
        publish_year=1904,
        physical_format="Paperback",
    ),
    "london": dict(
        isbn_13="9780142437735",
        title="The Call of the Wild",
        authors=["Jack London"],
        publish_year=1903,
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
        import os
        from django.core.management.base import CommandError

        if "production" in os.environ.get("DJANGO_SETTINGS_MODULE", ""):
            raise CommandError(
                "seed_e2e may only be run outside of production. "
                "Do not run seed commands against production."
            )

        if options["reset"]:
            self._reset()

        users = self._seed_users()
        books = self._seed_books()
        inventory = self._seed_inventory(users, books)
        self._seed_matches(users, books, inventory)
        self._seed_proposals(users, books, inventory)
        self._seed_trade(users, books)
        self._seed_completed_trade(users, books, inventory)
        self._seed_donations(users, books, inventory)

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
          alice has: Orwell (match 1), Hemingway (proposal 1 + match 3), Austen (trade + donation 1)
          alice wants: Gatsby (for match)
          bob   has: Gatsby (match 1), Dickens (proposal 1), Tolstoy (match 2)
          bob   wants: Orwell (for match)
          carol has: Chekhov (match 2 + proposal 2), London (match 3 + proposal 3 + match 4)
          carol wants: Twain (wishlist UI only)
          dave  has: Twain (match 4) — deletion-test user
          dave  wants: London (for match 4)
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
        inventory["bob_tolstoy"] = self._get_or_create_user_book(
            users["bob"],
            books["tolstoy"],
            ConditionChoices.VERY_GOOD,
            UserBook.Status.AVAILABLE,
        )

        inventory["carol_chekhov"] = self._get_or_create_user_book(
            users["carol"],
            books["chekhov"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )
        inventory["carol_london"] = self._get_or_create_user_book(
            users["carol"],
            books["london"],
            ConditionChoices.GOOD,
            UserBook.Status.AVAILABLE,
        )

        inventory["dave_twain"] = self._get_or_create_user_book(
            users["dave"],
            books["twain"],
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
        WishlistItem.objects.get_or_create(
            user=users["dave"],
            book=books["london"],
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

    # ── Matches ───────────────────────────────────────────────────────────────

    def _seed_matches(self, users, books, inventory):
        """
        Three pending direct matches so each destructive test has its own record:
          Match 1: alice(Orwell) ↔ bob(Gatsby)   — alice accepts
          Match 2: bob(Tolstoy)  ↔ carol(Chekhov) — bob declines
          Match 3: alice(Hemingway) ↔ carol(London) — carol tries to accept (address error)
        """
        self._seed_one_match(
            sender_a=users["alice"],
            ub_a=inventory["alice_orwell"],
            sender_b=users["bob"],
            ub_b=inventory["bob_gatsby"],
            label="Match 1 (alice↔bob)",
        )
        self._seed_one_match(
            sender_a=users["bob"],
            ub_a=inventory["bob_tolstoy"],
            sender_b=users["carol"],
            ub_b=inventory["carol_chekhov"],
            label="Match 2 (bob↔carol)",
        )
        self._seed_one_match(
            sender_a=users["alice"],
            ub_a=inventory["alice_hemingway"],
            sender_b=users["carol"],
            ub_b=inventory["carol_london"],
            label="Match 3 (alice↔carol)",
        )
        self._seed_one_match(
            sender_a=users["dave"],
            ub_a=inventory["dave_twain"],
            sender_b=users["carol"],
            ub_b=inventory["carol_london"],
            label="Match 4 (dave↔carol) — deletion-test match",
        )

    def _seed_one_match(self, sender_a, ub_a, sender_b, ub_b, label):
        existing = Match.objects.filter(
            status=Match.Status.PENDING,
            legs__sender=sender_a,
            legs__user_book=ub_a,
        ).first()
        if existing:
            self.stdout.write(f"  {label} exists — skipped.")
            return
        match = Match.objects.create(
            match_type=Match.MatchType.DIRECT,
            status=Match.Status.PENDING,
            expires_at=timezone.now() + timedelta(hours=48),
        )
        MatchLeg.objects.create(
            match=match, sender=sender_a, receiver=sender_b, user_book=ub_a, position=0
        )
        MatchLeg.objects.create(
            match=match, sender=sender_b, receiver=sender_a, user_book=ub_b, position=1
        )
        self.stdout.write(f"  {label} created.")

    # ── Proposals ─────────────────────────────────────────────────────────────

    def _seed_proposals(self, users, books, inventory):
        """
        Three pending proposals to alice so each action test has its own record:
          Proposal 1: bob(Dickens) → alice(Hemingway)  — alice accepts
          Proposal 2: carol(Chekhov) → alice(Orwell)   — alice declines
          Proposal 3: carol(London) → alice(Austen)    — extra pending proposal
        Proposals 2 and 3 use different books (carol_chekhov vs carol_london) as the
        unique key, allowing two pending carol→alice proposals to coexist.
        """
        alice = users["alice"]
        bob = users["bob"]
        carol = users["carol"]

        self._seed_one_proposal(
            proposer=bob,
            recipient=alice,
            proposer_ub=inventory["bob_dickens"],
            recipient_ub=inventory["alice_hemingway"],
            message="Happy to trade!",
            label="Proposal 1 (bob→alice)",
        )
        self._seed_one_proposal(
            proposer=carol,
            recipient=alice,
            proposer_ub=inventory["carol_chekhov"],
            recipient_ub=inventory["alice_orwell"],
            message="Interested in your Orwell!",
            label="Proposal 2 (carol→alice, chekhov)",
        )
        self._seed_one_proposal(
            proposer=carol,
            recipient=alice,
            proposer_ub=inventory["carol_london"],
            recipient_ub=inventory["alice_austen"],
            message="Would love to swap!",
            label="Proposal 3 (carol→alice, london)",
        )

    def _seed_one_proposal(
        self, proposer, recipient, proposer_ub, recipient_ub, message, label
    ):
        # Idempotency: match on the proposer's specific book to distinguish proposals.
        existing = TradeProposal.objects.filter(
            proposer=proposer,
            recipient=recipient,
            status=TradeProposal.Status.PENDING,
            items__user_book=proposer_ub,
        ).first()
        if existing:
            self.stdout.write(f"  {label} exists — skipped.")
            return
        proposal = TradeProposal.objects.create(
            proposer=proposer,
            recipient=recipient,
            status=TradeProposal.Status.PENDING,
            message=message,
            expires_at=timezone.now() + timedelta(hours=72),
        )
        TradeProposalItem.objects.create(
            proposal=proposal,
            direction=TradeProposalItem.Direction.PROPOSER_SENDS,
            user_book=proposer_ub,
        )
        TradeProposalItem.objects.create(
            proposal=proposal,
            direction=TradeProposalItem.Direction.RECIPIENT_SENDS,
            user_book=recipient_ub,
        )
        self.stdout.write(f"  {label} created.")

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

    def _seed_completed_trade(self, users, books, inventory):
        """
        Pre-staged COMPLETED trade so rating-flow tests have a rateable trade.
        Uses Hemingway (alice) ↔ Gatsby (bob) — different books from the CONFIRMED trade.
        """
        alice = users["alice"]
        bob = users["bob"]
        alice_ub = inventory["alice_hemingway"]
        bob_ub = inventory["bob_gatsby"]

        source_id = uuid.uuid5(
            uuid.NAMESPACE_DNS, f"e2e-completed-trade-{alice.pk}-{bob.pk}"
        )

        trade, was_created = Trade.objects.get_or_create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=source_id,
            defaults={"status": Trade.Status.COMPLETED},
        )

        if was_created:
            now = timezone.now()
            TradeShipment.objects.get_or_create(
                trade=trade,
                sender=alice,
                receiver=bob,
                user_book=alice_ub,
                defaults={
                    "status": TradeShipment.Status.RECEIVED,
                    "shipped_at": now - timedelta(days=10),
                    "received_at": now - timedelta(days=3),
                },
            )
            TradeShipment.objects.get_or_create(
                trade=trade,
                sender=bob,
                receiver=alice,
                user_book=bob_ub,
                defaults={
                    "status": TradeShipment.Status.RECEIVED,
                    "shipped_at": now - timedelta(days=10),
                    "received_at": now - timedelta(days=3),
                },
            )
            self.stdout.write(f"  Completed trade created (id={trade.id}).")
        else:
            self.stdout.write("  Completed trade exists — skipped.")

    # ── Donations ─────────────────────────────────────────────────────────────

    def _seed_donations(self, users, books, inventory):
        """
        Two offered donations to the library so each action test has its own record:
          Donation 1: alice(Austen)  → library — library accepts
          Donation 2: bob(Tolstoy)   → library — library declines
        """
        library = users["library"]

        self._seed_one_donation(
            donor=users["alice"],
            institution=library,
            user_book=inventory["alice_austen"],
            message="Hope this helps your collection!",
            label="Donation 1 (alice→library)",
        )
        self._seed_one_donation(
            donor=users["bob"],
            institution=library,
            user_book=inventory["bob_tolstoy"],
            message="Happy to donate this one!",
            label="Donation 2 (bob→library)",
        )

    def _seed_one_donation(self, donor, institution, user_book, message, label):
        existing = Donation.objects.filter(
            donor=donor,
            institution=institution,
            user_book=user_book,
            status=Donation.Status.OFFERED,
        ).first()
        if existing:
            self.stdout.write(f"  {label} exists — skipped.")
            return
        Donation.objects.create(
            donor=donor,
            institution=institution,
            user_book=user_book,
            status=Donation.Status.OFFERED,
            message=message,
        )
        self.stdout.write(f"  {label} created.")

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self, users):
        self.stdout.write("\n── E2E Test Users ───────────────────────────────────────")
        for key, user in users.items():
            self.stdout.write(f"  {key:10s}  {user.email}  /  {E2E_PASSWORD}")
        self.stdout.write("────────────────────────────────────────────────────────\n")

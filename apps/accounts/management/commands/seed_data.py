import random
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.books.models import Book
from apps.inventory.models import ConditionChoices, UserBook, WishlistItem


@dataclass(frozen=True)
class SeedSize:
    extra_users: int
    extra_books: int
    inventory_per_user: int
    wishlist_per_user: int


SIZE_MAP = {
    "small": SeedSize(
        extra_users=0, extra_books=0, inventory_per_user=2, wishlist_per_user=2
    ),
    "medium": SeedSize(
        extra_users=8, extra_books=20, inventory_per_user=5, wishlist_per_user=5
    ),
    "large": SeedSize(
        extra_users=25, extra_books=75, inventory_per_user=10, wishlist_per_user=10
    ),
}

BASE_USERS = [
    {
        "email": "alice@example.com",
        "username": "alice",
        "full_name": "Alice Smith",
        "address_line_1": "123 Main St",
        "city": "Portland",
        "state": "OR",
        "zip_code": "97201",
        "account_type": User.AccountType.INDIVIDUAL,
    },
    {
        "email": "bob@example.com",
        "username": "bob",
        "full_name": "Bob Jones",
        "address_line_1": "456 Oak Ave",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98101",
        "account_type": User.AccountType.INDIVIDUAL,
    },
    {
        "email": "carol@example.com",
        "username": "carol",
        "full_name": "Carol Williams",
        "address_line_1": "789 Pine Rd",
        "city": "Denver",
        "state": "CO",
        "zip_code": "80201",
        "account_type": User.AccountType.INDIVIDUAL,
    },
    {
        "email": "portlandlibrary@example.com",
        "username": "portlandpubliclibrary",
        "full_name": "",
        "address_line_1": "",
        "city": "Portland",
        "state": "OR",
        "zip_code": "97201",
        "account_type": User.AccountType.LIBRARY,
        "institution_name": "Portland Public Library",
        "institution_url": "https://multcolib.org",
    },
]

BASE_BOOKS = [
    {
        "isbn_13": "9780201616224",
        "isbn_10": "020161622X",
        "title": "The Pragmatic Programmer",
        "authors": ["David Thomas", "Andrew Hunt"],
        "publisher": "Addison-Wesley",
        "publish_year": 1999,
        "page_count": 352,
    },
    {
        "isbn_13": "9780596007645",
        "isbn_10": "0596007647",
        "title": "Learning Python",
        "authors": ["Mark Lutz"],
        "publisher": "O'Reilly Media",
        "publish_year": 2004,
        "page_count": 620,
    },
    {
        "isbn_13": "9780735619678",
        "isbn_10": "0735619670",
        "title": "Code Complete",
        "authors": ["Steve McConnell"],
        "publisher": "Microsoft Press",
        "publish_year": 2004,
        "page_count": 960,
    },
    {
        "isbn_13": "9780316769174",
        "isbn_10": "0316769177",
        "title": "The Catcher in the Rye",
        "authors": ["J.D. Salinger"],
        "publisher": "Little, Brown",
        "publish_year": 1951,
        "page_count": 277,
    },
    {
        "isbn_13": "9780062315007",
        "isbn_10": "0062315005",
        "title": "Sapiens: A Brief History of Humankind",
        "authors": ["Yuval Noah Harari"],
        "publisher": "Harper",
        "publish_year": 2015,
        "page_count": 464,
    },
]

CONDITIONS = [
    ConditionChoices.ACCEPTABLE,
    ConditionChoices.GOOD,
    ConditionChoices.VERY_GOOD,
    ConditionChoices.LIKE_NEW,
]


class Command(BaseCommand):
    help = "Seed development data with deterministic options"

    def add_arguments(self, parser):
        parser.add_argument(
            "--size",
            choices=tuple(SIZE_MAP.keys()),
            default="small",
            help="Dataset size profile (default: small)",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for deterministic generated data (default: 42)",
        )
        parser.add_argument(
            "--password",
            default="testpassword123",
            help="Password to set for newly created seeded users",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded records (by known seed email/isbn patterns) before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        size = SIZE_MAP[options["size"]]
        rng = random.Random(options["seed"])
        password = options["password"]

        if options["reset"]:
            self._reset_seeded_data()

        users = self._seed_users(rng, size, password)
        books = self._seed_books(rng, size)

        self._seed_core_inventory(users, books)
        self._seed_generated_inventory(users, books, size, rng)

        self._print_summary()
        self.stdout.write(self.style.SUCCESS("Seed complete."))

    def _seed_users(
        self, rng: random.Random, size: SeedSize, password: str
    ) -> list[User]:
        users: list[User] = []

        for data in BASE_USERS:
            user = self._upsert_user(data, password=password)
            users.append(user)

        for i in range(size.extra_users):
            idx = i + 1
            data = {
                "email": f"seed_user_{idx}@example.com",
                "username": f"seed_user_{idx}",
                "full_name": f"Seed User {idx}",
                "address_line_1": f"{100 + idx} Seed Street",
                "city": rng.choice(
                    ["Portland", "Seattle", "Denver", "Austin", "Boston"]
                ),
                "state": rng.choice(["OR", "WA", "CO", "TX", "MA"]),
                "zip_code": f"{90000 + idx}",
                "account_type": User.AccountType.INDIVIDUAL,
            }
            users.append(self._upsert_user(data, password=password))

        return users

    def _seed_books(self, rng: random.Random, size: SeedSize) -> list[Book]:
        books: list[Book] = []

        for data in BASE_BOOKS:
            books.append(self._upsert_book(data))

        for i in range(size.extra_books):
            idx = i + 1
            isbn_13 = f"978111111{idx:04d}"
            data = {
                "isbn_13": isbn_13,
                "isbn_10": f"111111{idx:04d}"[:10],
                "title": f"Seed Book {idx}",
                "authors": [f"Author {rng.randint(1, 50)}"],
                "publisher": rng.choice(["Acme Press", "Northwind", "Contoso Books"]),
                "publish_year": rng.randint(1980, 2024),
                "page_count": rng.randint(120, 900),
            }
            books.append(self._upsert_book(data))

        return books

    def _seed_core_inventory(self, users: list[User], books: list[Book]) -> None:
        alice, bob, carol, library = users[0], users[1], users[2], users[3]
        prog_programmer, learning_python, code_complete, catcher, sapiens = books[:5]

        self._upsert_user_book(alice, prog_programmer, ConditionChoices.VERY_GOOD)
        self._upsert_user_book(alice, catcher, ConditionChoices.GOOD)
        self._upsert_wishlist_item(alice, learning_python, ConditionChoices.GOOD)

        self._upsert_user_book(bob, learning_python, ConditionChoices.LIKE_NEW)
        self._upsert_user_book(bob, sapiens, ConditionChoices.VERY_GOOD)
        self._upsert_wishlist_item(bob, prog_programmer, ConditionChoices.GOOD)

        self._upsert_user_book(carol, code_complete, ConditionChoices.ACCEPTABLE)
        self._upsert_wishlist_item(carol, sapiens, ConditionChoices.ACCEPTABLE)
        self._upsert_wishlist_item(carol, catcher, ConditionChoices.GOOD)

        self._upsert_wishlist_item(
            library, learning_python, ConditionChoices.ACCEPTABLE
        )
        self._upsert_wishlist_item(library, code_complete, ConditionChoices.ACCEPTABLE)

    def _seed_generated_inventory(
        self,
        users: list[User],
        books: list[Book],
        size: SeedSize,
        rng: random.Random,
    ) -> None:
        if not size.extra_users and not size.extra_books:
            return

        generated_users = users[4:] if len(users) > 4 else []
        if not generated_users:
            return

        for user in generated_users:
            inventory_books = rng.sample(
                books, k=min(size.inventory_per_user, len(books))
            )
            wishlist_books = rng.sample(
                books, k=min(size.wishlist_per_user, len(books))
            )

            for book in inventory_books:
                self._upsert_user_book(user, book, rng.choice(CONDITIONS))

            for book in wishlist_books:
                self._upsert_wishlist_item(user, book, rng.choice(CONDITIONS))

    def _upsert_user(self, data: dict, password: str) -> User:
        defaults = {
            "username": data["username"],
            "full_name": data.get("full_name", ""),
            "address_line_1": data.get("address_line_1", ""),
            "city": data.get("city", ""),
            "state": data.get("state", ""),
            "zip_code": data.get("zip_code", ""),
            "account_type": data.get("account_type", User.AccountType.INDIVIDUAL),
            "institution_name": data.get("institution_name", ""),
            "institution_url": data.get("institution_url", ""),
            "email_verified": True,
            "is_active": True,
        }

        user, created = User.objects.update_or_create(
            email=data["email"],
            defaults=defaults,
        )

        if created:
            user.set_password(password)
            user.save(update_fields=["password"])

        if (
            user.account_type in (User.AccountType.LIBRARY, User.AccountType.BOOKSTORE)
            and not user.is_verified
        ):
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        return user

    def _upsert_book(self, data: dict) -> Book:
        book, _ = Book.objects.update_or_create(
            isbn_13=data["isbn_13"],
            defaults={
                "isbn_10": data.get("isbn_10"),
                "title": data.get("title"),
                "authors": data.get("authors", []),
                "publisher": data.get("publisher"),
                "publish_year": data.get("publish_year"),
                "page_count": data.get("page_count"),
            },
        )
        return book

    def _upsert_user_book(self, user: User, book: Book, condition: str) -> None:
        user_book = (
            UserBook.objects.filter(user=user, book=book).order_by("created_at").first()
        )

        if user_book:
            user_book.condition = condition
            user_book.status = UserBook.Status.AVAILABLE
            user_book.save(update_fields=["condition", "status", "updated_at"])
            return

        UserBook.objects.create(
            user=user,
            book=book,
            condition=condition,
            status=UserBook.Status.AVAILABLE,
        )

    def _upsert_wishlist_item(self, user: User, book: Book, min_condition: str) -> None:
        WishlistItem.objects.update_or_create(
            user=user,
            book=book,
            defaults={
                "min_condition": min_condition,
                "is_active": True,
            },
        )

    def _reset_seeded_data(self) -> None:
        seeded_emails = [user["email"] for user in BASE_USERS]
        seeded_emails.extend(
            User.objects.filter(
                email__startswith="seed_user_", email__endswith="@example.com"
            ).values_list("email", flat=True)
        )

        seeded_isbns = [book["isbn_13"] for book in BASE_BOOKS]
        seeded_isbns.extend(
            Book.objects.filter(isbn_13__startswith="978111111").values_list(
                "isbn_13", flat=True
            )
        )

        users_qs = User.objects.filter(email__in=seeded_emails)
        books_qs = Book.objects.filter(isbn_13__in=seeded_isbns)

        UserBook.objects.filter(user__in=users_qs).delete()
        WishlistItem.objects.filter(user__in=users_qs).delete()
        books_qs.delete()
        users_qs.delete()

        self.stdout.write(self.style.WARNING("Existing seeded data removed."))

    def _print_summary(self) -> None:
        seeded_user_count = User.objects.filter(
            email__in=[u["email"] for u in BASE_USERS]
        ).count()
        generated_user_count = User.objects.filter(
            email__startswith="seed_user_"
        ).count()
        seeded_book_count = Book.objects.filter(
            isbn_13__in=[b["isbn_13"] for b in BASE_BOOKS]
        ).count()
        generated_book_count = Book.objects.filter(
            isbn_13__startswith="978111111"
        ).count()

        self.stdout.write("\nSeed summary:")
        self.stdout.write(f"  Base users: {seeded_user_count}")
        self.stdout.write(f"  Generated users: {generated_user_count}")
        self.stdout.write(f"  Base books: {seeded_book_count}")
        self.stdout.write(f"  Generated books: {generated_book_count}")
        self.stdout.write(f"  User books total: {UserBook.objects.count()}")
        self.stdout.write(f"  Wishlist items total: {WishlistItem.objects.count()}")

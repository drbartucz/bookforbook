import factory

from apps.accounts.models import User
from apps.books.models import Book
from apps.inventory.models import ConditionChoices, UserBook, WishlistItem


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    email_verified = True


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    isbn_13 = factory.Sequence(lambda n: f"9780000000{n:03d}")
    title = factory.Sequence(lambda n: f"Test Book {n}")
    authors = factory.LazyFunction(lambda: ["Test Author"])


class UserBookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserBook

    user = factory.SubFactory(UserFactory)
    book = factory.SubFactory(BookFactory)
    condition = ConditionChoices.GOOD
    status = UserBook.Status.AVAILABLE


class WishlistItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WishlistItem

    user = factory.SubFactory(UserFactory)
    book = factory.SubFactory(BookFactory)
    min_condition = ConditionChoices.ACCEPTABLE
    is_active = True

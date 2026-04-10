import uuid

import factory

from apps.accounts.models import User
from apps.books.models import Book
from apps.inventory.models import ConditionChoices, UserBook, WishlistItem
from apps.messaging.models import TradeMessage
from apps.notifications.models import Notification
from apps.trading.models import Trade, TradeShipment


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


class TradeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Trade

    source_type = Trade.SourceType.PROPOSAL
    source_id = factory.LazyFunction(uuid.uuid4)
    status = Trade.Status.CONFIRMED


class TradeShipmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TradeShipment

    trade = factory.SubFactory(TradeFactory)
    sender = factory.SubFactory(UserFactory)
    receiver = factory.SubFactory(UserFactory)
    user_book = factory.SubFactory(UserBookFactory)
    status = TradeShipment.Status.PENDING


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    notification_type = "new_match"
    title = factory.Sequence(lambda n: f"Notification {n}")
    body = "A notification body."
    is_read = False


class TradeMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TradeMessage

    trade = factory.SubFactory(TradeFactory)
    sender = factory.SubFactory(UserFactory)
    message_type = TradeMessage.MessageType.GENERAL_NOTE
    content = "Hello, looking forward to this trade!"

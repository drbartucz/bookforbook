import uuid

import factory

from apps.accounts.models import User
from apps.books.models import Book
from apps.backups.models import BackupRecord
from apps.donations.models import Donation
from apps.inventory.models import ConditionChoices, UserBook, WishlistItem
from apps.ratings.models import Rating
from apps.matching.models import Match, MatchLeg
from apps.messaging.models import TradeMessage
from apps.trading.models import Trade, TradeShipment, TradeProposal, TradeProposalItem
from apps.notifications.models import Notification
from apps.trading.models import Trade, TradeShipment


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    email_verified = True
    address_verification_status = User.AddressVerificationStatus.VERIFIED

    @factory.post_generation
    def persist_password(self, create, extracted, **kwargs):
        if create:
            self.save(update_fields=["password"])


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


class BackupRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BackupRecord

    backup_type = BackupRecord.BackupType.DATABASE
    status = BackupRecord.Status.PENDING
    is_automatic = True



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


class MatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Match

    match_type = Match.MatchType.DIRECT
    status = Match.Status.PENDING


class MatchLegFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MatchLeg

    match = factory.SubFactory(MatchFactory)
    sender = factory.SubFactory(UserFactory)
    receiver = factory.SubFactory(UserFactory)
    user_book = factory.SubFactory(UserBookFactory)
    position = 0
    status = MatchLeg.Status.PENDING


class TradeProposalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TradeProposal

    proposer = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    status = TradeProposal.Status.PENDING


class TradeProposalItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TradeProposalItem

    proposal = factory.SubFactory(TradeProposalFactory)
    user_book = factory.SubFactory(UserBookFactory)


class DonationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Donation

    donor = factory.SubFactory(UserFactory)
    institution = factory.SubFactory(UserFactory, account_type=User.AccountType.LIBRARY)
    user_book = factory.SubFactory(UserBookFactory)
    status = Donation.Status.OFFERED


class RatingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Rating

    trade = factory.SubFactory(TradeFactory)
    rater = factory.SubFactory(UserFactory)
    rated = factory.SubFactory(UserFactory)
    score = 5
    book_condition_accurate = True





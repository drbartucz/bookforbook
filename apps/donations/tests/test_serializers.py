import pytest
from unittest.mock import MagicMock

from apps.donations.serializers import DonationSerializer, DonationCreateSerializer
from apps.donations.models import Donation
from apps.inventory.models import UserBook, ConditionChoices, WishlistItem
from apps.accounts.models import User
from apps.tests.factories import UserFactory, UserBookFactory, DonationFactory, WishlistItemFactory

@pytest.mark.django_db
class TestDonationSerializers:
    def test_donation_serializer_reveal_address(self):
        donor = UserFactory(username="donor")
        inst = UserFactory(
            username="library",
            institution_name="Main Lib",
            address_line_1="123 Lib St",
            account_type=User.AccountType.LIBRARY
        )
        donation = DonationFactory(donor=donor, recipient=inst, status=Donation.Status.ACCEPTED)

        # 1. As donor -> should see address
        request = MagicMock(user=donor)
        serializer = DonationSerializer(instance=donation, context={'request': request})
        assert serializer.data['recipient_address']['address_line_1'] == "123 Lib St"
        assert serializer.data['is_recipient'] is False

        # 2. As recipient -> should not see their own address in this field but is_recipient is True
        request_inst = MagicMock(user=inst)
        serializer_inst = DonationSerializer(instance=donation, context={'request': request_inst})
        assert serializer_inst.data['recipient_address'] is None
        assert serializer_inst.data['is_recipient'] is True

    def test_donation_create_serializer_validation(self):
        donor = UserFactory()
        # Invalid institution (not verified)
        inst_unverified = UserFactory(account_type=User.AccountType.LIBRARY, is_verified=False)
        ub = UserBookFactory(user=donor, status=UserBook.Status.AVAILABLE)

        request = MagicMock(user=donor)
        data = {
            "recipient_id": str(inst_unverified.id),
            "user_book_id": str(ub.id)
        }
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'recipient_id' in serializer.errors

        # Valid institution
        inst_verified = UserFactory(account_type=User.AccountType.LIBRARY, is_verified=True)
        data['recipient_id'] = str(inst_verified.id)
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert serializer.is_valid()

        # Invalid book (not available)
        ub.status = UserBook.Status.RESERVED
        ub.save()
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'user_book_id' in serializer.errors

    def test_self_gifting_rejected(self):
        donor = UserFactory()
        ub = UserBookFactory(user=donor, status=UserBook.Status.AVAILABLE)

        request = MagicMock(user=donor)
        data = {"recipient_id": str(donor.id), "user_book_id": str(ub.id)}
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'recipient_id' in serializer.errors

    def test_donation_create_condition_validation_for_individual(self):
        donor = UserFactory()
        recipient = UserFactory()
        ub = UserBookFactory(user=donor, status=UserBook.Status.AVAILABLE, condition=ConditionChoices.ACCEPTABLE)

        request = MagicMock(user=donor)

        # Recipient wants like_new — donor's acceptable copy should be rejected
        wishlist = WishlistItemFactory(user=recipient, book=ub.book, min_condition=ConditionChoices.LIKE_NEW)
        data = {"recipient_id": str(recipient.id), "user_book_id": str(ub.id)}
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'user_book_id' in serializer.errors

        # Recipient lowers minimum to acceptable — same book should now be valid
        wishlist.min_condition = ConditionChoices.ACCEPTABLE
        wishlist.save()
        serializer = DonationCreateSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors

import pytest

from apps.matching.models import DeclinedPairing
from apps.tests.factories import BookFactory, UserBookFactory, UserFactory


pytestmark = pytest.mark.django_db


class TestDeclinedPairing:
    def test_record_creates_in_canonical_order(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        # Determine which id is "smaller" by string comparison
        smaller, larger = sorted([ub_a.pk, ub_b.pk], key=str)
        DeclinedPairing.record_by_ids(larger, smaller)  # pass in reversed order

        pairing = DeclinedPairing.objects.get()
        assert str(pairing.user_book_a_id) == str(smaller)
        assert str(pairing.user_book_b_id) == str(larger)

    def test_record_idempotent(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)
        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)

        assert DeclinedPairing.objects.count() == 1

    def test_record_reversed_args_is_idempotent(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)
        DeclinedPairing.record_by_ids(ub_b.pk, ub_a.pk)

        assert DeclinedPairing.objects.count() == 1

    def test_cascade_delete_on_user_book_removal(self):
        user_a = UserFactory()
        user_b = UserFactory()
        ub_a = UserBookFactory(user=user_a, book=BookFactory())
        ub_b = UserBookFactory(user=user_b, book=BookFactory())

        DeclinedPairing.record_by_ids(ub_a.pk, ub_b.pk)
        assert DeclinedPairing.objects.count() == 1

        ub_a.delete()
        assert DeclinedPairing.objects.count() == 0

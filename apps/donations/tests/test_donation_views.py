import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

from apps.tests.factories import UserFactory, UserBookFactory, DonationFactory
from apps.donations.models import Donation
from apps.inventory.models import UserBook
from apps.accounts.models import User

@pytest.mark.django_db
class TestDonationViews:
    def test_donation_list(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        DonationFactory(donor=user)

        url = reverse('donation-list-create')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_donation_offer(self, api_client):
        donor = UserFactory()
        inst = UserFactory(account_type=User.AccountType.BOOKSTORE, is_verified=True)
        ub = UserBookFactory(user=donor, status=UserBook.Status.AVAILABLE)
        api_client.force_authenticate(user=donor)

        url = reverse('donation-list-create')
        data = {
            "recipient_id": str(inst.id),
            "user_book_id": str(ub.id),
            "message": "Enjoy!"
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Donation.objects.filter(donor=donor, recipient=inst).exists()

    def test_donation_accept_success(self, api_client):
        inst = UserFactory(account_type=User.AccountType.LIBRARY, is_verified=True)
        api_client.force_authenticate(user=inst)

        donation = DonationFactory(recipient=inst, status=Donation.Status.OFFERED)

        url = reverse('donation-accept', kwargs={'pk': donation.pk})

        with patch("apps.donations.views.user_has_verified_shipping_address", return_value=True, create=True):
            response = api_client.post(url)
            assert response.status_code == status.HTTP_200_OK
            donation.refresh_from_db()
            assert donation.status == Donation.Status.ACCEPTED

    def test_donation_decline(self, api_client):
        inst = UserFactory(account_type=User.AccountType.LIBRARY)
        api_client.force_authenticate(user=inst)

        donation = DonationFactory(recipient=inst, status=Donation.Status.OFFERED)
        ub = donation.user_book

        url = reverse('donation-decline', kwargs={'pk': donation.pk})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        donation.refresh_from_db()
        assert donation.status == Donation.Status.CANCELLED
        ub.refresh_from_db()
        assert ub.status == UserBook.Status.AVAILABLE

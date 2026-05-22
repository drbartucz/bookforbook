import pytest
from django.urls import reverse
from rest_framework import status

from apps.inventory.models import UserBook, ConditionChoices
from apps.accounts.models import User
from apps.tests.factories import UserFactory, UserBookFactory, WishlistItemFactory


@pytest.mark.django_db
class TestBookWantedByView:
    def _url(self, user_book_id):
        return reverse('my-book-wanted-by', kwargs={'pk': user_book_id})

    def test_requires_authentication(self, api_client):
        ub = UserBookFactory()
        response = api_client.get(self._url(ub.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_wishlist_users(self, api_client):
        owner = UserFactory()
        wanter = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=wanter, book=ub.book, min_condition=ConditionChoices.GOOD)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['user']['id'] == str(wanter.id)
        assert response.data[0]['min_condition'] == ConditionChoices.GOOD

    def test_excludes_owner_from_results(self, api_client):
        owner = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=owner, book=ub.book)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_excludes_inactive_wishlist_items(self, api_client):
        owner = UserFactory()
        wanter = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=wanter, book=ub.book, is_active=False)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_returns_404_for_another_users_book(self, api_client):
        owner = UserFactory()
        other = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)

        api_client.force_authenticate(user=other)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_for_unavailable_book(self, api_client):
        owner = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.RESERVED)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_multiple_wanters_with_varying_conditions(self, api_client):
        owner = UserFactory()
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=UserFactory(), book=ub.book, min_condition=ConditionChoices.LIKE_NEW)
        WishlistItemFactory(user=UserFactory(), book=ub.book, min_condition=ConditionChoices.GOOD)
        WishlistItemFactory(user=UserFactory(), book=ub.book, min_condition=ConditionChoices.ACCEPTABLE)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        conditions = {entry['min_condition'] for entry in response.data}
        assert conditions == {ConditionChoices.LIKE_NEW, ConditionChoices.GOOD, ConditionChoices.ACCEPTABLE}

    def test_includes_institution_wanters(self, api_client):
        owner = UserFactory()
        lib = UserFactory(account_type=User.AccountType.LIBRARY, is_verified=True)
        ub = UserBookFactory(user=owner, status=UserBook.Status.AVAILABLE)
        WishlistItemFactory(user=lib, book=ub.book)

        api_client.force_authenticate(user=owner)
        response = api_client.get(self._url(ub.pk))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['user']['id'] == str(lib.id)

import pytest
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db


ADMIN_CHANGE_LIST_URLS = [
    "/admin/accounts/user/",
    "/admin/books/book/",
    "/admin/inventory/userbook/",
    "/admin/inventory/wishlistitem/",
    "/admin/matching/match/",
    "/admin/matching/matchleg/",
    "/admin/trading/tradeproposal/",
    "/admin/trading/trade/",
    "/admin/trading/tradeshipment/",
    "/admin/donations/donation/",
    "/admin/ratings/rating/",
    "/admin/notifications/notification/",
    "/admin/messaging/trademessage/",
    "/admin/backups/backuprecord/",
]


def _make_superuser():
    return get_user_model().objects.create_superuser(
        email="admin-admin-tests@example.com",
        username="admin_admin_tests",
        password="adminpass123",
    )


@pytest.mark.parametrize("url", ADMIN_CHANGE_LIST_URLS)
def test_admin_changelists_render_for_superuser(client, url):
    superuser = _make_superuser()
    client.force_login(superuser)

    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.parametrize("url", ["/admin/accounts/user/", "/admin/books/book/"])
def test_admin_requires_authentication(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]

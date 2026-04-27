import pytest

from apps.accounts.admin import UserAdmin
from apps.accounts.models import User
from apps.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


def test_accounts_admin_changelist_renders_for_superuser(client):
    superuser = User.objects.create_superuser(
        email="admin-accounts-tests@example.com",
        username="admin_accounts_tests",
        password="adminpass123",
    )
    client.force_login(superuser)

    response = client.get("/admin/accounts/user/")

    assert response.status_code == 200


def test_accounts_admin_change_form_shows_email_verified_at_and_now_button(client):
    superuser = User.objects.create_superuser(
        email="admin-accounts-form@example.com",
        username="admin_accounts_form",
        password="adminpass123",
    )
    user = UserFactory(email="target-user@example.com", username="target_user")
    client.force_login(superuser)

    response = client.get(f"/admin/accounts/user/{user.pk}/change/")

    assert response.status_code == 200
    # Datetime widgets can render as split fields (_0/_1) or a single field.
    assert (
        b'id="id_email_verified_at_0"' in response.content
        or b'id="id_email_verified_at"' in response.content
    )
    assert b"admin/accounts/user_admin.js" in response.content


def test_accounts_admin_email_verified_at_is_editable():
    assert "email_verified_at" not in UserAdmin.readonly_fields

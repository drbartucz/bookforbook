import pytest
from django.contrib import admin

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


def test_accounts_admin_change_form_shows_address_verification_fields(client):
    superuser = User.objects.create_superuser(
        email="admin-accounts-address-form@example.com",
        username="admin_accounts_address_form",
        password="adminpass123",
    )
    user = UserFactory(
        email="target-address-user@example.com", username="target_address"
    )
    client.force_login(superuser)

    response = client.get(f"/admin/accounts/user/{user.pk}/change/")

    assert response.status_code == 200
    assert b'id="id_address_verification_status"' in response.content
    # Datetime widgets can render as split fields (_0/_1) or a single field.
    assert (
        b'id="id_address_verified_at_0"' in response.content
        or b'id="id_address_verified_at"' in response.content
    )


def test_accounts_admin_email_verified_at_is_editable():
    assert "email_verified_at" not in UserAdmin.readonly_fields


def test_accounts_admin_address_verification_fields_are_editable_and_listed():
    assert "address_verified_at" not in UserAdmin.readonly_fields
    assert "address_verification_label" in UserAdmin.list_display
    assert "address_verification_status" in UserAdmin.list_filter


def test_accounts_admin_address_verification_label_uses_friendly_display():
    user_admin = UserAdmin(User, admin.site)

    verified_user = UserFactory(
        address_verification_status=User.AddressVerificationStatus.VERIFIED
    )
    failed_user = UserFactory(
        address_verification_status=User.AddressVerificationStatus.FAILED
    )

    assert user_admin.address_verification_label(verified_user) == "Verified"
    assert user_admin.address_verification_label(failed_user) == "Failed"

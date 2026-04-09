"""
API tests for accounts auth endpoints.
register, verify-email, login, logout, password-reset
"""

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from apps.accounts.tokens import email_verification_token
from apps.tests.factories import UserFactory


@pytest.mark.django_db
class TestRegisterView:
    url = "/api/v1/auth/register/"

    def test_register_success(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "new@example.com",
                "username": "newuser",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "detail" in resp.data

    def test_register_password_mismatch(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "new@example.com",
                "username": "newuser",
                "password": "StrongPass123!",
                "password2": "WrongPass123!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, verified_user):
        resp = api_client.post(
            self.url,
            {
                "email": verified_user.email,
                "username": "anotheruser",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_institution_requires_name(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "lib@example.com",
                "username": "somelibrary",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
                "account_type": "library",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_institution_with_name(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "lib@example.com",
                "username": "somelibrary",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
                "account_type": "library",
                "institution_name": "Public Library",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_register_weak_password_rejected(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "weak@example.com",
                "username": "weakuser",
                "password": "123",
                "password2": "123",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLoginView:
    url = "/api/v1/auth/token/"

    def test_login_success(self, api_client, verified_user):
        resp = api_client.post(
            self.url,
            {
                "email": verified_user.email,
                "password": "testpass123",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert "user" in resp.data

    def test_login_wrong_password(self, api_client, verified_user):
        resp = api_client.post(
            self.url,
            {
                "email": verified_user.email,
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_unverified_email_rejected(self, api_client, user):
        resp = api_client.post(
            self.url,
            {
                "email": user.email,
                "password": "testpass123",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user_rejected(self, api_client, db):
        inactive = UserFactory(email_verified=True, is_active=False)
        resp = api_client.post(
            self.url,
            {
                "email": inactive.email,
                "password": "testpass123",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestVerifyEmailView:
    url = "/api/v1/auth/verify-email/"

    def test_verify_email_success(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        resp = api_client.post(self.url, {"uid": uid, "token": token})
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.email_verified is True
        assert user.email_verified_at is not None

    def test_verify_email_invalid_token(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        resp = api_client.post(self.url, {"uid": uid, "token": "bad-token"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_invalid_uid(self, api_client):
        resp = api_client.post(self.url, {"uid": "notauid", "token": "sometoken"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserMeView:
    url = "/api/v1/users/me/"

    def test_get_me_authenticated(self, auth_api_client, verified_user):
        resp = auth_api_client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["email"] == verified_user.email
        assert resp.data["username"] == verified_user.username

    def test_get_me_unauthenticated(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_me_updates_address(self, auth_api_client):
        resp = auth_api_client.patch(
            self.url,
            {
                "full_name": "Alice Smith",
                "city": "Portland",
                "state": "OR",
                "zip_code": "97201",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["city"] == "Portland"
        assert resp.data["state"] == "OR"

    def test_patch_me_invalid_state(self, auth_api_client):
        resp = auth_api_client.patch(self.url, {"state": "XX"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_me_invalid_zip(self, auth_api_client):
        resp = auth_api_client.patch(self.url, {"zip_code": "not-a-zip"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_address_not_returned_in_public_profile(self, api_client, verified_user):
        """Address fields must never appear in public profile responses."""
        resp = api_client.get(f"/api/v1/users/{verified_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        for field in ("address_line_1", "full_name", "zip_code"):
            assert field not in resp.data


@pytest.mark.django_db
class TestPasswordReset:
    request_url = "/api/v1/auth/password-reset/"
    confirm_url = "/api/v1/auth/password-reset/confirm/"

    def test_reset_request_returns_200_regardless_of_email(self, api_client):
        resp = api_client.post(self.request_url, {"email": "nobody@example.com"})
        assert resp.status_code == status.HTTP_200_OK

    def test_reset_confirm_success(self, api_client, verified_user):
        uid = urlsafe_base64_encode(force_bytes(verified_user.pk))
        token = default_token_generator.make_token(verified_user)
        resp = api_client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass1!",
                "new_password2": "NewStrongPass1!",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        verified_user.refresh_from_db()
        assert verified_user.check_password("NewStrongPass1!")

    def test_reset_confirm_password_mismatch(self, api_client, verified_user):
        uid = urlsafe_base64_encode(force_bytes(verified_user.pk))
        token = default_token_generator.make_token(verified_user)
        resp = api_client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass1!",
                "new_password2": "DifferentPass1!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

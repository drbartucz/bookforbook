import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from unittest.mock import patch
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

from apps.accounts.models import User
from apps.accounts.tokens import email_verification_token
from apps.tests.factories import UserFactory

@pytest.mark.django_db
class TestAccountViews:
    def test_register_view(self, api_client):
        url = reverse('auth-register')
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "testpass123A!",
            "password2": "testpass123A!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_login_view(self, api_client):
        user = UserFactory(email_verified=True)
        user.set_password("testpass123")
        user.save()
        
        url = reverse('auth-login')
        data = {"email": user.email, "password": "testpass123"}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_verify_email_view(self, api_client):
        user = UserFactory(email_verified=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        
        url = reverse('auth-verify-email')
        data = {"uid": uid, "token": token}
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.email_verified is True

    def test_user_me_view(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        
        url = reverse('user-me')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email

    def test_me_get_refreshes_last_active_at_when_stale(self, api_client):
        user = UserFactory()
        stale_time = timezone.now() - timedelta(hours=25)
        User.objects.filter(pk=user.pk).update(last_active_at=stale_time)
        user.refresh_from_db()
        api_client.force_authenticate(user=user)

        api_client.get(reverse("user-me"))

        user.refresh_from_db()
        assert user.last_active_at > stale_time

    def test_me_get_skips_update_when_active_recently(self, api_client):
        user = UserFactory()
        recent_time = timezone.now() - timedelta(hours=1)
        User.objects.filter(pk=user.pk).update(last_active_at=recent_time)
        user.refresh_from_db()
        api_client.force_authenticate(user=user)

        api_client.get(reverse("user-me"))

        user.refresh_from_db()
        assert abs((user.last_active_at - recent_time).total_seconds()) < 2

    def test_user_me_update_view(self, api_client):
        user = UserFactory(full_name="Old Name")
        api_client.force_authenticate(user=user)
        
        url = reverse('user-me')
        data = {"full_name": "New Name"}
        response = api_client.patch(url, data)
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.full_name == "New Name"

    def test_password_reset_request_view(self, api_client):
        user = UserFactory()
        url = reverse('auth-password-reset')
        data = {"email": user.email}
        
        with patch("django_q.tasks.async_task") as mock_async:
            response = api_client.post(url, data)
            assert response.status_code == status.HTTP_200_OK
            assert mock_async.called

    def test_password_reset_confirm_view(self, api_client):
        user = UserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        url = reverse('auth-password-reset-confirm')
        data = {
            "uid": uid,
            "token": token,
            "new_password": "NewSecurePassword123!",
            "new_password2": "NewSecurePassword123!",
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        
        # Verify can login with new password
        user.refresh_from_db()
        assert user.check_password("NewSecurePassword123!")

    def test_account_delete_view(self, api_client):
        user = UserFactory()
        user.set_password("deletepass123")
        user.save()
        api_client.force_authenticate(user=user)
        
        url = reverse('user-me')
        data = {"password": "deletepass123"}
        response = api_client.delete(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is False

    def test_address_verify_view(self, api_client):
        user = UserFactory(address_verification_status=User.AddressVerificationStatus.UNVERIFIED, email_verified=True)
        api_client.force_authenticate(user=user)
        
        url = reverse('user-address-verify')
        data = {
            "full_name": "John Doe",
            "address_line_1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001"
        }
        
        normalized = {
            "address_line_1": "123 MAIN ST",
            "address_line_2": "",
            "city": "NEW YORK",
            "state": "NY",
            "zip_code": "10001-1234"
        }
        
        # The view imports it locally: from .services.usps import verify_address_with_usps
        with patch("apps.accounts.services.usps.verify_address_with_usps") as mock_verify:
            mock_verify.return_value = normalized
            response = api_client.post(url, data)
            
            assert response.status_code == status.HTTP_200_OK
            user.refresh_from_db()
            assert user.address_verification_status == User.AddressVerificationStatus.VERIFIED
            assert user.city == "NEW YORK"

import pytest
from unittest.mock import MagicMock
from apps.accounts.permissions import EmailVerifiedPermission
from apps.tests.factories import UserFactory

@pytest.mark.django_db
class TestEmailVerifiedPermission:
    def test_verified_user_has_permission(self):
        user = UserFactory(email_verified=True)
        request = MagicMock()
        request.user = user
        permission = EmailVerifiedPermission()
        assert permission.has_permission(request, None) is True

    def test_unverified_user_no_permission(self):
        user = UserFactory(email_verified=False)
        request = MagicMock()
        request.user = user
        permission = EmailVerifiedPermission()
        assert permission.has_permission(request, None) is False

    def test_unauthenticated_user_no_permission(self):
        request = MagicMock()
        request.user.is_authenticated = False
        permission = EmailVerifiedPermission()
        assert permission.has_permission(request, None) is False

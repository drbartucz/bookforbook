import pytest
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import (
    RegisterSerializer,
    LoginSerializer,
    EmailVerificationSerializer,
    PasswordResetConfirmSerializer,
    UserMeUpdateSerializer,
    AccountDeletionSerializer,
    AddressVerificationSerializer,
)
from apps.accounts.tokens import email_verification_token
from apps.tests.factories import UserFactory

@pytest.mark.django_db
class TestAccountSerializers:
    def test_register_serializer_disposable_email(self):
        data = {
            "email": "test@mailinator.com",
            "username": "testuser",
            "password": "testpass123A!",
            "password2": "testpass123A!",
        }
        serializer = RegisterSerializer(data=data)
        with pytest.raises(serializers.ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert "disposable email" in str(excinfo.value)

    def test_register_serializer_password_mismatch(self):
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass123A!",
            "password2": "different",
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_register_serializer_institution_name_required(self):
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass123A!",
            "password2": "testpass123A!",
            "account_type": User.AccountType.LIBRARY,
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert "institution_name" in serializer.errors

    def test_login_serializer_unverified(self):
        user = UserFactory(email_verified=False)
        data = {"email": user.email, "password": "testpass123"}
        serializer = LoginSerializer(data=data)
        assert not serializer.is_valid()

    def test_email_verification_serializer(self):
        user = UserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        
        data = {"uid": uid, "token": token}
        serializer = EmailVerificationSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['user'] == user

    def test_password_reset_confirm_serializer(self):
        user = UserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        data = {
            "uid": uid, 
            "token": token,
            "new_password": "newpassword123A!",
            "new_password2": "newpassword123A!"
        }
        serializer = PasswordResetConfirmSerializer(data=data)
        assert serializer.is_valid()

    def test_user_me_update_serializer_resets_address_status(self):
        user = UserFactory(address_verification_status=User.AddressVerificationStatus.VERIFIED)
        data = {"address_line_1": "123 New St"}
        serializer = UserMeUpdateSerializer(instance=user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()
        assert updated_user.address_verification_status == User.AddressVerificationStatus.UNVERIFIED

    def test_user_me_update_serializer_invalid_state(self):
        data = {"state": "ZZ"}
        serializer = UserMeUpdateSerializer(data=data, partial=True)
        assert not serializer.is_valid()
        assert "state" in serializer.errors

    def test_user_me_update_serializer_invalid_zip(self):
        data = {"zip_code": "abc"}
        serializer = UserMeUpdateSerializer(data=data, partial=True)
        assert not serializer.is_valid()
        assert "zip_code" in serializer.errors

    def test_account_deletion_serializer(self):
        user = UserFactory()
        user.set_password("correctpass")
        user.save()
        
        # Mock request context
        class MockRequest:
            def __init__(self, user):
                self.user = user
        
        data = {"password": "correctpass"}
        serializer = AccountDeletionSerializer(data=data, context={'request': MockRequest(user)})
        assert serializer.is_valid()
        
        data_wrong = {"password": "wrong"}
        serializer_wrong = AccountDeletionSerializer(data=data_wrong, context={'request': MockRequest(user)})
        assert not serializer_wrong.is_valid()

    def test_address_verification_serializer(self):
        data = {
            "full_name": "John Doe",
            "address_line_1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001"
        }
        serializer = AddressVerificationSerializer(data=data)
        assert serializer.is_valid()
        
        data_invalid_state = {**data, "state": "INVALID"}
        assert not AddressVerificationSerializer(data=data_invalid_state).is_valid()

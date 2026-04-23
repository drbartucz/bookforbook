"""
Unit tests for the accounts app User model.
"""

import pytest

from apps.accounts.models import User, CONTINENTAL_US_STATES


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="securepassword123",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.account_type == User.AccountType.INDIVIDUAL
        assert not user.email_verified
        assert not user.is_staff
        assert user.is_active

    def test_max_active_matches_new_user(self):
        user = User(rating_count=0)
        assert user.max_active_matches == 2

    def test_max_active_matches_experienced_user(self):
        user = User(rating_count=5)
        assert user.max_active_matches == 5

    def test_max_active_matches_capped_at_10(self):
        user = User(rating_count=15)
        assert user.max_active_matches == 10

    def test_continental_us_states_count(self):
        # 48 continental states + DC = 49
        assert len(CONTINENTAL_US_STATES) == 49

    def test_is_institutional_for_library(self):
        user = User(account_type=User.AccountType.LIBRARY)
        assert user.is_institutional

    def test_is_institutional_for_individual(self):
        user = User(account_type=User.AccountType.INDIVIDUAL)
        assert not user.is_institutional

    def test_str_representation(self):
        user = User(username="alice", email="alice@example.com")
        assert "alice" in str(user)
        assert "alice@example.com" in str(user)


@pytest.mark.django_db
class TestUserManager:
    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            username="admin",
            password="adminpassword",
        )
        assert user.is_staff
        assert user.is_superuser
        assert user.is_active
        assert user.email_verified

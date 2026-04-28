"""
API tests for accounts auth endpoints.
register, verify-email, login, logout, password-reset
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.tokens import email_verification_token
from apps.matching.models import Match, MatchLeg
from apps.notifications.models import Notification
from apps.ratings.models import Rating
from apps.tests.factories import (
    BookFactory,
    UserBookFactory,
    UserFactory,
    WishlistItemFactory,
)
from apps.trading.models import Trade, TradeProposal


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

    @patch("django_q.tasks.async_task")
    def test_register_schedules_admin_alert(
        self, mock_async_task, api_client, settings
    ):
        settings.ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS = False
        resp = api_client.post(
            self.url,
            {
                "email": "new@bookforbook.com",
                "username": "newmember",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new@bookforbook.com")
        assert any(
            queued[0][0] == "apps.notifications.tasks.send_admin_registration_alert"
            and queued[0][1] == str(user.pk)
            for queued in mock_async_task.call_args_list
        )


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

    @patch("django_q.tasks.async_task")
    def test_verify_email_schedules_admin_alert(
        self, mock_async_task, api_client, user
    ):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)

        resp = api_client.post(self.url, {"uid": uid, "token": token})

        assert resp.status_code == status.HTTP_200_OK
        mock_async_task.assert_called_once_with(
            "apps.notifications.tasks.send_admin_email_verified_alert",
            str(user.pk),
        )


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

    @patch("django_q.tasks.async_task")
    def test_delete_me_initiates_scheduled_deletion(
        self, mock_async_task, auth_api_client, verified_user
    ):
        resp = auth_api_client.delete(
            self.url,
            {"password": "testpass123"},
            format="json",
        )

        assert resp.status_code == status.HTTP_200_OK
        assert "Account deletion initiated" in resp.data["detail"]

        verified_user.refresh_from_db()
        assert verified_user.is_active is False
        assert verified_user.deletion_requested_at is not None
        assert verified_user.deletion_scheduled_for is not None
        assert (
            verified_user.deletion_scheduled_for > verified_user.deletion_requested_at
        )

        mock_async_task.assert_called_once_with(
            "apps.notifications.tasks.send_account_deletion_initiated",
            str(verified_user.pk),
        )

    def test_delete_me_requires_password(self, auth_api_client):
        resp = auth_api_client.delete(self.url, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @patch("django_q.tasks.async_task")
    def test_delete_me_cancels_active_matches(self, _mock, api_client, db):
        """Pending matches are set to EXPIRED when a participant deletes their account."""
        user = UserFactory(email_verified=True)
        other = UserFactory(email_verified=True)
        book_a = UserBookFactory(user=user)
        book_b = UserBookFactory(user=other)

        match = Match.objects.create(match_type="direct", status=Match.Status.PENDING)
        MatchLeg.objects.create(
            match=match,
            sender=user,
            receiver=other,
            user_book=book_a,
            position=0,
            status=MatchLeg.Status.PENDING,
        )
        MatchLeg.objects.create(
            match=match,
            sender=other,
            receiver=user,
            user_book=book_b,
            position=1,
            status=MatchLeg.Status.PENDING,
        )

        client = api_client
        client.force_authenticate(user=user)
        resp = client.delete(self.url, {"password": "testpass123"}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        match.refresh_from_db()
        assert match.status == Match.Status.EXPIRED

    @patch("django_q.tasks.async_task")
    def test_delete_me_cancels_pending_proposals(self, _mock, api_client, db):
        """Pending proposals are set to CANCELLED when a participant deletes their account."""
        user = UserFactory(email_verified=True)
        other = UserFactory(email_verified=True)

        proposal = TradeProposal.objects.create(
            proposer=user,
            recipient=other,
            status=TradeProposal.Status.PENDING,
        )

        client = api_client
        client.force_authenticate(user=user)
        client.delete(self.url, {"password": "testpass123"}, format="json")

        proposal.refresh_from_db()
        assert proposal.status == TradeProposal.Status.CANCELLED

    @patch("django_q.tasks.async_task")
    def test_delete_me_notifies_match_counterparties(self, _mock, api_client, db):
        """Counterparties in active matches receive an account_deleted_impact notification."""
        user = UserFactory(email_verified=True)
        other = UserFactory(email_verified=True)
        book_a = UserBookFactory(user=user)
        book_b = UserBookFactory(user=other)

        match = Match.objects.create(match_type="direct", status=Match.Status.PENDING)
        MatchLeg.objects.create(
            match=match,
            sender=user,
            receiver=other,
            user_book=book_a,
            position=0,
            status=MatchLeg.Status.PENDING,
        )
        MatchLeg.objects.create(
            match=match,
            sender=other,
            receiver=user,
            user_book=book_b,
            position=1,
            status=MatchLeg.Status.PENDING,
        )

        client = api_client
        client.force_authenticate(user=user)
        client.delete(self.url, {"password": "testpass123"}, format="json")

        assert Notification.objects.filter(
            user=other, notification_type="account_deleted_impact"
        ).exists()

    @patch("django_q.tasks.async_task")
    def test_delete_me_is_idempotent_after_first_request(
        self, mock_async_task, auth_api_client
    ):
        first = auth_api_client.delete(
            self.url,
            {"password": "testpass123"},
            format="json",
        )
        second = auth_api_client.delete(
            self.url,
            {"password": "testpass123"},
            format="json",
        )

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert "already been initiated" in second.data["detail"]
        assert mock_async_task.call_count == 1


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


@pytest.mark.django_db
class TestAddressVerification:
    url = "/api/v1/users/me/address/verify/"

    @patch("django_q.tasks.async_task")
    def test_verify_address_success(
        self, mock_async_task, auth_api_client, verified_user
    ):
        from unittest.mock import patch

        with patch(
            "apps.accounts.services.usps.verify_address_with_usps",
            return_value={
                "address_line_1": "123 MAIN ST",
                "address_line_2": "APT 2",
                "city": "DENVER",
                "state": "CO",
                "zip_code": "80202-1234",
            },
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "full_name": "Reader One",
                    "address_line_1": "123 Main Street",
                    "address_line_2": "Apt 2",
                    "city": "Denver",
                    "state": "CO",
                    "zip_code": "80202",
                },
            )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["address_verification_status"] == "verified"
        assert resp.data["address_line_1"] == "123 MAIN ST"
        mock_async_task.assert_called_once_with(
            "apps.notifications.tasks.send_admin_postal_verified_alert",
            str(verified_user.pk),
        )

    def test_verify_address_failure(self, auth_api_client):
        from unittest.mock import patch

        from apps.accounts.services.usps import USPSVerificationError

        with patch(
            "apps.accounts.services.usps.verify_address_with_usps",
            side_effect=USPSVerificationError("Address not found."),
        ):
            resp = auth_api_client.post(
                self.url,
                {
                    "full_name": "Reader One",
                    "address_line_1": "Nope",
                    "city": "Nowhere",
                    "state": "CO",
                    "zip_code": "80202",
                },
            )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["code"] == "address_verification_failed"


@pytest.mark.django_db
class TestLogoutView:
    url = "/api/v1/auth/logout/"
    refresh_url = "/api/v1/auth/token/refresh/"

    def test_logout_blacklists_refresh_token(self, auth_api_client, verified_user):
        refresh = RefreshToken.for_user(verified_user)

        resp = auth_api_client.post(self.url, {"refresh": str(refresh)})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["detail"] == "Logged out."
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()

    def test_logout_without_refresh_token_still_succeeds(self, auth_api_client):
        resp = auth_api_client.post(self.url, {})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["detail"] == "Logged out."

    def test_logout_with_already_blacklisted_refresh_token_still_succeeds(
        self, auth_api_client, verified_user
    ):
        refresh = RefreshToken.for_user(verified_user)
        refresh.blacklist()

        resp = auth_api_client.post(self.url, {"refresh": str(refresh)})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["detail"] == "Logged out."
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).count() == 1

    def test_logged_out_refresh_token_cannot_be_used_to_mint_new_access_token(
        self, auth_api_client, api_client, verified_user
    ):
        refresh = RefreshToken.for_user(verified_user)

        logout_resp = auth_api_client.post(self.url, {"refresh": str(refresh)})
        refresh_resp = api_client.post(self.refresh_url, {"refresh": str(refresh)})

        assert logout_resp.status_code == status.HTTP_200_OK
        assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserExportView:
    url = "/api/v1/users/me/export/"

    def test_export_structure_snapshot_like(self, auth_api_client, verified_user):
        verified_user.full_name = "Reader Example"
        verified_user.address_line_1 = "123 Main St"
        verified_user.city = "Denver"
        verified_user.state = "CO"
        verified_user.zip_code = "80202"
        verified_user.save(
            update_fields=[
                "full_name",
                "address_line_1",
                "city",
                "state",
                "zip_code",
            ]
        )

        book = BookFactory(isbn_13="9780141187761", title="1984")
        UserBookFactory(user=verified_user, book=book, condition="good")
        WishlistItemFactory(user=verified_user, book=book, min_condition="acceptable")

        other_user = UserFactory()
        outgoing_trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=uuid.uuid4(),
            status=Trade.Status.COMPLETED,
        )
        incoming_trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=uuid.uuid4(),
            status=Trade.Status.COMPLETED,
        )
        Rating.objects.create(
            trade=outgoing_trade,
            rater=verified_user,
            rated=other_user,
            score=5,
            comment="Great swap",
            book_condition_accurate=True,
        )
        Rating.objects.create(
            trade=incoming_trade,
            rater=other_user,
            rated=verified_user,
            score=4,
            comment="Arrived as described",
            book_condition_accurate=False,
        )

        resp = auth_api_client.get(self.url)

        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.data.keys()) == {
            "profile",
            "address",
            "books",
            "wishlist",
            "ratings_given",
            "ratings_received",
        }
        assert set(resp.data["profile"].keys()) == {
            "id",
            "email",
            "username",
            "account_type",
            "created_at",
            "total_trades",
            "avg_recent_rating",
        }
        assert set(resp.data["address"].keys()) == {
            "full_name",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "zip_code",
        }
        assert len(resp.data["books"]) == 1
        assert set(resp.data["books"][0].keys()) == {
            "id",
            "isbn_13",
            "title",
            "condition",
            "status",
            "created_at",
        }
        assert len(resp.data["wishlist"]) == 1
        assert set(resp.data["wishlist"][0].keys()) == {
            "id",
            "isbn_13",
            "title",
            "min_condition",
            "is_active",
        }
        assert len(resp.data["ratings_given"]) == 1
        assert set(resp.data["ratings_given"][0].keys()) == {
            "id",
            "trade_id",
            "rated_username",
            "score",
            "comment",
            "created_at",
        }
        assert resp.data["ratings_given"][0]["rated_username"] == other_user.username
        assert resp.data["ratings_given"][0]["score"] == 5
        assert len(resp.data["ratings_received"]) == 1
        assert set(resp.data["ratings_received"][0].keys()) == {
            "id",
            "trade_id",
            "score",
            "comment",
            "book_condition_accurate",
            "created_at",
        }
        assert resp.data["ratings_received"][0]["score"] == 4
        assert resp.data["ratings_received"][0]["book_condition_accurate"] is False


@pytest.mark.django_db
class TestAsyncTaskExceptionHandling:
    """Covers exception branches in RegisterView, PasswordResetRequestView, and UserMeView.delete."""

    register_url = "/api/v1/auth/register/"
    password_reset_url = "/api/v1/auth/password-reset/"
    me_url = "/api/v1/users/me/"

    @patch("django_q.tasks.async_task", side_effect=Exception("queue unavailable"))
    def test_register_still_returns_201_when_async_task_fails(self, _mock, api_client):
        resp = api_client.post(
            self.register_url,
            {
                "email": "qfail@example.com",
                "username": "qfailuser",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "detail" in resp.data

    @patch("django_q.tasks.async_task")
    def test_password_reset_queues_email_for_existing_user(
        self, mock_async_task, api_client, verified_user
    ):
        """Lines 133-137: uid/token are built and async_task is called for a real user."""
        resp = api_client.post(self.password_reset_url, {"email": verified_user.email})
        assert resp.status_code == status.HTTP_200_OK
        mock_async_task.assert_called_once()
        args = mock_async_task.call_args[0]
        assert args[0] == "apps.notifications.tasks.send_password_reset_email"
        assert args[1] == str(verified_user.pk)

    @patch("django_q.tasks.async_task", side_effect=Exception("queue unavailable"))
    def test_delete_still_returns_200_when_async_task_fails(
        self, _mock, api_client, verified_user
    ):
        client = api_client
        client.force_authenticate(user=verified_user)
        resp = client.delete(self.me_url, {"password": "testpass123"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert "Account deletion initiated" in resp.data["detail"]
        verified_user.refresh_from_db()
        assert verified_user.deletion_requested_at is not None


@pytest.mark.django_db
class TestUserPublicEndpoints:
    """Covers UserRatingsView, UserOfferedBooksView, and UserWantedBooksView."""

    def test_ratings_404_for_unknown_user(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/users/{uuid.uuid4()}/ratings/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_ratings_200_with_list_for_known_user(self, api_client, db):
        import uuid

        from apps.ratings.models import Rating
        from apps.trading.models import Trade

        user = UserFactory(email_verified=True)
        other = UserFactory(email_verified=True)
        trade = Trade.objects.create(
            source_type=Trade.SourceType.PROPOSAL,
            source_id=uuid.uuid4(),
            status=Trade.Status.COMPLETED,
        )
        Rating.objects.create(
            trade=trade,
            rater=other,
            rated=user,
            score=5,
            comment="Great!",
            book_condition_accurate=True,
        )

        resp = api_client.get(f"/api/v1/users/{user.id}/ratings/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    def test_offered_books_404_for_unknown_user(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/users/{uuid.uuid4()}/offered/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_offered_books_200_with_list_for_known_user(self, api_client, db):
        user = UserFactory(email_verified=True)
        book = BookFactory()
        UserBookFactory(user=user, book=book)

        resp = api_client.get(f"/api/v1/users/{user.id}/offered/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    def test_wanted_books_404_for_unknown_user(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/users/{uuid.uuid4()}/wanted/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_wanted_books_200_with_list_for_known_user(self, api_client, db):
        user = UserFactory(email_verified=True)
        book = BookFactory()
        WishlistItemFactory(user=user, book=book, is_active=True)

        resp = api_client.get(f"/api/v1/users/{user.id}/wanted/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1


@pytest.mark.django_db
class TestInstitutionEndpoints:
    """Covers InstitutionListView, InstitutionDetailView, and InstitutionWantedView."""

    list_url = "/api/v1/institutions/"

    def _make_institution(self, account_type=None):
        from apps.accounts.models import User

        kwargs = {
            "account_type": account_type or User.AccountType.LIBRARY,
            "institution_name": "City Public Library",
            "is_verified": True,
            "email_verified": True,
        }
        return UserFactory(**kwargs)

    def test_institution_list_filtered_by_search(self, api_client, db):
        inst = self._make_institution()
        # A second institution that should NOT match
        UserFactory(
            account_type="library",
            institution_name="Other Place",
            is_verified=True,
            email_verified=True,
        )

        resp = api_client.get(self.list_url, {"search": "City"})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        ids = [item["id"] for item in results]
        assert str(inst.id) in ids
        # The other one should not appear
        for item in results:
            assert "Other" not in (item.get("institution_name") or "")

    def test_institution_list_filtered_by_institution_type(self, api_client, db):
        from apps.accounts.models import User

        library = self._make_institution(account_type=User.AccountType.LIBRARY)
        bookstore = UserFactory(
            account_type=User.AccountType.BOOKSTORE,
            institution_name="Corner Bookstore",
            is_verified=True,
            email_verified=True,
        )

        resp = api_client.get(self.list_url, {"institution_type": "library"})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        ids = [item["id"] for item in results]
        assert str(library.id) in ids
        assert str(bookstore.id) not in ids

    def test_institution_list_includes_offered_and_wanted_counts(self, api_client, db):
        from apps.inventory.models import UserBook

        inst = self._make_institution()
        other_inst = UserFactory(
            account_type=User.AccountType.BOOKSTORE,
            institution_name="Corner Bookstore",
            is_verified=True,
            email_verified=True,
        )

        book_1 = BookFactory()
        book_2 = BookFactory()
        book_3 = BookFactory()
        book_4 = BookFactory()

        UserBookFactory(user=inst, book=book_1, status=UserBook.Status.AVAILABLE)
        UserBookFactory(user=inst, book=book_2, status=UserBook.Status.RESERVED)
        WishlistItemFactory(user=inst, book=book_3, is_active=True)
        WishlistItemFactory(user=inst, book=book_4, is_active=False)

        UserBookFactory(
            user=other_inst, book=BookFactory(), status=UserBook.Status.AVAILABLE
        )
        WishlistItemFactory(user=other_inst, book=BookFactory(), is_active=True)

        resp = api_client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK

        results = resp.data.get("results", resp.data)
        inst_row = next(item for item in results if item["id"] == str(inst.id))
        other_row = next(item for item in results if item["id"] == str(other_inst.id))

        assert inst_row["offered_count"] == 1
        assert inst_row["wanted_count"] == 1
        assert other_row["offered_count"] == 1
        assert other_row["wanted_count"] == 1

    def test_institution_detail_includes_offered_and_wanted_counts(
        self, api_client, db
    ):
        from apps.inventory.models import UserBook

        inst = self._make_institution()

        UserBookFactory(user=inst, book=BookFactory(), status=UserBook.Status.AVAILABLE)
        UserBookFactory(user=inst, book=BookFactory(), status=UserBook.Status.RESERVED)
        WishlistItemFactory(user=inst, book=BookFactory(), is_active=True)
        WishlistItemFactory(user=inst, book=BookFactory(), is_active=False)

        resp = api_client.get(f"/api/v1/institutions/{inst.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["offered_count"] == 1
        assert resp.data["wanted_count"] == 1

    def test_institution_detail_404_for_unknown_id(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/institutions/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_institution_wanted_404_for_unknown_id(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/institutions/{uuid.uuid4()}/wanted/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_institution_wanted_200_with_items_for_known_institution(
        self, api_client, db
    ):
        inst = self._make_institution()
        book = BookFactory()
        WishlistItemFactory(user=inst, book=book, is_active=True)

        resp = api_client.get(f"/api/v1/institutions/{inst.id}/wanted/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    @patch("django_q.tasks.async_task")
    def test_delete_notifies_counterparties_when_proposals_exist(
        self, _mock, api_client, db
    ):
        """Line 490: bulk_create is called when proposals with counterparties exist."""
        user = UserFactory(email_verified=True)
        other = UserFactory(email_verified=True)

        TradeProposal.objects.create(
            proposer=other,
            recipient=user,
            status=TradeProposal.Status.PENDING,
        )

        client = api_client
        client.force_authenticate(user=user)
        resp = client.delete(
            "/api/v1/users/me/", {"password": "testpass123"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(
            user=other, notification_type="account_deleted_impact"
        ).exists()


@pytest.mark.django_db
class TestUserModelDeleteMethod:
    def test_delete_does_not_propagate_outstanding_token_exception(self, db):
        """User.delete() swallows exceptions from the simplejwt token cleanup."""
        user = UserFactory(email_verified=True)
        with patch(
            "rest_framework_simplejwt.token_blacklist.models.OutstandingToken.objects.filter",
            side_effect=Exception("DB error"),
        ):
            # Should complete without raising
            user.delete()

        from apps.accounts.models import User as UserModel

        assert not UserModel.objects.filter(pk=user.pk).exists()

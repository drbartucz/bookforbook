"""
Tests for the notifications app:
  - Notification model behaviour
  - NotificationListView GET
  - NotificationMarkReadView POST
  - NotificationMarkAllReadView POST
  - send_email helper (mocked mail backend)
  - send_verification_email / send_match_notification_email helpers
  - Tasks: send_verification_email, send_match_notification, send_inactivity_warning_1m,
           send_inactivity_warning_2m, send_books_delisted_notification, check_inactivity
"""

import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.matching.models import Match, MatchLeg
from apps.notifications.models import Notification
from apps.trading.models import TradeProposal
from apps.tests.factories import (
    NotificationFactory,
    TradeFactory,
    TradeShipmentFactory,
    UserBookFactory,
    UserFactory,
)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationModel:
    def test_str_representation(self):
        notif = NotificationFactory(notification_type="new_match", title="Test title")
        assert "new_match" in str(notif)
        assert notif.user.username in str(notif)

    def test_defaults(self):
        notif = NotificationFactory()
        assert notif.is_read is False
        assert notif.read_at is None
        assert notif.metadata == {}

    def test_ordering_newest_first(self):
        user = UserFactory()
        n1 = NotificationFactory(user=user)
        n2 = NotificationFactory(user=user)
        qs = list(Notification.objects.filter(user=user))
        # newest first
        assert qs[0].pk == n2.pk
        assert qs[1].pk == n1.pk


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationListView:
    def test_returns_own_notifications(self):
        user = UserFactory()
        NotificationFactory(user=user, title="Mine")
        NotificationFactory(user=UserFactory(), title="Others")

        resp = auth_client(user).get("/api/v1/notifications/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["title"] == "Mine"

    def test_unauthenticated_gets_401(self):
        resp = APIClient().get("/api/v1/notifications/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_at_most_50(self):
        user = UserFactory()
        NotificationFactory.create_batch(55, user=user)

        resp = auth_client(user).get("/api/v1/notifications/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 55
        assert len(resp.data["results"]) == 20
        assert resp.data["page"] == 1
        assert resp.data["page_size"] == 20

    def test_empty_list_for_user_with_no_notifications(self):
        user = UserFactory()
        resp = auth_client(user).get("/api/v1/notifications/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 0
        assert resp.data["results"] == []

    def test_read_status_included_in_response(self):
        user = UserFactory()
        NotificationFactory(user=user, is_read=True)
        NotificationFactory(user=user, is_read=False)

        resp = auth_client(user).get("/api/v1/notifications/")
        read_flags = {n["is_read"] for n in resp.data["results"]}
        assert read_flags == {True, False}

    def test_supports_page_and_page_size_params(self):
        user = UserFactory()
        NotificationFactory.create_batch(30, user=user)

        resp = auth_client(user).get("/api/v1/notifications/?page=2&page_size=10")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 30
        assert resp.data["page"] == 2
        assert resp.data["page_size"] == 10
        assert len(resp.data["results"]) == 10

    def test_invalid_page_params_rejected(self):
        user = UserFactory()
        resp = auth_client(user).get("/api/v1/notifications/?page=0&page_size=10")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/counts/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationCountsView:
    def test_returns_pending_match_and_proposal_counts(self):
        user = UserFactory()
        other = UserFactory()

        pending_match = Match.objects.create(match_type="direct", status="pending")
        MatchLeg.objects.create(
            match=pending_match,
            sender=user,
            receiver=other,
            user_book=UserBookFactory(user=user),
        )

        proposed_match = Match.objects.create(match_type="direct", status="proposed")
        MatchLeg.objects.create(
            match=proposed_match,
            sender=other,
            receiver=user,
            user_book=UserBookFactory(user=other),
        )

        ignored_match = Match.objects.create(match_type="direct", status="completed")
        MatchLeg.objects.create(
            match=ignored_match,
            sender=user,
            receiver=other,
            user_book=UserBookFactory(user=user),
        )

        TradeProposal.objects.create(recipient=user, proposer=other, status="pending")
        TradeProposal.objects.create(recipient=user, proposer=other, status="accepted")
        TradeProposal.objects.create(recipient=other, proposer=user, status="pending")

        NotificationFactory(user=user, is_read=False)
        NotificationFactory(user=user, is_read=True)

        resp = auth_client(user).get("/api/v1/notifications/counts/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["pending_matches"] == 2
        assert resp.data["pending_proposals"] == 1
        assert resp.data["unread_notifications"] == 1
        assert resp.data["total_pending"] == 3

    def test_unauthenticated_gets_401(self):
        resp = APIClient().get("/api/v1/notifications/counts/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/:id/read/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationMarkReadView:
    def test_marks_unread_notification_as_read(self):
        user = UserFactory()
        notif = NotificationFactory(user=user, is_read=False)

        resp = auth_client(user).post(f"/api/v1/notifications/{notif.pk}/read/")
        assert resp.status_code == status.HTTP_200_OK
        notif.refresh_from_db()
        assert notif.is_read is True
        assert notif.read_at is not None

    def test_idempotent_when_already_read(self):
        user = UserFactory()
        earlier = timezone.now() - timedelta(hours=1)
        notif = NotificationFactory(user=user, is_read=True, read_at=earlier)

        auth_client(user).post(f"/api/v1/notifications/{notif.pk}/read/")
        notif.refresh_from_db()
        # read_at should not have changed
        assert abs((notif.read_at - earlier).total_seconds()) < 1

    def test_cannot_mark_other_users_notification(self):
        owner = UserFactory()
        attacker = UserFactory()
        notif = NotificationFactory(user=owner, is_read=False)

        resp = auth_client(attacker).post(f"/api/v1/notifications/{notif.pk}/read/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        notif.refresh_from_db()
        assert notif.is_read is False

    def test_unauthenticated_gets_401(self):
        notif = NotificationFactory()
        resp = APIClient().post(f"/api/v1/notifications/{notif.pk}/read/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/read-all/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationMarkAllReadView:
    def test_marks_all_unread_as_read(self):
        user = UserFactory()
        NotificationFactory.create_batch(3, user=user, is_read=False)

        resp = auth_client(user).post("/api/v1/notifications/read-all/")
        assert resp.status_code == status.HTTP_200_OK
        assert "3" in resp.data["detail"]
        assert Notification.objects.filter(user=user, is_read=False).count() == 0

    def test_does_not_affect_other_users_notifications(self):
        user = UserFactory()
        other = UserFactory()
        NotificationFactory(user=other, is_read=False)

        auth_client(user).post("/api/v1/notifications/read-all/")

        assert Notification.objects.filter(user=other, is_read=False).count() == 1

    def test_returns_zero_when_nothing_to_mark(self):
        user = UserFactory()
        NotificationFactory(user=user, is_read=True)

        resp = auth_client(user).post("/api/v1/notifications/read-all/")
        assert "0" in resp.data["detail"]

    def test_unauthenticated_gets_401(self):
        resp = APIClient().post("/api/v1/notifications/read-all/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

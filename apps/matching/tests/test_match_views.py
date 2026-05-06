import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, MatchFactory, MatchLegFactory
from apps.matching.models import Match, MatchLeg
from apps.trading.models import Trade

@pytest.mark.django_db
class TestMatchViews:
    def test_match_list(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        # Match as sender
        m1 = MatchFactory()
        MatchLegFactory(match=m1, sender=user, receiver=other)

        # Match as receiver
        m2 = MatchFactory()
        MatchLegFactory(match=m2, sender=other, receiver=user)

        url = reverse('match-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_match_list_status_filter_accepted_shows_completed_matches(self, api_client):
        """Completed matches (both legs accepted) must appear under status=accepted."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        completed_match = MatchFactory(status=Match.Status.COMPLETED)
        MatchLegFactory(match=completed_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)
        MatchLegFactory(match=completed_match, sender=other, receiver=user, status=MatchLeg.Status.ACCEPTED)
        trade = Trade.objects.create(
            source_type=Trade.SourceType.MATCH,
            source_id=completed_match.id,
            status=Trade.Status.CONFIRMED,
        )

        proposed_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=proposed_match, sender=user, receiver=other, status=MatchLeg.Status.PENDING)

        url = reverse('match-list')
        response = api_client.get(url, {'status': 'accepted'})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data}
        assert str(completed_match.id) in returned_ids
        assert str(proposed_match.id) not in returned_ids
        completed_payload = next(item for item in response.data if item['id'] == str(completed_match.id))
        assert completed_payload['trade_id'] == str(trade.id)

    def test_match_list_status_filter_proposed_includes_waiting_for_partner(self, api_client):
        """A match stays in proposed for a user who has already accepted until ALL parties accept."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        proposed_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=proposed_match, sender=user, receiver=other, status=MatchLeg.Status.PENDING)

        # User already accepted their sender leg; match is still PROPOSED waiting for the other party.
        # This must still appear in the proposed tab — not the accepted tab.
        waiting_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=waiting_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)
        MatchLegFactory(match=waiting_match, sender=other, receiver=user, status=MatchLeg.Status.PENDING)

        completed_match = MatchFactory(status=Match.Status.COMPLETED)
        MatchLegFactory(match=completed_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)

        url = reverse('match-list')
        response = api_client.get(url, {'status': 'proposed'})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data}
        assert str(proposed_match.id) in returned_ids
        assert str(waiting_match.id) in returned_ids  # must stay proposed until partner also accepts
        assert str(completed_match.id) not in returned_ids

    def test_match_list_status_filter_accepted_excludes_waiting_for_partner(self, api_client):
        """A match where the user accepted but the partner hasn't must NOT appear under status=accepted."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        # User accepted their leg but the overall match is still PROPOSED (partner hasn't responded).
        waiting_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=waiting_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)
        MatchLegFactory(match=waiting_match, sender=other, receiver=user, status=MatchLeg.Status.PENDING)

        completed_match = MatchFactory(status=Match.Status.COMPLETED)
        MatchLegFactory(match=completed_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)
        MatchLegFactory(match=completed_match, sender=other, receiver=user, status=MatchLeg.Status.ACCEPTED)

        url = reverse('match-list')
        response = api_client.get(url, {'status': 'accepted'})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data}
        assert str(completed_match.id) in returned_ids
        assert str(waiting_match.id) not in returned_ids

    def test_match_list_status_filter_accepted_excludes_expired(self, api_client):
        """EXPIRED matches (partner declined after user accepted) must not appear under status=accepted."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        # User accepted but the match expired because someone else declined.
        expired_match = MatchFactory(status=Match.Status.EXPIRED)
        MatchLegFactory(match=expired_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)
        MatchLegFactory(match=expired_match, sender=other, receiver=user, status=MatchLeg.Status.DECLINED)

        completed_match = MatchFactory(status=Match.Status.COMPLETED)
        MatchLegFactory(match=completed_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)

        url = reverse('match-list')
        response = api_client.get(url, {'status': 'accepted'})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data}
        assert str(completed_match.id) in returned_ids
        assert str(expired_match.id) not in returned_ids

    def test_match_list_no_filter_returns_all(self, api_client):
        """No status filter (All tab) returns matches in any status."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        proposed_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=proposed_match, sender=user, receiver=other)

        completed_match = MatchFactory(status=Match.Status.COMPLETED)
        MatchLegFactory(match=completed_match, sender=user, receiver=other, status=MatchLeg.Status.ACCEPTED)

        url = reverse('match-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data}
        assert str(proposed_match.id) in returned_ids
        assert str(completed_match.id) in returned_ids

    def test_match_detail(self, api_client):
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        match = MatchFactory()
        MatchLegFactory(match=match, sender=user, receiver=other)

        url = reverse('match-detail', kwargs={'pk': match.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(match.id)

    def test_match_detail_not_participant(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)

        match = MatchFactory()
        MatchLegFactory(match=match, sender=UserFactory(), receiver=UserFactory())

        url = reverse('match-detail', kwargs={'pk': match.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.matching.views.user_has_verified_shipping_address", return_value=True)
    @patch("apps.trading.services.trade_workflow.create_trade_from_match")
    def test_match_accept_success(self, mock_create_trade, mock_verify, api_client):
        user_a = UserFactory()
        user_b = UserFactory()

        match = MatchFactory()
        # Direct match: A sends to B, B sends to A
        leg_a = MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        leg_b = MatchLegFactory(match=match, sender=user_b, receiver=user_a)

        url = reverse('match-accept', kwargs={'pk': match.pk})

        # User A accepts
        api_client.force_authenticate(user=user_a)
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        leg_a.refresh_from_db()
        assert leg_a.status == MatchLeg.Status.ACCEPTED

        # User B accepts
        api_client.force_authenticate(user=user_b)
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        match.refresh_from_db()
        assert match.status == Match.Status.COMPLETED
        assert mock_create_trade.called

    def test_match_accept_no_address(self, api_client):
        user = UserFactory(address_verification_status='unverified')
        api_client.force_authenticate(user=user)

        match = MatchFactory()
        MatchLegFactory(match=match, sender=user, receiver=UserFactory())

        url = reverse('match-accept', kwargs={'pk': match.pk})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data['code'] == 'address_verification_required'

    def test_match_decline(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)

        match = MatchFactory(match_type=Match.MatchType.DIRECT)
        leg = MatchLegFactory(match=match, sender=user, receiver=UserFactory())

        url = reverse('match-decline', kwargs={'pk': match.pk})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        leg.refresh_from_db()
        assert leg.status == MatchLeg.Status.DECLINED
        match.refresh_from_db()
        assert match.status == Match.Status.EXPIRED

    @patch("apps.matching.views.transaction.on_commit")
    def test_match_decline_ring_retry(self, mock_on_commit, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)

        match = MatchFactory(match_type=Match.MatchType.RING)
        MatchLegFactory(match=match, sender=user, receiver=UserFactory())

        url = reverse('match-decline', kwargs={'pk': match.pk})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert mock_on_commit.called

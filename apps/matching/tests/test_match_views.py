import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch

from apps.tests.factories import UserFactory, BookFactory, UserBookFactory, MatchFactory, MatchLegFactory
from apps.matching.models import Match, MatchLeg

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

    def test_match_list_includes_proposed_status(self, api_client):
        """Matches created by the matching engine use PROPOSED status.
        The list endpoint must return them so the frontend can display
        Accept/Decline controls.  This is a regression guard for the bug
        where MatchCard only showed buttons for 'pending' status."""
        user = UserFactory()
        other = UserFactory()
        api_client.force_authenticate(user=user)

        proposed_match = MatchFactory(status=Match.Status.PROPOSED)
        MatchLegFactory(match=proposed_match, sender=user, receiver=other)

        url = reverse('match-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['id'] == str(proposed_match.id)
        assert response.data[0]['status'] == 'proposed'

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

    @patch("apps.matching.views.user_has_verified_shipping_address", return_value=True)
    @patch("apps.trading.services.trade_workflow.create_trade_from_match")
    def test_match_accept_proposed_status(self, mock_create_trade, mock_verify, api_client):
        """Accept must work for PROPOSED matches — the status used by the
        matching engine in production (regression guard)."""
        user_a = UserFactory()
        user_b = UserFactory()

        match = MatchFactory(status=Match.Status.PROPOSED)
        leg_a = MatchLegFactory(match=match, sender=user_a, receiver=user_b)
        MatchLegFactory(match=match, sender=user_b, receiver=user_a)

        url = reverse('match-accept', kwargs={'pk': match.pk})
        api_client.force_authenticate(user=user_a)
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        leg_a.refresh_from_db()
        assert leg_a.status == MatchLeg.Status.ACCEPTED

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

    def test_match_decline_proposed_status(self, api_client):
        """Decline must work for PROPOSED matches — the status used by the
        matching engine in production (regression guard)."""
        user = UserFactory()
        api_client.force_authenticate(user=user)

        match = MatchFactory(match_type=Match.MatchType.DIRECT, status=Match.Status.PROPOSED)
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

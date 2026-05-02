import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from apps.tests.factories import UserFactory, RatingFactory
from apps.ratings.services.rolling_average import recompute_rating_average
from apps.ratings.models import Rating

@pytest.mark.django_db
class TestRollingAverage:
    def test_no_ratings(self):
        user = UserFactory()
        recompute_rating_average(user)
        assert user.avg_recent_rating is None
        assert user.rating_count == 0

    def test_single_rating(self):
        user = UserFactory()
        RatingFactory(rated=user, score=4)
        recompute_rating_average(user)
        assert user.avg_recent_rating == Decimal("4.00")
        assert user.rating_count == 1

    def test_more_than_ten_ratings(self):
        user = UserFactory()
        now = timezone.now()
        
        # Create 10 5-star ratings
        r5s = []
        for i in range(10):
            r = RatingFactory(rated=user, score=5)
            r5s.append(r)
        
        # Create 2 1-star ratings
        r1s = []
        for i in range(2):
            r = RatingFactory(rated=user, score=1)
            r1s.append(r)
            
        # Manually set created_at to ensure order
        # r5s are newest
        for i, r in enumerate(r5s):
            Rating.objects.filter(pk=r.pk).update(created_at=now - timedelta(minutes=i))
            
        # r1s are old
        for i, r in enumerate(r1s):
            Rating.objects.filter(pk=r.pk).update(created_at=now - timedelta(days=i+1))
        
        recompute_rating_average(user)
        
        # Only the 10 most recent (all 5s) should be averaged
        assert user.avg_recent_rating == Decimal("5.00")
        assert user.rating_count == 12

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.matching.services.prioritization import condition_priority_value, priority_ordered_wishlist_entries
from apps.inventory.models import WishlistItem, ConditionChoices
from apps.tests.factories import WishlistItemFactory

def test_condition_priority_value():
    assert condition_priority_value("like_new") == 0
    assert condition_priority_value("acceptable") == 3
    assert condition_priority_value("garbage") == 4

@pytest.mark.django_db
class TestPrioritizationService:
    def test_priority_ordered_wishlist_entries(self):
        now = timezone.now()
        
        # 1. Oldest creation (Priority 1)
        w1 = WishlistItemFactory(min_condition=ConditionChoices.GOOD)
        WishlistItem.objects.filter(pk=w1.pk).update(created_at=now - timedelta(days=10))
        
        # 2. Newer creation but stricter condition (Priority 2 vs 3)
        w2 = WishlistItemFactory(min_condition=ConditionChoices.LIKE_NEW)
        WishlistItem.objects.filter(pk=w2.pk).update(created_at=now - timedelta(days=5))
        
        # 3. Same age as w2 but looser condition
        w3 = WishlistItemFactory(min_condition=ConditionChoices.ACCEPTABLE)
        WishlistItem.objects.filter(pk=w3.pk).update(created_at=now - timedelta(days=5))
        
        qs = WishlistItem.objects.all()
        ordered = list(priority_ordered_wishlist_entries(qs))
        
        assert ordered[0] == w1
        assert ordered[1] == w2
        assert ordered[2] == w3

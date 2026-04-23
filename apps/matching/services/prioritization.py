from django.db.models import Case, IntegerField, Value, When


def condition_priority_value(min_condition: str) -> int:
    """Lower value means stricter requirement."""
    order = {
        "like_new": 0,
        "very_good": 1,
        "good": 2,
        "acceptable": 3,
    }
    return order.get(min_condition, 4)


def priority_ordered_wishlist_entries(queryset):
    """
    Order wishlist entries for deterministic scarce-copy allocation.

    Priority policy:
    1) oldest wishlist first (created_at ASC)
    2) stricter minimum condition first
    3) stable tie-break by wishlist id
    """
    condition_rank = Case(
        When(min_condition="like_new", then=Value(0)),
        When(min_condition="very_good", then=Value(1)),
        When(min_condition="good", then=Value(2)),
        When(min_condition="acceptable", then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    return queryset.annotate(_condition_rank=condition_rank).order_by(
        "created_at", "_condition_rank", "id"
    )

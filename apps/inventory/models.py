import uuid

from django.conf import settings
from django.db import models


class ConditionChoices(models.TextChoices):
    LIKE_NEW = 'like_new', 'Like New'
    VERY_GOOD = 'very_good', 'Very Good'
    GOOD = 'good', 'Good'
    ACCEPTABLE = 'acceptable', 'Acceptable'


# Ordering for condition comparison (higher index = better condition)
CONDITION_ORDER = [
    ConditionChoices.ACCEPTABLE,
    ConditionChoices.GOOD,
    ConditionChoices.VERY_GOOD,
    ConditionChoices.LIKE_NEW,
]


def condition_meets_minimum(actual: str, minimum: str) -> bool:
    """Return True if 'actual' condition meets or exceeds 'minimum' condition."""
    try:
        return CONDITION_ORDER.index(actual) >= CONDITION_ORDER.index(minimum)
    except ValueError:
        return False


class UserBook(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        RESERVED = 'reserved', 'Reserved'
        TRADED = 'traded', 'Traded'
        DONATED = 'donated', 'Donated'
        REMOVED = 'removed', 'Removed'
        DELISTED = 'delisted', 'Delisted'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_books',
    )
    book = models.ForeignKey(
        'books.Book',
        on_delete=models.CASCADE,
        related_name='user_listings',
    )
    condition = models.CharField(max_length=20, choices=ConditionChoices.choices)
    condition_notes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Book'
        verbose_name_plural = 'User Books'
        indexes = [
            models.Index(fields=['user', 'book', 'status']),
            models.Index(fields=['book', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.book.title} [{self.condition}] ({self.status})'


class WishlistItem(models.Model):
    class EditionPreference(models.TextChoices):
        EXACT = 'exact', 'Exact edition only'
        SAME_LANGUAGE = 'same_language', 'Same work, same language'
        ANY_LANGUAGE = 'any_language', 'Same work, any language'
        CUSTOM = 'custom', 'Custom rules'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    book = models.ForeignKey(
        'books.Book',
        on_delete=models.CASCADE,
        related_name='wishlist_entries',
    )
    min_condition = models.CharField(
        max_length=20,
        choices=ConditionChoices.choices,
        default=ConditionChoices.ACCEPTABLE,
    )
    edition_preference = models.CharField(
        max_length=20,
        choices=EditionPreference.choices,
        default=EditionPreference.SAME_LANGUAGE,
    )
    allow_translations = models.BooleanField(default=False)
    exclude_abridged = models.BooleanField(default=True)
    format_preferences = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        unique_together = [('user', 'book')]
        indexes = [
            models.Index(fields=['book', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user.username} wants {self.book.title} (min: {self.min_condition})'

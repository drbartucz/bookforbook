import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Match(models.Model):
    class MatchType(models.TextChoices):
        DIRECT = 'direct', 'Direct'
        RING = 'ring', 'Ring'

    class Status(models.TextChoices):
        PROPOSED = 'proposed', 'Proposed'
        EXPIRED = 'expired', 'Expired'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match_type = models.CharField(max_length=10, choices=MatchType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    detected_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'
        indexes = [
            models.Index(fields=['status', 'detected_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.match_type} match [{self.status}] detected at {self.detected_at}'


class MatchLeg(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='legs')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_legs_as_sender',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_legs_as_receiver',
    )
    user_book = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='match_legs',
    )
    position = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = 'Match Leg'
        verbose_name_plural = 'Match Legs'
        indexes = [
            models.Index(fields=['sender', 'status']),
            models.Index(fields=['receiver', 'status']),
        ]

    def __str__(self):
        return (
            f'Leg {self.position}: {self.sender.username} → '
            f'{self.receiver.username} ({self.user_book.book.title}) [{self.status}]'
        )


class DeclinedPairing(models.Model):
    """
    Records a specific book pairing that was explicitly declined so the matcher
    will not recreate the same match on subsequent scans.

    Books are stored in canonical UUID order (smaller pk first) so a single row
    covers both directions and the unique constraint prevents duplicate entries.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_book_a = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='declined_pairings_as_a',
    )
    user_book_b = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='declined_pairings_as_b',
    )
    declined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Declined Pairing'
        verbose_name_plural = 'Declined Pairings'
        constraints = [
            models.UniqueConstraint(
                fields=['user_book_a', 'user_book_b'],
                name='unique_declined_pairing',
            )
        ]
        indexes = [
            models.Index(fields=['user_book_a', 'user_book_b']),
        ]

    @classmethod
    def record_by_ids(cls, id_x, id_y) -> None:
        a_id, b_id = sorted([id_x, id_y], key=str)
        cls.objects.get_or_create(user_book_a_id=a_id, user_book_b_id=b_id)

    def __str__(self):
        return f'DeclinedPairing [{self.user_book_a_id} / {self.user_book_b_id}]'

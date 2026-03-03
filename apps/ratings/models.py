import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trade = models.ForeignKey(
        'trading.Trade',
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_given',
    )
    rated = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_received',
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(null=True, blank=True, max_length=500)
    book_condition_accurate = models.BooleanField(
        help_text='Did the book match its listed condition?'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
        unique_together = [('trade', 'rater')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rater.username} rated {self.rated.username}: {self.score}/5 for trade {self.trade_id}'

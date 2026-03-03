import uuid

from django.conf import settings
from django.db import models


class Donation(models.Model):
    class Status(models.TextChoices):
        OFFERED = 'offered', 'Offered'
        ACCEPTED = 'accepted', 'Accepted'
        SHIPPED = 'shipped', 'Shipped'
        RECEIVED = 'received', 'Received'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations_given',
    )
    institution = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations_received',
    )
    user_book = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='donations',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFERED)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Donation'
        verbose_name_plural = 'Donations'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Donation: {self.donor.username} → {self.institution.institution_name or self.institution.username} '
            f'({self.user_book.book.title}) [{self.status}]'
        )

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class TradeProposal(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        COUNTERED = 'countered', 'Countered'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proposals_sent',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proposals_received',
    )
    origin_match = models.ForeignKey(
        'matching.Match',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Trade Proposal'
        verbose_name_plural = 'Trade Proposals'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=72)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Proposal: {self.proposer.username} → {self.recipient.username} [{self.status}]'


class TradeProposalItem(models.Model):
    class Direction(models.TextChoices):
        PROPOSER_SENDS = 'proposer_sends', 'Proposer Sends'
        RECIPIENT_SENDS = 'recipient_sends', 'Recipient Sends'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        TradeProposal,
        on_delete=models.CASCADE,
        related_name='items',
    )
    direction = models.CharField(max_length=20, choices=Direction.choices)
    user_book = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='proposal_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Trade Proposal Item'
        verbose_name_plural = 'Trade Proposal Items'

    def __str__(self):
        return f'{self.proposal} — {self.direction}: {self.user_book.book.title}'


class Trade(models.Model):
    class SourceType(models.TextChoices):
        MATCH = 'match', 'Match'
        PROPOSAL = 'proposal', 'Proposal'
        DONATION = 'donation', 'Donation'

    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        SHIPPING = 'shipping', 'Shipping'
        ONE_RECEIVED = 'one_received', 'One Received'
        COMPLETED = 'completed', 'Completed'
        AUTO_CLOSED = 'auto_closed', 'Auto Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    auto_close_at = models.DateTimeField(null=True, blank=True)
    rating_reminders_sent = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Trade'
        verbose_name_plural = 'Trades'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.auto_close_at:
            self.auto_close_at = timezone.now() + timedelta(weeks=3)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Trade {self.id} [{self.source_type}] — {self.status}'


class TradeShipment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SHIPPED = 'shipped', 'Shipped'
        RECEIVED = 'received', 'Received'
        NOT_RECEIVED = 'not_received', 'Not Received'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name='shipments')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipments_sent',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipments_received',
    )
    user_book = models.ForeignKey(
        'inventory.UserBook',
        on_delete=models.CASCADE,
        related_name='shipments',
    )
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    shipping_method = models.CharField(max_length=100, null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Trade Shipment'
        verbose_name_plural = 'Trade Shipments'

    def __str__(self):
        return (
            f'Shipment: {self.sender.username} → {self.receiver.username} '
            f'({self.user_book.book.title}) [{self.status}]'
        )

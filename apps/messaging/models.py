import uuid

from django.conf import settings
from django.db import models


class TradeMessage(models.Model):
    class MessageType(models.TextChoices):
        SHIPPING_UPDATE = 'shipping_update', 'Shipping Update'
        QUESTION = 'question', 'Question'
        ISSUE_REPORT = 'issue_report', 'Issue Report'
        GENERAL_NOTE = 'general_note', 'General Note'
        DELAY_NOTICE = 'delay_notice', 'Delay Notice'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trade = models.ForeignKey(
        'trading.Trade',
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trade_messages_sent',
    )
    message_type = models.CharField(max_length=30, choices=MessageType.choices)
    content = models.TextField(max_length=1000)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Trade Message'
        verbose_name_plural = 'Trade Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['trade', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.message_type}] {self.sender.username} in trade {self.trade_id}'

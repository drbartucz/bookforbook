import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0002_remove_match_pending_status"),
        ("inventory", "0002_wishlistitem_edition_preferences"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeclinedPairing",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "user_book_a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="declined_pairings_as_a",
                        to="inventory.userbook",
                    ),
                ),
                (
                    "user_book_b",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="declined_pairings_as_b",
                        to="inventory.userbook",
                    ),
                ),
                ("declined_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Declined Pairing",
                "verbose_name_plural": "Declined Pairings",
            },
        ),
        migrations.AddConstraint(
            model_name="declinedpairing",
            constraint=models.UniqueConstraint(
                fields=["user_book_a", "user_book_b"],
                name="unique_declined_pairing",
            ),
        ),
        migrations.AddIndex(
            model_name="declinedpairing",
            index=models.Index(
                fields=["user_book_a", "user_book_b"],
                name="matching_declinedpairing_books_idx",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="physical_format",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]

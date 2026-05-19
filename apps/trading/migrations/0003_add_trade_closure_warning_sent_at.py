from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0002_trade_trade_unique_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='trade',
            name='closure_warning_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

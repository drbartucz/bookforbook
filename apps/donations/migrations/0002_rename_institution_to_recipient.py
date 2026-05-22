from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('donations', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='Donation',
            old_name='institution',
            new_name='recipient',
        ),
    ]

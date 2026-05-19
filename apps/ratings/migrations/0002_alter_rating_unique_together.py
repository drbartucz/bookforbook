from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ratings', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='rating',
            unique_together={('trade', 'rater', 'rated')},
        ),
    ]

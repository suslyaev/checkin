# Generated migration for composite index on Action(event, action_type)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='action',
            index=models.Index(
                fields=['event', 'action_type'],
                name='event_action_event_type_idx',
            ),
        ),
    ]

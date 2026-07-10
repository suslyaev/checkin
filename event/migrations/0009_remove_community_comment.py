from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0008_community_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='community',
            name='comment',
        ),
    ]

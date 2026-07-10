from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0009_remove_community_comment'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactDuplicateConflict',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match_reason', models.CharField(blank=True, max_length=255, verbose_name='Причина совпадения')),
                ('status', models.CharField(choices=[('unprocessed', 'Не обработан'), ('duplicate', 'Дубль'), ('not_duplicate', 'Не дубль')], db_index=True, default='unprocessed', max_length=20, verbose_name='Статус')),
                ('create_date', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('update_date', models.DateTimeField(auto_now=True, verbose_name='Дата изменения')),
                ('contact_a', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='duplicate_as_a', to='event.contact', verbose_name='Контакт A')),
                ('contact_b', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='duplicate_as_b', to='event.contact', verbose_name='Контакт B')),
            ],
            options={
                'verbose_name': 'Возможный дубль',
                'verbose_name_plural': 'Возможные дубли',
                'ordering': ['-create_date'],
            },
        ),
        migrations.AddConstraint(
            model_name='contactduplicateconflict',
            constraint=models.UniqueConstraint(fields=('contact_a', 'contact_b'), name='unique_duplicate_conflict_pair'),
        ),
    ]

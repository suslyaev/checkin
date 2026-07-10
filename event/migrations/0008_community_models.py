from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0007_alter_actionlog_new_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Community',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Наименование сообщества')),
                ('comment', models.CharField(blank=True, max_length=255, null=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Сообщество',
                'verbose_name_plural': 'Сообщества',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CommunityMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('community', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event.community', verbose_name='Сообщество')),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event.contact', verbose_name='Человек')),
            ],
            options={
                'verbose_name': 'Участник сообщества',
                'verbose_name_plural': 'Участники сообществ',
            },
        ),
        migrations.AddField(
            model_name='infocontact',
            name='community',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.community', verbose_name='Сообщество'),
        ),
        migrations.AlterField(
            model_name='infocontact',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.contact', verbose_name='Человек'),
        ),
        migrations.AddConstraint(
            model_name='communitymember',
            constraint=models.UniqueConstraint(fields=('community', 'contact'), name='unique_community_member'),
        ),
    ]


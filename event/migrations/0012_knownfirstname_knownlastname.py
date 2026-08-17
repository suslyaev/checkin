from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event', '0011_alter_community_options_alter_infocontact_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnownFirstName',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Имя')),
                ('comment', models.CharField(blank=True, max_length=100, null=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Известное имя',
                'verbose_name_plural': 'Известные имена',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='KnownLastName',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Фамилия')),
                ('comment', models.CharField(blank=True, max_length=100, null=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Известная фамилия',
                'verbose_name_plural': 'Известные фамилии',
                'ordering': ['name'],
            },
        ),
    ]

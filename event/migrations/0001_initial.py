# Generated by Django 5.1.4 on 2024-12-20 14:07

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_date', models.DateTimeField(auto_now=True, null=True, verbose_name='Дата и время действия')),
                ('is_last_state', models.BooleanField(default=True, verbose_name='Текущее состояние')),
            ],
            options={
                'verbose_name': 'Действие',
                'verbose_name_plural': 'Действия',
            },
        ),
        migrations.CreateModel(
            name='ActionType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Наименование типа')),
                ('comment', models.CharField(blank=True, max_length=100, null=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Тип действия',
                'verbose_name_plural': 'Типы действий',
            },
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_name', models.CharField(max_length=100, verbose_name='Фамилия')),
                ('first_name', models.CharField(max_length=100, verbose_name='Имя')),
                ('middle_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Отчество')),
                ('sex', models.CharField(blank=True, choices=[('male', 'Муж'), ('female', 'Жен')], max_length=100, null=True, verbose_name='Пол')),
                ('date_of_birth', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, unique=True, verbose_name='Email')),
                ('phone', models.CharField(blank=True, max_length=16, null=True, unique=True, validators=[django.core.validators.RegexValidator(regex='^\\+?1?\\d{8,15}$')], verbose_name='Телефон')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Комментарий')),
                ('validated', models.BooleanField(default=False, verbose_name='Данные проверены')),
                ('create_date', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Создано')),
                ('update_date', models.DateTimeField(auto_now=True, null=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Человек',
                'verbose_name_plural': 'Люди',
                'ordering': ['last_name'],
            },
        ),
        migrations.CreateModel(
            name='EventType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Наименование события')),
                ('comment', models.CharField(blank=True, max_length=100, null=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Тип события',
                'verbose_name_plural': 'Типы событий',
            },
        ),
        migrations.CreateModel(
            name='Checkin',
            fields=[
            ],
            options={
                'verbose_name': 'Регистрация',
                'verbose_name_plural': 'Подтвердить посещение',
                'ordering': ['pk'],
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('event.action',),
        ),
        migrations.AddField(
            model_name='action',
            name='action_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.actiontype', verbose_name='Тип действия'),
        ),
        migrations.AddField(
            model_name='action',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.contact', verbose_name='Контакт'),
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Наименование мероприятия')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Описание мероприятия')),
                ('event_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.eventtype', verbose_name='Тип события')),
            ],
            options={
                'verbose_name': 'Мероприятие',
                'verbose_name_plural': 'Мероприятия',
            },
        ),
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Наименование модуля')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Описание модуля')),
                ('event', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.event', verbose_name='Родительское мероприятие')),
            ],
            options={
                'verbose_name': 'Модуль',
                'verbose_name_plural': 'Модули',
            },
        ),
        migrations.CreateModel(
            name='ModuleInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_start', models.DateTimeField(blank=True, null=True, verbose_name='Дата и время начала')),
                ('date_end', models.DateTimeField(blank=True, null=True, verbose_name='Дата и время окончания')),
                ('visible', models.BooleanField(default=False, verbose_name='Отображать для регистрации')),
                ('is_notify', models.BooleanField(default=False, verbose_name='Отправлять оповещение')),
                ('module', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.module', verbose_name='Родительский модуль')),
            ],
            options={
                'verbose_name': 'Событие',
                'verbose_name_plural': 'События',
            },
        ),
        migrations.AddField(
            model_name='action',
            name='module_instance',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='event.moduleinstance', verbose_name='Событие'),
        ),
    ]

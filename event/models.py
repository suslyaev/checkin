from django.db import models
from django.contrib.auth.models import User
import event.services as service
from django import forms
from django.urls import reverse
from django.utils.html import format_html
from PIL import Image


# Кастомная модель пользователей
class CustomUser(User):
    class Meta:
        proxy = True
        ordering = ['last_name', 'first_name']  # Сортировка по фамилии и имени

    def __str__(self):
        # Отображение имени, фамилии или логина, если имя и фамилия пустые
        if self.first_name and self.last_name:
            return f"{self.last_name} {self.first_name}"
        return self.username


# Базовый класс с параметрами по умолчанию
class BaseModelClass(models.Model):
    def __str__(self):
        return f'{self.name}'

    class Meta:
        abstract = True
        ordering = ['name']


# Компания
class Company(BaseModelClass):
    name = models.CharField(max_length=100, verbose_name='Наименование компании')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'


# Категория
class CategoryContact(BaseModelClass):
    name = models.CharField(max_length=100, verbose_name='Наименование категории')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)
    color = models.CharField(max_length=7, verbose_name='Цвет')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


# Человек
class Contact(models.Model):
    fio = models.CharField(max_length=300, verbose_name='ФИО')
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Компания')
    category = models.ForeignKey('CategoryContact', on_delete=models.SET_NULL, blank=True, null=True,
                                 verbose_name='Категория')
    comment = models.TextField(verbose_name='Комментарий', blank=True, null=True)
    photo = models.ImageField(upload_to='contacts/photos/', blank=True, null=True, verbose_name='Фото сотрудника')

    def __str__(self):
        return f'{self.fio}'

    def photo_link(self):
        if self.photo:
            return self.photo.url
        return "-"

    def photo_preview(self):
        """
        Возвращает HTML для отображения фото в админке.
        """
        if self.photo:
            return format_html('<img src="{}" style="width: 100px; height: auto; border-radius: 5px;" />',
                               self.photo.url)
        return "Нет фото"

    photo_preview.short_description = 'Фото'

    def link_contact(self):
        mess = 'Перейти к записи'
        url = reverse('admin:event_contact_change', args=(self.pk,))
        return format_html('<a href="{}">{}</a>', url, mess)

    link_contact.short_description = 'Ссылка на контакт'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.photo:
            img = Image.open(self.photo.path)

            # Ограничиваем максимальный размер изображения
            max_size = (300, 300)  # ширина x высота
            img.thumbnail(max_size)

            # Сохраняем уменьшенное изображение
            img.save(self.photo.path)

    class Meta:
        verbose_name = 'Человек'
        verbose_name_plural = 'Люди'
        ordering = ['fio']


# Мероприятие
class ModuleInstance(models.Model):
    name = models.CharField(max_length=100, verbose_name='Наименование cобытия')
    address = models.TextField(verbose_name='Адрес проведения', blank=True, null=True)
    date_start = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время начала')
    date_end = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время окончания')

    admins = models.ManyToManyField(
        CustomUser,
        related_name='admin_events',
        verbose_name='Администраторы',
        blank=True
    )
    checkers = models.ManyToManyField(
        CustomUser,
        related_name='checker_events',
        verbose_name='Проверяющие',
        blank=True
    )

    def link_module_instance(self):
        mess = 'Перейти к мероприятию'
        url = reverse('admin:event_moduleinstance_change', args=(self.pk,))
        return format_html('<a href="{}">{}</a>', url, mess)

    link_module_instance.short_description = 'Ссылка на мероприятие'

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'


# Действие
class Action(models.Model):
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, null=True, verbose_name='Контакт')
    module_instance = models.ForeignKey('ModuleInstance', on_delete=models.CASCADE, null=True, verbose_name='Мероприятие')
    action_type = models.CharField(max_length=100, choices=(('new', 'Регистрация'), ('checkin', 'Чекин'), ('cancel', 'Отмена')),  verbose_name='Тип действия', default='new')
    action_date = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name='Дата и время действия')
    is_last_state = models.BooleanField(default=True, verbose_name='Текущее состояние')

    def __str__(self):
        return service.get_name_action(self.action_type, self.contact, self.module_instance, self.action_date)

    def clean(self):
        if self.id is None:
            check_action = service.check_create_action(self)
            if check_action['error']:
                raise forms.ValidationError(check_action['error_message'])
        if self.contact is None or self.module_instance is None:
            raise forms.ValidationError('Заполните обязательные поля')

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        if self.contact is None or self.module_instance is None:
            raise forms.ValidationError('Заполните обязательные поля')
        check_action = service.check_create_action(self)
        if check_action['error']:
            raise forms.ValidationError(check_action['error_message'])
        else:
            service.do_after_add_action(self)
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Действие'
        verbose_name_plural = 'Все действия'


# Прокси модель для чекина на события
class Checkin(Action):

    def __str__(self):
        return f'Регистрация {self.contact}'

    def photo_contact(self):
        if self.contact.photo:
            return format_html('<img src="{}" style="width: 100px; height: auto; border-radius: 5px;" />',
                               self.contact.photo.url)
        return "Нет фото"

    photo_contact.short_description = 'Фото'

    class Meta:
        proxy = True
        verbose_name = 'Регистрация'
        verbose_name_plural = 'Регистрации на мероприятия'
        ordering = ['pk']

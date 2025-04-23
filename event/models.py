import uuid
from django.db import models
from colorfield.fields import ColorField
from django.utils import timezone
from django.core.exceptions import ValidationError
from django import forms
from django.urls import reverse
from django.utils.html import format_html
from PIL import Image

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


PHONE_PATTERNS = {
    "ru": ("+7", 10),
    "uk": ("+44", 10),
}

class CustomUserManager(BaseUserManager):
    """
    Менеджер пользователей, использующий телефон как логин (USERNAME_FIELD).
    """
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Телефон обязателен для создания пользователя")
        phone = str(phone).strip()
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя с логином по телефону.
    """
    phone = models.CharField(max_length=20, unique=True, verbose_name='Телефон')
    first_name = models.CharField(max_length=150, blank=True, null=True, verbose_name='Имя')
    last_name = models.CharField(max_length=150, blank=True, null=True, verbose_name='Фамилия')

    ext_id = models.CharField(max_length=150, blank=True, null=True, verbose_name='Внешний ID')
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    auth_token = models.UUIDField(blank=True, null=True, unique=True)

    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []  # Если хотите, можно добавить first_name/last_name

    def generate_auth_token(self):
        self.auth_token = uuid.uuid4()
        self.save(update_fields=['auth_token'])
        return self.auth_token
    
    def get_short_name(self):
        if self.first_name:
            return f"{self.first_name or ''}".strip()
        return self.phone
    
    def clean(self):
        """
        Проверяет корректность номера перед сохранением.
        """
        super().clean()  # Вызываем стандартную валидацию модели

        phone = self.phone.strip()
        for code, length in PHONE_PATTERNS.values():
            if phone.startswith(code) and len(phone) == len(code) + length:
                return  # Валидация прошла

        raise ValidationError(f"Некорректный номер телефона: {phone}. Доступные форматы: " +
                              ", ".join(f"{code}X...X ({length} цифр)" for code, length in PHONE_PATTERNS.values()))

    class Meta:
        verbose_name = 'Пользователя'
        verbose_name_plural = 'Пользователи'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        if self.last_name or self.first_name:
            return f"{self.last_name or ''} {self.first_name or ''}".strip()
        return self.phone


class ManagerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "Менеджера"
        verbose_name_plural = "Менеджеры"

class ProducerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "Продюсера"
        verbose_name_plural = "Продюсеры"

class CheckerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "Модератора"
        verbose_name_plural = "Модераторы"

# Базовый класс с параметрами по умолчанию
class BaseModelClass(models.Model):
    def __str__(self):
        return f'{self.name}'
    class Meta:
        abstract = True
        ordering = ['name']

# Компания
class CompanyContact(BaseModelClass):
    name = models.CharField(max_length=100, unique=True, verbose_name='Наименование компании')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)

    class Meta:
        verbose_name = 'Компанию'
        verbose_name_plural = 'Компании'

# Категория
class CategoryContact(BaseModelClass):
    name = models.CharField(max_length=100, unique=True, verbose_name='Наименование категории')
    color = ColorField(default='#FFFFFF', verbose_name='Цвет категории')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)

    class Meta:
        verbose_name = 'Категорию'
        verbose_name_plural = 'Категории'

# Тип гостя
class TypeGuestContact(BaseModelClass):
    name = models.CharField(max_length=100, unique=True, verbose_name='Наименование типа')
    color = ColorField(default='#FFFFFF', verbose_name='Цвет типа')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)

    class Meta:
        verbose_name = 'Тип гостя'
        verbose_name_plural = 'Типы гостя'

# Человек
class Contact(models.Model):
    last_name = models.CharField(max_length=300, verbose_name='Фамилия')
    first_name = models.CharField(max_length=300, verbose_name='Имя')
    middle_name = models.CharField(max_length=300, blank=True, null=True, verbose_name='Отчество')
    nickname = models.CharField(max_length=300, blank=True, null=True, verbose_name='Никнейм')
    company = models.ForeignKey('CompanyContact', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Компания')
    category = models.ForeignKey('CategoryContact', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Категория')
    type_guest = models.ForeignKey('TypeGuestContact', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Тип гостя')
    producer = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Продюсер')
    comment = models.TextField(verbose_name='Комментарий', blank=True, null=True)
    photo = models.ImageField(upload_to='contacts/photos/', blank=True, null=True, verbose_name='Фото сотрудника')

    def __str__(self):
        return self.get_fio()
    
    def get_fio(self):
        return f'{self.last_name} {self.first_name}'
    get_fio.short_description = 'ФИО'
    
    def photo_link(self):
        if self.photo:
            return self.photo.url
        return "-"
    
    def photo_preview(self):
        """
        Возвращает HTML для отображения фото в админке.
        """
        if self.photo:
            return format_html('<img src="{}" style="width: 100px; height: auto; border-radius: 5px;" />', self.photo.url)
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
        verbose_name = 'Человека'
        verbose_name_plural = 'Люди'
        ordering = ['last_name', 'first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['last_name', 'first_name', 'middle_name'],
                name='unique_contact',
                violation_error_message="Человек с указанными ФИО уже существует в системе."
            )
        ]

# Мероприятие
class ModuleInstance(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Наименование cобытия')
    address = models.TextField(verbose_name='Адрес проведения', blank=True, null=True)
    date_start = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время начала')
    date_end = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время окончания')
    is_visible = models.BooleanField(default=False, verbose_name='Отображать')

    managers = models.ManyToManyField(
        CustomUser,
        related_name='manager_events',
        verbose_name='Менеджеры',
        blank=True
    )
    producers = models.ManyToManyField(
        CustomUser,
        related_name='producer_events',
        verbose_name='Продюсеры',
        blank=True
    )
    checkers = models.ManyToManyField(
        CustomUser,
        related_name='checker_events',
        verbose_name='Модераторы',
        blank=True
    )
    
    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'

# Действие
class Action(models.Model):
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, null=True, verbose_name='Контакт', db_index=True)
    event = models.ForeignKey('ModuleInstance', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Мероприятие', db_index=True)
    action_type = models.CharField(max_length=100, choices=(('new', 'Регистрация'), ('checkin', 'Чекин')),  verbose_name='Тип действия', default='new', db_index=True)
    create_date = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='Дата создания записи')
    update_date = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='Дата изменения записи')
    create_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='create_user', verbose_name='Кто создал')
    update_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='update_user', verbose_name='Кто обновил')

    def __str__(self):
        return f"{self.contact} -> {self.event} ({self.action_type})"
    
    def photo_contact(self):
        if self.contact and self.contact.photo:
            return format_html('<img src="{}" style="width: 100px; height: auto; border-radius: 5px;" />', self.contact.photo.url)
        return "Нет фото"
    photo_contact.short_description = 'Фото'

    def get_category_contact(self):
        if self.contact is not None:
            return self.contact.category
        return None
    get_category_contact.short_description = 'Категория'

    def get_type_guest_contact(self):
        if self.contact is not None:
            return self.contact.type_guest
        return None
    get_type_guest_contact.short_description = 'Статус'
    
    class Meta:
        verbose_name = 'Действие'
        verbose_name_plural = 'Все действия'
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'event'],
                name='unique_reg_contact_to_event',
                violation_error_message="Человек уже зарегистрирован на данное мероприятие."
            )
        ]

# Социальные сети
class SocialNetwork(BaseModelClass):
    name = models.CharField(max_length=100, unique=True, verbose_name='Наименование соцсети')
    comment = models.CharField(max_length=100, verbose_name='Описание', blank=True, null=True)
    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Социальную сеть'
        verbose_name_plural = 'Социальные сети'

# Контакт человека
class InfoContact(models.Model):
    contact = models.ForeignKey('Contact', on_delete=models.SET_NULL, null=True, verbose_name='Человек', db_index=True)
    social_network = models.ForeignKey('SocialNetwork', on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Социальная сеть', db_index=True)
    external_id = models.CharField(max_length=255, verbose_name='Имя или айди')
    subscribers = models.IntegerField(blank=True, null=True, verbose_name='Подписчики')

    def __str__(self):
        return f"{self.contact} - {self.social_network.name} ({self.external_id})"

    class Meta:
        verbose_name = 'Контакт человека'
        verbose_name_plural = 'Контакты человека'

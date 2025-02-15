from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
import event.services as service
from .models import CustomUser, Company, CategoryContact, Contact, ModuleInstance, Action, Checkin
from .forms import ActionForm, CheckinOrCancelForm, ModuleInstanceForm
from django.shortcuts import render
from django.http import HttpResponseRedirect
from import_export.admin import ExportActionModelAdmin, ImportExportActionModelAdmin
from .resources import CheckinResource
from admin_auto_filters.filters import AutocompleteFilter
from django.utils.html import format_html
from django.urls import reverse
from django import forms
from django.http import FileResponse
import os
from django.forms import Textarea
from django.db import models

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import path
from django.urls import reverse

# В админке можно использовать форму изменения пароля для стандартной модели User
class CustomUserPasswordChangeForm(PasswordChangeForm):
    class Meta:
        model = get_user_model()
        fields = ['password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['new_password1'])
        if commit:
            user.save()
        return user


class CustomUserForm(UserCreationForm):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, widget=forms.Select, label="Роль")

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'group']

class CustomUserChangeForm(UserChangeForm):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, widget=forms.Select, label="Роль")

    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput,
        required=False  # НЕобязательно
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
        required=False  # НЕобязательно
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'group']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Устанавливаем текущую группу как значение по умолчанию
            self.fields['group'].initial = self.instance.groups.first() if self.instance.groups.exists() else None
    
    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')

        # Если оба поля пустые, пропускаем
        if not p1 and not p2:
            return cleaned_data

        # Иначе, если заполнили хотя бы одно, проверяем совпадение
        if p1 != p2:
            self.add_error('new_password2', "Пароли не совпадают!")
        return cleaned_data


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    app_label = 'event'
    form = CustomUserChangeForm
    add_form = CustomUserForm
    search_fields = ['username', 'last_name', 'first_name']  # Поля для поиска
    list_display = ['username', 'last_name', 'first_name', 'get_group']  # Для отображения в списке
    list_filter = ('groups',)
    readonly_fields = ['date_joined', 'last_login', 'get_group']

    def get_form(self, request, obj=None, **kwargs):
        if obj:  # Если это редактирование существующего пользователя
            self.form = CustomUserChangeForm
        else:  # Если это создание нового пользователя
            self.form = CustomUserForm
        return super().get_form(request, obj, **kwargs)
    
    def get_queryset(self, request):
        # Получаем базовый queryset
        queryset = super().get_queryset(request)

        #if request.user.groups.filter(name='Менеджер').exists():
        #    qs = qs.filter(checkers=request.user)
        
        # Исключаем пользователей с is_superuser=True
        return queryset.exclude(is_superuser=True)

    def get_fields(self, request, obj=None):
        
        if obj:  # Редактирование записи
            return [
                ('username', ),
                ('first_name', 'last_name'),
                ('group',),
                ('date_joined', 'last_login'),
                ('new_password1', 'new_password2'),
            ]
        else:  # Создание новой записи
            return [
                ('username',),
                ('password1', 'password2'),
                ('first_name', 'last_name'),
                ('group',),
                ('date_joined', 'last_login'),
            ]

    def get_group(self, obj):
        # Если у пользователя есть группа, показываем её
        return obj.groups.first().name if obj.groups.exists() else None
    get_group.short_description = 'Роль'



    def save_model(self, request, obj, form, change):

        # Если пользователь ввёл новый пароль
        p1 = form.cleaned_data.get('new_password1')
        p2 = form.cleaned_data.get('new_password2')
        if p1 and p1 == p2:
            obj.set_password(p1)
        
        if not obj.pk:
            obj.is_staff = True
            obj.is_active = True
            obj.save()
        
        group = form.cleaned_data['group']
        obj.groups.set([group])
        super().save_model(request, obj, form, change)

# Базовый класс с параметрами по умолчанию
class BaseAdminPage(admin.ModelAdmin):
    list_per_page = 25
    view_on_site = False

# Фильтр с автозаполнением для module_instance
class ModuleInstanceFilter(AutocompleteFilter):
    title = 'Мероприятие'  # Название фильтра
    field_name = 'module_instance'  # Поле модели, по которому будет фильтрация

class CompanyFilter(AutocompleteFilter):
    title = 'Компания'
    field_name = 'company'

class CategoryContactFilter(AutocompleteFilter):
    title = 'Категория'
    field_name = 'category'

# Инлайн регистраций для страницы событий
class RegistrationInline(admin.TabularInline):
    model = Action
    fields = ['contact', 'action_type', 'action_date']
    readonly_fields = ['contact', 'action_type', 'action_date']
    extra = 0
    ordering = ('-action_date',)

    verbose_name = "Регистрация"
    verbose_name_plural = "Зарегистрировавшиеся"

    def has_add_permission(self, request, obj=None, **kwargs):
        return False

    # Выборка регистраций
    def get_queryset(self, request):
        return Action.objects.filter(is_last_state=True, action_type='new')

# Инлайн посетителей для страницы событий
class CheckinInline(admin.TabularInline):
    model = Action
    fields = ['contact', 'action_type', 'action_date']
    readonly_fields = ['contact', 'action_type', 'action_date']
    extra = 0
    ordering = ('-action_date',)

    verbose_name = "Чекин"
    verbose_name_plural = "Посетившие событие"

    def has_add_permission(self, request, obj=None, **kwargs):
        return False

    # Выборка чекинов
    def get_queryset(self, request):
        return Action.objects.filter(is_last_state=True, action_type='checkin')

# Инлайн отмененных регистраций для страницы событий
class CancelInline(admin.TabularInline):
    model = Action
    fields = ['contact', 'action_type', 'action_date']
    readonly_fields = ['contact', 'action_type', 'action_date']
    extra = 0
    ordering = ('-action_date',)

    verbose_name = "Отмена регистрации"
    verbose_name_plural = "Отменившие регистрацию"

    def has_add_permission(self, request, obj=None, **kwargs):
        return False

    # Выборка отмененных регистраций
    def get_queryset(self, request):
        return Action.objects.filter(is_last_state=True, action_type='cancel')

# Человек
@admin.register(Contact)
class ContactAdmin(BaseAdminPage, ExportActionModelAdmin):
    list_display = ('fio', 'company', 'category', 'photo_preview', 'comment')
    list_filter = (CompanyFilter, CategoryContactFilter,)
    readonly_fields = ('photo_preview',)
    autocomplete_fields = ['company', 'category',]
    search_fields = ['fio']
    fieldsets = (
        (None, {
            'fields': [('fio',)]
        }),
        (None, {
            'fields': [('company', 'category')]
        }),
        ('Фото', {
            'fields': ['photo', 'photo_preview'],
        }),
        (None, {
            'fields': [('comment',)]
        }),
    )

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={
            'rows': 2,
            'cols': 60,
            'style': 'width: 400px;'
        })},
    }

# Компания
@admin.register(Company)
class CompanyAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment')
    list_editable = ('name', 'comment')
    search_fields = ['name']

# Категория
@admin.register(CategoryContact)
class CategoryContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'color', 'comment')
    list_editable = ('name', 'color', 'comment')
    search_fields = ['name']

# Событие
@admin.register(ModuleInstance)
class ModuleInstanceAdmin(ExportActionModelAdmin):
    form = ModuleInstanceForm
    search_fields = ['get_name_module_instance']
    fieldsets = (
        (None, {
            'fields': [('name', 'address',)]
        }),
        ('Когда', {
            'fields': [('date_start', 'date_end')]
        }),
        ('Администрирование', {
            'fields': [('managers', 'checkers')]
        }),
    )
    autocomplete_fields = ['managers', 'checkers',]
    list_display = ('name', 'date_start', 'date_end')
    inlines = [RegistrationInline, CheckinInline, CancelInline]
    save_on_top = True
    list_per_page = 25
    view_on_site = False

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={
            'rows': 2,
            'cols': 60,
            'style': 'width: 400px;'
        })},
    }

    def get_form(self, request, obj=None, **kwargs):
        # Прописываем нашу форму
        kwargs['form'] = self.form
        form_class = super().get_form(request, obj, **kwargs)

        # Оборачиваем, чтобы передать request в форму
        class FormWithRequest(form_class):
            def __init__(self2, *args, **inner_kwargs):
                inner_kwargs['request'] = request
                super().__init__(*args, **inner_kwargs)

        return FormWithRequest

    # Исключаем суперпользователей
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in ['managers', ]:
            # Исключаем суперпользователей
            kwargs['queryset'] = CustomUser.objects.filter(is_superuser=False, groups__name='Менеджер')
        if db_field.name in ['checkers', ]:
            # Исключаем суперпользователей
            kwargs['queryset'] = CustomUser.objects.filter(is_superuser=False, groups__name='Проверяющий')
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    
    # Ограничение ролевой модели
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Если пользователь — суперюзер или админ, видит все
        if request.user.is_superuser:
            return qs
        
        # Если пользователь в группе "Проверяющий" — видит только те,
        # где он указан в массиве checkers
        if request.user.groups.filter(name='Проверяющий').exists():
            qs = qs.filter(checkers=request.user)

        return qs
    
    def has_change_permission(self, request, obj=None):
        """
        Менеджеры могут редактировать только те мероприятия,
        где они указаны в поле 'managers'.
        """
        # Если нет конкретного объекта (список или страница добавления) — 
        # смотрим, есть ли право 'change_moduleinstance'
        if obj is None:
            return request.user.has_perm('event.change_moduleinstance')

        # Суперпользователь — всё может
        if request.user.is_superuser:
            return True

        # Если нет права change_moduleinstance — сразу отказ
        if not request.user.has_perm('event.change_moduleinstance'):
            return False

        # Проверяем, состоит ли пользователь в группе "Менеджер"
        if request.user.groups.filter(name='Менеджер').exists():
            # Разрешаем редактировать только если user в obj.managers
            return request.user in obj.managers.all()

        # Иначе возвращаем стандартную проверку
        return super().has_change_permission(request, obj=obj)


# Чекин
@admin.register(Checkin)
class CheckinAdmin(BaseAdminPage, ImportExportActionModelAdmin):
    resource_class = CheckinResource
    search_fields = ['contact__fio', 'module_instance__module__name']
    list_display = ('contact', 'photo_contact', 'module_instance', 'get_buttons_action',)
    readonly_fields = ('operator',)
    autocomplete_fields = ['contact', 'module_instance']
    list_filter = (ModuleInstanceFilter, )
    list_per_page = 25
    view_on_site = False

    class Media:
        js = ('js/checkin_list.js',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/download-template-checkin-create/', self.admin_site.admin_view(self.download_checkin_template_create), name="checkin_template_create"),
            path('import/download-template-checkin-update/', self.admin_site.admin_view(self.download_checkin_template_update), name="checkin_template_update"),
        ]
        return custom_urls + urls

    def download_checkin_template_create(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "templates", "checkin_template_create.xlsx")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="checkin_template_create.xlsx")
    def download_checkin_template_update(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "templates", "checkin_template_update.xlsx")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="checkin_template_update.xlsx")

    def get_fields(self, request, obj=None):
        
        if obj:  # Редактирование записи
            return [
                ('action_type',),
                ('module_instance',),
                ('contact',),
                ('photo_contact',),
                ('get_buttons_action',),
                ('operator',),
            ]
        else:  # Создание новой записи
            return [
                ('contact',),
                ('module_instance',),
            ]
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            return ['contact', 'action_type', 'action_date', 'is_last_state', 'module_instance', 'get_buttons_action', 'photo_contact', 'operator']
        else:  # Создание новой записи
            return [ 'action_type', 'get_buttons_action']

    # Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context.update(service.get_params_visible_buttons_save(request, obj))
        return super().render_change_form(request, context, add, change, form_url, obj)

    actions = ['checkin_actions', 'cancel_actions']

    def get_buttons_action(self, obj):
        if not obj or obj.pk is None:
            return format_html('<span>Действия недоступны для новой записи</span>')

        confirm_url = reverse('checkin_confirm', args=[obj.pk])
        cancel_url = reverse('checkin_cancel', args=[obj.pk])

        buttons_html = f'''
            <div style="display: flex; gap: 5px; justify-content: center; align-items: center;">
                <button type="button" class="button-confirm" data-url="{confirm_url}" data-id="{obj.pk}" style="background-color: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; font-size: 12px;">Подтвердить</button>
                <button type="button" class="button-cancel" data-url="{cancel_url}" data-id="{obj.pk}" style="background-color: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 3px; font-size: 12px;">Отменить</button>
            </div>
        '''
        return format_html(buttons_html)

    get_buttons_action.short_description = 'Действия'


    @admin.action(description='Чекин')
    def checkin_actions(self, request, queryset):
        message_title = 'Ниже указаны регистрации на событие, которые будут подтверждены:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'checkin'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Подтверждено посещение по событию. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'checkin_actions', 'message_title': message_title, 'items': queryset,'form': form, 'title':u'Подтверждение посещения'})
    
    @admin.action(description='Отмена')
    def cancel_actions(self, request, queryset):
        message_title = 'Ниже указаны регистрации на событие, которые будут отменены:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'cancel'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Отменена регистрация по событию. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'cancel_actions','message_title': message_title, 'items': queryset,'form': form, 'title':u'Отмена регистрации'})

    # Выборка регистраций
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.groups.filter(name='Проверяющий').exists():
            qs = qs.filter(module_instance__checkers=request.user)
        return qs.filter(is_last_state=True, action_type='new')
    
    def save_model(self, request, obj, form, change):
        obj.operator = request.user
        super().save_model(request, obj, form, change)


# Действие
@admin.register(Action)
class ActionAdmin(ExportActionModelAdmin):
    form = ActionForm
    list_display = ('contact', 'action_type', 'module_instance', 'action_date')
    list_filter = (ModuleInstanceFilter, 'action_type', 'module_instance__date_start')
    autocomplete_fields = ['contact', 'module_instance']
    readonly_fields = ('contact', 'action_type', 'module_instance', 'action_date', 'is_last_state')
    list_per_page = 25
    view_on_site = False

    # Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context.update(service.get_params_visible_buttons_save(request, obj))
        return super().render_change_form(request, context, add, change, form_url, obj)

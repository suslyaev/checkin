from django.contrib import admin
import event.services as service
from .models import CustomUser, ManagerUser, ProducerUser,  CheckerUser, CompanyContact, CategoryContact, TypeGuestContact, SocialNetwork, InfoContact, Contact, ModuleInstance, Action
from .forms import CheckinOrCancelForm, ModuleInstanceForm, CustomUserForm, CustomUserChangeForm
from django.shortcuts import render
from django.http import HttpResponseRedirect
from import_export.admin import ExportActionModelAdmin, ExportActionMixin, ImportExportModelAdmin, ImportExportActionModelAdmin
from .resources import ContactResource, ModuleInstanceResource, ActionResource, ActionResourceRead
from admin_auto_filters.filters import AutocompleteFilter
from django.utils.html import format_html
from django.urls import reverse
from django.http import FileResponse
import os
from django.forms import Textarea
from django.db import models
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.shortcuts import redirect

class CustomAdminSite(admin.AdminSite):

    def index(self, request, extra_context=None):
        return redirect(reverse("admin:event_moduleinstance_changelist"))

    def get_app_list(self, request, app_label=None):
        """
        Кастомный порядок моделей в приложении event с разделителями.
        """
        app_list = super().get_app_list(request)

        # Ищем в списке приложение event
        for app in app_list:
            if app["app_label"] == "event":
                # Желаемый порядок моделей
                custom_order = [
                    "События",
                    "Contact",
                    "ModuleInstance",
                    "Action",
                    "Справочники",
                    "CompanyContact",
                    "CategoryContact",
                    "TypeGuestContact",
                    "SocialNetwork",
                    "Доступы",
                    "CustomUser",
                ]

                # Разбиваем модели на словарь {Имя модели: данные}
                model_dict = {model["object_name"]: model for model in app["models"]}

                # Создаем новый список моделей в заданном порядке
                new_models = []
                for model_name in custom_order:
                    if model_name == "---":
                        new_models.append({"name": "---", "admin_url": None})
                    elif model_name == "События":
                        new_models.append({"name": "-- События --", "admin_url": None})
                    elif model_name == "Справочники":
                        new_models.append({"name": "-- Справочники --", "admin_url": None})
                    elif model_name == "Доступы":
                        new_models.append({"name": "-- Доступы --", "admin_url": None})
                    elif model_name in model_dict:
                        new_models.append(model_dict[model_name])

                # Обновляем модели приложения
                app["models"] = new_models

        return app_list

admin.site.__class__ = CustomAdminSite

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    app_label = 'event'
    form = CustomUserChangeForm
    add_form = CustomUserForm
    search_fields = ['phone', 'last_name', 'first_name']  # Поля для поиска
    list_display = ['phone', 'last_name', 'first_name', 'get_group']  # Для отображения в списке
    list_filter = ('groups',)
    readonly_fields = ['date_joined', 'last_login', 'get_group']

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

    def get_form(self, request, obj=None, **kwargs):
        if obj:  # Если это редактирование существующего пользователя
            self.form = CustomUserChangeForm
        else:  # Если это создание нового пользователя
            self.form = CustomUserForm
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        # Получаем базовый queryset
        qs = super().get_queryset(request)
        # Исключаем пользователей с is_superuser=True
        return qs.exclude(is_superuser=True)

    def get_fields(self, request, obj=None):

        if obj:  # Редактирование записи
            return [
                ('phone', 'ext_id'),
                ('group',),
                ('first_name', 'last_name'),
                ('date_joined', 'last_login'),
                ('new_password1', 'new_password2'),
            ]
        else:  # Создание новой записи
            return [
                ('phone', ),
                ('group',),
                ('password1', ),
                ('password2', ),
                ('first_name', 'last_name'),
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
    
    def get_search_results(self, request, queryset, search_term):
        """
        Фильтруем queryset в зависимости от того, 
        для какого поля (managers/checkers) идёт автокомплит.
        """
        # Сначала получаем стандартные результаты
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # Django при автокомплите передаёт GET-параметр 'field_name'
        field_name = request.GET.get('field_name')

        if field_name == 'managers':
            # Оставляем только тех, кто в группе "Менеджер"
            queryset = queryset.filter(groups__name='Менеджер')
        elif field_name == 'producers':
            # Оставляем только тех, кто в группе "Продюсер"
            queryset = queryset.filter(groups__name='Продюсер')
        elif field_name == 'checkers':
            # Оставляем только тех, кто в группе "Модератор"
            queryset = queryset.filter(groups__name='Модератор')

        return queryset, use_distinct


@admin.register(ManagerUser)
class ManagerUserAdmin(admin.ModelAdmin):
    search_fields = ["phone", "first_name", "last_name"]

    def get_queryset(self, request):
        # Показываем только пользователей из группы "Менеджер"
        qs = super().get_queryset(request)
        return qs.filter(groups__name='Менеджер')

@admin.register(ProducerUser)
class ProducerUserAdmin(admin.ModelAdmin):
    search_fields = ["phone", "first_name", "last_name"]

    def get_queryset(self, request):
        # Показываем только пользователей из группы "Продюсер"
        qs = super().get_queryset(request)
        return qs.filter(groups__name='Продюсер')

@admin.register(CheckerUser)
class CheckerUserAdmin(admin.ModelAdmin):
    search_fields = ["phone", "first_name", "last_name"]

    def get_queryset(self, request):
        # Показываем только пользователей из группы "Модератор"
        qs = super().get_queryset(request)
        return qs.filter(groups__name='Модератор')

# Базовый класс с параметрами по умолчанию
class BaseAdminPage(admin.ModelAdmin):
    list_per_page = 25
    view_on_site = False

# Фильтр с автозаполнением для event
class ModuleInstanceFilter(AutocompleteFilter):
    title = 'Мероприятие'  # Название фильтра
    field_name = 'event'  # Поле модели, по которому будет фильтрация

class CompanyContactFilter(AutocompleteFilter):
    title = 'Компания'
    field_name = 'company'

class CategoryContactFilter(AutocompleteFilter):
    title = 'Категория'
    field_name = 'category'

class TypeGuestContactFilter(AutocompleteFilter):
    title = 'Тип гостя'
    field_name = 'type_guest'

class CategoryContactCheckinFilter(AutocompleteFilter):
    title = 'Категория человека'
    field_name = 'get_category_contact'

class TypeGuestContactCheckinFilter(AutocompleteFilter):
    title = 'Тип гостя'
    field_name = 'contact'

# Социальная сеть
@admin.register(SocialNetwork)
class SocialNetworkAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment')
    list_editable = ('name', 'comment')
    search_fields = ['name']

class InfoContactInline(admin.TabularInline):
    model = InfoContact
    fields = ['contact', 'social_network', 'external_id', 'subscribers']
    autocomplete_fields = ['social_network', ]
    readonly_fields = ['contact',]
    extra = 0
    verbose_name = 'Контакт'
    verbose_name_plural = "Контакты"

# Человек
@admin.register(Contact)
class ContactAdmin(BaseAdminPage, ExportActionMixin, ImportExportModelAdmin):
    resource_class = ContactResource
    list_display = ('get_fio', 'company', 'category', 'type_guest', 'photo_preview')
    list_filter = (CompanyContactFilter, CategoryContactFilter, TypeGuestContactFilter)
    readonly_fields = ('get_fio', 'photo_preview', 'registered_events_list', 'checkin_events_list')
    autocomplete_fields = ['company', 'category', 'type_guest']
    search_fields = ['last_name', 'first_name', 'middle_name', 'nickname']
    inlines = [InfoContactInline, ]
    show_change_form_export = False
    fieldsets = (
        (None, {
            'fields': [('last_name', 'first_name', 'middle_name', 'nickname')]
        }),
        (None, {
            'fields': [('company', 'category', 'type_guest')]
        }),
        ('Фото', {
            'fields': ['photo', 'photo_preview'],
        }),
        (None, {
            'fields': [('comment',)]
        }),
        ('Участие в мероприятиях', {
            'fields': ['registered_events_list', 'checkin_events_list'],
        }),
    )

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={
            'rows': 2,
            'cols': 60,
            'style': 'width: 400px;'
        })},
    }

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/download_template_import_cont/', self.admin_site.admin_view(self.download_template_import_cont), name="template_import_cont"),
        ]
        return custom_urls + urls

    def download_template_import_cont(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "templates", "import_cont.xlsx")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="import_cont.xlsx")

    def registered_events_list(self, obj):
        """
        Список мероприятий, где contact=obj, action_type__in=['new', 'checkin']
        """
        from .models import Action  # или импорт вверху файла
        actions = Action.objects.filter(
            contact=obj,
            action_type__in=['new', 'checkin']
        ).select_related('event')

        return service.get_link_list_for_event(actions, 'moduleinstance', 'more-registrations')
    registered_events_list.short_description = "Регистрации"

    def checkin_events_list(self, obj):
        """
        Список мероприятий, где contact=obj, action_type='checkin'
        """
        from .models import Action
        actions = Action.objects.filter(
            contact=obj,
            action_type='checkin'
        ).select_related('event')

        return service.get_link_list_for_event(actions, 'moduleinstance', 'more-checkins')
    checkin_events_list.short_description = "Чекины"

# Компания
@admin.register(CompanyContact)
class CompanyContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment', 'contacts_count_link')
    list_editable = ('name', 'comment')
    search_fields = ['name']

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?company__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact__count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Категория
@admin.register(CategoryContact)
class CategoryContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'color', 'comment', 'contacts_count_link')
    list_editable = ('name', 'color', 'comment')
    search_fields = ['name']

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?category__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact__count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Статус
@admin.register(TypeGuestContact)
class TypeGuestContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'color', 'comment', 'contacts_count_link')
    list_editable = ('name', 'color', 'comment')
    search_fields = ['name']

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?type_guest__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact__count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Событие
@admin.register(ModuleInstance)
class ModuleInstanceAdmin(ExportActionModelAdmin):
    resource_class = ModuleInstanceResource
    form = ModuleInstanceForm
    search_fields = ['get_name_event']
    show_change_form_export = False
    fieldsets = (
        (None, {
            'fields': [('name', 'is_visible', 'address',)]
        }),
        ('Когда', {
            'fields': [('date_start', 'date_end')]
        }),
        ('Администрирование', {
            'fields': [('managers', 'producers', 'checkers')]
        }),
        ('Участники', {
            'fields': [('registrations_count', 'checkins_count'),'registered_list', 'checkin_list'],
        }),
    )
    readonly_fields = ['registered_list', 'checkin_list', 'registrations_count', 'checkins_count']
    autocomplete_fields = ['managers', 'producers', 'checkers']
    list_display = ('name', 'date_start', 'registrations_count', 'checkins_count', 'is_visible')
    list_editable = ('is_visible',)
    list_filter = ('is_visible',)
    show_change_form_export = False
    save_on_top = True
    list_per_page = 25
    view_on_site = False

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

    def registrations_count(self, obj):
        return Action.objects.filter(event=obj, action_type__in=['new', 'checkin']).count()
    registrations_count.short_description = 'Регистрации'

    def checkins_count(self, obj):
        return Action.objects.filter(event=obj, action_type='checkin').count()
    checkins_count.short_description = 'Чекины'

    def registered_list(self, obj):
        """
        Список зарегистрированных (action_type__in=['new', 'checkin'])
        """
        actions = Action.objects.filter(
            action_type__in=['new', 'checkin'],
            event=obj
        ).select_related('contact')

        return service.get_link_list_for_event(actions, 'contact', 'more-registrations')
    registered_list.short_description = "Регистрации"

    def checkin_list(self, obj):
        """
        Список чекинившихся (action_type='checkin')
        """
        actions = Action.objects.filter(
            action_type='checkin',
            event=obj
        ).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-checkins')
    checkin_list.short_description = "Чекины"

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
        if db_field.name in ['producers', ]:
            # Исключаем суперпользователей
            kwargs['queryset'] = CustomUser.objects.filter(is_superuser=False, groups__name='Продюсер')
        if db_field.name in ['checkers', ]:
            # Исключаем суперпользователей
            kwargs['queryset'] = CustomUser.objects.filter(is_superuser=False, groups__name='Модератор')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # Ограничение ролевой модели
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Если пользователь — суперюзер или админ, видит все
        if request.user.is_superuser:
            return qs

        # Если пользователь в группе "Модератор" — видит только те,
        # где он указан в массиве checkers
        if request.user.groups.filter(name='Модератор').exists():
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

class ContactActionFilter(AutocompleteFilter):
    title = 'Человек'
    field_name = 'contact'

# Действие
@admin.register(Action)
class ActionAdmin(BaseAdminPage, ImportExportActionModelAdmin):
    resource_class = ActionResource
    #resource_class = ActionResource
    list_display = ('contact', 'photo_contact', 'event', 'update_date', 'get_buttons_action')
    list_filter = (ModuleInstanceFilter, ContactActionFilter, 'action_type', 'event__date_start')
    autocomplete_fields = ['contact', 'event']
    readonly_fields = ('action_type', 'create_date', 'update_date', 'create_user', 'update_user')
    list_per_page = 25
    view_on_site = False
    show_change_form_export = False

    class Media:
        js = ('js/checkin_list.js',)

    def get_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            return [
                ('action_type',),
                ('event',),
                ('contact',),
                ('photo_contact',),
                ('get_buttons_action',),
                ('create_date', 'create_user'),
                ('update_date',  'update_user'),
            ]
        else:  # Создание новой записи
            return [
                ('contact',),
                ('event',),
            ]
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            if request.user.is_superuser == True: # Если суперадмин
                return ['create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action']
            else:
                return ['action_type', 'contact', 'event', 'create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action']
        else:  # Создание новой записи
            return [ 'action_type', 'create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action']
    
    actions = ['checkin_actions', 'cancel_actions']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/download_template_import_reg/', self.admin_site.admin_view(self.download_template_import_reg), name="template_import_reg"),
        ]
        return custom_urls + urls

    def download_template_import_reg(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "templates", "import_reg.xlsx")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="import_reg.xlsx")

    def get_buttons_action(self, obj):
        if not obj or obj.pk is None:
            return format_html('<span>Действия недоступны для новой записи</span>')

        if obj.action_type == 'new':
            button_url = reverse('checkin_confirm', args=[obj.pk])
            current_status = 'Зарегистрирован'
            button_class = 'button-confirm'
            button_color = '#26a526'
            button_text = 'Подтвердить'
        else:
            button_url = reverse('checkin_cancel', args=[obj.pk])
            current_status = 'Посетил'
            button_class = 'button-cancel'
            button_color = '#dc3545'
            button_text = 'Отменить'

        buttons_html = f'''
            <div style="display: flex; gap: 20px; align-items: center; min-width: 240px;">
                <div style="width: 120px; text-align: center; white-space: nowrap;">
                    {current_status}
                </div>
                <button type="button" class="{button_class}" data-url="{button_url}" data-id="{obj.pk}" style="width: 120px; background: none;color: {button_color};border: 2px solid {button_color};padding: 5px 5px;border-radius: 3px;font-size: 12px;">
                    {button_text}
                </button>
            </div>
        '''

        return format_html(buttons_html)

    get_buttons_action.short_description = 'Статус'


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
                action_type = 'new'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Отменена регистрация по событию. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'cancel_actions','message_title': message_title, 'items': queryset,'form': form, 'title':u'Отмена регистрации'})

    def save_model(self, request, obj, form, change):
        if not change:
            obj.create_user = request.user
        obj.update_user = request.user
        super().save_model(request, obj, form, change)
    
    # Выборка регистраций
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='Модератор').exists():
            qs = qs.filter(event__checkers=request.user)
        if request.user.groups.filter(name='Менеджер').exists():
            qs = qs.filter(event__managers=request.user)
        return qs

    # Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context.update(service.get_params_visible_buttons_save(request, obj))
        return super().render_change_form(request, context, add, change, form_url, obj)

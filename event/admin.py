from django.contrib import admin, messages
import event.services as service
from .models import CustomUser, ManagerUser, ProducerUser,  CheckerUser, CompanyContact, CategoryContact, TypeGuestContact, SocialNetwork, InfoContact, Contact, ModuleInstance, Action, ActionLog
from .forms import CheckinOrCancelForm, ModuleInstanceForm, CustomUserForm, CustomUserChangeForm
from django.shortcuts import render
from django.http import HttpResponseRedirect
from import_export.admin import ExportActionModelAdmin, ExportActionMixin, ImportExportModelAdmin, ImportExportActionModelAdmin
from .resources import ContactImport, EventExport
from admin_auto_filters.filters import AutocompleteFilter, AutocompleteFilterFactory
from django.db.models import Count, Q
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from django.http import FileResponse, QueryDict
import os
from django.utils import timezone
from django.forms import Textarea
from django.db import models
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.shortcuts import redirect
from admin_auto_filters.filters import AutocompleteFilterMultiple
from django import forms
from django.contrib.admin.widgets import AutocompleteSelect


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
class ModuleInstanceFilter(AutocompleteFilterMultiple):
    title = 'Мероприятие'
    field_name = 'event'

class ContactFilter(AutocompleteFilterMultiple):
    title = 'Человек'
    field_name = 'contact'

class CompanyContactFilter(AutocompleteFilterMultiple):
    title = 'Компания'
    field_name = 'company'

class CategoryContactFilter(AutocompleteFilterMultiple):
    title = 'Категория'
    field_name = 'category'

class TypeGuestContactFilter(AutocompleteFilterMultiple):
    title = 'Тип гостя'
    field_name = 'type_guest'

class ProducerContactFilter(AutocompleteFilterMultiple):
    title = 'Продюсер'
    field_name = 'producer'

class CopyInvitationsForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    source_event = forms.ModelChoiceField(
        queryset=ModuleInstance.objects.all(),
        label='Выберите источник приглашений'
    )

    def __init__(self, *args, **kwargs):
        admin_site = kwargs.pop('admin_site', None)
        super().__init__(*args, **kwargs)
        if admin_site:
            rel = Action._meta.get_field('event').remote_field
            widget = AutocompleteSelect(rel, admin_site)
            widget.attrs.update({'style': 'width: 100%; min-width: 320px;'})
            self.fields['source_event'].widget = widget

ProducerActionFilter = AutocompleteFilterFactory(
    'Продюсер',
    'contact__producer'
)

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
class ContactAdmin(BaseAdminPage, ImportExportModelAdmin, ImportExportActionModelAdmin):
    list_display = ('get_fio', 'company', 'category', 'type_guest', 'producer', 'photo_preview')
    list_editable = ('company', 'category', 'type_guest', 'producer')
    list_filter = (CompanyContactFilter, CategoryContactFilter, TypeGuestContactFilter, ProducerContactFilter)
    readonly_fields = ('get_fio', 'photo_preview', 'registered_events_list', 'checkin_events_list')
    autocomplete_fields = ['company', 'category', 'type_guest', 'producer']
    search_fields = ['last_name', 'first_name', 'middle_name', 'nickname']
    inlines = [InfoContactInline, ]
    show_change_form_export = False
    list_max_show_all = 10000
    fieldsets = (
        (None, {
            'fields': [('last_name', 'first_name', 'middle_name', 'nickname')]
        }),
        (None, {
            'fields': [('company', 'category', 'type_guest'), ('producer',)]
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

    def get_import_resource_class(self):
        from .resources import ContactImport
        return ContactImport

    def get_export_resource_class(self):
        from .resources import ContactExport
        return ContactExport

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
        Список мероприятий, где contact=obj
        """
        from .models import Action  # или импорт вверху файла
        actions = Action.objects.filter(
            contact=obj
        ).select_related('event')

        return service.get_link_list_for_event(actions, 'moduleinstance', 'more-registrations')
    registered_events_list.short_description = "Заявлено"

    def checkin_events_list(self, obj):
        """
        Список мероприятий, где contact=obj, action_type='visited'
        """
        from .models import Action
        actions = Action.objects.filter(
            contact=obj,
            action_type='visited'
        ).select_related('event')

        return service.get_link_list_for_event(actions, 'moduleinstance', 'more-checkins')
    checkin_events_list.short_description = "Посещено"

# Компания
@admin.register(CompanyContact)
class CompanyContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment', 'contacts_count_link')
    list_editable = ('name', 'comment')
    search_fields = ['name']
    ordering = ['name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(contact_count=Count('contact'))

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?company__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact_count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Категория
@admin.register(CategoryContact)
class CategoryContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'color', 'comment', 'contacts_count_link')
    list_editable = ('name', 'color', 'comment')
    search_fields = ['name']
    ordering = ['name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(contact_count=Count('contact'))

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?category__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact_count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Статус
@admin.register(TypeGuestContact)
class TypeGuestContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'color', 'comment', 'contacts_count_link')
    list_editable = ('name', 'color', 'comment')
    search_fields = ['name']
    ordering = ['name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(contact_count=Count('contact'))

    def contacts_count_link(self, obj):
        count = obj.contact_set.count()
        url = reverse('admin:event_contact_changelist') + f'?type_guest__pk__exact={obj.pk}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, count)
    contacts_count_link.short_description = 'Контактов'
    contacts_count_link.admin_order_field = 'contact_count'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ

# Событие
@admin.register(ModuleInstance)
class ModuleInstanceAdmin(BaseAdminPage, ExportActionModelAdmin):
    form = ModuleInstanceForm
    resource_class = EventExport
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
            'fields': [('announced_count', 'invited_count', 'registered_count', 'checkins_count', 'cancelled_count'),
                       ('add_person_button',),
                       ('announced_list', 'invited_list',),
                       ('registered_list', 'visited_list',),
                       ('cancelled_list',)],
        }),
    )
    readonly_fields = ['announced_list', 'invited_list', 'cancelled_list', 'registered_list', 'visited_list', 'announced_count', 'invited_count', 'cancelled_count', 'registered_count', 'checkins_count', 'add_person_button']
    autocomplete_fields = ['managers', 'producers', 'checkers']
    list_display = ('name', 'date_start', 'announced_count', 'invited_count', 'cancelled_count', 'registered_count', 'checkins_count', 'is_visible')
    list_editable = ('is_visible',)
    list_filter = ('is_visible', 'date_start')
    show_change_form_export = False
    save_on_top = True
    list_per_page = 25
    view_on_site = False
    list_max_show_all = 10000
    actions = ['copy_invitations_action', 'delete_selected']
    action_changelist_url_name = 'admin:event_action_changelist'
    event_filter_param = 'event__pk__in'
    status_filter_param = 'action_type__exact'

    class Media:
        js = ('js/admin.js',) # Костыль для замены УДАЛЕНО на УДАЛИТЬ
    
    def add_person_button(self, obj):
        if not obj.pk:
            return "-"
        url = reverse('admin:event_action_add') + f'?event={obj.pk}&_popup=1'
        return format_html(
            '<a href="{url}" onclick="return showAddAnotherPopup(this);" '
            'class="button" style="width: 200px; background: none;color: gray;border: 2px solid gray;padding: 5px 5px;border-radius: 3px;font-size: 12px;">Добавить</a>',
            url=url
        )
    add_person_button.short_description = "Добавить человека на мероприятие"

    def announced_count(self, obj):
        return self._status_count_link(obj, 'announced', 'announced_total')
    announced_count.short_description = 'Заявлено'
    announced_count.admin_order_field = 'announced_total'

    def invited_count(self, obj):
        return self._status_count_link(obj, 'invited', 'invited_total')
    invited_count.short_description = 'Приглашено'
    invited_count.admin_order_field = 'invited_total'

    def registered_count(self, obj):
        return self._status_count_link(obj, 'registered', 'registered_total')
    registered_count.short_description = 'Согласовано'
    registered_count.admin_order_field = 'registered_total'

    def checkins_count(self, obj):
        return self._status_count_link(obj, 'visited', 'visited_total')
    checkins_count.short_description = 'Посещено'
    checkins_count.admin_order_field = 'visited_total'

    def cancelled_count(self, obj):
        return self._status_count_link(obj, 'cancelled', 'cancelled_total')
    cancelled_count.short_description = 'Отклонено'
    cancelled_count.admin_order_field = 'cancelled_total'

    def _status_count_link(self, obj, status, annotation_attr):
        count = getattr(obj, annotation_attr, None)
        if count is None:
            queryset = Action.objects.filter(event=obj)
            if status:
                queryset = queryset.filter(action_type=status)
            count = queryset.count()
        url = self._build_action_changelist_url(obj.pk, status)
        return format_html('<a href="{url}">{count}</a>', url=url, count=count)

    def _build_action_changelist_url(self, event_pk, status=None):
        base_url = reverse(self.action_changelist_url_name)
        params = QueryDict('', mutable=True)
        params[self.event_filter_param] = str(event_pk)
        if status:
            params[self.status_filter_param] = status
        return f'{base_url}?{params.urlencode()}'

    def announced_list(self, obj): # Список заявленных (action_type='announced')
        actions = Action.objects.filter(action_type='announced', event=obj).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-announced')
    announced_list.short_description = "Список заявленных"

    def invited_list(self, obj): # Список приглашенных (action_type='invited')
        actions = Action.objects.filter(action_type='invited', event=obj).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-invited')
    invited_list.short_description = "Список приглашенных"

    def registered_list(self, obj): # Список подтвержденных (action_type='registered')
        actions = Action.objects.filter(action_type='registered', event=obj).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-registered')
    registered_list.short_description = "Список подтвержденных"

    def visited_list(self, obj): # Список посетивших (action_type='visited')
        actions = Action.objects.filter(action_type='visited', event=obj).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-visited')
    visited_list.short_description = "Список посетивших"

    def cancelled_list(self, obj): # Список отмененных (action_type='cancelled')
        actions = Action.objects.filter(action_type='cancelled', event=obj).select_related('contact')
        return service.get_link_list_for_event(actions, 'contact', 'more-cancelled')
    cancelled_list.short_description = "Список отмененных"

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

        return qs.annotate(
            announced_total=Count('action', filter=Q(action__action_type='announced')),
            invited_total=Count('action', filter=Q(action__action_type='invited')),
            registered_total=Count('action', filter=Q(action__action_type='registered')),
            visited_total=Count('action', filter=Q(action__action_type='visited')),
            cancelled_total=Count('action', filter=Q(action__action_type='cancelled')),
        )

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

    @admin.action(description='Импортировать приглашения')
    def copy_invitations_action(self, request, queryset):
        selected_ids = request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        if not selected_ids:
            selected_ids = [str(pk) for pk in queryset.values_list('pk', flat=True)]
        if not selected_ids:
            self.message_user(request, "Сначала выберите одно или несколько мероприятий.", level=messages.WARNING)
            return

        form = None
        if 'apply' in request.POST:
            form = CopyInvitationsForm(request.POST, admin_site=self.admin_site)
            if form.is_valid():
                source_event = form.cleaned_data['source_event']
                target_events = list(queryset.exclude(pk=source_event.pk))
                if not target_events:
                    self.message_user(request, "Нет мероприятий для копирования (источник исключается из списка).", level=messages.WARNING)
                    return HttpResponseRedirect(request.get_full_path())

                stats = self._copy_invitations_from_event(request.user, source_event, target_events)
                total_created = sum(stats.values())
                if total_created:
                    summary = "; ".join(f'"{event.name}" — {count}' for event, count in stats.items())
                    self.message_user(request, f'Создано {total_created} приглашений: {summary}')
                else:
                    self.message_user(request, 'Новые приглашения не созданы: все выбранные участники уже присутствуют.', level=messages.INFO)

                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CopyInvitationsForm(
                initial={'_selected_action': selected_ids},
                admin_site=self.admin_site
            )

        context = {
            'title': 'Импорт приглашений',
            'selected_events': list(queryset),
            'form': form,
            'action_name': 'copy_invitations_action',
            'opts': self.model._meta,
        }

        return render(request, 'event/copy_invitations.html', context)

    def _copy_invitations_from_event(self, user, source_event, target_events):
        source_actions = list(
            Action.objects.filter(event=source_event, contact__isnull=False).select_related('contact')
        )
        results = {}

        for target in target_events:
            existing_contact_ids = set(
                Action.objects.filter(event=target).values_list('contact_id', flat=True)
            )
            to_create = []

            for action in source_actions:
                contact_id = action.contact_id
                if not contact_id or contact_id in existing_contact_ids:
                    continue
                to_create.append(Action(
                    contact=action.contact,
                    event=target,
                    action_type='announced',
                    comment=action.comment,
                    create_user=user,
                    update_user=user,
                ))
                existing_contact_ids.add(contact_id)

            if to_create:
                Action.objects.bulk_create(to_create, ignore_conflicts=True)

            results[target] = len(to_create)

        return results

# Действие
@admin.register(Action)
class ActionAdmin(BaseAdminPage, ImportExportModelAdmin, ImportExportActionModelAdmin):
    change_list_template = 'admin/event/action/change_list.html'
    list_display = ('contact', 'photo_contact', 'event', 'update_date', 'get_buttons_action')
    list_filter = (ModuleInstanceFilter, ContactFilter, ProducerActionFilter, 'action_type', 'event__date_start')
    search_fields = ['contact__last_name', 'contact__first_name', 'contact__middle_name']
    autocomplete_fields = ['contact', 'event']
    readonly_fields = ('action_type', 'create_date', 'update_date', 'create_user', 'update_user', 'audit_log_table')
    list_per_page = 100
    view_on_site = False
    show_change_form_export = False
    list_max_show_all = 10000
    per_page_default = 100
    per_page_options = [25, 50, 100, 200]
    per_page_query_param = 'per_page'
    per_page_session_key = 'event_action_admin_per_page'

    class Media:
        js = ('js/checkin_list.js',)
    
    def get_import_resource_class(self):
        from .resources import ActionImport
        return ActionImport

    def get_export_resource_class(self):
        from .resources import ActionExport
        return ActionExport

    def get_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            return [
                ('event',),
                ('contact',),
                ('photo_contact',),
                ('get_buttons_action',),
                ('comment',),
                ('create_date', 'create_user'),
                ('update_date',  'update_user'),
                ('audit_log_table',)
            ]
        else:  # Создание новой записи
            return [
                ('contact',),
                ('event',),
                ('comment',),
            ]
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            if request.user.is_superuser == True: # Если суперадмин
                return ['create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action', 'audit_log_table']
            else:
                return ['action_type', 'contact', 'event', 'create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action', 'audit_log_table']
        else:  # Создание новой записи
            return [ 'action_type', 'create_date', 'create_user', 'update_date',  'update_user', 'photo_contact', 'get_buttons_action', 'audit_log_table']

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

        buttons = []
        if obj.action_type == 'announced':
            buttons.append({
                'button_url': reverse('action_invited', args=[obj.pk]),
                'current_status': 'Заявлен',
                'button_class': 'button-invited',
                'button_color': '#007bff',
                'button_text': 'Пригласить'
            })
        elif obj.action_type == 'invited':
            buttons.append({
                'button_url': reverse('action_registered', args=[obj.pk]),
                'current_status': 'Приглашён',
                'button_class': 'button-registered',
                'button_color': '#28a745',
                'button_text': 'Подтвердил'
            })
            buttons.append({
                'button_url': reverse('action_cancelled', args=[obj.pk]),
                'current_status': 'Приглашён',
                'button_class': 'button-cancelled',
                'button_color': '#dc3545',
                'button_text': 'Отклонил'
            })
        elif obj.action_type == 'registered':
            buttons.append({
                'button_url': reverse('action_visited', args=[obj.pk]),
                'current_status': 'Зарегистрирован',
                'button_class': 'button-visited',
                'button_color': '#6610f2',
                'button_text': 'Чекин'
            })
        elif obj.action_type == 'visited':
            buttons.append({
                'button_url': reverse('action_registered', args=[obj.pk]),
                'current_status': 'Отмечен',
                'button_class': 'button-cancel-checkin',
                'button_color': '#dc3545',
                'button_text': 'Отменить чекин'
            })
        elif obj.action_type == 'cancelled':
            buttons.append({
                'button_url': reverse('action_invited', args=[obj.pk]),
                'current_status': 'Отменён',
                'button_class': 'button-invited',
                'button_color': '#28a745',
                'button_text': 'Пригласить'
            })

        buttons_html = f'''
            <div style="display: flex; gap: 20px; align-items: center; min-width: 240px;">
                <div style="width: 120px; text-align: center; white-space: nowrap;">
                    {obj.get_action_type_display()}
                </div>
        '''
        for button in buttons: buttons_html = buttons_html + f'''
                <button type="button" class="{button['button_class']}" data-url="{button['button_url']}" data-id="{obj.pk}" style="width: 120px; background: none;color: {button['button_color']};border: 2px solid {button['button_color']};padding: 5px 5px;border-radius: 3px;font-size: 12px;">
                    {button['button_text']}
                </button>
        '''
            
        buttons_html = buttons_html + '</div>'

        return format_html(buttons_html)

    get_buttons_action.short_description = 'Статус'

    actions = ['invited_actions', 'registered_actions', 'cancelled_actions', 'visited_actions']

    @admin.action(description='В статус Приглашён')
    def invited_actions(self, request, queryset):
        message_title = 'Ниже указаны люди, которых надо отметить как приглашённых:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'invited'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Приглашены на событие. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'invited_actions', 'message_title': message_title, 'items': queryset,'form': form, 'title':u'Приглашение на событие'})
    
    @admin.action(description='В статус Зарегистрирован')
    def registered_actions(self, request, queryset):
        message_title = 'Ниже указаны люди, которых надо отметить как согласившихся на посещение события:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'registered'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Согласовали посещение события. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'registered_actions', 'message_title': message_title, 'items': queryset,'form': form, 'title':u'Регистрация на событие'})

    @admin.action(description='В статус Отменён')
    def cancelled_actions(self, request, queryset):
        message_title = 'Ниже указаны люди, которых надо отметить как отказавшихся от посещения события:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'cancelled'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Отклонили приглашение на событие. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'cancelled_actions', 'message_title': message_title, 'items': queryset,'form': form, 'title':u'Отклонили приглашение на событие'})

    @admin.action(description='В статус Зачекинен')
    def visited_actions(self, request, queryset):
        message_title = 'Ниже указаны регистрации на событие, которые будут подтверждены:'
        form = None
        if 'apply' in request.POST:
            form = CheckinOrCancelForm(request.POST)
            if form.is_valid():
                action_type = 'visited'
                service.update_actions(action_type, queryset)
                count = len(queryset)
                self.message_user(request, "Подтверждено посещение по событию. Количество человек: %d." % (count))
                return HttpResponseRedirect(request.get_full_path())

        if not form:
            form = CheckinOrCancelForm(initial={'_selected_action': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)})

        return render(request, 'event/update_actions.html', {'action_def': 'visited_actions', 'message_title': message_title, 'items': queryset,'form': form, 'title':u'Подтверждение посещения'})

    def audit_log_table(self, obj):
        logs = obj.actionlog_set.order_by('-create_date')
        if not logs.exists():
            return "Нет записей истории."

        table_header = """
        <table style="border-collapse: collapse; width: 100%; min-width: 600px;">
            <thead>
                <tr>
                    <th style="border: 1px solid #ccc; padding: 5px;">Дата</th>
                    <th style="border: 1px solid #ccc; padding: 5px;">Пользователь</th>
                    <th style="border: 1px solid #ccc; padding: 5px;">Было</th>
                    <th style="border: 1px solid #ccc; padding: 5px;">Стало</th>
                </tr>
            </thead>
            <tbody>
        """

        table_rows = format_html_join(
            '\n',
            '<tr>'
            '<td style="border: 1px solid #ccc; padding: 5px;">{}</td>'
            '<td style="border: 1px solid #ccc; padding: 5px;">{}</td>'
            '<td style="border: 1px solid #ccc; padding: 5px;">{}</td>'
            '<td style="border: 1px solid #ccc; padding: 5px;">{}</td>'
            '</tr>',
            ((timezone.localtime(log.create_date).strftime("%d.%m.%Y %H:%M"), log.create_user or "—", log.get_old_status_display(), log.get_new_status_display()) for log in logs)
        )

        table_footer = "</tbody></table>"
        return format_html(table_header + table_rows + table_footer)

    audit_log_table.short_description = "История изменений"

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={
            'rows': 2,
            'cols': 60,
            'style': 'width: 400px;'
        })},
    }

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
    
    def _get_per_page_value(self, request):
        per_page_param = request.GET.get(self.per_page_query_param)
        valid_values = set(self.per_page_options)

        if per_page_param:
            try:
                per_page_value = int(per_page_param)
            except (TypeError, ValueError):
                per_page_value = self.per_page_default
            else:
                if per_page_value not in valid_values:
                    per_page_value = self.per_page_default
            request.session[self.per_page_session_key] = per_page_value
            return per_page_value

        stored_value = request.session.get(self.per_page_session_key)
        if isinstance(stored_value, int) and stored_value in valid_values:
            return stored_value

        request.session[self.per_page_session_key] = self.per_page_default
        return self.per_page_default

    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty_first_page=True):
        per_page = self._get_per_page_value(request)
        return super().get_paginator(
            request,
            queryset,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        base_params = request.GET.copy()
        if self.per_page_query_param in base_params:
            base_params.pop(self.per_page_query_param)
        extra_context.update({
            'per_page_options': self.per_page_options,
            'current_per_page': self._get_per_page_value(request),
            'per_page_query_param': self.per_page_query_param,
            'per_page_base_query': base_params.urlencode(),
        })
        return super().changelist_view(request, extra_context)

    # Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context.update(service.get_params_visible_buttons_save(request, obj))
        return super().render_change_form(request, context, add, change, form_url, obj)

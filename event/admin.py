from django.conf import settings
from django.contrib import admin, messages
from django.db import IntegrityError
import event.services as service
from .models import (
    CustomUser,
    ManagerUser,
    ProducerUser,
    CheckerUser,
    CompanyContact,
    CategoryContact,
    TypeGuestContact,
    SocialNetwork,
    InfoContact,
    Contact,
    ModuleInstance,
    Action,
    ActionLog,
    Community,
    CommunityMember,
)
from .forms import (
    CheckinOrCancelForm,
    ModuleInstanceForm,
    CustomUserForm,
    CustomUserChangeForm,
    ContactMergeForm,
)
from .contact_merge import format_contact_merge_label, merge_contacts
from .contact_duplicates import (
    build_duplicate_candidates_q,
    duplicate_candidates_queryset,
    get_duplicate_match_reasons,
    get_global_duplicate_reasons,
    presumed_duplicates_queryset,
)
from django.shortcuts import render
from django.http import HttpResponseRedirect
from import_export.admin import ExportActionModelAdmin, ExportActionMixin, ImportExportModelAdmin, ImportExportActionModelAdmin
from .resources import ContactImport, EventExport
from admin_auto_filters.filters import AutocompleteFilter, AutocompleteFilterFactory
from django.db.models import Count, Q
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
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

# Импорт миксина для интерактивной таблицы гостей
from .admin_guests_table_mixin import GuestsTableMixin

class CustomAdminSite(admin.AdminSite):

    def get_urls(self):
        from event.staged_import.views import staged_import_urls
        return staged_import_urls(self) + super().get_urls()

    def index(self, request, extra_context=None):
        return redirect(reverse("admin:event_moduleinstance_changelist"))

    def get_app_list(self, request, app_label=None):
        """
        Возвращает кастомный список приложений с настоящей группировкой
        """
        app_list = super().get_app_list(request)

        # Создаём кастомные группы
        custom_apps = []

        # 1. События
        events_group = {
            'name': 'События',
            'app_label': 'event_events',
            'app_url': '/admin/event/',
            'has_module_perms': True,
            'models': []
        }

        # 2. Справочники
        reference_group = {
            'name': 'Справочники',
            'app_label': 'event_reference',
            'app_url': '/admin/event/',
            'has_module_perms': True,
            'models': []
        }

        # 3. Доступы
        access_group = {
            'name': 'Доступы',
            'app_label': 'event_access',
            'app_url': '/admin/event/',
            'has_module_perms': True,
            'models': []
        }

        # 4. Табличный интерфейс /table/
        table_group = None
        if getattr(settings, 'ATTENDLY_TABLE_ENABLED', True):
            table_group = {
                'name': 'Таблицы',
                'app_label': 'attendly_table',
                'app_url': reverse('table:workspace_root'),
                'has_module_perms': True,
                'models': [{
                    'name': 'Таблицы',
                    'object_name': 'AttendlyTable',
                    'admin_url': reverse('table:workspace_root'),
                    'add_url': None,
                    'view_only': True,
                    'perms': {'view': True},
                }],
            }

        # 5. Пошаговая загрузка (временно скрыто в меню)
        STAGED_IMPORT_MENU_ENABLED = False
        upload_group = None
        if STAGED_IMPORT_MENU_ENABLED and request.user.has_perm('event.add_contact'):
            upload_group = {
                'name': 'Загрузка',
                'app_label': 'event_upload',
                'app_url': reverse('admin:staged_import_contacts'),
                'has_module_perms': True,
                'models': [{
                    'name': 'Люди',
                    'object_name': 'StagedContactImport',
                    'admin_url': reverse('admin:staged_import_contacts'),
                    'add_url': None,
                    'view_only': True,
                    'perms': {'view': True},
                }],
            }

        # Распределяем модели по группам
        for app in app_list:
            if app["app_label"] == "event":
                # Создаём словарь для быстрого поиска
                model_dict = {model["object_name"]: model for model in app["models"]}

                # События
                for model_name in ['Contact', 'Community', 'ModuleInstance', 'Action']:
                    if model_name in model_dict:
                        events_group['models'].append(model_dict[model_name])

                # Справочники
                for model_name in ['CompanyContact', 'CategoryContact', 'TypeGuestContact', 'SocialNetwork']:
                    if model_name in model_dict:
                        reference_group['models'].append(model_dict[model_name])

                # Доступы
                for model_name in ['CustomUser']:
                    if model_name in model_dict:
                        access_group['models'].append(model_dict[model_name])

        # Добавляем только непустые группы
        for group in [events_group, reference_group, table_group, upload_group, access_group]:
            if group and group.get('models'):
                custom_apps.append(group)

        return custom_apps

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


class DuplicateOfContactFilter(admin.SimpleListFilter):
    """Фильтр списка по предположительным дублям выбранной карточки."""
    title = 'Предположительные дубли'
    parameter_name = 'duplicate_of'

    def lookups(self, request, model_admin):
        value = request.GET.get(self.parameter_name)
        if not value:
            return ()
        try:
            contact = Contact.objects.get(pk=int(value))
        except (Contact.DoesNotExist, ValueError, TypeError):
            return ()
        return [(value, contact.get_fio())]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        try:
            anchor = Contact.objects.get(pk=int(value))
        except (Contact.DoesNotExist, ValueError, TypeError):
            return queryset.none()
        return queryset.filter(build_duplicate_candidates_q(anchor)).distinct()


class PresumedDuplicatesOnlyFilter(admin.SimpleListFilter):
    """Глобальный список всех карточек с возможными дублями."""
    title = 'Возможные дубли'
    parameter_name = 'presumed_duplicates'

    def lookups(self, request, model_admin):
        if self.value() == 'yes':
            return [('yes', 'Только с возможными дублями')]
        return ()

    def queryset(self, request, queryset):
        if self.value() != 'yes' or request.GET.get('duplicate_of'):
            return queryset
        if request.method == 'POST' and request.POST.get('action') == 'merge_duplicates_action':
            return queryset
        pks = presumed_duplicates_queryset().values_list('pk', flat=True)
        return queryset.filter(pk__in=pks)


class CopyInvitationsForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    source_event = forms.ModelChoiceField(
        queryset=ModuleInstance.objects.all(),
        label='Выберите источник приглашений',
        required=True,
        widget=forms.Select(attrs={
            'class': 'admin-autocomplete',
            'data-autocomplete-light-function': 'select2',
            'data-placeholder': 'Начните вводить название мероприятия...',
            'style': 'max-width: 500px; width: 500px;'
        })
    )
    
    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css',)
        }
        js = ()

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
    fk_name = 'contact'
    fields = ['social_network', 'external_id', 'subscribers']
    autocomplete_fields = ['social_network']
    extra = 0
    verbose_name = 'Контакт'
    verbose_name_plural = "Контакты"


class InfoCommunityInline(admin.TabularInline):
    model = InfoContact
    fk_name = 'community'
    fields = ['social_network', 'external_id', 'subscribers']
    autocomplete_fields = ['social_network']
    extra = 0
    verbose_name = 'Соцсеть сообщества'
    verbose_name_plural = "Соцсети сообщества"


class CommunityMemberInline(admin.TabularInline):
    model = CommunityMember
    fields = ['contact']
    autocomplete_fields = ['contact']
    extra = 0
    verbose_name = 'Участник'
    verbose_name_plural = "Участники"


class CommunityMemberForContactInline(admin.TabularInline):
    model = CommunityMember
    fk_name = 'contact'
    fields = ['community', 'community_members_count']
    readonly_fields = ['community_members_count']
    autocomplete_fields = ['community']
    extra = 0
    verbose_name = 'Сообщество'
    verbose_name_plural = "Сообщества"

    def community_members_count(self, obj):
        if obj and obj.community_id:
            return obj.community.communitymember_set.count()
        return '—'
    community_members_count.short_description = 'Участников'

# Человек
@admin.register(Contact)
class ContactAdmin(BaseAdminPage, ImportExportModelAdmin, ImportExportActionModelAdmin):
    change_list_template = 'admin/event/contact_change_list.html'
    import_export_change_list_template = 'admin/event/contact_change_list_import_export.html'
    actions = ['merge_duplicates_action', 'delete_selected']
    list_display = ('get_fio', 'company', 'category', 'type_guest', 'producer', 'photo_preview')
    list_editable = ('company', 'category', 'type_guest', 'producer')
    list_filter = (
        PresumedDuplicatesOnlyFilter,
        DuplicateOfContactFilter,
        CompanyContactFilter,
        CategoryContactFilter,
        TypeGuestContactFilter,
        ProducerContactFilter,
    )
    readonly_fields = (
        'find_duplicates_button',
        'get_fio',
        'photo_preview',
        'registered_events_list',
        'checkin_events_list',
    )
    autocomplete_fields = ['company', 'category', 'type_guest', 'producer']
    search_fields = ['last_name', 'first_name', 'middle_name', 'nickname']
    inlines = [InfoContactInline, CommunityMemberForContactInline]
    show_change_form_export = False
    list_max_show_all = 10000
    fieldsets = (
        ('Возможные дубли', {
            'fields': ['find_duplicates_button'],
            'description': (
                'Поиск других карточек с похожими ФИО, ником или контактами в соцсетях. '
                'Из найденного списка отметьте записи и выполните действие «Объединить дубли».'
            ),
        }),
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

    def _has_presumed_duplicates(self, obj):
        if not obj or not obj.pk:
            return False
        return duplicate_candidates_queryset(obj).exclude(pk=obj.pk).exists()

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(self.fieldsets)
        if not self._has_presumed_duplicates(obj):
            fieldsets = [fs for fs in fieldsets if fs[0] != 'Возможные дубли']
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not self._has_presumed_duplicates(obj):
            fields = [f for f in fields if f != 'find_duplicates_button']
        return fields

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/download_template_import_cont/', self.admin_site.admin_view(self.download_template_import_cont), name="template_import_cont"),
        ]
        return custom_urls + urls

    def download_template_import_cont(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "templates", "import_cont.xlsx")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="import_cont.xlsx")

    def changelist_view(self, request, extra_context=None):
        # Старые ссылки с possible_duplicates_of → duplicate_of
        legacy_pk = request.GET.get('possible_duplicates_of')
        if legacy_pk and not request.GET.get('duplicate_of'):
            params = request.GET.copy()
            params['duplicate_of'] = legacy_pk
            if 'possible_duplicates_of' in params:
                del params['possible_duplicates_of']
            return HttpResponseRedirect(f'{request.path}?{params.urlencode()}')

        anchor_pk = request.GET.get('duplicate_of')
        global_duplicates = request.GET.get('presumed_duplicates') == 'yes'
        if anchor_pk:
            try:
                anchor_pk_int = int(anchor_pk)
                anchor = Contact.objects.get(pk=anchor_pk_int)
                count = duplicate_candidates_queryset(anchor).count()
                clear_url = reverse('admin:event_contact_changelist')
                change_url = reverse('admin:event_contact_change', args=[anchor.pk])
                self.message_user(
                    request,
                    format_html(
                        'Показаны <strong>предположительные дубли</strong> для '
                        '<a href="{}">{}</a> ({} {}). '
                        'Совпадения: фамилия+имя, имя+отчество, никнейм, контакт в соцсетях. '
                        'Отметьте нужные строки → «Объединить дубли». '
                        '<a href="{}">Показать весь справочник</a>.',
                        change_url,
                        anchor.get_fio(),
                        count,
                        self.model._meta.verbose_name_plural,
                        clear_url,
                    ),
                    level=messages.INFO,
                )
            except (Contact.DoesNotExist, ValueError, TypeError):
                self.message_user(request, 'Карточка для поиска дублей не найдена.', level=messages.WARNING)
        elif global_duplicates and request.method != 'POST':
            count = presumed_duplicates_queryset().count()
            clear_url = reverse('admin:event_contact_changelist')
            self.message_user(
                request,
                format_html(
                    'Показаны все карточки с <strong>возможными дублями</strong> '
                    '({} {}). Совпадения: фамилия+имя, имя+отчество, никнейм, контакт в соцсетях. '
                    'Отметьте нужные строки → «Объединить дубли». '
                    '<a href="{}">Показать весь справочник</a>.',
                    count,
                    self.model._meta.verbose_name_plural,
                    clear_url,
                ),
                level=messages.INFO,
            )
        return super().changelist_view(request, extra_context)

    def _duplicate_match_hint_column(self, anchor=None, *, global_mode=False):
        def column(obj):
            if global_mode:
                reasons = get_global_duplicate_reasons(obj)
            elif anchor is not None:
                reasons = get_duplicate_match_reasons(anchor, obj)
            else:
                return '—'
            return ', '.join(reasons) if reasons else '—'

        column.short_description = 'Совпадение'
        return column

    def get_list_display(self, request):
        display = list(super().get_list_display(request))
        duplicate_of = request.GET.get('duplicate_of')
        if duplicate_of:
            try:
                anchor = Contact.objects.get(pk=int(duplicate_of))
            except (Contact.DoesNotExist, ValueError, TypeError):
                anchor = None
            if anchor is not None:
                display.insert(1, self._duplicate_match_hint_column(anchor))
        elif request.GET.get('presumed_duplicates') == 'yes':
            display.insert(1, self._duplicate_match_hint_column(global_mode=True))
        return display

    def find_duplicates_button(self, obj):
        if not obj.pk:
            return 'Сохраните карточку, затем можно искать дубли.'
        count = duplicate_candidates_queryset(obj).count()
        others = max(count - 1, 0)
        url = reverse('admin:event_contact_changelist') + f'?duplicate_of={obj.pk}'
        label = f'Найти возможные дубли ({others})' if others else 'Найти возможные дубли'
        return format_html(
            '<a href="{}" style="display:inline-block;background:none;color:gray;border:2px solid gray;'
            'padding:6px 14px;border-radius:3px;font-size:12px;text-decoration:none;">{}</a>',
            url,
            label,
        )

    find_duplicates_button.short_description = 'Поиск дублей'

    MERGE_CONTACTS_MAX = 20

    @admin.action(description='Объединить дубли')
    def merge_duplicates_action(self, request, queryset):
        selected_ids = request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        if not selected_ids:
            if 'apply' in request.POST:
                self.message_user(
                    request,
                    'Не удалось определить выбранные карточки. Вернитесь в список и выберите людей заново.',
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(reverse('admin:event_contact_changelist'))
            selected_ids = [str(pk) for pk in queryset.values_list('pk', flat=True)]
        selected_ids = list(dict.fromkeys(selected_ids))
        if len(selected_ids) < 2:
            self.message_user(
                request,
                'Не выбраны записи для объединения: отметьте минимум двух человек.',
                level=messages.ERROR,
            )
            return
        if len(selected_ids) > self.MERGE_CONTACTS_MAX:
            self.message_user(
                request,
                f'Слишком много карточек для объединения ({len(selected_ids)}). '
                f'Отметьте не более {self.MERGE_CONTACTS_MAX} человек.',
                level=messages.ERROR,
            )
            return

        contacts = list(
            Contact.objects.filter(pk__in=selected_ids)
            .select_related('company', 'category', 'type_guest', 'producer')
            .annotate(
                actions_count=Count('action_set', distinct=True),
                info_count=Count('infocontact_set', distinct=True),
                communities_count=Count('communitymember_set', distinct=True),
            )
            .order_by('last_name', 'first_name')
        )
        if len(contacts) < 2:
            self.message_user(
                request,
                'Не выбраны записи для объединения: отметьте минимум двух человек.',
                level=messages.ERROR,
            )
            return

        form = None
        if 'apply' in request.POST:
            form = ContactMergeForm(request.POST, contacts=contacts)
            if form.is_valid():
                primary = form.cleaned_data['primary_contact']
                duplicates = [c for c in contacts if c.pk != primary.pk]
                field_values = {
                    'last_name': form.cleaned_data['last_name'],
                    'first_name': form.cleaned_data['first_name'],
                    'middle_name': form.cleaned_data['middle_name'],
                    'nickname': form.cleaned_data['nickname'],
                    'company': form.cleaned_data['company'],
                    'category': form.cleaned_data['category'],
                    'type_guest': form.cleaned_data['type_guest'],
                    'producer': form.cleaned_data['producer'],
                    'comment': form.cleaned_data['comment'],
                }
                try:
                    removed = merge_contacts(
                        primary,
                        duplicates,
                        field_values,
                        photo_from_contact_id=form.cleaned_data['photo_source'],
                    )
                except ValueError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                except IntegrityError:
                    self.message_user(
                        request,
                        'Не удалось объединить: конфликт уникальных данных (ФИО или регистрация на мероприятие). '
                        'Измените ФИО или обратитесь к администратору.',
                        level=messages.ERROR,
                    )
                else:
                    change_url = reverse('admin:event_contact_change', args=[primary.pk])
                    self.message_user(
                        request,
                        format_html(
                            'Объединение выполнено: карточка «<a href="{}">{}</a>» сохранена, '
                            'удалено дубликатов: {}.',
                            change_url,
                            primary.get_fio(),
                            removed,
                        ),
                    )
                    return HttpResponseRedirect(change_url)

        if not form:
            form = ContactMergeForm(
                initial={'_selected_action': selected_ids},
                contacts=contacts,
            )

        contact_stats = [
            {
                'contact': contact,
                'label': format_contact_merge_label(contact),
                'actions_count': contact.actions_count,
                'info_count': contact.info_count,
                'communities_count': contact.communities_count,
            }
            for contact in contacts
        ]

        context = {
            'title': 'Объединение дублей',
            'contact_stats': contact_stats,
            'form': form,
            'action_name': 'merge_duplicates_action',
            'opts': self.model._meta,
        }
        return render(request, 'event/merge_contacts.html', context)

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


@admin.register(Community)
class CommunityAdmin(BaseAdminPage):
    list_display = ('name', 'members_count_link')
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ('members_socials_summary',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(members_count=Count('communitymember'))

    def members_count_link(self, obj):
        count = obj.communitymember_set.count()
        url = reverse('admin:event_community_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, count)
    members_count_link.short_description = 'Участников'
    members_count_link.admin_order_field = 'members_count'
    inlines = [InfoCommunityInline, CommunityMemberInline]
    fieldsets = (
        (None, {
            'fields': ('name',)
        }),
        ('Участники и их соцсети', {
            'fields': ('members_socials_summary',),
            'description': 'Сводка по соцсетям участников сообщества (для людей — из карточки человека)',
        }),
    )

    def members_socials_summary(self, obj):
        """Выводит список участников сообщества с их соцсетями."""
        if not obj or not obj.pk:
            return format_html('<p style="color: #888;">Сохраните сообщество, чтобы увидеть участников.</p>')

        members = CommunityMember.objects.filter(community=obj).select_related('contact').order_by('contact__last_name', 'contact__first_name')
        if not members.exists():
            return format_html('<p style="color: #888;">Нет участников. Добавьте их в блоке «Участники» ниже.</p>')

        blocks = []
        for m in members:
            contact = m.contact
            contact_url = reverse('admin:event_contact_change', args=[contact.pk])
            contact_name = contact.get_fio() or f'#{contact.pk}'

            # Соцсети человека (InfoContact где contact задан, community пустой)
            infos = InfoContact.objects.filter(contact=contact, community__isnull=True).select_related('social_network').order_by('social_network__name')

            lines = []
            for info in infos:
                sn_name = info.social_network.name if info.social_network else '—'
                ext = (info.external_id or '').strip()
                subs = f' ({info.subscribers:,})' if info.subscribers is not None else ''
                if ext.startswith(('http://', 'https://')):
                    line = format_html(
                        '• <a href="{}" target="_blank" rel="noopener">{}</a>{}',
                        ext, sn_name, subs
                    )
                else:
                    line = format_html('• {} — {} {}', sn_name, ext, subs)
                lines.append(line)

            if lines:
                socials_html = mark_safe('<br>'.join(str(line) for line in lines))
            else:
                socials_html = format_html('<span style="color: #999;">нет соцсетей</span>')

            block = format_html(
                '<div style="margin-bottom: 14px; padding: 10px 12px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #417690;">'
                '<strong><a href="{}">{}</a></strong><br>'
                '<div style="margin-top: 6px; margin-left: 4px; font-size: 13px; color: #333;">{}</div>'
                '</div>',
                contact_url, contact_name, socials_html
            )
            blocks.append(block)

        return format_html('<div style="max-width: 600px;">{}</div>', format_html_join('', '{}', ((b,) for b in blocks)))

    members_socials_summary.short_description = 'Участники и соцсети'

    class Media:
        js = ('js/admin.js',)  # Костыль для замены УДАЛЕНО на УДАЛИТЬ

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
class ModuleInstanceAdmin(GuestsTableMixin, BaseAdminPage, ExportActionModelAdmin):
    form = ModuleInstanceForm
    resource_class = EventExport
    search_fields = ['name', 'address']
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('autocomplete-events/', self.admin_site.admin_view(self.autocomplete_events_view), name='autocomplete_events'),
        ]
        return custom_urls + urls
    
    def autocomplete_events_view(self, request):
        """Кастомный autocomplete для выбора мероприятий"""
        from django.http import JsonResponse
        term = request.GET.get('term', '')
        
        queryset = ModuleInstance.objects.all()
        if term:
            queryset = queryset.filter(name__icontains=term)
        
        # Ограничиваем результаты
        queryset = queryset[:20]
        
        results = [{'id': obj.pk, 'text': str(obj)} for obj in queryset]
        
        return JsonResponse({
            'results': results,
            'pagination': {'more': False}
        })
    
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
            form = CopyInvitationsForm(request.POST)
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
                initial={'_selected_action': selected_ids}
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
    list_display = ('contact', 'photo_contact', 'event', 'update_date', 'get_buttons_action')
    list_filter = (ModuleInstanceFilter, ContactFilter, ProducerActionFilter, 'action_type', 'event__date_start')
    search_fields = ['contact__last_name', 'contact__first_name', 'contact__middle_name']
    autocomplete_fields = ['contact', 'event']
    readonly_fields = ('action_type', 'create_date', 'update_date', 'create_user', 'update_user', 'audit_log_table')
    list_per_page = 100
    view_on_site = False
    show_change_form_export = False
    list_max_show_all = 10000

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

    # Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context.update(service.get_params_visible_buttons_save(request, obj))
        return super().render_change_form(request, context, add, change, form_url, obj)

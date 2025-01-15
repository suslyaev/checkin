from django.contrib import admin
import event.services as service
from .models import CustomUser, Company, CategoryContact, Contact, ModuleInstance, Action, Checkin
from .forms import ActionForm, CheckinOrCancelForm
from django.shortcuts import render
from django.http import HttpResponseRedirect
from import_export.admin import ExportActionModelAdmin, ImportExportActionModelAdmin
from .resources import ContactResource, CheckinResource
from admin_auto_filters.filters import AutocompleteFilter
from django.utils.html import format_html
from django.urls import reverse
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    search_fields = ['username', 'first_name', 'last_name']  # Поля для поиска
    list_display = ['username', 'first_name', 'last_name', 'email']  # Для отображения в списке

# Форма для модели ModuleInstance
class ModuleInstanceForm(forms.ModelForm):
    class Meta:
        model = ModuleInstance
        fields = '__all__'
        widgets = {
            'admins': FilteredSelectMultiple('Администраторы', is_stacked=False),
            'checkers': FilteredSelectMultiple('Проверяющие', is_stacked=False),
        }


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
class ContactAdmin(BaseAdminPage, ImportExportActionModelAdmin):
    resource_class = ContactResource
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

# Компания
@admin.register(Company)
class CompanyAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment')
    list_editable = ('name', 'comment')
    search_fields = ['name']

# Категория
@admin.register(CategoryContact)
class CategoryContactAdmin(BaseAdminPage):
    list_display = ('id', 'name', 'comment')
    list_editable = ('name', 'comment')
    search_fields = ['name']

# Событие
@admin.register(ModuleInstance)
class ModuleInstanceAdmin(ExportActionModelAdmin):
    search_fields = ['get_name_module_instance']
    fieldsets = (
        ('Что', {
            'fields': [('name',)]
        }),
        ('Где', {
            'fields': [('address',)]
        }),
        ('Когда', {
            'fields': [('date_start', 'date_end')]
        }),
        ('Администрирование', {
            'fields': [('admins', 'checkers')]
        }),
    )
    autocomplete_fields = ['admins', 'checkers',]
    list_display = ('name', 'date_start', 'date_end')
    inlines = [RegistrationInline, CheckinInline, CancelInline]
    save_on_top = True
    list_per_page = 25
    view_on_site = False

# Чекин
@admin.register(Checkin)
class CheckinAdmin(BaseAdminPage, ImportExportActionModelAdmin):
    resource_class = CheckinResource
    search_fields = ['contact__fio', 'module_instance__module__name']
    list_display = ('contact', 'photo_contact', 'module_instance', 'get_buttons_action',)
    autocomplete_fields = ['contact', 'module_instance']
    list_filter = (ModuleInstanceFilter, )
    list_per_page = 25
    view_on_site = False

    class Media:
        js = ('js/checkin_list.js',)

    def get_fields(self, request, obj=None):
        
        if obj:  # Редактирование записи
            return [
                ('action_type',),
                ('module_instance',),
                ('contact',),
                ('photo_contact',),
                ('get_buttons_action',),
            ]
        else:  # Создание новой записи
            return [
                ('contact',),
                ('module_instance',),
            ]
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование записи
            return ['contact', 'action_type', 'action_date', 'is_last_state', 'module_instance', 'get_buttons_action', 'photo_contact']
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
        return Checkin.objects.filter(is_last_state=True, action_type='new')


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

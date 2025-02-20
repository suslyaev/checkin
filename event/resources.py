from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.results import RowResult
from django.utils.safestring import mark_safe
from .models import Contact, CompanyContact, CategoryContact, StatusContact, Checkin, ModuleInstance

class ForeignKeyWidgetWithFallback(ForeignKeyWidget):
    """ Виджет, создающий новую запись, если она не найдена. """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        value = str(value).strip()
        try:
            return self.model.objects.get(**{self.field: value})
        except self.model.DoesNotExist:
            return self.model.objects.create(**{self.field: value})

class CheckinResource(resources.ModelResource):
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    event = fields.Field(column_name='event', attribute='event', widget=ForeignKeyWidgetWithFallback(ModuleInstance, 'name'))

    last_name = fields.Field(column_name='last_name', attribute='contact__last_name')
    first_name = fields.Field(column_name='first_name', attribute='contact__first_name')
    middle_name = fields.Field(column_name='middle_name', attribute='contact__middle_name')

    company = fields.Field(column_name='company', attribute='contact__company', widget=ForeignKeyWidgetWithFallback(CompanyContact, 'name'))
    category = fields.Field(column_name='category', attribute='contact__category', widget=ForeignKeyWidgetWithFallback(CategoryContact, 'name'))
    status = fields.Field(column_name='status', attribute='contact__status', widget=ForeignKeyWidgetWithFallback(StatusContact, 'name'))
    comment = fields.Field(column_name='comment', attribute='contact__comment')

    def import_row(self, row, *args, **kwargs):
        row_number = kwargs.pop('row_number', None)

        last_name = (row.get('last_name') or '').strip()
        first_name = (row.get('first_name') or '').strip()
        middle_name = (row.get('middle_name') or '').strip()
        company_name = (row.get('company') or '').strip()
        category_name = (row.get('category') or '').strip()
        status_name = (row.get('status') or '').strip()
        comment = (row.get('comment') or '').strip()
        event_name = (row.get('event') or '').strip()

        result = self.get_row_result_class()()

        if not last_name or not first_name:
            result.import_type = RowResult.IMPORT_TYPE_EMPTY
            result.object_id = ''
            result.object_repr = 'No Last/First Name'
            result.diff = []
            return result

        # Поиск или создание контакта
        contact, created = Contact.objects.get_or_create(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            defaults={}
        )

        # Сохранение "старых" значений
        old_company = contact.company.name if contact.company else None
        old_category = contact.category.name if contact.category else None
        old_status = contact.status.name if contact.status else None
        old_comment = contact.comment if contact.comment else None

        # Обновление полей у контакта
        if company_name:
            company_obj, _ = CompanyContact.objects.get_or_create(name=company_name)
            contact.company = company_obj
        if category_name:
            category_obj, _ = CategoryContact.objects.get_or_create(name=category_name)
            contact.category = category_obj
        if status_name:
            status_obj, _ = StatusContact.objects.get_or_create(name=status_name)
            contact.status = status_obj
        if comment:
            contact.comment = comment
        contact.save()

        # Настройка результата
        result.import_type = RowResult.IMPORT_TYPE_NEW if created else RowResult.IMPORT_TYPE_UPDATE
        result.object_id = contact.pk
        result.object_repr = f"{contact.last_name} {contact.first_name}"

        diff_list = []
        diff_list.append('-')
        if not event_name:
            diff_list.append('-')
        else:
            diff_list.append(event_name)
        diff_list.append(last_name)
        diff_list.append(first_name)
        diff_list.append(middle_name)

        if company_name:
            if old_company != company_name:
                diff_html = f'<del style="color: red;">{old_company}</del> → <span style="color: green; font-weight: bold;">{company_name}</span>'
                diff_list.append(mark_safe(diff_html))  # Используем mark_safe
            else:
                diff_list.append(company_name)
        
        if category_name:
            if old_category != category_name:
                diff_html = f'<del style="color: red;">{old_category}</del> → <span style="color: green; font-weight: bold;">{category_name}</span>'
                diff_list.append(mark_safe(diff_html))  # Используем mark_safe
            else:
                diff_list.append(category_name)
        
        if status_name:
            if old_status != status_name:
                diff_html = f'<del style="color: red;">{old_status}</del> → <span style="color: green; font-weight: bold;">{status_name}</span>'
                diff_list.append(mark_safe(diff_html))  # Используем mark_safe
            else:
                diff_list.append(status_name)
        
        if category_name:
            if comment == '':
                comment = None
            if old_comment != comment:
                diff_html = f'<del style="color: red;">{old_comment}</del> → <span style="color: green; font-weight: bold;">{comment}</span>'
                diff_list.append(mark_safe(diff_html))  # Используем mark_safe
            else:
                diff_list.append(comment)

        result.diff = diff_list

        # Если event не указан, не создаем Checkin
        if not event_name:
            return result

        # Создаем Checkin
        checkin, _ = Checkin.objects.get_or_create(
            contact=contact,
            event=ModuleInstance.objects.get(name=event_name),
            defaults={'action_type': 'new', 'is_last_state': True}
        )

        return result

    class Meta:
        model = Checkin
        fields = ('id', 'event', 'last_name', 'first_name', 'middle_name', 'company', 'category', 'status', 'comment')
        export_order = ('id', 'event', 'last_name', 'first_name', 'middle_name', 'company', 'category', 'status', 'comment')

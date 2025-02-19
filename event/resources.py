from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.results import RowResult
from .models import Contact, CompanyContact, CategoryContact, Checkin, ModuleInstance

class ForeignKeyWidgetWithFallback(ForeignKeyWidget):
    """
    Виджет, возвращающий объект ForeignKey, создавая новую запись,
    если она не найдена по указанному полю (self.field).
    """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        value = str(value).strip()
        try:
            return self.model.objects.get(**{self.field: value})
        except self.model.DoesNotExist:
            return self.model.objects.create(**{self.field: value})

class CheckinResource(resources.ModelResource):
    """
    Один ресурс для:
      - Импорта/обновления Контактов (если event пуст),
      - Импорта/обновления Чекинов (если event указан).
    """
    id = fields.Field(
        column_name='id',
        attribute='id',
        readonly=True
    )
    event = fields.Field(
        column_name='event',
        attribute='event',
        widget=ForeignKeyWidgetWithFallback(ModuleInstance, 'name')
    )
    fio = fields.Field(
        column_name='fio',
        attribute='contact',
        widget=ForeignKeyWidgetWithFallback(Contact, 'fio')
    )
    company = fields.Field(
        column_name='company',
        attribute='contact__company',
        widget=ForeignKeyWidgetWithFallback(CompanyContact, 'name')
    )
    category = fields.Field(
        column_name='category',
        attribute='contact__category',
        widget=ForeignKeyWidgetWithFallback(CategoryContact, 'name')
    )
    comment = fields.Field(
        column_name='comment',
        attribute='contact__comment'
    )

    def import_row(self, row, *args, **kwargs):
        """
        - Если event пуст, создаём/обновляем Contact и показываем изменения в diff.
        - Если event заполнен, создаём/обновляем Checkin (через super()).
        """
        # Извлекаем row_number из kwargs, чтобы избежать ошибки "multiple values"
        row_number = kwargs.pop('row_number', None)

        # Считываем данные из Excel
        fio = (row.get('fio') or '').strip()
        company_name = (row.get('company') or '').strip()
        category_name = (row.get('category') or '').strip()
        comment = (row.get('comment') or '').strip()
        event_name = (row.get('event') or '').strip()

        # Создаём результат (RowResult), чтобы настроить вывод в отчёте
        result = self.get_row_result_class()()

        # Если ФИО пустое, считаем строку "EMPTY"
        if not fio:
            result.import_type = RowResult.IMPORT_TYPE_EMPTY
            result.object_id = ''
            result.object_repr = 'No FIO'
            result.diff = []
            return result

        # Ищем или создаём контакт (обрабатываем дубли FIO)
        qs = Contact.objects.filter(fio=fio)
        if qs.count() == 1:
            contact = qs.first()
            created = False
        elif qs.count() == 0:
            contact = Contact.objects.create(fio=fio)
            created = True
        else:
            # Есть несколько контактов с одинаковым FIO
            # Берём первый или выбрасываем ошибку
            contact = qs.first()
            created = False
            # Или:
            # raise Exception(f"Найдено несколько контактов с ФИО='{fio}'")

        # Сохраняем "старые" значения (если хотим отобразить старое -> новое)
        old_company = contact.company.name if contact.company else None
        old_category = contact.category.name if contact.category else None
        old_comment = contact.comment if contact.comment else None

        # Обновляем поля у контакта
        if company_name:
            company_obj, _ = CompanyContact.objects.get_or_create(name=company_name)
            contact.company = company_obj
        if category_name:
            category_obj, _ = CategoryContact.objects.get_or_create(name=category_name)
            contact.category = category_obj
        if comment:
            contact.comment = comment
        contact.save()

        # Настраиваем результат
        result.import_type = RowResult.IMPORT_TYPE_NEW if created else RowResult.IMPORT_TYPE_UPDATE
        result.object_id = contact.pk
        result.object_repr = f"Contact {contact.pk}: {contact.fio}"

        # Собираем diff с СИСТЕМНЫМИ ИМЕНАМИ полей, чтобы Django Import-Export
        # понимал, куда их поставить в таблице отчёта.
        diff_list = []
        # FIO
        diff_list.append(("fio", None, fio))  # Считаем, что старого FIO нет (или тоже fio)
        # COMPANY
        if company_name:
            diff_list.append(("company", old_company, company_name))
        # CATEGORY
        if category_name:
            diff_list.append(("category", old_category, category_name))
        # COMMENT
        if comment:
            diff_list.append(("comment", old_comment, comment))

        result.diff = diff_list

        # Если event пуст -> НЕ создаём Checkin
        if not event_name:
            return result

        # Иначе (event заполнен) -> вызываем super() для создания/обновления Checkin
        checkin_result = super().import_row(row, row_number=row_number, *args, **kwargs)
        return checkin_result

    # Методы для экспорта (dehydrate), если нужна выгрузка
    def dehydrate_event(self, obj):
        return obj.event.name if obj.event else ''

    def dehydrate_fio(self, obj):
        return obj.contact.fio if obj.contact else ''

    def dehydrate_company(self, obj):
        return obj.contact.company.name if obj.contact and obj.contact.company else ''

    def dehydrate_category(self, obj):
        return obj.contact.category.name if obj.contact and obj.contact.category else ''

    def dehydrate_comment(self, obj):
        return obj.contact.comment if obj.contact and obj.contact.comment else ''

    class Meta:
        model = Checkin
        fields = ('id', 'event', 'fio', 'company', 'category', 'comment')
        export_order = ('id', 'event', 'fio', 'company', 'category', 'comment')

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Contact, Company, CategoryContact, Checkin, ModuleInstance


class ForeignKeyWidgetWithFallback(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        # Преобразуем значение в строку
        value = str(value).strip()
        try:
            return self.model.objects.get(**{self.field: value})
        except self.model.DoesNotExist:
            # Создаем запись, если не найдена
            return self.model.objects.create(**{self.field: value})

class ContactResource(resources.ModelResource):
    # Поле для обработки компании
    company = fields.Field(
        column_name='company',
        attribute='company',
        widget=ForeignKeyWidgetWithFallback(Company, 'name')  # Для импорта
    )
    # Поле для обработки категории
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyWidgetWithFallback(CategoryContact, 'name')  # Для импорта
    )

    def dehydrate_company(self, obj):
        """
        Экспорт текстового значения для компании.
        """
        return obj.company.name if obj.company else ''

    def dehydrate_category(self, obj):
        """
        Экспорт текстового значения для категории.
        """
        return obj.category.name if obj.category else ''

    class Meta:
        model = Contact
        fields = ('id', 'fio', 'company', 'category', 'comment')
        export_order = ('id', 'fio', 'company', 'category', 'comment')


class CheckinResource(resources.ModelResource):
    id = fields.Field(
        column_name='id',
        attribute='id',
        readonly=True
    )
    module_instance = fields.Field(
        column_name='module_instance',
        attribute='module_instance',
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
        widget=ForeignKeyWidgetWithFallback(Company, 'name')
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

    def dehydrate_module_instance(self, obj):
        """
        Преобразовать `module_instance` в его имя.
        """
        return obj.module_instance.name if obj.module_instance else ''

    def dehydrate_fio(self, obj):
        """
        Преобразовать `contact` в его ФИО.
        """
        return obj.contact.fio if obj.contact else ''

    def dehydrate_company(self, obj):
        """
        Преобразовать `company` в имя компании.
        """
        return obj.contact.company.name if obj.contact and obj.contact.company else ''

    def dehydrate_category(self, obj):
        """
        Преобразовать `category` в имя категории.
        """
        return obj.contact.category.name if obj.contact and obj.contact.category else ''

    def dehydrate_comment(self, obj):
        """
        Преобразовать комментарий.
        """
        return obj.contact.comment if obj.contact and obj.contact.comment else ''

    class Meta:
        model = Checkin
        fields = ('id', 'module_instance', 'fio', 'company', 'category', 'comment')
        export_order = ('id', 'module_instance', 'fio', 'company', 'category', 'comment')

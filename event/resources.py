from import_export import resources, fields
from django.db import transaction
from import_export.widgets import ForeignKeyWidget
from django.db.models import Q

from .models import Contact, InfoContact, SocialNetwork, ModuleInstance, CompanyContact, CategoryContact, TypeGuestContact, Action

class ForeignKeyGetOrCreateWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        try:
            return self.model.objects.get(**{self.field: value})
        except self.model.DoesNotExist:
            return self.model.objects.create(**{self.field: value})

class ContactResource(resources.ModelResource):
    social_network_name = fields.Field(column_name='Соцсеть')
    social_network_id = fields.Field(column_name='ID соцсети')
    social_network_subscribers = fields.Field(column_name='Подписчики')
    company = fields.Field(
        column_name='company',
        attribute='company',
        widget=ForeignKeyGetOrCreateWidget(CompanyContact, 'name')
    )
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyGetOrCreateWidget(CategoryContact, 'name')
    )
    type_guest = fields.Field(
        column_name='type_guest',
        attribute='type_guest',
        widget=ForeignKeyGetOrCreateWidget(TypeGuestContact, 'name')
    )

    class Meta:
        model = Contact
        fields = (
            'last_name', 'first_name', 'middle_name', 'nickname',
            'company', 'category', 'type_guest', 'comment'
        )
        # Используем уникальные поля для поиска существующего контакта
        import_id_fields = ('last_name', 'first_name', 'middle_name')
        skip_unchanged = True
        use_bulk = False

    def get_instance(self, instance_loader, row):
        last_name = row.get('last_name') or row.get('Фамилия')
        first_name = row.get('first_name') or row.get('Имя')
        middle_name = row.get('middle_name') or row.get('Отчество')
        qs = Contact.objects.filter(
            last_name=last_name or '',
            first_name=first_name or '',
            middle_name=middle_name or ''
        )
        if qs.exists():
            return qs.first()
        return None
    
    def before_import_row(self, row, **kwargs):
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.strip()
        return row

    def after_import_row(self, row, row_result, **kwargs):
        # Обработка соцсетей после сохранения контакта
        social_name = row.get('social_network_name') or row.get('Соцсеть')
        social_id = row.get('social_network_id') or row.get('ID соцсети')
        social_subscribers = row.get('social_network_subscribers') or row.get('Подписчики')
        if social_name and social_id:
            instance = self.get_instance(None, row)
            if instance:
                social_network, _ = SocialNetwork.objects.get_or_create(name=social_name)
                info_contact, created = InfoContact.objects.get_or_create(
                    contact=instance,
                    social_network=social_network,
                    defaults={'external_id': social_id, 'subscribers': social_subscribers}
                )
                if not created:
                    info_contact.external_id = social_id
                    info_contact.subscribers = social_subscribers
                    info_contact.save()
        return row_result

class ActionResource(resources.ModelResource):
    module_name = fields.Field(column_name='Мероприятие')
    last_name = fields.Field(column_name='Фамилия')
    first_name = fields.Field(column_name='Имя')
    middle_name = fields.Field(column_name='Отчество')
    
    class Meta:
        model = Action
        fields = ('module_name', 'last_name', 'first_name', 'middle_name')
        import_id_fields = ()  # id не требуется
        skip_unchanged = True
        use_bulk = False  # обрабатываем строки по одной
    
    def before_import_row(self, row, **kwargs):
        with transaction.atomic():
            request = kwargs.get('user')
            # Нормализация входных данных: убираем пробелы и приводим к стандартному виду
            event_name = (row.get('event') or row.get('Мероприятие') or "").strip()
            last_name = (row.get('last_name') or row.get('Фамилия') or "").strip()
            first_name = (row.get('first_name') or row.get('Имя') or "").strip()
            middle_name = row.get('middle_name') or row.get('Отчество')
            if middle_name:
                middle_name = middle_name.strip()
            
            if not event_name:
                raise ValueError(f"Ошибка: Не указано мероприятие в строке данных: {row}")
            
            event, _ = ModuleInstance.objects.get_or_create(name=event_name)
            
            # Формируем комплексное условие поиска:
            q = Q(last_name__iexact=last_name) & Q(first_name__iexact=first_name)
            # Если отчество задано – требуем совпадения, иначе ищем записи, где отчество не задано
            if middle_name:
                q &= Q(middle_name__iexact=middle_name)
            else:
                q &= (Q(middle_name__isnull=True) | Q(middle_name=''))
            
            contact = Contact.objects.filter(q).first()
            if not contact:
                raise ValueError(f"Ошибка: Не найден человек по указанным данным: {row}")
            
            # Создаем или получаем запись Action
            checkin, created = Action.objects.get_or_create(
                contact=contact, event=event,
                defaults={'create_user': request}
            )
    
class ModuleInstanceResource(resources.ModelResource):
    managers = fields.Field(column_name='managers')
    producers = fields.Field(column_name='producers')
    checkers = fields.Field(column_name='checkers')
    registrations_count = fields.Field(column_name='registrations_count')
    checkins_count = fields.Field(column_name='checkins_count')

    class Meta:
        model = ModuleInstance
        fields = ('name', 'address', 'date_start', 'date_end', 'is_visible', 'managers', 'producers', 'checkers', 'registrations_count', 'checkins_count')
        export_order = ('name', 'address', 'date_start', 'date_end', 'is_visible', 'managers', 'producers', 'checkers', 'registrations_count', 'checkins_count')

    def dehydrate_managers(self, obj):
        """Формирует список менеджеров в формате Фамилия Имя или телефон"""
        return ', '.join([f"{m.last_name} {m.first_name}" if m.last_name and m.first_name else m.phone for m in obj.managers.all()])

    def dehydrate_producers(self, obj):
        """Формирует список продюсеров в формате Фамилия Имя или телефон"""
        return ', '.join([f"{p.last_name} {p.first_name}" if p.last_name and p.first_name else p.phone for p in obj.producers.all()])

    def dehydrate_checkers(self, obj):
        """Формирует список модераторов в формате Фамилия Имя или телефон"""
        return ', '.join([f"{c.last_name} {c.first_name}" if c.last_name and c.first_name else c.phone for c in obj.checkers.all()])

    def dehydrate_registrations_count(self, obj):
        """Считает количество регистраций"""
        return Action.objects.filter(event=obj, action_type__in=['new', 'checkin']).count()

    def dehydrate_checkins_count(self, obj):
        """Считает количество чекинов"""
        return Action.objects.filter(event=obj, action_type='checkin').count()
    
    def dehydrate_is_visible(self, obj):
        """
        Преобразует булево значение is_visible в "Да"/"Нет".
        """
        return "Да" if obj.is_visible else "Нет"


class ActionResourceRead(resources.ModelResource):
    social_networks = fields.Field(column_name='social_networks')
    action_type_display = fields.Field(column_name='action_type_display')
    
    class Meta:
        model = Action
        fields = ('id', 'event__name', 'contact__last_name', 'contact__first_name', 'contact__middle_name',
                  'contact__nickname', 'contact__company__name', 'contact__category__name', 'contact__type_guest__name',
                  'action_type_display', 'update_date', 'create_user__last_name', 'create_user__first_name', 'social_networks')
        export_order = ('id', 'event__name', 'contact__last_name', 'contact__first_name', 'contact__middle_name',
                        'contact__nickname', 'contact__company__name', 'contact__category__name', 'contact__type_guest__name',
                        'action_type_display', 'update_date', 'update_user__last_name', 'update_user__first_name', 'social_networks')

    def dehydrate_social_networks(self, obj):
        """
        Формирует строку с соцсетями в формате:
        "Facebook: 12345 (444), Instagram: 67890 (888)"
        """
        social_networks = InfoContact.objects.filter(contact=obj.contact)
        return ', '.join([f"{s.social_network.name}: {s.external_id} ({s.subscribers})" for s in social_networks])
    
    def dehydrate_action_type_display(self, obj):
        """
        Преобразует тип действия в удобочитаемый формат.
        """
        action_types = {
            'new': 'Регистрация',
            'checkin': 'Чекин'
        }
        return action_types.get(obj.action_type, obj.action_type)

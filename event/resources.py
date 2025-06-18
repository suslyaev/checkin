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

class ContactImport(resources.ModelResource):
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

class ContactExport(resources.ModelResource):
    id = fields.Field(attribute='id', column_name='ID')
    last_name = fields.Field(attribute='last_name', column_name='Фамилия')
    first_name = fields.Field(attribute='first_name', column_name='Имя')
    middle_name = fields.Field(attribute='middle_name', column_name='Отчество')
    nickname = fields.Field(attribute='nickname', column_name='Ник')
    company__name = fields.Field(attribute='company__name', column_name='Компания')
    category__name = fields.Field(attribute='category__name', column_name='Категория')
    type_guest__name = fields.Field(attribute='type_guest__name', column_name='Тип гостя')
    producer__last_name = fields.Field(attribute='producer__last_name', column_name='Фамилия продюсера')
    producer__first_name = fields.Field(attribute='producer__first_name', column_name='Имя продюсера')
    comment = fields.Field(attribute='comment', column_name='Комментарий')
    social_networks = fields.Field(attribute='social_networks', column_name='Соцсети')

    class Meta:
        model = Contact
        fields = ('id', 'last_name', 'first_name', 'middle_name',
                    'nickname', 'company__name', 'category__name', 'type_guest__name',
                    'producer__last_name', 'producer__first_name', 'comment',
                    'social_networks')

    def dehydrate_social_networks(self, obj):
        """
        Формирует строку с соцсетями для выгрузки в формате:
        VK (151627)
        https://vk.com/...

        Instagram (105400)
        https://www.instagram.com/...

        И т.д.
        """
        social_networks = InfoContact.objects.filter(contact=obj)
        parts = []
        for s in social_networks:
            title = f"{s.social_network.name} ({s.subscribers})" if s.subscribers else s.social_network.name
            link = s.external_id or ""
            parts.append(f"{title}\n{link}")
        return '\n\n'.join(parts)
    
class EventExport(resources.ModelResource):
    name = fields.Field(attribute='name', column_name='Наименование')
    address = fields.Field(attribute='address', column_name='Адрес')
    date_start = fields.Field(attribute='date_start', column_name='Дата начала')
    date_end = fields.Field(attribute='date_end', column_name='Дата окончания')
    is_visible = fields.Field(attribute='is_visible', column_name='Видимость на портале')
    managers = fields.Field(attribute='managers', column_name='Менеджеры')
    producers = fields.Field(attribute='producers', column_name='Продюсеры')
    checkers = fields.Field(attribute='checkers', column_name='Модераторы')
    announced_count = fields.Field(attribute='announced_count', column_name='Количество заявленных')
    invited_count = fields.Field(attribute='invited_count', column_name='Количество приглашенных')
    registered_count = fields.Field(attribute='registered_count', column_name='Количество зарегистрированных')
    cancelled_count = fields.Field(attribute='cancelled_count', column_name='Количество отмененных')
    visited_count = fields.Field(attribute='visited_count', column_name='Количество посетивших')

    class Meta:
        model = ModuleInstance
        fields = ('name', 'address', 'date_start', 'date_end', 'is_visible', 'managers', 'producers', 'checkers', 'announced_count', 'invited_count', 'registered_count', 'cancelled_count', 'visited_count')

    def dehydrate_managers(self, obj):
        """Формирует список менеджеров в формате Фамилия Имя или телефон"""
        return ', '.join([f"{m.last_name} {m.first_name}" if m.last_name and m.first_name else m.phone for m in obj.managers.all()])

    def dehydrate_producers(self, obj):
        """Формирует список продюсеров в формате Фамилия Имя или телефон"""
        return ', '.join([f"{p.last_name} {p.first_name}" if p.last_name and p.first_name else p.phone for p in obj.producers.all()])

    def dehydrate_checkers(self, obj):
        """Формирует список модераторов в формате Фамилия Имя или телефон"""
        return ', '.join([f"{c.last_name} {c.first_name}" if c.last_name and c.first_name else c.phone for c in obj.checkers.all()])

    def dehydrate_announced_count(self, obj):
        """Считает количество заявленных"""
        return Action.objects.filter(event=obj, action_type='announced').count()

    def dehydrate_invited_count(self, obj):
        """Считает количество приглашенных"""
        return Action.objects.filter(event=obj, action_type='invited').count()

    def dehydrate_registered_count(self, obj):
        """Считает количество зарегистрированных"""
        return Action.objects.filter(event=obj, action_type='registered').count()
    
    def dehydrate_cancelled_count(self, obj):
        """Считает количество отмененных"""
        return Action.objects.filter(event=obj, action_type='cancelled').count()
    
    def dehydrate_visited_count(self, obj):
        """Считает количество посетивших"""
        return Action.objects.filter(event=obj, action_type='visited').count()
    
    def dehydrate_is_visible(self, obj):
        """
        Преобразует булево значение is_visible в "Да"/"Нет".
        """
        return "Да" if obj.is_visible else "Нет"

class ActionImport(resources.ModelResource):
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

class ActionExport(resources.ModelResource):
    id = fields.Field(attribute='id', column_name='ID')
    event__name = fields.Field(attribute='event__name', column_name='Наименование события')
    contact__last_name = fields.Field(attribute='contact__last_name', column_name='Фамилия')
    contact__first_name = fields.Field(attribute='contact__first_name', column_name='Имя')
    contact__middle_name = fields.Field(attribute='contact__middle_name', column_name='Отчество')
    contact__nickname = fields.Field(attribute='contact__nickname', column_name='Ник')
    contact__company__name = fields.Field(attribute='contact__company__name', column_name='Компания')
    contact__category__name = fields.Field(attribute='contact__category__name', column_name='Категория')
    contact__type_guest__name = fields.Field(attribute='contact__type_guest__name', column_name='Тип гостя')
    contact__producer = fields.Field(attribute='contact__producer', column_name='Продюсер')
    action_type_display = fields.Field(attribute='action_type_display', column_name='Статус')
    create_date = fields.Field(attribute='create_date', column_name='Когда создано')
    update_date = fields.Field(attribute='update_date', column_name='Когда обновлено')
    create_user = fields.Field(attribute='create_user', column_name='Кем создано')
    update_user = fields.Field(attribute='update_user', column_name='Кем обновлено')
    social_networks = fields.Field(attribute='social_networks', column_name='Социальные сети')
    
    class Meta:
        model = Action
        fields = ('id', 'event__name', 'contact__last_name', 'contact__first_name', 'contact__middle_name',
                  'contact__nickname', 'contact__company__name', 'contact__category__name', 'contact__type_guest__name',
                  'contact__producer',
                  'action_type_display', 'create_date', 'update_date', 'create_user', 'update_user', 'social_networks')
        
    def dehydrate_contact__producer(self, obj):
        """Формирует список менеджеров в формате Фамилия Имя или телефон"""
        if obj.contact.producer:
            return f"{obj.contact.producer.last_name} {obj.contact.producer.first_name}"
        else:
            return "-"
    
    def dehydrate_create_user(self, obj):
        """Формирует список менеджеров в формате Фамилия Имя или телефон"""
        return f"{obj.create_user.last_name} {obj.create_user.first_name}"
    
    def dehydrate_update_user(self, obj):
        """Формирует список менеджеров в формате Фамилия Имя или телефон"""
        return f"{obj.update_user.last_name} {obj.update_user.first_name}"

    def dehydrate_social_networks(self, obj):
        """
        Формирует строку с соцсетями для выгрузки в формате:
        VK (151627)
        https://vk.com/...

        Instagram (105400)
        https://www.instagram.com/...

        И т.д.
        """
        social_networks = InfoContact.objects.filter(contact=obj.contact)
        parts = []
        for s in social_networks:
            title = f"{s.social_network.name} ({s.subscribers})" if s.subscribers else s.social_network.name
            link = s.external_id or ""
            parts.append(f"{title}\n{link}")
        return '\n\n'.join(parts)
    
    def dehydrate_action_type_display(self, obj):
        """
        Преобразует тип действия в удобочитаемый формат.
        """
        action_types = {
            'announced': 'Заявлен',
            'invited': 'Приглашён',
            'registered': 'Зарегистрирован',
            'cancelled': 'Отменён',
            'visited': 'Зачекинен',
        }
        return action_types.get(obj.action_type, obj.action_type)

from import_export import resources, fields
from django.db import transaction
from import_export.widgets import ForeignKeyWidget
from django.db.models import Q

from .models import Contact, InfoContact, SocialNetwork, ModuleInstance, Checkin, CompanyContact, CategoryContact, TypeGuestContact, Action

class ContactResource(resources.ModelResource):
    social_network_name = fields.Field(column_name='Соцсеть')
    social_network_id = fields.Field(column_name='ID соцсети')
    social_network_subscribers = fields.Field(column_name='Подписчики')
    company = fields.Field(column_name='Компания', attribute='company', widget=ForeignKeyWidget(CompanyContact, 'name'))
    category = fields.Field(column_name='Категория', attribute='category', widget=ForeignKeyWidget(CategoryContact, 'name'))
    type_guest = fields.Field(column_name='Тип гостя', attribute='type_guest', widget=ForeignKeyWidget(TypeGuestContact, 'name'))
    
    class Meta:
        model = Contact
        fields = ('last_name', 'first_name', 'middle_name', 'nickname', 'company', 'category', 'type_guest', 'comment')
        import_id_fields = ('last_name', 'first_name', 'middle_name', 'nickname')
        skip_unchanged = True
        use_bulk = True
    
    def before_import_row(self, row, **kwargs):
        with transaction.atomic():  # Если что-то пойдет не так, изменения не сохранятся
            last_name = row.get('last_name') or row.get('Фамилия')
            first_name = row.get('first_name') or row.get('Имя')
            middle_name = row.get('middle_name') or row.get('Отчество')
            nickname = row.get('nickname') or row.get('Ник')
            social_name = row.get('social_network_name') or row.get('Соцсеть')
            social_id = row.get('social_network_id') or row.get('ID соцсети')
            social_subscribers = row.get('social_network_subscribers') or row.get('Подписчики')
            company_name = row.get('company') or row.get('Компания')
            category_name = row.get('category') or row.get('Категория')
            type_guest_name = row.get('type_guest') or row.get('Тип гостя')

            if not last_name and not nickname:
                raise ValueError(f"Ошибка: Не указана фамилия или никнейм в строке данных: {row}")
        

            company = CompanyContact.objects.get_or_create(name=company_name)[0] if company_name else None
            category = CategoryContact.objects.get_or_create(name=category_name)[0] if category_name else None
            type_guest = TypeGuestContact.objects.get_or_create(name=type_guest_name)[0] if type_guest_name else None

            contact, created = Contact.objects.get_or_create(
                last_name=last_name or '', 
                first_name=first_name or '', 
                middle_name=middle_name or '', 
                nickname=nickname or '',
                defaults={'company': company, 'category': category, 'type_guest': type_guest, 'comment': row.get('comment') or row.get('Комментарий') or ''}
            )

            if not created:
                contact.company = company
                contact.category = category
                contact.type_guest = type_guest
                contact.comment = row.get('comment') or row.get('Комментарий') or ''
                contact.save()

            if social_name and social_id:
                social_network, _ = SocialNetwork.objects.get_or_create(name=social_name)
                info_contact, created = InfoContact.objects.get_or_create(
                    contact=contact, social_network=social_network, defaults={'external_id': social_id, 'subscribers': social_subscribers})
                if not created:
                    info_contact.external_id = social_id
                    info_contact.subscribers = social_subscribers
                    info_contact.save()

class CheckinResource(resources.ModelResource):
    module_name = fields.Field(column_name='Мероприятие')
    last_name = fields.Field(column_name='Фамилия')
    first_name = fields.Field(column_name='Имя')
    middle_name = fields.Field(column_name='Отчество')
    nickname = fields.Field(column_name='Никнейм')
    
    class Meta:
        model = Checkin
        fields = ('module_name', 'last_name', 'first_name', 'middle_name', 'nickname')
        import_id_fields = ()  # Оставляем пустым, чтобы не требовался id
        skip_unchanged = True
        use_bulk = True
    
    def before_import_row(self, row, **kwargs):
        with transaction.atomic(): 
            request = kwargs.get('user')
            event_name = row.get('event') or row.get('Мероприятие')
            last_name = row.get('last_name') or row.get('Фамилия')
            first_name = row.get('first_name') or row.get('Имя')
            middle_name = row.get('middle_name') or row.get('Отчество')
            nickname = row.get('nickname') or row.get('Никнейм')
            
            if not event_name:
                raise ValueError(f"Ошибка: Не указано мероприятие в строке данных: {row}")
            
            event, _ = ModuleInstance.objects.get_or_create(name=event_name)
            
            contact = None
            if nickname:
                contact = Contact.objects.filter(nickname=nickname).first()

            if not contact and last_name and first_name:
                contact = Contact.objects.filter(
                    last_name=last_name, 
                    first_name=first_name
                ).filter(
                    Q(middle_name=middle_name) | Q(middle_name__isnull=True) | Q(middle_name='')
                ).first()
            
            if not contact:
                raise ValueError(f"Ошибка: Не найден человек по указанным данным: {row}")

            checkin, created = Checkin.objects.get_or_create(
                contact=contact, event=event,
                defaults={'operator': request}
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
        return Action.objects.filter(event=obj, action_type='new').count()

    def dehydrate_checkins_count(self, obj):
        """Считает количество чекинов"""
        return Action.objects.filter(event=obj, action_type='checkin', is_last_state=True).count()
    
    def dehydrate_is_visible(self, obj):
        """
        Преобразует булево значение is_visible в "Да"/"Нет".
        """
        return "Да" if obj.is_visible else "Нет"


class ActionResource(resources.ModelResource):
    social_networks = fields.Field(column_name='social_networks')
    action_type_display = fields.Field(column_name='action_type_display')
    is_last_state_display = fields.Field(column_name='is_last_state_display')
    
    class Meta:
        model = Action
        fields = ('id', 'event__name', 'contact__last_name', 'contact__first_name', 'contact__middle_name',
                  'contact__nickname', 'contact__company__name', 'contact__category__name', 'contact__type_guest__name',
                  'action_type_display', 'action_date', 'operator__last_name', 'operator__first_name', 'is_last_state_display',
                  'social_networks')
        export_order = ('id', 'event__name', 'contact__last_name', 'contact__first_name', 'contact__middle_name',
                        'contact__nickname', 'contact__company__name', 'contact__category__name', 'contact__type_guest__name',
                        'action_type_display', 'action_date', 'operator__last_name', 'operator__first_name', 'is_last_state_display',
                        'social_networks')

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

    def dehydrate_is_last_state_display(self, obj):
        """
        Преобразует булево значение is_last_state в "Да"/"Нет".
        """
        return "Да" if obj.is_last_state else "Нет"

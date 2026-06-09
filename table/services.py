from django.db import transaction, IntegrityError
from django.db.models import Q

from event.models import (
    Action,
    Contact,
    CompanyContact,
    CategoryContact,
    TypeGuestContact,
    ModuleInstance,
    CustomUser,
    STATUS_MODEL,
)

STATUS_LABELS = dict(STATUS_MODEL)
STATUS_BY_LABEL = {label: key for key, label in STATUS_MODEL}


def serialize_contact(contact):
    return {
        'id': contact.id,
        'last_name': contact.last_name or '',
        'first_name': contact.first_name or '',
        'middle_name': contact.middle_name or '',
        'nickname': contact.nickname or '',
        'company': contact.company.name if contact.company else '',
        'category': contact.category.name if contact.category else '',
        'type_guest': contact.type_guest.name if contact.type_guest else '',
        'producer': (
            f'{contact.producer.last_name} {contact.producer.first_name}'.strip()
            if contact.producer else ''
        ),
        'comment': contact.comment or '',
    }


def _resolve_producer(name):
    name = (name or '').strip()
    if not name:
        return None
    parts = name.split()
    if len(parts) >= 2:
        return CustomUser.objects.filter(
            last_name__iexact=parts[0],
            first_name__iexact=parts[1],
            groups__name='Продюсер',
        ).first()
    return CustomUser.objects.filter(
        last_name__iexact=parts[0],
        groups__name='Продюсер',
    ).first()


def save_contact(data, contact_id=None):
    last_name = (data.get('last_name') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    if not last_name or not first_name:
        raise ValueError('Фамилия и имя обязательны')

    with transaction.atomic():
        if contact_id:
            contact = Contact.objects.get(pk=contact_id)
        else:
            contact = Contact()

        contact.last_name = last_name
        contact.first_name = first_name
        contact.middle_name = (data.get('middle_name') or '').strip() or None
        contact.nickname = (data.get('nickname') or '').strip() or None
        contact.comment = (data.get('comment') or '').strip() or None

        company_name = (data.get('company') or '').strip()
        contact.company = (
            CompanyContact.objects.get_or_create(name=company_name)[0]
            if company_name else None
        )

        category_name = (data.get('category') or '').strip()
        contact.category = (
            CategoryContact.objects.get_or_create(name=category_name)[0]
            if category_name else None
        )

        type_guest_name = (data.get('type_guest') or '').strip()
        contact.type_guest = (
            TypeGuestContact.objects.get_or_create(name=type_guest_name)[0]
            if type_guest_name else None
        )

        contact.producer = _resolve_producer(data.get('producer'))

        try:
            contact.save()
        except FileNotFoundError:
            contact.photo = None
            contact.save()

        return contact


def serialize_event(event):
    return {
        'id': event.id,
        'name': event.name or '',
        'address': event.address or '',
        'date_start': event.date_start.isoformat(sep=' ', timespec='minutes') if event.date_start else '',
        'date_end': event.date_end.isoformat(sep=' ', timespec='minutes') if event.date_end else '',
        'is_visible': 'Да' if event.is_visible else 'Нет',
    }


def save_event(data, event_id=None):
    name = (data.get('name') or '').strip()
    if not name:
        raise ValueError('Название обязательно')

    with transaction.atomic():
        if event_id:
            event = ModuleInstance.objects.get(pk=event_id)
        else:
            event = ModuleInstance()
        event.name = name
        event.address = (data.get('address') or '').strip() or None
        event.is_visible = (data.get('is_visible') or '').strip().lower() in ('да', '1', 'true', 'yes')
        event.save()
        return event


def serialize_reference(item):
    return {
        'id': item.id,
        'name': item.name or '',
        'comment': getattr(item, 'comment', '') or '',
    }


def save_reference(model, data, item_id=None):
    name = (data.get('name') or '').strip()
    if not name:
        raise ValueError('Название обязательно')
    with transaction.atomic():
        if item_id:
            item = model.objects.get(pk=item_id)
        else:
            item = model()
        item.name = name
        if hasattr(item, 'comment'):
            item.comment = (data.get('comment') or '').strip() or None
        item.save()
        return item


def autocomplete_reference(model, term=''):
    qs = model.objects.all().order_by('name')
    if term:
        qs = qs.filter(name__icontains=term)
        limit = 50
    else:
        limit = 1000
    return [{'id': o.id, 'name': o.name} for o in qs[:limit]]


def serialize_action(action):
    contact = action.contact
    return {
        'id': action.id,
        'contact_id': contact.id if contact else None,
        'event': action.event.name if action.event else '',
        'last_name': (contact.last_name or '') if contact else '',
        'first_name': (contact.first_name or '') if contact else '',
        'middle_name': (contact.middle_name or '') if contact else '',
        'nickname': (contact.nickname or '') if contact else '',
        'company': contact.company.name if contact and contact.company else '',
        'category': contact.category.name if contact and contact.category else '',
        'type_guest': contact.type_guest.name if contact and contact.type_guest else '',
        'producer': (
            f'{contact.producer.last_name} {contact.producer.first_name}'.strip()
            if contact and contact.producer else ''
        ),
        'action_type': action.action_type or 'announced',
        'comment': action.comment or '',
        'update_date': (
            action.update_date.strftime('%d.%m.%Y %H:%M')
            if action.update_date else ''
        ),
    }


def _resolve_event(name):
    name = (name or '').strip()
    if not name:
        return None
    return ModuleInstance.objects.filter(name__iexact=name).first()


def _find_or_create_contact(data):
    last_name = (data.get('last_name') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    middle_name = (data.get('middle_name') or '').strip()

    existing = Contact.objects.filter(
        last_name__iexact=last_name,
        first_name__iexact=first_name,
    ).first()

    if existing:
        if not middle_name or not existing.middle_name or existing.middle_name.lower() == middle_name.lower():
            return existing
    return Contact()


def _apply_contact_fields(contact, data):
    contact.last_name = (data.get('last_name') or '').strip()
    contact.first_name = (data.get('first_name') or '').strip()
    contact.middle_name = (data.get('middle_name') or '').strip() or None
    contact.nickname = (data.get('nickname') or '').strip() or None

    company_name = (data.get('company') or '').strip()
    contact.company = (
        CompanyContact.objects.get_or_create(name=company_name)[0]
        if company_name else None
    )

    category_name = (data.get('category') or '').strip()
    contact.category = (
        CategoryContact.objects.get_or_create(name=category_name)[0]
        if category_name else None
    )

    type_guest_name = (data.get('type_guest') or '').strip()
    contact.type_guest = (
        TypeGuestContact.objects.get_or_create(name=type_guest_name)[0]
        if type_guest_name else None
    )

    contact.producer = _resolve_producer(data.get('producer'))

    try:
        contact.save()
    except FileNotFoundError:
        contact.photo = None
        contact.save()

    return contact


def _normalize_action_type(value):
    value = (value or 'announced').strip()
    if value in STATUS_LABELS:
        return value
    return STATUS_BY_LABEL.get(value, value)


def save_action(data, action_id=None, user=None):
    event_name = (data.get('event') or '').strip()
    if not event_name:
        raise ValueError('Мероприятие обязательно')

    event = _resolve_event(event_name)
    if not event:
        raise ValueError(f'Мероприятие «{event_name}» не найдено')

    last_name = (data.get('last_name') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    if not last_name or not first_name:
        raise ValueError('Фамилия и имя обязательны')

    action_type = _normalize_action_type(data.get('action_type'))
    if action_type not in STATUS_LABELS:
        raise ValueError('Недопустимый статус')

    with transaction.atomic():
        if action_id:
            action = Action.objects.select_related('contact', 'event').get(pk=action_id)
            contact = action.contact or _find_or_create_contact(data)
        else:
            action = Action(create_user=user, update_user=user)
            contact = _find_or_create_contact(data)

        _apply_contact_fields(contact, data)

        action.contact = contact
        action.event = event
        action.action_type = action_type
        action.comment = (data.get('comment') or '').strip() or None
        action.update_user = user

        try:
            action.save()
        except IntegrityError:
            raise ValueError('Человек уже зарегистрирован на данное мероприятие')

        return Action.objects.select_related(
            'contact',
            'contact__company',
            'contact__category',
            'contact__type_guest',
            'contact__producer',
            'event',
        ).get(pk=action.pk)


def autocomplete_events(term=''):
    qs = ModuleInstance.objects.all().order_by('-date_start', 'name')
    if term:
        qs = qs.filter(name__icontains=term)
        limit = 50
    else:
        limit = 500
    return [{'id': e.id, 'name': e.name} for e in qs[:limit]]


def autocomplete_producers(term=''):
    qs = CustomUser.objects.filter(groups__name='Продюсер').distinct()
    if term:
        qs = qs.filter(Q(last_name__icontains=term) | Q(first_name__icontains=term))
        limit = 50
    else:
        limit = 500
    return [
        {'id': u.id, 'name': f'{u.last_name} {u.first_name}'.strip()}
        for u in qs.order_by('last_name', 'first_name')[:limit]
    ]

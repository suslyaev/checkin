import os

from django.core.files.base import ContentFile
from django.db import transaction
from .models import Action, CommunityMember, Contact, InfoContact

ACTION_MERGE_PRIORITY = {
    'visited': 50,
    'registered': 40,
    'invited': 30,
    'announced': 20,
    'cancelled': 10,
}


def action_priority(action):
    return ACTION_MERGE_PRIORITY.get(action.action_type, 0)


def pick_better_action(action_a, action_b):
    pa, pb = action_priority(action_a), action_priority(action_b)
    if pa != pb:
        return (action_a, action_b) if pa > pb else (action_b, action_a)
    if action_a.update_date and action_b.update_date:
        if action_a.update_date != action_b.update_date:
            return (action_a, action_b) if action_a.update_date > action_b.update_date else (action_b, action_a)
    return (action_a, action_b)


def fio_conflicts(last_name, first_name, middle_name, exclude_ids):
    qs = Contact.objects.filter(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
    )
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    return qs.exists()


def _copy_photo_to_contact(target, source_contact):
    if not source_contact or not source_contact.photo:
        return
    source_contact.photo.open('rb')
    try:
        data = source_contact.photo.read()
    finally:
        source_contact.photo.close()
    filename = os.path.basename(source_contact.photo.name)
    if target.photo:
        target.photo.delete(save=False)
    target.photo.save(filename, ContentFile(data), save=False)


def _merge_action_into_primary(primary, action):
    existing = Action.objects.filter(contact=primary, event=action.event).first()
    if not existing:
        action.contact = primary
        action.save(update_fields=['contact'])
        return

    winner, loser = pick_better_action(existing, action)
    if winner.pk == action.pk:
        loser.delete()
        action.contact = primary
        action.save(update_fields=['contact'])
    else:
        action.delete()


def _reassign_related(primary, duplicates):
    duplicate_ids = [c.pk for c in duplicates]

    InfoContact.objects.filter(contact_id__in=duplicate_ids).update(contact=primary)

    for duplicate in duplicates:
        for member in CommunityMember.objects.filter(contact=duplicate):
            if CommunityMember.objects.filter(contact=primary, community=member.community).exists():
                member.delete()
            else:
                member.contact = primary
                member.save(update_fields=['contact'])

    for duplicate in duplicates:
        for action in Action.objects.filter(contact=duplicate).select_related('event'):
            _merge_action_into_primary(primary, action)


@transaction.atomic
def merge_contacts(primary, duplicates, field_values, photo_from_contact_id=None):
    """
    Объединяет дубликаты в primary, переносит связи и удаляет лишние карточки.
    field_values: dict с полями Contact (без photo).
    photo_from_contact_id: pk Contact, с которого скопировать фото, или None — не менять фото.
    Пустая строка в photo_from_contact_id трактуется как «убрать фото».
    """
    duplicate_ids = [c.pk for c in duplicates]
    if primary.pk in duplicate_ids:
        raise ValueError('Основная запись не должна быть среди удаляемых дубликатов.')

    exclude_ids = [primary.pk] + duplicate_ids
    if fio_conflicts(
        field_values['last_name'],
        field_values['first_name'],
        field_values.get('middle_name'),
        exclude_ids=exclude_ids,
    ):
        raise ValueError(
            'Человек с такими ФИО уже есть в системе. Измените ФИО или выберите другую основную запись.'
        )

    for attr, value in field_values.items():
        setattr(primary, attr, value)

    if photo_from_contact_id == '':
        if primary.photo:
            primary.photo.delete(save=False)
        primary.photo = None
    elif photo_from_contact_id:
        source = Contact.objects.filter(pk=photo_from_contact_id).first()
        if source and source.photo:
            _copy_photo_to_contact(primary, source)

    primary.save()
    _reassign_related(primary, duplicates)
    Contact.objects.filter(pk__in=duplicate_ids).delete()
    return len(duplicate_ids)

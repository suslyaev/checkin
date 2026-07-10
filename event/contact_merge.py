import os
from collections import defaultdict

from django.core.files.base import ContentFile
from django.db import transaction
from .models import Action, CommunityMember, Contact, InfoContact

def format_contact_merge_label(contact):
    """Подпись карточки в форме объединения: ФИО, отчество, ник, id."""
    parts = [contact.get_fio()]
    if contact.middle_name:
        parts.append(contact.middle_name)
    if contact.nickname:
        parts.append(f'«{contact.nickname}»')
    parts.append(f'id: {contact.pk}')
    return ', '.join(parts)


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


def _best_action(actions):
    best = actions[0]
    for other in actions[1:]:
        best, _ = pick_better_action(best, other)
    return best


def _reassign_related(primary, duplicates):
    duplicate_ids = [c.pk for c in duplicates]

    InfoContact.objects.filter(contact_id__in=duplicate_ids).update(contact=primary)

    primary_community_ids = set(
        CommunityMember.objects.filter(contact=primary).values_list('community_id', flat=True)
    )
    member_delete_pks = []
    member_reassign_pks = []
    for member in CommunityMember.objects.filter(contact_id__in=duplicate_ids):
        if member.community_id in primary_community_ids:
            member_delete_pks.append(member.pk)
        else:
            member_reassign_pks.append(member.pk)
            primary_community_ids.add(member.community_id)
    if member_delete_pks:
        CommunityMember.objects.filter(pk__in=member_delete_pks).delete()
    if member_reassign_pks:
        CommunityMember.objects.filter(pk__in=member_reassign_pks).update(contact=primary)

    primary_actions = {
        action.event_id: action
        for action in Action.objects.filter(contact=primary).select_related('event')
    }
    dup_by_event = defaultdict(list)
    for action in Action.objects.filter(contact_id__in=duplicate_ids).select_related('event'):
        dup_by_event[action.event_id].append(action)

    action_delete_pks = []
    action_reassign_pks = []
    for event_id, dup_actions in dup_by_event.items():
        best_dup = _best_action(dup_actions)
        for action in dup_actions:
            if action.pk != best_dup.pk:
                action_delete_pks.append(action.pk)

        existing = primary_actions.get(event_id)
        if not existing:
            action_reassign_pks.append(best_dup.pk)
            primary_actions[event_id] = best_dup
            continue

        winner, loser = pick_better_action(existing, best_dup)
        if winner.pk == best_dup.pk:
            action_delete_pks.append(existing.pk)
            action_reassign_pks.append(best_dup.pk)
            primary_actions[event_id] = best_dup
        else:
            action_delete_pks.append(best_dup.pk)

    if action_delete_pks:
        Action.objects.filter(pk__in=action_delete_pks).delete()
    if action_reassign_pks:
        Action.objects.filter(pk__in=action_reassign_pks).update(contact=primary)


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

    if photo_from_contact_id and photo_from_contact_id != '':
        source = Contact.objects.filter(pk=photo_from_contact_id).first()
        if source and source.photo:
            _copy_photo_to_contact(primary, source)

    _reassign_related(primary, duplicates)
    Contact.objects.filter(pk__in=duplicate_ids).delete()

    for attr, value in field_values.items():
        setattr(primary, attr, value)

    if photo_from_contact_id == '':
        if primary.photo:
            primary.photo.delete(save=False)
        primary.photo = None

    primary.save()
    return len(duplicate_ids)

"""
Поиск предположительных дублей контакта для списка в админке.
"""
from django.db.models import Count, Q
from django.db.models.functions import Lower

from .models import Contact, InfoContact


def _norm(value):
    if value is None:
        return ''
    return str(value).strip()


def build_duplicate_candidates_q(contact, *, weak_last_name=False):
    """
    Q-фильтр: другие люди (и сам контакт), похожие на переданную карточку.
    weak_last_name: совпадение только по фамилии (даёт очень длинные списки).
    """
    conditions = Q()
    last = _norm(contact.last_name)
    first = _norm(contact.first_name)
    middle = _norm(contact.middle_name)
    nick = _norm(contact.nickname)

    # Фамилия + имя (отчество может отличаться или быть пустым)
    if last and first:
        conditions |= Q(last_name__iexact=last, first_name__iexact=first)

    # Имя + отчество (ошибка в фамилии при импорте)
    if first and middle:
        conditions |= Q(first_name__iexact=first, middle_name__iexact=middle)

    # Только фамилия — опционально, по умолчанию выключено
    if weak_last_name and last and len(last) >= 3:
        conditions |= Q(last_name__iexact=last)

    # Никнейм
    if nick and len(nick) >= 2:
        conditions |= Q(nickname__iexact=nick)

    # Одинаковый логин/ID в соцсетях (InfoContact человека)
    handles = list(
        InfoContact.objects.filter(contact=contact, community__isnull=True)
        .exclude(external_id='')
        .values_list('external_id', flat=True)
        .distinct()
    )
    if handles:
        related_ids = (
            InfoContact.objects.filter(community__isnull=True, external_id__in=handles)
            .exclude(contact__isnull=True)
            .values_list('contact_id', flat=True)
            .distinct()
        )
        conditions |= Q(pk__in=related_ids)

    if not conditions:
        return Q(pk__in=[])

    return conditions


def duplicate_candidates_queryset(contact, *, weak_last_name=False):
    return Contact.objects.filter(
        build_duplicate_candidates_q(contact, weak_last_name=weak_last_name)
    ).distinct()


def _ids_from_grouped_contacts(group_fields, *, min_field_length=None):
    """Контакты из групп, где по group_fields больше одной записи."""
    ids = set()
    base_qs = Contact.objects.annotate(**{f'{f}_l': Lower(f) for f in group_fields})
    if min_field_length is not None and len(group_fields) == 1:
        base_qs = base_qs.filter(**{f'{group_fields[0]}__length__gte': min_field_length})

    groups = (
        base_qs
        .values(*(f'{f}_l' for f in group_fields))
        .annotate(cnt=Count('pk'))
        .filter(cnt__gt=1)
    )
    for group in groups:
        filters = {f'{f}_l': group[f'{f}_l'] for f in group_fields}
        for empty_field in group_fields:
            filters[f'{empty_field}_l__gt'] = ''
        chunk_qs = Contact.objects.annotate(**{f'{f}_l': Lower(f) for f in group_fields})
        if min_field_length is not None and len(group_fields) == 1:
            chunk_qs = chunk_qs.filter(**{f'{group_fields[0]}__length__gte': min_field_length})
        ids.update(chunk_qs.filter(**filters).values_list('pk', flat=True))
    return ids


def _ids_from_duplicate_social_handles():
    ids = set()
    handles = (
        InfoContact.objects.filter(community__isnull=True)
        .exclude(external_id='')
        .exclude(contact__isnull=True)
        .values('external_id')
        .annotate(cnt=Count('contact_id', distinct=True))
        .filter(cnt__gt=1)
    )
    for row in handles:
        ids.update(
            InfoContact.objects.filter(
                community__isnull=True,
                external_id=row['external_id'],
            )
            .exclude(contact__isnull=True)
            .values_list('contact_id', flat=True)
        )
    return ids


def all_presumed_duplicate_contact_ids():
    """Все карточки, у которых есть хотя бы один предположительный дубль."""
    ids = set()
    ids.update(_ids_from_grouped_contacts(['last_name', 'first_name']))
    ids.update(_ids_from_grouped_contacts(['first_name', 'middle_name']))
    ids.update(_ids_from_grouped_contacts(['nickname'], min_field_length=2))
    ids.update(_ids_from_duplicate_social_handles())
    return ids


def presumed_duplicates_queryset():
    ids = all_presumed_duplicate_contact_ids()
    if not ids:
        return Contact.objects.none()
    return Contact.objects.filter(pk__in=ids)


def get_global_duplicate_reasons(contact):
    """Почему контакт попал в глобальный список возможных дублей."""
    reasons = []
    last = _norm(contact.last_name)
    first = _norm(contact.first_name)
    middle = _norm(contact.middle_name)
    nick = _norm(contact.nickname)

    if last and first:
        if Contact.objects.filter(
            last_name__iexact=last,
            first_name__iexact=first,
        ).exclude(pk=contact.pk).exists():
            reasons.append('фамилия и имя')

    if first and middle:
        if Contact.objects.filter(
            first_name__iexact=first,
            middle_name__iexact=middle,
        ).exclude(pk=contact.pk).exists():
            reasons.append('имя и отчество')

    if nick and len(nick) >= 2:
        if Contact.objects.filter(nickname__iexact=nick).exclude(pk=contact.pk).exists():
            reasons.append('никнейм')

    handles = list(
        InfoContact.objects.filter(contact=contact, community__isnull=True)
        .exclude(external_id='')
        .values_list('external_id', flat=True)
    )
    for handle in handles:
        if InfoContact.objects.filter(
            community__isnull=True,
            external_id=handle,
        ).exclude(contact=contact).exclude(contact__isnull=True).exists():
            reasons.append('контакт в соцсетях')
            break

    return reasons


def get_duplicate_match_reasons(anchor, candidate):
    """Краткие подписи, почему запись попала в подборку."""
    reasons = []
    last = _norm(anchor.last_name)
    first = _norm(anchor.first_name)
    middle = _norm(anchor.middle_name)
    nick = _norm(anchor.nickname)

    c_last = _norm(candidate.last_name)
    c_first = _norm(candidate.first_name)
    c_middle = _norm(candidate.middle_name)
    c_nick = _norm(candidate.nickname)

    if last and first and c_last.lower() == last.lower() and c_first.lower() == first.lower():
        reasons.append('фамилия и имя')
    if first and middle and c_first.lower() == first.lower() and c_middle.lower() == middle.lower():
        reasons.append('имя и отчество')
    if (
        last
        and len(last) >= 3
        and c_last.lower() == last.lower()
        and not (first and c_first.lower() == first.lower())
    ):
        reasons.append('фамилия')
    if nick and len(nick) >= 2 and c_nick.lower() == nick.lower():
        reasons.append('никнейм')

    anchor_handles = set(
        InfoContact.objects.filter(contact=anchor, community__isnull=True)
        .exclude(external_id='')
        .values_list('external_id', flat=True)
    )
    if anchor_handles:
        candidate_handles = set(
            InfoContact.objects.filter(contact=candidate, community__isnull=True)
            .exclude(external_id='')
            .values_list('external_id', flat=True)
        )
        if anchor_handles & candidate_handles:
            reasons.append('контакт в соцсетях')

    if candidate.pk == anchor.pk:
        reasons.append('эта карточка')

    return reasons

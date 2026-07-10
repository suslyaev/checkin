"""
Поиск предположительных дублей контакта для списка в админке.
"""
from collections import defaultdict
from itertools import combinations

from django.db.models import Q

from .models import Contact, ContactDuplicateConflict, InfoContact


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


def _pairs_from_groups(groups):
    """Все пары id внутри каждой группы размером > 1 (канонический порядок a < b)."""
    pairs = set()
    for ids in groups.values():
        unique_ids = sorted(set(ids))
        if len(unique_ids) < 2:
            continue
        pairs.update(combinations(unique_ids, 2))
    return pairs


def _candidate_pairs_with_reasons():
    """
    Пары контактов-кандидатов в дубли и причины совпадения, посчитанные
    за 2 запроса к БД (без корреляции на каждую карточку) — используется
    только явным пересчётом, не на горячем пути запросов.
    """
    reasons_by_pair = defaultdict(set)

    by_last_first = defaultdict(list)
    by_first_middle = defaultdict(list)
    by_nickname = defaultdict(list)
    for pk, last, first, middle, nick in Contact.objects.values_list(
        'pk', 'last_name', 'first_name', 'middle_name', 'nickname'
    ):
        last, first, middle, nick = _norm(last).lower(), _norm(first).lower(), _norm(middle).lower(), _norm(nick).lower()
        if last and first:
            by_last_first[(last, first)].append(pk)
        if first and middle:
            by_first_middle[(first, middle)].append(pk)
        if len(nick) >= 2:
            by_nickname[nick].append(pk)

    for pair in _pairs_from_groups(by_last_first):
        reasons_by_pair[pair].add('фамилия и имя')
    for pair in _pairs_from_groups(by_first_middle):
        reasons_by_pair[pair].add('имя и отчество')
    for pair in _pairs_from_groups(by_nickname):
        reasons_by_pair[pair].add('никнейм')

    by_handle = defaultdict(list)
    for contact_id, external_id in (
        InfoContact.objects.filter(community__isnull=True, contact__isnull=False)
        .exclude(external_id='')
        .values_list('contact_id', 'external_id')
    ):
        by_handle[external_id.strip().lower()].append(contact_id)
    for pair in _pairs_from_groups(by_handle):
        reasons_by_pair[pair].add('контакт в соцсетях')

    return reasons_by_pair


def sync_duplicate_conflicts():
    """
    Пересчитывает возможные дубли и добавляет только новые пары (insert-only):
    уже существующие строки — с любым статусом — не трогает, поэтому решённые
    конфликты остаются решёнными, а новые похожие карточки всплывают отдельной парой.
    Возвращает количество добавленных пар.
    """
    reasons_by_pair = _candidate_pairs_with_reasons()
    existing_pairs = set(
        ContactDuplicateConflict.objects.values_list('contact_a_id', 'contact_b_id')
    )
    new_conflicts = [
        ContactDuplicateConflict(
            contact_a_id=a,
            contact_b_id=b,
            match_reason=', '.join(sorted(reasons)),
        )
        for (a, b), reasons in reasons_by_pair.items()
        if (a, b) not in existing_pairs
    ]
    if new_conflicts:
        ContactDuplicateConflict.objects.bulk_create(new_conflicts, ignore_conflicts=True)
    return len(new_conflicts)


def get_conflict_reasons_for_contact(contact):
    """Причины из уже посчитанных строк ContactDuplicateConflict для этой карточки."""
    reasons = []
    for match_reason in (
        ContactDuplicateConflict.objects.filter(
            Q(contact_a=contact) | Q(contact_b=contact),
            status='unprocessed',
        ).values_list('match_reason', flat=True)
    ):
        for reason in match_reason.split(', '):
            if reason and reason not in reasons:
                reasons.append(reason)
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

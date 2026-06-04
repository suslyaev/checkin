"""
Поиск предположительных дублей контакта для списка в админке.
"""
from django.db.models import Q

from .models import Contact, InfoContact


def _norm(value):
    if value is None:
        return ''
    return str(value).strip()


def build_duplicate_candidates_q(contact):
    """
    Q-фильтр: другие люди (и сам контакт), похожие на переданную карточку.
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

    # Та же фамилия (слабое совпадение — у популярных фамилий список может быть длинным)
    if last and len(last) >= 3:
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


def duplicate_candidates_queryset(contact):
    return Contact.objects.filter(build_duplicate_candidates_q(contact)).distinct()


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

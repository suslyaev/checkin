"""Распознавание соцсетей по ссылке и раскладка значений по столбцам.

Файлы часто собирают не из шаблона, а из своих таблиц, где на соцсеть
приходится пара «ссылка, подписчики» без названия сети — под тройками
заголовков «Соцсеть N / Ссылка N / Подписчики N» такие значения встают со
сдвигом. Название сети однозначно восстанавливается по домену ссылки, а
порядок значений в строке сохраняется — по нему и раскладываем заново.
"""

import re

from .contact_columns import social_field_key, social_groups_in_keys
from .numbers import NUMBER_DASHES, parse_int_like

# Названия — как уже заведены в справочнике соцсетей (SocialNetwork):
# get_or_create при импорте ищет точным совпадением, другое написание
# завело бы дубль сети.
SOCIAL_NETWORK_HOSTS = [
    ('Instagram', re.compile(r'(^|\.)(i?nstagram\.com|instagr\.am)$')),
    ('VK', re.compile(r'(^|\.)(vk\.(com|ru|me)|vkontakte\.ru)$')),
    ('Telegram', re.compile(r'(^|\.)(t\.me|telegram\.(me|org)|teleg\.run)$|^t\.me')),
    ('TikTok', re.compile(r'(^|\.)tiktok\.com$')),
    ('YouTube', re.compile(r'(^|\.)(youtube\.com|youtu\.be)$')),
]
OTHER_NETWORK = 'Other'

SOCIAL_NETWORK_ALIASES = {
    'Instagram': {'instagram', 'insta', 'inst', 'инстаграм', 'инстаграмм', 'инста', 'инст'},
    'VK': {'vk', 'vkontakte', 'вк', 'вконтакте', 'в контакте'},
    'Telegram': {'telegram', 'tg', 'тг', 'телеграм', 'телеграмм', 'телега'},
    'TikTok': {'tiktok', 'tik tok', 'тикток', 'тик ток', 'тик-ток'},
    'YouTube': {'youtube', 'yt', 'ютуб', 'ютьюб'},
    OTHER_NETWORK: {'other', 'другое'},
}
_ALIAS_TO_NETWORK = {
    alias: name for name, aliases in SOCIAL_NETWORK_ALIASES.items() for alias in aliases | {name.lower()}
}

_URL_RE = re.compile(
    r'^(?:[a-z][a-z0-9+.-]*://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z][a-z0-9-]*)(?:[/?#:]|$)',
    re.IGNORECASE,
)
_PARTS = ('name', 'id', 'subscribers')


def link_host(value):
    """Домен ссылки в нижнем регистре или None, если это не ссылка."""
    value = (value or '').strip()
    if not value or re.search(r'\s', value):
        return None
    m = _URL_RE.match(value)
    return m.group(1).lower() if m else None


def network_from_link(value):
    """Название соцсети по ссылке: известный домен -> его сеть, любая другая
    ссылка -> Other, не ссылка (например, «@handle») -> None."""
    host = link_host(value)
    if not host:
        return None
    for name, pattern in SOCIAL_NETWORK_HOSTS:
        if pattern.search(host):
            return name
    return OTHER_NETWORK


def canonical_network_name(value):
    """«вк»/«vk»/«ВКонтакте» -> «VK»; неизвестное название -> None."""
    return _ALIAS_TO_NETWORK.get(re.sub(r'\s+', ' ', (value or '').strip().lower()))


def _is_number(value):
    try:
        return parse_int_like(value) is not None
    except ValueError:
        return False


def _row_is_misaligned(row, groups):
    """Ссылка в «Соцсети»/«Подписчиках» или число в «Соцсети»/«Ссылке» —
    значения стоят не под своими заголовками."""
    for n in groups:
        name = (row.get(social_field_key(n, 'name')) or '').strip()
        link = (row.get(social_field_key(n, 'id')) or '').strip()
        subs = (row.get(social_field_key(n, 'subscribers')) or '').strip()
        if link_host(name) or link_host(subs):
            return True
        if _is_number(name) or (_is_number(link) and not link_host(link)):
            return True
    return False


def _reflow_values(values):
    """Значения соцсетей строки по порядку -> [{'name', 'id', 'subscribers'}].
    Ссылка (или «@handle») начинает новую сеть, число после неё — её
    подписчики, прочерк сразу после ссылки — 0 подписчиков, известное
    название сети — название для следующей ссылки. Прочий текст (должности,
    комментарии, попавшие в эти столбцы) отбрасывается — как и раньше при
    валидации, соцсетью он не является."""
    networks = []
    pending_name = None
    previous_was_link = False
    for raw in values:
        value = (raw or '').strip()
        is_link = bool(link_host(value)) or (value.startswith('@') and not re.search(r'\s', value))
        if not value:
            previous_was_link = False
            continue
        if is_link:
            networks.append({
                'name': pending_name or network_from_link(value) or '',
                'id': value,
                'subscribers': '',
            })
            pending_name = None
        elif value in NUMBER_DASHES:
            if previous_was_link:
                networks[-1]['subscribers'] = '0'
        elif _is_number(value):
            if networks and not networks[-1]['subscribers']:
                networks[-1]['subscribers'] = value
        elif canonical_network_name(value):
            pending_name = canonical_network_name(value)
        previous_was_link = is_link
    return networks


def reflow_social_columns(rows, present_columns):
    """Раскладывает значения соцсетей по своим столбцам в строках, где они
    сдвинуты (см. _row_is_misaligned). Если сетей в строке оказалось больше,
    чем групп столбцов в файле, добавляет группы. Возвращает
    (rows, present_columns, число переразложенных строк)."""
    groups = sorted(social_groups_in_keys(present_columns))
    if not groups:
        return rows, present_columns, 0

    reflowed = 0
    max_networks = len(groups)
    for row in rows:
        if not _row_is_misaligned(row, groups):
            continue
        values = [row.get(social_field_key(n, part), '') for n in groups for part in _PARTS]
        networks = _reflow_values(values)
        for n in groups:
            for part in _PARTS:
                row[social_field_key(n, part)] = ''
        row['_social_networks'] = networks
        max_networks = max(max_networks, len(networks))
        reflowed += 1

    target_groups = list(groups)
    while len(target_groups) < max_networks:
        target_groups.append(target_groups[-1] + 1)
    new_keys = {social_field_key(n, part) for n in target_groups for part in _PARTS}

    for row in rows:
        for key in new_keys:
            row.setdefault(key, '')
        for n, network in zip(target_groups, row.pop('_social_networks', [])):
            for part in _PARTS:
                row[social_field_key(n, part)] = network[part]

    return rows, set(present_columns) | new_keys, reflowed

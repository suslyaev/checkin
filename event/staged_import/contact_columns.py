"""Колонки файла импорта людей.

Заголовки подобраны так, чтобы совпадать с тем, что реально отдаёт выгрузка
Контактов из админки (event/resources.py:ContactExport) — администратор
может выгрузить карточки, обрезать лишние столбцы и залить файл обратно
этим же загрузчиком без пересборки формата.

Группы соцсетей ("Соцсеть N" / "Ссылка N" / "Подписчики N") — без
фиксированного числа: сколько групп реально есть в конкретном загруженном
файле, столько и обрабатывается (см. parsers.py). Здесь — только паттерн
и хелперы для работы с произвольным N, без списка "поддерживаемых" номеров.
"""

import re

from event.models import CategoryContact, CompanyContact, ModuleInstance, STATUS_MODEL, TypeGuestContact

# Регистрация на мероприятие (Фаза 4) — закрытый список статусов, не
# растущий справочник: в сетке рендерится как <select>, а не текстовое поле.
STATUS_CODE_TO_LABEL = dict(STATUS_MODEL)
STATUS_LABEL_TO_CODE = {label: code for code, label in STATUS_MODEL}
STATUS_LABELS = [label for _, label in STATUS_MODEL]
DEFAULT_STATUS_CODE = 'announced'

# Поля-справочники, для которых новые значения не создаются молча (п.3
# требований) — используется и для сбора значений на подтверждение
# (contact_import.py), и для приведения регистра к уже существующему
# значению (contact_validation.py). 'event' сюда же — то же самое правило
# «новое имя не создаётся молча», просто сущность — мероприятие, а не
# карточка-справочник контакта (Фаза 4).
REFERENCE_FIELD_MODELS = {
    'company': CompanyContact,
    'category': CategoryContact,
    'type_guest': TypeGuestContact,
    'event': ModuleInstance,
}

# 'id' — необязательная колонка для сопоставления по ID карточки (см.
# contact_import.py) — приоритетнее поиска по ФИО, когда указана и найдена.
# Соцсети сюда не входят — они per-сессия, см. columns_for_session ниже.
CONTACT_IMPORT_COLUMNS = [
    'id',
    'last_name',
    'first_name',
    'middle_name',
    'nickname',
    'company',
    'category',
    'type_guest',
    'producer_last_name',
    'producer_first_name',
    'comment',
    'event',
    'status',
]

CONTACT_COLUMN_LABELS = {
    'id': 'ID',
    'last_name': 'Фамилия',
    'first_name': 'Имя',
    'middle_name': 'Отчество',
    'nickname': 'Ник',
    'company': 'Компания',
    'category': 'Категория',
    'type_guest': 'Тип гостя',
    'producer_last_name': 'Фамилия продюсера',
    'producer_first_name': 'Имя продюсера',
    'comment': 'Комментарий',
    'event': 'Наименование события',
    'status': 'Статус',
}

# Заголовок файла -> внутренний ключ поля, для БАЗОВЫХ (не-соцсетевых)
# колонок. CONTACT_COLUMN_LABELS — источник истины и для подписей в сетке,
# и для распознавания колонок при загрузке (parsers.py), чтобы они не могли
# разойтись.
HEADER_TO_FIELD = {label: key for key, label in CONTACT_COLUMN_LABELS.items()}

REQUIRED_CONTACT_COLUMNS = {'last_name', 'first_name'}

NAME_FIELDS = {'last_name', 'first_name', 'middle_name', 'nickname'}

# Поля, к которым применяется нормализация ё -> е (ФИО-подобные поля).
YO_NORMALIZE_FIELDS = NAME_FIELDS | {'producer_last_name', 'producer_first_name'}


# ---- Соцсети: произвольное число групп ----

SOCIAL_PART_LABELS = {'name': 'Соцсеть', 'id': 'Ссылка', 'subscribers': 'Подписчики'}
_SOCIAL_LABEL_TO_PART = {label: part for part, label in SOCIAL_PART_LABELS.items()}
SOCIAL_HEADER_RE = re.compile(r'^(Соцсеть|Ссылка|Подписчики)\s+(\d+)$')
_SOCIAL_FIELD_KEY_RE = re.compile(r'^social_network_(\d+)_(name|id|subscribers)$')


def social_field_key(n, part):
    return f'social_network_{n}_{part}'


def social_field_label(n, part):
    return f'{SOCIAL_PART_LABELS[part]} {n}'


def match_social_header(header_text):
    """Заголовок файла вида 'Соцсеть 4'/'Ссылка 4'/'Подписчики 4' -> (n, internal_key).
    Любое N, без ограничения сверху и без требования непрерывной нумерации.
    Возвращает None, если заголовок не подходит под паттерн."""
    m = SOCIAL_HEADER_RE.match((header_text or '').strip())
    if not m:
        return None
    part = _SOCIAL_LABEL_TO_PART[m.group(1)]
    n = int(m.group(2))
    return n, social_field_key(n, part)


def social_groups_in_keys(keys):
    """Множество номеров групп соцсетей, встречающихся среди переданных
    ключей (обычно row.keys() или present_columns) — строка/набор колонок
    сами себя описывают, отдельно список групп протаскивать не нужно."""
    groups = set()
    for key in keys:
        m = _SOCIAL_FIELD_KEY_RE.match(key)
        if m:
            groups.add(int(m.group(1)))
    return groups


def columns_for_session(social_groups):
    """Полный список колонок для конкретной загрузки: базовые + столько
    групп соцсетей, сколько реально было в файле."""
    columns = list(CONTACT_IMPORT_COLUMNS)
    for n in sorted(social_groups):
        for part in ('name', 'id', 'subscribers'):
            columns.append(social_field_key(n, part))
    return columns


def labels_for_session(social_groups):
    labels = dict(CONTACT_COLUMN_LABELS)
    for n in sorted(social_groups):
        for part in ('name', 'id', 'subscribers'):
            labels[social_field_key(n, part)] = social_field_label(n, part)
    return labels

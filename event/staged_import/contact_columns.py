"""Колонки файла импорта людей.

Заголовки подобраны так, чтобы совпадать с тем, что реально отдаёт выгрузка
Контактов из админки (event/resources.py:ContactExport) — администратор
может выгрузить карточки, обрезать лишние столбцы и залить файл обратно
этим же загрузчиком без пересборки формата.
"""

from event.models import CategoryContact, CompanyContact, ModuleInstance, STATUS_MODEL, TypeGuestContact

SOCIAL_NETWORK_GROUPS = (1, 2, 3)

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


def _social_columns():
    columns = []
    for i in SOCIAL_NETWORK_GROUPS:
        columns += [
            f'social_network_{i}_name',
            f'social_network_{i}_id',
            f'social_network_{i}_subscribers',
        ]
    return columns


# 'id' — необязательная колонка для сопоставления по ID карточки (см.
# contact_import.py) — приоритетнее поиска по ФИО, когда указана и найдена.
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
] + _social_columns()

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
for _i in SOCIAL_NETWORK_GROUPS:
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_name'] = f'Соцсеть {_i}'
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_id'] = f'Ссылка {_i}'
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_subscribers'] = f'Подписчики {_i}'

# Заголовок файла -> внутренний ключ поля. CONTACT_COLUMN_LABELS — источник
# истины и для подписей в сетке, и для распознавания колонок при загрузке
# (parsers.py), чтобы они не могли разойтись.
HEADER_TO_FIELD = {label: key for key, label in CONTACT_COLUMN_LABELS.items()}

REQUIRED_CONTACT_COLUMNS = {'last_name', 'first_name'}

NAME_FIELDS = {'last_name', 'first_name', 'middle_name', 'nickname'}

# Поля, к которым применяется нормализация ё -> е (ФИО-подобные поля).
YO_NORMALIZE_FIELDS = NAME_FIELDS | {'producer_last_name', 'producer_first_name'}

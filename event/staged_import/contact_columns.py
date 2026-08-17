"""Колонки файла импорта людей (тот же формат, что import_cont.xlsx)."""

from event.models import CategoryContact, CompanyContact, TypeGuestContact

SOCIAL_NETWORK_GROUPS = (1, 2, 3)

# Поля-справочники, для которых новые значения не создаются молча (п.3
# требований) — используется и для сбора значений на подтверждение
# (contact_import.py), и для приведения регистра к уже существующему
# значению (contact_validation.py).
REFERENCE_FIELD_MODELS = {
    'company': CompanyContact,
    'category': CategoryContact,
    'type_guest': TypeGuestContact,
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


CONTACT_IMPORT_COLUMNS = [
    'last_name',
    'first_name',
    'middle_name',
    'nickname',
    'company',
    'category',
    'type_guest',
    'producer',
    'comment',
] + _social_columns()

CONTACT_COLUMN_LABELS = {
    'last_name': 'Фамилия',
    'first_name': 'Имя',
    'middle_name': 'Отчество',
    'nickname': 'Никнейм',
    'company': 'Компания',
    'category': 'Категория',
    'type_guest': 'Тип гостя',
    'producer': 'Продюсер',
    'comment': 'Комментарий',
}
for _i in SOCIAL_NETWORK_GROUPS:
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_name'] = f'Соцсеть {_i}'
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_id'] = f'ID/ссылка соцсети {_i}'
    CONTACT_COLUMN_LABELS[f'social_network_{_i}_subscribers'] = f'Подписчики {_i}'

REQUIRED_CONTACT_COLUMNS = {'last_name', 'first_name'}

NAME_FIELDS = {'last_name', 'first_name', 'middle_name', 'nickname'}

# Поля, к которым применяется нормализация ё -> е (ФИО-подобные поля).
YO_NORMALIZE_FIELDS = NAME_FIELDS | {'producer'}

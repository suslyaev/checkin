"""Колонки файла импорта людей (тот же формат, что import_cont.xlsx)."""

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
    'social_network_name',
    'social_network_id',
    'social_network_subscribers',
]

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
    'social_network_name': 'Соцсеть',
    'social_network_id': 'ID/ссылка соцсети',
    'social_network_subscribers': 'Подписчики',
}

REQUIRED_CONTACT_COLUMNS = {'last_name', 'first_name'}

NAME_FIELDS = {'last_name', 'first_name', 'middle_name', 'nickname'}

import tablib

from .contact_columns import CONTACT_IMPORT_COLUMNS, HEADER_TO_FIELD, columns_for_session, match_social_header


def _normalize_header(value):
    if value is None:
        return ''
    return str(value).strip()


def parse_spreadsheet(uploaded_file):
    """
    Читает xlsx/csv в список словарей по колонкам импорта людей.
    Неизвестные колонки игнорируются. Порядок колонок в файле не важен —
    важны только заголовки (см. CONTACT_COLUMN_LABELS/HEADER_TO_FIELD).
    Колонки соцсетей ("Соцсеть N"/"Ссылка N"/"Подписчики N") распознаются
    для любого N, без ограничения сверху и без требования непрерывной
    нумерации — сколько групп реально в файле, столько и обрабатывается.

    Возвращает (rows, present_columns) — present_columns это множество полей,
    которые реально были в файле (не только с непустыми значениями): столбец,
    которого нет в файле вообще, при обновлении не должен затирать то, что
    уже есть в карточке (см. contact_import.py). Соцсетевые ключи внутри
    present_columns неявно определяют, сколько групп соцсетей у этой загрузки
    (см. contact_columns.social_groups_in_keys).
    """
    name = (uploaded_file.name or '').lower()
    raw = uploaded_file.read()

    if name.endswith('.csv'):
        dataset = tablib.Dataset().load(raw.decode('utf-8-sig'), format='csv')
    elif name.endswith('.xlsx'):
        dataset = tablib.Dataset().load(raw, format='xlsx')
    else:
        raise ValueError('Поддерживаются файлы .xlsx и .csv')

    if not dataset.headers:
        raise ValueError('В файле нет строки заголовков')

    header_map = {}
    social_groups = set()
    for idx, header in enumerate(dataset.headers):
        normalized_header = _normalize_header(header)
        key = HEADER_TO_FIELD.get(normalized_header)
        if key in CONTACT_IMPORT_COLUMNS:
            header_map[idx] = key
            continue
        social_match = match_social_header(normalized_header)
        if social_match:
            n, social_key = social_match
            header_map[idx] = social_key
            social_groups.add(n)

    if not header_map:
        raise ValueError(
            'Не найдены колонки импорта. Ожидаются заголовки как в шаблоне '
            '(Фамилия, Имя, …) — например, из выгрузки списка людей в админке.'
        )

    present_columns = set(header_map.values())
    row_template_columns = columns_for_session(social_groups)

    rows = []
    for row_index, raw_row in enumerate(dataset, start=2):
        if not any(cell not in (None, '') for cell in raw_row):
            continue
        row = {col: '' for col in row_template_columns}
        for col_idx, field_name in header_map.items():
            value = raw_row[col_idx] if col_idx < len(raw_row) else ''
            if value is None:
                value = ''
            elif not isinstance(value, str):
                value = str(value)
            row[field_name] = value
        row['_row_number'] = row_index
        row['excluded'] = False
        rows.append(row)

    if not rows:
        raise ValueError('В файле нет строк с данными')

    return rows, present_columns

import tablib

from .contact_columns import CONTACT_IMPORT_COLUMNS


def _normalize_header(value):
    if value is None:
        return ''
    return str(value).strip()


def parse_spreadsheet(uploaded_file):
    """
    Читает xlsx/csv в список словарей по колонкам импорта людей.
    Неизвестные колонки игнорируются.
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
    for idx, header in enumerate(dataset.headers):
        key = _normalize_header(header)
        if key in CONTACT_IMPORT_COLUMNS:
            header_map[idx] = key

    if not header_map:
        raise ValueError(
            'Не найдены колонки импорта. Ожидаются заголовки как в шаблоне '
            '(last_name, first_name, …).'
        )

    rows = []
    for row_index, raw_row in enumerate(dataset, start=2):
        if not any(cell not in (None, '') for cell in raw_row):
            continue
        row = {col: '' for col in CONTACT_IMPORT_COLUMNS}
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

    return rows

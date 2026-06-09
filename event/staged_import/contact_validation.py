import re

from .contact_columns import CONTACT_IMPORT_COLUMNS, NAME_FIELDS, REQUIRED_CONTACT_COLUMNS

FORBIDDEN_CHARS_PATTERN = re.compile(r'[<>"{}|\\`\x00-\x08\x0b\x0c\x0e-\x1f]')
MAX_FIELD_LENGTH = 300


def _cell_issues(field, raw_value):
    errors = []
    warnings = []
    value = '' if raw_value is None else str(raw_value)

    if field in REQUIRED_CONTACT_COLUMNS:
        if not value.strip():
            errors.append('Обязательное поле')

    if value != value.strip() and value.strip():
        warnings.append('Пробелы в начале или конце — будут обрезаны при загрузке')
    elif value != value.strip() and not value.strip():
        if field in REQUIRED_CONTACT_COLUMNS:
            pass  # already "required"
        else:
            warnings.append('Содержит только пробелы')

    if value.strip() and len(value) > MAX_FIELD_LENGTH:
        errors.append(f'Длина больше {MAX_FIELD_LENGTH} символов')

    if field in NAME_FIELDS and value.strip() and FORBIDDEN_CHARS_PATTERN.search(value):
        errors.append('Недопустимые символы (< > " { } | \\ и управляющие)')

    if field == 'social_network_subscribers' and value.strip():
        try:
            int(float(value.strip().replace(' ', '').replace(',', '.')))
        except (ValueError, TypeError):
            errors.append('Должно быть числом')

    return errors, warnings


def validate_contact_row(row):
    """Возвращает row с полями errors, warnings, has_errors, has_warnings."""
    errors = {}
    warnings = {}
    for field in CONTACT_IMPORT_COLUMNS:
        field_errors, field_warnings = _cell_issues(field, row.get(field, ''))
        if field_errors:
            errors[field] = field_errors
        if field_warnings:
            warnings[field] = field_warnings

    result = dict(row)
    result['errors'] = errors
    result['warnings'] = warnings
    result['has_errors'] = bool(errors)
    result['has_warnings'] = bool(warnings)
    return result


def validate_contact_rows(rows):
    validated = [validate_contact_row(row) for row in rows]
    active = [r for r in validated if not r.get('excluded')]
    summary = {
        'total': len(validated),
        'active': len(active),
        'excluded': len(validated) - len(active),
        'error_rows': sum(1 for r in active if r['has_errors']),
        'warning_rows': sum(1 for r in active if r['has_warnings'] and not r['has_errors']),
    }
    summary['can_import'] = summary['active'] > 0 and summary['error_rows'] == 0
    return validated, summary


def normalize_row_for_import(row):
    """Подготовка строки к ContactImport (trim строк)."""
    normalized = {col: '' for col in CONTACT_IMPORT_COLUMNS}
    for col in CONTACT_IMPORT_COLUMNS:
        value = row.get(col, '')
        if value is None:
            value = ''
        if not isinstance(value, str):
            value = str(value)
        normalized[col] = value.strip()
    if not normalized['middle_name']:
        normalized['middle_name'] = ''
    return normalized

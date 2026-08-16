import re

from .contact_columns import (
    CONTACT_IMPORT_COLUMNS,
    NAME_FIELDS,
    REQUIRED_CONTACT_COLUMNS,
    SOCIAL_NETWORK_GROUPS,
    YO_NORMALIZE_FIELDS,
)

FORBIDDEN_CHARS_PATTERN = re.compile(r'[<>"{}|\\`\x00-\x08\x0b\x0c\x0e-\x1f]')
MAX_FIELD_LENGTH = 300
YO_PATTERN = re.compile('[ёЁ]')


def normalize_yo(value):
    """Приводит «ё» к «е» (обязательное приведение, не проверка)."""
    if value is None:
        return value
    return YO_PATTERN.sub(lambda m: 'е' if m.group() == 'ё' else 'Е', value)


def _looks_like_social_handle(value):
    """Ссылка/хэндл соцсети не содержит пробелов; должность вроде
    «Сотрудник MQP» или «Аккаунт менеджер» — содержит."""
    value = value.strip()
    if not value:
        return True
    return not re.search(r'\s', value)


def _apply_normalization(row):
    """Обязательное приведение значений до валидации: ё->е в ФИО-полях,
    очистка мусора в полях соцсетей. Возвращает (row, social_clear_notes)."""
    normalized = dict(row)
    for field in YO_NORMALIZE_FIELDS:
        if field in normalized:
            normalized[field] = normalize_yo(normalized[field])

    social_clear_notes = {}
    for i in SOCIAL_NETWORK_GROUPS:
        id_field = f'social_network_{i}_id'
        raw_id = normalized.get(id_field, '')
        raw_id = '' if raw_id is None else str(raw_id)
        if raw_id.strip() and not _looks_like_social_handle(raw_id):
            name_field = f'social_network_{i}_name'
            subs_field = f'social_network_{i}_subscribers'
            normalized[id_field] = ''
            normalized[name_field] = ''
            normalized[subs_field] = ''
            social_clear_notes[id_field] = (
                'Похоже, это не ссылка/ID соцсети — значение очищено'
            )

    return normalized, social_clear_notes


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

    subscriber_columns = {f'social_network_{i}_subscribers' for i in SOCIAL_NETWORK_GROUPS}
    if field in subscriber_columns and value.strip():
        try:
            int(float(value.strip().replace(' ', '').replace(',', '.')))
        except (ValueError, TypeError):
            errors.append('Должно быть числом')

    return errors, warnings


def validate_contact_row(row):
    """Возвращает row с полями errors, warnings, has_errors, has_warnings."""
    normalized_row, social_clear_notes = _apply_normalization(row)

    errors = {}
    warnings = {}
    for field in CONTACT_IMPORT_COLUMNS:
        field_errors, field_warnings = _cell_issues(field, normalized_row.get(field, ''))
        if field in social_clear_notes:
            field_warnings = list(field_warnings) + [social_clear_notes[field]]
        if field_errors:
            errors[field] = field_errors
        if field_warnings:
            warnings[field] = field_warnings

    result = dict(normalized_row)
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

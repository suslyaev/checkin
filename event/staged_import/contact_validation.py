import re

from event.models import KnownFirstName, KnownLastName

from .contact_columns import (
    CONTACT_IMPORT_COLUMNS,
    NAME_FIELDS,
    REQUIRED_CONTACT_COLUMNS,
    SOCIAL_NETWORK_GROUPS,
    YO_NORMALIZE_FIELDS,
)

NAME_SWAP_WARNING = 'Похоже, имя и фамилия перепутаны местами — проверьте'

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


def _load_known_name_sets():
    """Множества известных имён/фамилий (регистр не важен, ё->е), для п.1.3.
    Списки заведомо неполные — пополняются вручную через админку."""
    first_names = {
        normalize_yo(name).strip().lower()
        for name in KnownFirstName.objects.values_list('name', flat=True)
    }
    last_names = {
        normalize_yo(name).strip().lower()
        for name in KnownLastName.objects.values_list('name', flat=True)
    }
    return first_names, last_names


def _looks_swapped(last_name, first_name, known_first_names, known_last_names):
    """True, если слово из "Имя" похоже на фамилию, а слово из "Фамилия" —
    на имя (и только тогда — единичное совпадение с одним из справочников
    ничего не значит, слишком много имён, которые бывают и фамилиями)."""
    last_word = (last_name or '').strip().split()
    first_word = (first_name or '').strip().split()
    if not last_word or not first_word:
        return False
    last_key = last_word[0].lower()
    first_key = first_word[0].lower()

    first_looks_like_surname = first_key in known_last_names and first_key not in known_first_names
    last_looks_like_firstname = last_key in known_first_names and last_key not in known_last_names
    return first_looks_like_surname and last_looks_like_firstname


def validate_contact_row(row, known_first_names=None, known_last_names=None):
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

    if known_first_names is not None and _looks_swapped(
        normalized_row.get('last_name', ''), normalized_row.get('first_name', ''),
        known_first_names, known_last_names,
    ):
        warnings.setdefault('last_name', []).append(NAME_SWAP_WARNING)
        warnings.setdefault('first_name', []).append(NAME_SWAP_WARNING)

    result = dict(normalized_row)
    result['errors'] = errors
    result['warnings'] = warnings
    result['has_errors'] = bool(errors)
    result['has_warnings'] = bool(warnings)
    return result


def validate_contact_rows(rows):
    known_first_names, known_last_names = _load_known_name_sets()
    validated = [validate_contact_row(row, known_first_names, known_last_names) for row in rows]
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

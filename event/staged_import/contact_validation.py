import re

from event.models import Contact, KnownFirstName, KnownLastName

from .contact_columns import (
    CONTACT_IMPORT_COLUMNS,
    NAME_FIELDS,
    REFERENCE_FIELD_MODELS,
    REQUIRED_CONTACT_COLUMNS,
    SOCIAL_NETWORK_GROUPS,
    STATUS_LABEL_TO_CODE,
    YO_NORMALIZE_FIELDS,
)

NAME_SWAP_WARNING = 'Похоже, имя и фамилия перепутаны местами — проверьте'
REFERENCE_CASING_NOTE = 'Приведено к уже существующему значению справочника: «{value}»'
NO_ID_NO_COLUMN_ERROR = 'Обязательное поле (в файле нет этого столбца, а ID для сопоставления не указан)'

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


def load_reference_casing_maps():
    """{field: {'exact': {точные значения в БД}, 'by_lower': {значение.lower(): одно
    из точных написаний}}} — чтобы «вип3» не завёл дубль категории рядом с уже
    существующей «ВИП3» только из-за регистра (ForeignKeyGetOrCreateWidget ищет
    точным совпадением). Если в базе одновременно есть и «гость», и «Гость» —
    точное совпадение всегда важнее регистронезависимого угадывания, иначе можно
    подменить ровно то значение, которое человек и имел в виду, на другое."""
    maps = {}
    for field, model in REFERENCE_FIELD_MODELS.items():
        names = list(model.objects.values_list('name', flat=True))
        by_lower = {}
        for name in names:
            by_lower.setdefault(name.strip().lower(), name)
        maps[field] = {'exact': set(names), 'by_lower': by_lower}
    return maps


def resolve_reference_casing(value, casing_map):
    """Возвращает существующее написание значения из справочника, если оно
    отличается от введённого только регистром, иначе None. Если введённое
    значение уже точно совпадает с чем-то в базе — это не про регистр, трогать
    нечего, даже если в базе рядом есть тёзка с другим регистром."""
    value = (value or '').strip()
    if not value:
        return None
    if value in casing_map.get('exact', set()):
        return None
    canonical = casing_map.get('by_lower', {}).get(value.lower())
    if canonical and canonical != value:
        return canonical
    return None


def load_existing_contact_ids():
    """Множество ID существующих карточек — для проверки колонки id (п.2 Фазы 3)."""
    return set(Contact.objects.values_list('pk', flat=True))


def _apply_normalization(row, reference_casing_maps=None):
    """Обязательное приведение значений до валидации: ё->е в ФИО-полях,
    очистка мусора в полях соцсетей, приведение регистра справочных полей
    к уже существующему значению. Возвращает (row, extra_notes)."""
    normalized = dict(row)
    for field in YO_NORMALIZE_FIELDS:
        if field in normalized:
            normalized[field] = normalize_yo(normalized[field])

    extra_notes = {}

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
            extra_notes[id_field] = 'Похоже, это не ссылка/ID соцсети — значение очищено'

    for field, casing_map in (reference_casing_maps or {}).items():
        canonical = resolve_reference_casing(normalized.get(field), casing_map)
        if canonical:
            # Значение в сетке/сессии намеренно НЕ трогаем — иначе при следующей
            # отрисовке несовпадение регистра уже не обнаружится и предупреждение
            # исчезнет, толком не показавшись пользователю (загрузка сразу
            # редиректит на страницу проверки). Каноническое написание
            # подставляется только в момент коммита, см. import_contact_rows.
            extra_notes[field] = REFERENCE_CASING_NOTE.format(value=canonical)

    return normalized, extra_notes


def _id_issues(value, existing_contact_ids):
    value = (value or '').strip()
    if not value:
        return [], []
    try:
        contact_id = int(value)
    except ValueError:
        return ['ID должен быть числом'], []
    if existing_contact_ids is not None and contact_id not in existing_contact_ids:
        return [f'Человек с ID={contact_id} не найден в базе'], []
    return [], []


def _cell_issues(field, raw_value, present_columns=None, row_has_id=False, existing_contact_ids=None):
    errors = []
    warnings = []
    value = '' if raw_value is None else str(raw_value)

    if field == 'id':
        id_errors, id_warnings = _id_issues(value, existing_contact_ids)
        errors += id_errors
        warnings += id_warnings

    if field == 'status' and value.strip() and value.strip() not in STATUS_LABEL_TO_CODE:
        errors.append(
            'Неизвестный статус. Допустимые значения: ' + ', '.join(STATUS_LABEL_TO_CODE)
        )

    if field in REQUIRED_CONTACT_COLUMNS:
        # Столбца нет в файле вообще — не то же самое, что пустая ячейка
        # (см. Фазу 3): если он есть, обнулить ФИО всё равно нельзя (так
        # требует модель), а если его нет — ок при условии, что человек
        # опознаётся по ID (тогда ФИО подставится из карточки при коммите).
        col_present = present_columns is None or field in present_columns
        if col_present:
            if not value.strip():
                errors.append('Обязательное поле')
        elif not row_has_id:
            errors.append(NO_ID_NO_COLUMN_ERROR)

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


def validate_contact_row(
    row,
    known_first_names=None,
    known_last_names=None,
    reference_casing_maps=None,
    present_columns=None,
    existing_contact_ids=None,
):
    """Возвращает row с полями errors, warnings, has_errors, has_warnings."""
    normalized_row, extra_notes = _apply_normalization(row, reference_casing_maps)
    row_has_id = bool((normalized_row.get('id') or '').strip())

    errors = {}
    warnings = {}
    for field in CONTACT_IMPORT_COLUMNS:
        field_errors, field_warnings = _cell_issues(
            field, normalized_row.get(field, ''),
            present_columns=present_columns, row_has_id=row_has_id,
            existing_contact_ids=existing_contact_ids,
        )
        if field in extra_notes:
            field_warnings = list(field_warnings) + [extra_notes[field]]
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


def validate_contact_rows(rows, present_columns=None):
    known_first_names, known_last_names = _load_known_name_sets()
    reference_casing_maps = load_reference_casing_maps()
    existing_contact_ids = load_existing_contact_ids()
    validated = [
        validate_contact_row(
            row, known_first_names, known_last_names, reference_casing_maps,
            present_columns=present_columns, existing_contact_ids=existing_contact_ids,
        )
        for row in rows
    ]
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

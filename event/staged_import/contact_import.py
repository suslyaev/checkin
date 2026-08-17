from collections import defaultdict

import tablib
from django.db import transaction
from django.urls import reverse

from event.models import Contact
from event.resources import ContactImport, find_producer

from .contact_columns import CONTACT_IMPORT_COLUMNS, REFERENCE_FIELD_MODELS
from .contact_validation import (
    load_reference_casing_maps,
    normalize_row_for_import,
    normalize_yo,
    resolve_reference_casing,
)

MATCH_CHOICE_NEW = 'new'


def _norm(value):
    """Ключ для сравнения ФИО: регистр не важен, «ё»/«е» не различаются —
    в базе могут быть старые карточки, заведённые до нормализации при загрузке."""
    if value is None:
        return ''
    return normalize_yo(str(value)).strip().lower()


def build_contact_match_index():
    """
    exact_index: (фамилия, имя, отчество) -> pk — для строк с указанным отчеством (п.2.1).
    candidates_index: (фамилия, имя) -> [{'pk', 'label', 'url'}] — все контакты с такой
    фамилией и именем, независимо от отчества карточки — используется только когда
    отчество во входной строке пустое (п.2.2), и никогда не приводит к автоматической
    привязке без подтверждения пользователя.
    existing_pks: множество всех ID карточек — для сопоставления по колонке id (Фаза 3).
    """
    exact_index = {}
    candidates_index = defaultdict(list)
    existing_pks = set()

    for pk, last_name, first_name, middle_name in Contact.objects.values_list(
        'pk', 'last_name', 'first_name', 'middle_name'
    ):
        existing_pks.add(pk)
        last_key = _norm(last_name)
        first_key = _norm(first_name)
        middle_key = _norm(middle_name)

        exact_index[(last_key, first_key, middle_key)] = pk

        label = f'{last_name} {first_name}' + (f' {middle_name}' if middle_name else '')
        candidates_index[(last_key, first_key)].append({
            'pk': pk,
            'label': label.strip(),
            'url': reverse('admin:event_contact_change', args=[pk]),
        })

    return exact_index, candidates_index, existing_pks


def _parse_middle_name(raw):
    if raw is None or raw == 'None':
        return None
    value = str(raw).strip()
    return value or None


def resolve_contact_import_action(row, exact_index, candidates_index, existing_pks):
    empty = {
        'action': None,
        'label': '—',
        'contact_pk': None,
        'contact_url': None,
        'match_candidates': [],
    }
    if row.get('excluded'):
        return empty

    normalized = normalize_row_for_import(row)

    # Колонка id — приоритетный способ сопоставления (Фаза 3): если указана,
    # ФИО вообще не участвует в поиске, только в самом обновлении карточки.
    # Некорректный/несуществующий ID уже отмечен ошибкой в contact_validation.py —
    # здесь для такой строки просто не резолвим действие (она в любом случае
    # заблокирована как has_errors).
    id_value = (normalized.get('id') or '').strip()
    if id_value:
        try:
            contact_id = int(id_value)
        except ValueError:
            return empty
        if contact_id not in existing_pks:
            return empty
        return {
            'action': 'update',
            'label': f'Обновить (#{contact_id}, по ID)',
            'contact_pk': contact_id,
            'contact_url': reverse('admin:event_contact_change', args=[contact_id]),
            'match_candidates': [],
        }

    last_name = normalized['last_name']
    first_name = normalized['first_name']
    middle_name = _parse_middle_name(normalized.get('middle_name'))

    if not last_name or not first_name:
        return empty

    last_key = _norm(last_name)
    first_key = _norm(first_name)

    if middle_name:
        pk = exact_index.get((last_key, first_key, _norm(middle_name)))
        if pk:
            return {
                'action': 'update',
                'label': f'Обновить (#{pk})',
                'contact_pk': pk,
                'contact_url': reverse('admin:event_contact_change', args=[pk]),
                'match_candidates': [],
            }
        return {
            'action': 'create',
            'label': 'Создать',
            'contact_pk': None,
            'contact_url': None,
            'match_candidates': [],
        }

    # Отчество не указано — никогда не привязываем автоматически (п.2.2).
    candidates = candidates_index.get((last_key, first_key), [])
    if not candidates:
        return {
            'action': 'create',
            'label': 'Создать',
            'contact_pk': None,
            'contact_url': None,
            'match_candidates': [],
        }

    choice = (row.get('match_choice') or '').strip()
    if choice == MATCH_CHOICE_NEW:
        return {
            'action': 'create',
            'label': 'Создать (подтверждено)',
            'contact_pk': None,
            'contact_url': None,
            'match_candidates': candidates,
        }
    if choice:
        try:
            chosen_pk = int(choice)
        except ValueError:
            chosen_pk = None
        chosen = next((c for c in candidates if c['pk'] == chosen_pk), None)
        if chosen:
            return {
                'action': 'update',
                'label': f'Обновить (#{chosen["pk"]}, подтверждено)',
                'contact_pk': chosen['pk'],
                'contact_url': chosen['url'],
                'match_candidates': candidates,
            }

    return {
        'action': 'confirm',
        'label': 'Требует подтверждения',
        'contact_pk': None,
        'contact_url': None,
        'match_candidates': candidates,
    }


# Базовые поля карточки, для которых на "Обновить"-строках показывается
# diff с текущим значением в базе (соцсети не сравниваем — там отдельная
# аддитивная логика per-network, не одно значение на поле) и которые при
# коммите бэкофилятся текущим значением, если их столбца нет в файле (Фаза 3).
BASE_DIFF_FIELDS = (
    'last_name', 'first_name', 'middle_name', 'nickname',
    'company', 'category', 'type_guest',
    'producer_last_name', 'producer_first_name', 'comment',
)


def _fetch_current_values(pks):
    """{pk: {field: текущее строковое значение}} для строк 'Обновить' —
    чтобы показать в таблице проверки, что реально изменится, и подставить
    вместо полей, чьих столбцов нет в загруженном файле (Фаза 3)."""
    if not pks:
        return {}
    contacts = Contact.objects.filter(pk__in=pks).select_related('company', 'category', 'type_guest', 'producer')
    result = {}
    for contact in contacts:
        result[contact.pk] = {
            'last_name': contact.last_name or '',
            'first_name': contact.first_name or '',
            'middle_name': contact.middle_name or '',
            'nickname': contact.nickname or '',
            'company': contact.company.name if contact.company else '',
            'category': contact.category.name if contact.category else '',
            'type_guest': contact.type_guest.name if contact.type_guest else '',
            'producer_last_name': contact.producer.last_name if contact.producer else '',
            'producer_first_name': contact.producer.first_name if contact.producer else '',
            'comment': contact.comment or '',
        }
    return result


def annotate_import_actions(rows):
    exact_index, candidates_index, existing_pks = build_contact_match_index()
    counts = {'create': 0, 'update': 0, 'confirm': 0}

    for row in rows:
        preview = resolve_contact_import_action(row, exact_index, candidates_index, existing_pks)
        row['import_action'] = preview['action']
        row['import_action_label'] = preview['label']
        row['import_action_pk'] = preview['contact_pk']
        row['import_action_url'] = preview['contact_url']
        row['match_candidates'] = preview['match_candidates']

        if row.get('excluded') or row.get('has_errors'):
            continue
        if preview['action'] in counts:
            counts[preview['action']] += 1

    update_pks = {row['import_action_pk'] for row in rows if row.get('import_action') == 'update' and row.get('import_action_pk')}
    current_values_by_pk = _fetch_current_values(update_pks)
    for row in rows:
        if row.get('import_action') == 'update':
            row['_current_values'] = current_values_by_pk.get(row.get('import_action_pk'), {})
        else:
            row['_current_values'] = {}

    return rows, counts


def _existing_reference_names(model):
    return {name.strip().lower() for name in model.objects.values_list('name', flat=True)}


def collect_new_reference_values(rows):
    """
    Значения company/category/type_guest из активных строк без ошибок, которых нет
    в справочнике: {field: {значение: [номера строк]}}. По ним запрашивается
    пакетное подтверждение (п.3) — без него ничего не создаётся молча.
    """
    existing = {field: _existing_reference_names(model) for field, model in REFERENCE_FIELD_MODELS.items()}
    new_values = {field: {} for field in REFERENCE_FIELD_MODELS}

    for row in rows:
        if row.get('excluded') or row.get('has_errors'):
            continue
        for field in REFERENCE_FIELD_MODELS:
            value = (row.get(field) or '').strip()
            if not value or value.lower() in existing[field]:
                continue
            new_values[field].setdefault(value, []).append(row.get('_row_number'))

    return new_values


def ensure_reference_values_exist(confirmed_refs):
    """Явно создаёт справочные значения, которые пользователь подтвердил
    (см. collect_new_reference_values) — до вызова ContactImport, чтобы
    ForeignKeyGetOrCreateWidget внутри просто их нашёл, а не создавал сам."""
    if not confirmed_refs:
        return
    for field, model in REFERENCE_FIELD_MODELS.items():
        for value in confirmed_refs.get(field, []):
            value = (value or '').strip()
            if value:
                model.objects.get_or_create(name=value)


def _combined_producer(row):
    last = (row.get('producer_last_name') or '').strip()
    first = (row.get('producer_first_name') or '').strip()
    return f'{last} {first}'.strip()


def collect_unresolved_producers(rows):
    """
    Продюсеры из активных строк без ошибок, которых нет среди пользователей
    системы: {значение: [номера строк]}. Только для отчёта (п.5) — контакт
    всё равно создаётся/обновляется, producer остаётся пустым, пока кто-то
    вручную не заведёт пользователя.
    """
    unresolved = {}
    for row in rows:
        if row.get('excluded') or row.get('has_errors'):
            continue
        value = _combined_producer(row)
        if not value:
            continue
        if find_producer(value) is None:
            unresolved.setdefault(value, []).append(row.get('_row_number'))
    return unresolved


def _effective_value(field, normalized, current_values, present_columns, is_update):
    """Значение поля для коммита: то, что в файле, либо (для 'Обновить'-строк,
    когда столбца нет в файле вовсе) текущее значение карточки — чтобы
    обрезанный файл без этого столбца не затирал его пустотой (Фаза 3)."""
    if is_update and present_columns is not None and field not in present_columns:
        return current_values.get(field, '')
    return normalized.get(field, '')


# Поля, которые реально уходят в ContactImport (без служебных id/producer_*).
_DATASET_BASE_FIELDS = [
    col for col in CONTACT_IMPORT_COLUMNS
    if col not in ('id', 'producer_last_name', 'producer_first_name')
]


def import_contact_rows(rows, user, confirmed_refs=None, present_columns=None):
    """Загружает отредактированные строки через ContactImport.

    Сопоставление с существующими карточками уже произведено в
    annotate_import_actions/resolve_contact_import_action — сюда прокидываются
    служебные колонки _force_new/_force_contact_id, чтобы ContactImport.get_instance
    не пытался угадывать карточку заново по неполному ФИО.
    """
    unresolved = [
        row.get('_row_number') for row in rows
        if not row.get('excluded') and row.get('import_action') == 'confirm'
    ]
    if unresolved:
        raise ValueError(
            'Есть строки, требующие подтверждения совпадения: '
            + ', '.join(str(n) for n in unresolved)
        )

    ensure_reference_values_exist(confirmed_refs)
    reference_casing_maps = load_reference_casing_maps()

    resource = ContactImport()
    headers = _DATASET_BASE_FIELDS + ['producer', '_force_new', '_force_contact_id']
    dataset = tablib.Dataset(headers=headers)

    for row in rows:
        if row.get('excluded'):
            continue
        normalized = normalize_row_for_import(row)
        is_update = row.get('import_action') == 'update'
        current_values = row.get('_current_values', {}) if is_update else {}

        # Опечатка в регистре (например "вип3" при существующей "ВИП3") не
        # должна плодить дубль справочника — приводим к уже существующему
        # написанию прямо перед сохранением (в сетке при этом остаётся то,
        # что реально ввёл пользователь, см. contact_validation.py).
        for field, casing_map in reference_casing_maps.items():
            canonical = resolve_reference_casing(normalized.get(field), casing_map)
            if canonical:
                normalized[field] = canonical

        base_values = [
            _effective_value(field, normalized, current_values, present_columns, is_update)
            for field in _DATASET_BASE_FIELDS
        ]

        producer_last = _effective_value('producer_last_name', normalized, current_values, present_columns, is_update)
        producer_first = _effective_value('producer_first_name', normalized, current_values, present_columns, is_update)
        producer_combined = f'{producer_last} {producer_first}'.strip()

        force_new = ''
        force_contact_id = ''
        if row.get('import_action') == 'create':
            force_new = '1'
        elif row.get('import_action') == 'update' and row.get('import_action_pk'):
            force_contact_id = str(row['import_action_pk'])

        values = base_values + [producer_combined, force_new, force_contact_id]
        dataset.append(values)

    if len(dataset) == 0:
        raise ValueError('Нет строк для загрузки')

    with transaction.atomic():
        result = resource.import_data(dataset, dry_run=False, user=user, raise_errors=True)
    return result

import tablib
from django.db import transaction
from django.urls import reverse

from event.models import Contact
from event.resources import ContactImport

from .contact_columns import CONTACT_IMPORT_COLUMNS
from .contact_validation import normalize_row_for_import


def build_contact_match_index():
    """Индексы для поиска контакта по ФИО (как ContactImport.get_instance)."""
    with_middle = {}
    without_middle = {}

    for pk, last_name, first_name, middle_name in Contact.objects.values_list(
        'pk', 'last_name', 'first_name', 'middle_name'
    ):
        if middle_name and str(middle_name).strip():
            with_middle[(last_name, first_name, str(middle_name).strip())] = pk
        else:
            key = (last_name, first_name)
            if key not in without_middle:
                without_middle[key] = pk

    return with_middle, without_middle


def _parse_middle_name(raw):
    if raw is None or raw == 'None':
        return None
    value = str(raw).strip()
    return value or None


def resolve_contact_import_action(row, with_middle, without_middle):
    if row.get('excluded'):
        return {'action': None, 'label': '—', 'contact_pk': None, 'contact_url': None}

    normalized = normalize_row_for_import(row)
    last_name = normalized['last_name']
    first_name = normalized['first_name']
    middle_name = _parse_middle_name(normalized.get('middle_name'))

    if not last_name or not first_name:
        return {'action': None, 'label': '—', 'contact_pk': None, 'contact_url': None}

    if middle_name:
        contact_pk = with_middle.get((last_name, first_name, middle_name))
    else:
        contact_pk = without_middle.get((last_name, first_name))

    if contact_pk:
        return {
            'action': 'update',
            'label': f'Обновить (#{contact_pk})',
            'contact_pk': contact_pk,
            'contact_url': reverse('admin:event_contact_change', args=[contact_pk]),
        }

    return {
        'action': 'create',
        'label': 'Создать',
        'contact_pk': None,
        'contact_url': None,
    }


def annotate_import_actions(rows):
    with_middle, without_middle = build_contact_match_index()
    create_count = 0
    update_count = 0

    for row in rows:
        preview = resolve_contact_import_action(row, with_middle, without_middle)
        row['import_action'] = preview['action']
        row['import_action_label'] = preview['label']
        row['import_action_pk'] = preview['contact_pk']
        row['import_action_url'] = preview['contact_url']

        if row.get('excluded') or row.get('has_errors'):
            continue
        if preview['action'] == 'create':
            create_count += 1
        elif preview['action'] == 'update':
            update_count += 1

    return rows, {'create': create_count, 'update': update_count}


def import_contact_rows(rows, user):
    """Загружает отредактированные строки через существующий ContactImport."""
    resource = ContactImport()
    dataset = tablib.Dataset(headers=CONTACT_IMPORT_COLUMNS)

    for row in rows:
        if row.get('excluded'):
            continue
        normalized = normalize_row_for_import(row)
        dataset.append([normalized[col] for col in CONTACT_IMPORT_COLUMNS])

    if len(dataset) == 0:
        raise ValueError('Нет строк для загрузки')

    with transaction.atomic():
        result = resource.import_data(dataset, dry_run=False, user=user, raise_errors=True)
    return result

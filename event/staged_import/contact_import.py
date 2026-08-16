from collections import defaultdict

import tablib
from django.db import transaction
from django.urls import reverse

from event.models import Contact
from event.resources import ContactImport

from .contact_columns import CONTACT_IMPORT_COLUMNS
from .contact_validation import normalize_row_for_import, normalize_yo

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
    """
    exact_index = {}
    candidates_index = defaultdict(list)

    for pk, last_name, first_name, middle_name in Contact.objects.values_list(
        'pk', 'last_name', 'first_name', 'middle_name'
    ):
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

    return exact_index, candidates_index


def _parse_middle_name(raw):
    if raw is None or raw == 'None':
        return None
    value = str(raw).strip()
    return value or None


def resolve_contact_import_action(row, exact_index, candidates_index):
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


def annotate_import_actions(rows):
    exact_index, candidates_index = build_contact_match_index()
    counts = {'create': 0, 'update': 0, 'confirm': 0}

    for row in rows:
        preview = resolve_contact_import_action(row, exact_index, candidates_index)
        row['import_action'] = preview['action']
        row['import_action_label'] = preview['label']
        row['import_action_pk'] = preview['contact_pk']
        row['import_action_url'] = preview['contact_url']
        row['match_candidates'] = preview['match_candidates']

        if row.get('excluded') or row.get('has_errors'):
            continue
        if preview['action'] in counts:
            counts[preview['action']] += 1

    return rows, counts


def import_contact_rows(rows, user):
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

    resource = ContactImport()
    headers = CONTACT_IMPORT_COLUMNS + ['_force_new', '_force_contact_id']
    dataset = tablib.Dataset(headers=headers)

    for row in rows:
        if row.get('excluded'):
            continue
        normalized = normalize_row_for_import(row)

        force_new = ''
        force_contact_id = ''
        if row.get('import_action') == 'create':
            force_new = '1'
        elif row.get('import_action') == 'update' and row.get('import_action_pk'):
            force_contact_id = str(row['import_action_pk'])

        values = [normalized[col] for col in CONTACT_IMPORT_COLUMNS] + [force_new, force_contact_id]
        dataset.append(values)

    if len(dataset) == 0:
        raise ValueError('Нет строк для загрузки')

    with transaction.atomic():
        result = resource.import_data(dataset, dry_run=False, user=user, raise_errors=True)
    return result

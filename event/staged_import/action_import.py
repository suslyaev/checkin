"""Регистрация на мероприятие через загрузчик (Фаза 4).

Колонки 'event'/'status' (см. contact_columns.py) не создают новую сущность
молча (мероприятие — через обычную панель подтверждения новых справочных
значений, см. REFERENCE_FIELD_MODELS) и не блокируют импорт карточек людей —
регистрация выполняется отдельным шагом уже после того, как у всех активных
строк гарантированно есть карточка (п.4 требований: «этап 4 запускается
только после этапа 3»).
"""

from event.models import Action, ModuleInstance

from .contact_columns import DEFAULT_STATUS_CODE, STATUS_LABEL_TO_CODE
from .contact_validation import resolve_reference_casing


def _canonical_event_name(value, event_casing_map):
    value = (value or '').strip()
    if not value:
        return ''
    return resolve_reference_casing(value, event_casing_map) or value


def preview_registrations(rows, reference_casing_maps):
    """
    Проставляет row['_registration_preview'] для активных строк без ошибок,
    где указано мероприятие: 'will_register' / 'will_update_status' /
    'already_registered'. Строки без мероприятия/с ошибками/исключённые —
    None (регистрация им не касается). Один bulk-запрос, без N+1.
    """
    event_casing_map = reference_casing_maps.get('event', {})
    candidates = []  # (row, contact_pk_or_None, canonical_event_name)

    for row in rows:
        row['_registration_preview'] = None
        if row.get('excluded') or row.get('has_errors'):
            continue
        event_name = _canonical_event_name(row.get('event'), event_casing_map)
        if not event_name:
            continue
        contact_pk = row.get('import_action_pk') if row.get('import_action') == 'update' else None
        candidates.append((row, contact_pk, event_name))

    lookup_pks = {pk for _, pk, _ in candidates if pk}
    lookup_names = {name for _, _, name in candidates}
    existing_by_key = {}
    if lookup_pks and lookup_names:
        actions = Action.objects.filter(
            contact_id__in=lookup_pks, event__name__in=lookup_names
        ).select_related('event')
        for action in actions:
            existing_by_key[(action.contact_id, action.event.name)] = action.action_type

    for row, contact_pk, event_name in candidates:
        status_label = (row.get('status') or '').strip()
        explicit_code = STATUS_LABEL_TO_CODE.get(status_label) if status_label else None
        current_code = existing_by_key.get((contact_pk, event_name)) if contact_pk else None
        if current_code is None:
            row['_registration_preview'] = 'will_register'
        elif explicit_code and explicit_code != current_code:
            row['_registration_preview'] = 'will_update_status'
        else:
            row['_registration_preview'] = 'already_registered'

    return rows


def register_actions(rows, commit_result, user, reference_casing_maps):
    """
    Регистрирует людей на мероприятия после успешного коммита карточек.
    rows — те же (полные, с excluded) строки, что были переданы в
    import_contact_rows; commit_result — то, что вернул ContactImport.import_data
    (result.rows идёт в том же порядке, что и активные строки датасета,
    и после сохранения содержит object_id — pk реально созданной/обновлённой
    карточки, см. import_export.results.RowResult.add_instance_info).

    Сбой регистрации одной строки не прерывает остальные — уже сохранённые
    карточки не должны теряться из-за проблемы с конкретной регистрацией
    (п.4 требований), ошибки собираются и возвращаются отдельным списком.
    """
    event_casing_map = reference_casing_maps.get('event', {})
    active_rows = [row for row in rows if not row.get('excluded')]

    summary = {'registered': 0, 'status_updated': 0, 'unchanged': 0, 'errors': []}

    for row, row_result in zip(active_rows, commit_result.rows):
        event_name = _canonical_event_name(row.get('event'), event_casing_map)
        if not event_name:
            continue

        row_number = row.get('_row_number')
        contact_pk = row_result.object_id
        if not contact_pk:
            summary['errors'].append({'row_number': row_number, 'error': 'Не удалось определить карточку для регистрации'})
            continue

        try:
            event_obj = ModuleInstance.objects.get(name=event_name)
        except ModuleInstance.DoesNotExist:
            summary['errors'].append({'row_number': row_number, 'error': f'Мероприятие «{event_name}» не найдено'})
            continue

        status_label = (row.get('status') or '').strip()
        explicit_code = STATUS_LABEL_TO_CODE.get(status_label) if status_label else None

        try:
            action, created = Action.objects.get_or_create(
                contact_id=contact_pk, event=event_obj,
                defaults={'action_type': explicit_code or DEFAULT_STATUS_CODE, 'create_user': user},
            )
            if created:
                summary['registered'] += 1
            elif explicit_code and action.action_type != explicit_code:
                action.action_type = explicit_code
                action.update_user = user
                action.save()
                summary['status_updated'] += 1
            else:
                summary['unchanged'] += 1
        except Exception as exc:
            summary['errors'].append({'row_number': row_number, 'error': str(exc)})

    return summary

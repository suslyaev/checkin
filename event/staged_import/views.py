import json
import os
import re

from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from event.models import CustomUser

from .contact_columns import STATUS_LABELS, columns_for_session, labels_for_session, social_groups_in_keys
from .contact_import import (
    BASE_DIFF_FIELDS,
    MATCH_CHOICE_NEW,
    REFERENCE_FIELD_MODELS,
    annotate_import_actions,
    collect_new_reference_values,
    collect_unresolved_producers,
    import_contact_rows,
)
from .contact_validation import load_reference_casing_maps, resolve_reference_casing, validate_contact_rows
from .forms import ContactStagedUploadForm
from .parsers import parse_spreadsheet
from .social_links import reflow_social_columns

SESSION_KEY = 'staged_contact_import_rows'
SESSION_REFS_KEY = 'staged_contact_import_confirmed_refs'
SESSION_PRESENT_COLUMNS_KEY = 'staged_contact_import_present_columns'


def _require_contact_import_perm(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if not request.user.has_perm('event.add_contact'):
        raise PermissionDenied


def _session_columns(present_columns):
    """Полный список колонок этой загрузки: базовые + столько групп соцсетей,
    сколько реально было распознано в файле (present_columns уже содержит их
    ключи, см. parsers.py) — без фиксированного числа групп."""
    return columns_for_session(social_groups_in_keys(present_columns or set()))


def _session_labels(present_columns):
    return labels_for_session(social_groups_in_keys(present_columns or set()))


def _rows_from_session(request):
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return None
    return json.loads(raw)


def _save_rows_to_session(request, rows, present_columns):
    columns = _session_columns(present_columns)
    serializable = []
    for row in rows:
        item = {col: row.get(col, '') for col in columns}
        item['_row_number'] = row.get('_row_number')
        item['excluded'] = bool(row.get('excluded'))
        item['match_choice'] = row.get('match_choice', '')
        serializable.append(item)
    request.session[SESSION_KEY] = json.dumps(serializable, ensure_ascii=False)
    request.session.modified = True


def _clear_session(request):
    request.session.pop(SESSION_KEY, None)
    request.session.pop(SESSION_REFS_KEY, None)
    request.session.pop(SESSION_PRESENT_COLUMNS_KEY, None)
    request.session.modified = True


def _present_columns_from_session(request):
    raw = request.session.get(SESSION_PRESENT_COLUMNS_KEY)
    return set(json.loads(raw)) if raw else None


def _save_present_columns_to_session(request, present_columns):
    request.session[SESSION_PRESENT_COLUMNS_KEY] = json.dumps(sorted(present_columns), ensure_ascii=False)
    request.session.modified = True


def _confirmed_refs_from_session(request):
    raw = request.session.get(SESSION_REFS_KEY)
    data = json.loads(raw) if raw else {}
    return {field: set(data.get(field, [])) for field in REFERENCE_FIELD_MODELS}


def _save_confirmed_refs_to_session(request, confirmed_refs):
    serializable = {field: sorted(values) for field, values in confirmed_refs.items()}
    request.session[SESSION_REFS_KEY] = json.dumps(serializable, ensure_ascii=False)
    request.session.modified = True


def _update_confirmed_refs_from_post(request):
    """Чекбоксы подтверждения новых значений справочников отражают ТЕКУЩЕЕ
    состояние формы при каждой отправке (как match_choice) — полностью
    заменяем сохранённый набор тем, что реально отмечено сейчас."""
    confirmed_refs = {
        field: set(request.POST.getlist(f'confirm_ref_{field}'))
        for field in REFERENCE_FIELD_MODELS
    }
    _save_confirmed_refs_to_session(request, confirmed_refs)
    return confirmed_refs


def _prepare_table_rows(validated_rows, new_reference_values, present_columns):
    new_reference_by_field = {
        field: set(values.keys()) for field, values in new_reference_values.items()
    }
    reference_casing_maps = load_reference_casing_maps()
    table_rows = []
    for index, row in enumerate(validated_rows):
        cells = []
        row_errors = row.get('errors', {})
        row_warnings = row.get('warnings', {})
        is_update = row.get('import_action') == 'update'
        current_values = row.get('_current_values', {}) if is_update else {}
        for col in _session_columns(present_columns):
            cell_errors = row_errors.get(col, [])
            cell_warnings = row_warnings.get(col, [])
            value = row.get(col, '')
            is_reference = col in REFERENCE_FIELD_MODELS
            is_new_reference = bool(value.strip()) and value.strip() in new_reference_by_field.get(col, set())
            in_file = present_columns is None or col in present_columns

            changed = False
            current_value = ''
            if is_update and col in BASE_DIFF_FIELDS and in_file:
                current_value = current_values.get(col, '')
                effective_value = value.strip()
                if is_reference:
                    # Опечатка в регистре — не "изменение", при коммите всё равно
                    # подставится уже существующее написание (см. contact_import.py).
                    effective_value = resolve_reference_casing(
                        effective_value, reference_casing_maps.get(col, {})
                    ) or effective_value
                changed = effective_value != current_value.strip()

            css_parts = []
            if cell_errors:
                css_parts.append('cell-error')
            elif cell_warnings:
                css_parts.append('cell-warning')
            if is_new_reference:
                css_parts.append('cell-new-reference')
            if not in_file:
                css_parts.append('cell-not-in-file')

            cells.append({
                'field': col,
                'value': value,
                'errors': cell_errors,
                'warnings': cell_warnings,
                'css': ' '.join(css_parts),
                'is_comment': col == 'comment',
                'is_reference': is_reference,
                'is_new_reference': is_new_reference,
                'is_status': col == 'status',
                'is_update': is_update,
                'changed': changed,
                'current_value': current_value,
                'in_file': in_file,
            })
        table_rows.append({
            'index': index,
            'row_number': row.get('_row_number'),
            'excluded': row.get('excluded'),
            'has_errors': row.get('has_errors'),
            'has_warnings': row.get('has_warnings'),
            'has_new_reference': any(cell['is_new_reference'] for cell in cells),
            'import_action': row.get('import_action'),
            'import_action_label': row.get('import_action_label', '—'),
            'import_action_url': row.get('import_action_url'),
            'needs_confirm': row.get('import_action') == 'confirm',
            'match_choice': row.get('match_choice', ''),
            'match_candidates': row.get('match_candidates', []),
            'registration_preview': row.get('_registration_preview'),
            'cells': cells,
        })
    return table_rows


def _issue_columns(table_rows, labels):
    """Столбцы, где у активных строк есть ошибки/предупреждения, — для
    фильтра «проблема в столбце …» на странице проверки."""
    counts = {}
    for row in table_rows:
        if row['excluded']:
            continue
        for cell in row['cells']:
            if cell['errors'] or cell['warnings']:
                item = counts.setdefault(cell['field'], {'errors': 0, 'warnings': 0})
                item['errors'] += bool(cell['errors'])
                item['warnings'] += bool(cell['warnings'])
    return [
        {'field': field, 'label': labels.get(field, field), **item}
        for field, item in counts.items()
    ]


def _prepare_new_reference_panels(new_reference_values, confirmed_refs):
    labels = {'company': 'Компания', 'category': 'Категория', 'type_guest': 'Тип гостя', 'event': 'Мероприятие'}
    panels = []
    pending_count = 0
    for field, values_by_row in new_reference_values.items():
        items = []
        for value, row_numbers in sorted(values_by_row.items()):
            confirmed = value in confirmed_refs.get(field, set())
            if not confirmed:
                pending_count += 1
            items.append({
                'value': value,
                'row_numbers': row_numbers,
                'confirmed': confirmed,
            })
        if items:
            panels.append({'field': field, 'label': labels.get(field, field), 'items': items})
    return panels, pending_count


def _full_preview(rows, request, present_columns):
    """Валидация + сопоставление + новые справочные значения + продюсеры одним вызовом."""
    validated, summary = validate_contact_rows(rows, present_columns=present_columns)
    validated, action_summary = annotate_import_actions(validated)
    summary['create_count'] = action_summary['create']
    summary['update_count'] = action_summary['update']
    summary['confirm_count'] = action_summary['confirm']

    new_reference_values = collect_new_reference_values(validated)
    confirmed_refs = _confirmed_refs_from_session(request)
    new_reference_panels, pending_refs_count = _prepare_new_reference_panels(
        new_reference_values, confirmed_refs
    )
    unresolved_producers = collect_unresolved_producers(validated)

    registration_counts = {'will_register': 0, 'will_update_status': 0, 'already_registered': 0}
    for row in validated:
        preview = row.get('_registration_preview')
        if preview in registration_counts:
            registration_counts[preview] += 1

    summary['pending_refs_count'] = pending_refs_count
    summary['unresolved_producers_count'] = len(unresolved_producers)
    summary['will_register_count'] = registration_counts['will_register']
    summary['will_update_status_count'] = registration_counts['will_update_status']
    summary['already_registered_count'] = registration_counts['already_registered']
    summary['can_import'] = (
        summary['can_import'] and summary['confirm_count'] == 0 and pending_refs_count == 0
    )

    extra = {
        'new_reference_values': new_reference_values,
        'new_reference_panels': new_reference_panels,
        'unresolved_producers': [
            {
                'value': value,
                'last_name': value.split(' ', 1)[0],
                'first_name': value.split(' ', 1)[1] if ' ' in value else '',
                'row_numbers': row_numbers,
            }
            for value, row_numbers in sorted(unresolved_producers.items())
        ],
        'confirmed_refs': confirmed_refs,
    }
    return validated, summary, extra


def _reference_datalists():
    return {
        field: sorted(model.objects.values_list('name', flat=True))
        for field, model in REFERENCE_FIELD_MODELS.items()
    }


_ROW_FIELD_RE = re.compile(r'^row_(\d+)__(.+)$')


def _rows_from_post(request, stored_rows, present_columns):
    """Строки таблицы с учётом правок из формы. Браузер присылает только
    изменённые ячейки одним JSON-полем row_changes (см. скрипт в
    contact_review.html) — иначе на файле в пару тысяч строк форма упирается
    в DATA_UPLOAD_MAX_NUMBER_FIELDS. Остальное берётся из сессии, куда
    сохранено ровно то, что было отрисовано в таблице."""
    columns = _session_columns(present_columns)
    raw_changes = request.POST.get('row_changes')
    if raw_changes is None:
        # Без JS форма приходит целиком, по полю на ячейку.
        changes = request.POST
        rows = [{'_row_number': row.get('_row_number'), 'excluded': False, 'match_choice': ''} for row in stored_rows]
        for index, row in enumerate(rows):
            row['excluded'] = changes.get(f'row_{index}__excluded') == 'on'
            row['match_choice'] = changes.get(f'row_{index}__match_choice', '')
            for col in columns:
                row[col] = changes.get(f'row_{index}__{col}', '')
        return rows

    rows = []
    for stored in stored_rows:
        row = {col: stored.get(col, '') for col in columns}
        row['_row_number'] = stored.get('_row_number')
        row['excluded'] = bool(stored.get('excluded'))
        row['match_choice'] = stored.get('match_choice', '')
        rows.append(row)

    try:
        changes = json.loads(raw_changes)
    except ValueError:
        changes = {}
    allowed = set(columns) | {'match_choice'}
    for name, value in (changes.items() if isinstance(changes, dict) else []):
        m = _ROW_FIELD_RE.match(name)
        if not m or int(m.group(1)) >= len(rows):
            continue
        row = rows[int(m.group(1))]
        field = m.group(2)
        if field == 'excluded':
            row['excluded'] = value == 'on'
        elif field in allowed:
            row[field] = '' if value is None else str(value)
    return rows


BULK_SCOPE_EMPTY = 'empty'
BULK_SCOPE_ERRORS = 'errors'
BULK_SCOPE_EQUALS = 'equals'
BULK_SCOPE_ALL = 'all'
BULK_SCOPES = [
    (BULK_SCOPE_EMPTY, 'где значение пустое'),
    (BULK_SCOPE_ERRORS, 'где в этом столбце ошибка'),
    (BULK_SCOPE_EQUALS, 'где значение равно…'),
    (BULK_SCOPE_ALL, 'во всех строках'),
]
BULK_MATCH_NEW = 'new'
BULK_MATCH_SINGLE = 'single'
# ID массово не проставляется — он у каждой строки свой.
BULK_EXCLUDED_FIELDS = {'id'}


def _bulk_row_indexes(request):
    """Индексы строк, показанных фильтром на странице: массовые действия
    тогда применяются только к ним. None — фильтр не включён, ко всем."""
    raw = request.POST.get('bulk_rows')
    if not raw:
        return None
    try:
        return {int(index) for index in json.loads(raw)}
    except (TypeError, ValueError):
        return None


def _bulk_fill_columns(present_columns):
    return [col for col in _session_columns(present_columns) if col not in BULK_EXCLUDED_FIELDS]


def _apply_bulk_fill(request, rows, present_columns):
    """Массово проставляет значение в одном столбце по всем активным строкам,
    подходящим под условие. Если столбца не было в файле и проставляется
    непустое значение — столбец становится «присутствующим» (например, файл
    без «Наименования события», а событие выбрали для всех строк разом).
    Возвращает (present_columns, число изменённых строк, ошибка или None)."""
    field = request.POST.get('bulk_field', '')
    scope = request.POST.get('bulk_scope', BULK_SCOPE_EMPTY)
    value = request.POST.get('bulk_value', '').strip()
    match_value = request.POST.get('bulk_match_value', '').strip()

    if field not in _bulk_fill_columns(present_columns):
        return present_columns, 0, 'Выберите столбец для массового изменения.'
    if scope not in dict(BULK_SCOPES):
        return present_columns, 0, 'Выберите, в каких строках менять значение.'

    only_rows = _bulk_row_indexes(request)
    rows_with_errors = set()
    if scope == BULK_SCOPE_ERRORS:
        validated, _summary = validate_contact_rows(rows, present_columns=present_columns)
        rows_with_errors = {i for i, row in enumerate(validated) if row['errors'].get(field)}

    changed = 0
    for index, row in enumerate(rows):
        if row.get('excluded') or (only_rows is not None and index not in only_rows):
            continue
        current = (row.get(field) or '').strip()
        if scope == BULK_SCOPE_EMPTY and current:
            continue
        if scope == BULK_SCOPE_ERRORS and index not in rows_with_errors:
            continue
        if scope == BULK_SCOPE_EQUALS and current.lower() != match_value.lower():
            continue
        if current != value:
            row[field] = value
            changed += 1

    if value and present_columns is not None and field not in present_columns:
        present_columns = set(present_columns) | {field}
        _save_present_columns_to_session(request, present_columns)
    return present_columns, changed, None


def _apply_bulk_match(request, rows, present_columns):
    """Проставляет «Действие» всем строкам «Требует подтверждения», где оно
    ещё не выбрано: создать нового, либо обновить карточку, если кандидат
    ровно один. Возвращает (число изменённых строк, ошибка или None)."""
    mode = request.POST.get('bulk_match_mode', '')
    if mode not in (BULK_MATCH_NEW, BULK_MATCH_SINGLE):
        return 0, 'Выберите действие для массового применения.'

    validated, _summary = validate_contact_rows(rows, present_columns=present_columns)
    validated, _counts = annotate_import_actions(validated)
    only_rows = _bulk_row_indexes(request)
    changed = 0
    for index, (row, preview) in enumerate(zip(rows, validated)):
        if only_rows is not None and index not in only_rows:
            continue
        if preview.get('import_action') != 'confirm' or (row.get('match_choice') or '').strip():
            continue
        candidates = preview.get('match_candidates') or []
        if mode == BULK_MATCH_NEW:
            row['match_choice'] = MATCH_CHOICE_NEW
        elif len(candidates) == 1:
            row['match_choice'] = str(candidates[0]['pk'])
        else:
            continue
        changed += 1
    return changed, None


PRODUCER_GROUP_NAME = 'Продюсер'


def _can_create_producers(user):
    return user.has_perm('event.add_customuser')


def _normalize_phone(value):
    """«8 (985) 170-02-71», «+7 985 170 02 71», «9851700271» -> «+79851700271».
    Остальное — как ввели (без пробелов/скобок/дефисов), формат проверит
    CustomUser.clean()."""
    value = (value or '').strip()
    digits = re.sub(r'\D', '', value)
    if not value.startswith('+'):
        if len(digits) == 11 and digits[0] in '78':
            return '+7' + digits[1:]
        if len(digits) == 10:
            return '+7' + digits
    return '+' + digits if digits else ''


def _create_producer(request, index):
    """Заводит пользователя-продюсера из панели «Продюсеры не найдены» —
    так же, как форма добавления пользователя в админке (is_staff, роль),
    только без пароля: его можно задать позже в карточке пользователя.
    Возвращает (уровень сообщения, текст)."""
    if not _can_create_producers(request.user):
        raise PermissionDenied
    prefix = f'new_producer_{index}_'
    last_name = request.POST.get(prefix + 'last_name', '').strip()
    first_name = request.POST.get(prefix + 'first_name', '').strip()
    phone = _normalize_phone(request.POST.get(prefix + 'phone', ''))
    group = Group.objects.filter(pk=request.POST.get(prefix + 'group') or None).first()

    if not last_name:
        return messages.ERROR, 'Чтобы завести продюсера, укажите фамилию.'
    full_name = f'{last_name} {first_name}'.strip()
    if not phone:
        return messages.ERROR, f'Чтобы завести продюсера «{full_name}», укажите телефон — это его логин.'
    if group is None:
        return messages.ERROR, 'Выберите роль для нового пользователя.'

    user = CustomUser(phone=phone, last_name=last_name, first_name=first_name or None, is_staff=True, is_active=True)
    user.set_unusable_password()
    try:
        user.full_clean(exclude=['password', 'auth_token'])
    except ValidationError as exc:
        return messages.ERROR, f'Не удалось завести «{full_name}»: ' + '; '.join(exc.messages)
    with transaction.atomic():
        user.save()
        user.groups.set([group])
    return messages.SUCCESS, (
        f'Заведён пользователь «{user}» ({phone}, роль «{group.name}») — '
        f'продюсер подставится в карточки при загрузке. Пароль можно задать в карточке пользователя.'
    )


def staged_contact_upload_view(request):
    _require_contact_import_perm(request)
    form = ContactStagedUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        try:
            rows, present_columns = parse_spreadsheet(form.cleaned_data['file'])
            rows, present_columns, reflowed_count = reflow_social_columns(rows, present_columns)
            _clear_session(request)
            _save_present_columns_to_session(request, present_columns)
            validated, summary, _extra = _full_preview(rows, request, present_columns)
            _save_rows_to_session(request, validated, present_columns)
            messages.info(
                request,
                f'Загружено строк: {summary["total"]}. '
                f'Создать: {summary["create_count"]}, обновить: {summary["update_count"]}, '
                f'требуют подтверждения: {summary["confirm_count"]}. '
                f'Ошибок: {summary["error_rows"]}, предупреждений: {summary["warning_rows"]}. '
                f'Будет зарегистрировано на мероприятия: {summary["will_register_count"]}.',
            )
            if reflowed_count:
                messages.info(
                    request,
                    f'В строках: {reflowed_count} значения соцсетей стояли не под своими заголовками — '
                    f'ссылки и подписчики разложены по столбцам, соцсеть определена по ссылке. Проверьте.',
                )
            return HttpResponseRedirect(reverse('admin:staged_import_contacts_review'))
        except ValueError as exc:
            form.add_error('file', str(exc))

    context = {
        'title': 'Пошаговая загрузка людей',
        'form': form,
        'template_url': reverse('admin:staged_import_contacts_template'),
        'step': 1,
    }
    return render(request, 'admin/event/staged_import/contact_upload.html', context)


def staged_contact_review_view(request):
    _require_contact_import_perm(request)
    stored = _rows_from_session(request)
    if not stored:
        messages.warning(request, 'Сначала загрузите файл.')
        return HttpResponseRedirect(reverse('admin:staged_import_contacts'))

    present_columns = _present_columns_from_session(request)

    if request.method == 'POST':
        action = request.POST.get('action', 'validate')
        rows = _rows_from_post(request, stored, present_columns)
        _update_confirmed_refs_from_post(request)
        bulk_message = None
        if action.startswith('create_producer:'):
            level, text = _create_producer(request, action.split(':', 1)[1])
            messages.add_message(request, level, text)
            action = 'create_producer'
        elif action == 'bulk_fill':
            present_columns, changed, bulk_error = _apply_bulk_fill(request, rows, present_columns)
            bulk_message = bulk_error or f'Массовое изменение: обновлено строк — {changed}.'
        elif action == 'bulk_match':
            changed, bulk_error = _apply_bulk_match(request, rows, present_columns)
            bulk_message = bulk_error or f'Действие проставлено в строках: {changed}.'
        validated, summary, extra = _full_preview(rows, request, present_columns)
        _save_rows_to_session(request, validated, present_columns)

        if action == 'import':
            if not summary['can_import']:
                messages.error(
                    request,
                    'Исправьте ошибки, подтвердите совпадения и новые значения справочников '
                    'или исключите проблемные строки перед загрузкой.',
                )
            else:
                try:
                    confirmed_refs = {field: list(values) for field, values in extra['confirmed_refs'].items()}
                    result, registration_summary = import_contact_rows(
                        validated, request.user,
                        confirmed_refs=confirmed_refs, present_columns=present_columns,
                    )
                    _clear_session(request)
                    success_text = (
                        f'Загрузка завершена: новых {result.totals.get("new", 0)}, '
                        f'обновлено {result.totals.get("update", 0)}, '
                        f'без изменений {result.totals.get("skip", 0)}.'
                    )
                    if any([registration_summary['registered'], registration_summary['status_updated'], registration_summary['unchanged']]):
                        success_text += (
                            f' Регистрация на мероприятия: новых {registration_summary["registered"]}, '
                            f'статус обновлён {registration_summary["status_updated"]}, '
                            f'без изменений {registration_summary["unchanged"]}.'
                        )
                    messages.success(request, success_text)
                    if registration_summary['errors']:
                        messages.warning(
                            request,
                            'Не удалось зарегистрировать (карточки при этом сохранены): ' + '; '.join(
                                f'строка {err["row_number"]}: {err["error"]}' for err in registration_summary['errors']
                            ),
                        )
                    return HttpResponseRedirect(reverse('admin:event_contact_changelist'))
                except Exception as exc:
                    messages.error(request, f'Ошибка при загрузке: {exc}')
        elif bulk_message:
            messages.info(request, bulk_message)
        elif action == 'create_producer':
            pass
        else:
            messages.info(request, 'Данные обновлены. Проверьте таблицу.')

        stored = validated

    else:
        stored, summary, extra = _full_preview(stored, request, present_columns)

    session_labels = _session_labels(present_columns)
    table_rows = _prepare_table_rows(stored, extra['new_reference_values'], present_columns)
    context = {
        'issue_columns': _issue_columns(table_rows, session_labels),
        'bulk_columns': [
            {'field': col, 'label': session_labels[col]} for col in _bulk_fill_columns(present_columns)
        ],
        'bulk_scopes': BULK_SCOPES,
        'bulk_match_new': BULK_MATCH_NEW,
        'bulk_match_single': BULK_MATCH_SINGLE,
        'title': 'Проверка данных перед загрузкой',
        'table_rows': table_rows,
        'column_labels': [session_labels[col] for col in _session_columns(present_columns)],
        'summary': summary,
        'new_reference_panels': extra['new_reference_panels'],
        'unresolved_producers': extra['unresolved_producers'],
        'can_create_producers': _can_create_producers(request.user),
        'user_groups': Group.objects.order_by('name'),
        'producer_group': Group.objects.filter(name=PRODUCER_GROUP_NAME).first(),
        'reference_datalists': _reference_datalists(),
        'status_labels': STATUS_LABELS,
        'upload_url': reverse('admin:staged_import_contacts'),
        'step': 2,
    }
    return render(request, 'admin/event/staged_import/contact_review.html', context)


def staged_contact_cancel_view(request):
    _require_contact_import_perm(request)
    _clear_session(request)
    messages.info(request, 'Загрузка отменена.')
    return HttpResponseRedirect(reverse('admin:staged_import_contacts'))


def staged_contact_template_view(request):
    _require_contact_import_perm(request)
    # Отдельный файл от event/templates/import_cont.xlsx — тот шаблон принадлежит
    # "сырому" импорту в стандартной админке (event.resources.ContactImport,
    # /admin/event/contact/import/), у него другой, более старый формат колонок.
    file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'staged_import_cont.xlsx')
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='staged_import_cont.xlsx')


def staged_import_urls(admin_site):
    wrap = admin_site.admin_view
    return [
        path(
            'staged-import/contacts/',
            wrap(staged_contact_upload_view),
            name='staged_import_contacts',
        ),
        path(
            'staged-import/contacts/template/',
            wrap(staged_contact_template_view),
            name='staged_import_contacts_template',
        ),
        path(
            'staged-import/contacts/review/',
            wrap(staged_contact_review_view),
            name='staged_import_contacts_review',
        ),
        path(
            'staged-import/contacts/cancel/',
            wrap(staged_contact_cancel_view),
            name='staged_import_contacts_cancel',
        ),
    ]

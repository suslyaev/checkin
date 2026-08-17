import json
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .contact_columns import CONTACT_COLUMN_LABELS, CONTACT_IMPORT_COLUMNS
from .contact_import import (
    REFERENCE_FIELD_MODELS,
    annotate_import_actions,
    collect_new_reference_values,
    collect_unresolved_producers,
    import_contact_rows,
)
from .contact_validation import validate_contact_rows
from .forms import ContactStagedUploadForm
from .parsers import parse_spreadsheet

SESSION_KEY = 'staged_contact_import_rows'
SESSION_REFS_KEY = 'staged_contact_import_confirmed_refs'


def _require_contact_import_perm(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if not request.user.has_perm('event.add_contact'):
        raise PermissionDenied


def _rows_from_session(request):
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return None
    return json.loads(raw)


def _save_rows_to_session(request, rows):
    serializable = []
    for row in rows:
        item = {col: row.get(col, '') for col in CONTACT_IMPORT_COLUMNS}
        item['_row_number'] = row.get('_row_number')
        item['excluded'] = bool(row.get('excluded'))
        item['match_choice'] = row.get('match_choice', '')
        serializable.append(item)
    request.session[SESSION_KEY] = json.dumps(serializable, ensure_ascii=False)
    request.session.modified = True


def _clear_session(request):
    request.session.pop(SESSION_KEY, None)
    request.session.pop(SESSION_REFS_KEY, None)
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


def _prepare_table_rows(validated_rows):
    table_rows = []
    for index, row in enumerate(validated_rows):
        cells = []
        row_errors = row.get('errors', {})
        row_warnings = row.get('warnings', {})
        for col in CONTACT_IMPORT_COLUMNS:
            cell_errors = row_errors.get(col, [])
            cell_warnings = row_warnings.get(col, [])
            css = ''
            if cell_errors:
                css = 'cell-error'
            elif cell_warnings:
                css = 'cell-warning'
            cells.append({
                'field': col,
                'value': row.get(col, ''),
                'errors': cell_errors,
                'warnings': cell_warnings,
                'css': css,
                'is_comment': col == 'comment',
                'is_reference': col in REFERENCE_FIELD_MODELS,
            })
        table_rows.append({
            'index': index,
            'row_number': row.get('_row_number'),
            'excluded': row.get('excluded'),
            'has_errors': row.get('has_errors'),
            'import_action': row.get('import_action'),
            'import_action_label': row.get('import_action_label', '—'),
            'import_action_url': row.get('import_action_url'),
            'needs_confirm': row.get('import_action') == 'confirm',
            'match_choice': row.get('match_choice', ''),
            'match_candidates': row.get('match_candidates', []),
            'cells': cells,
        })
    return table_rows


def _prepare_new_reference_panels(new_reference_values, confirmed_refs):
    labels = {'company': 'Компания', 'category': 'Категория', 'type_guest': 'Тип гостя'}
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


def _full_preview(rows, request):
    """Валидация + сопоставление + новые справочные значения + продюсеры одним вызовом."""
    validated, summary = validate_contact_rows(rows)
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

    summary['pending_refs_count'] = pending_refs_count
    summary['unresolved_producers_count'] = len(unresolved_producers)
    summary['can_import'] = (
        summary['can_import'] and summary['confirm_count'] == 0 and pending_refs_count == 0
    )

    extra = {
        'new_reference_panels': new_reference_panels,
        'unresolved_producers': [
            {'value': value, 'row_numbers': row_numbers}
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


def _rows_from_post(request, row_count):
    rows = []
    for index in range(row_count):
        row = {
            '_row_number': request.POST.get(f'row_{index}__row_number', index + 2),
            'excluded': request.POST.get(f'row_{index}__excluded') == 'on',
            'match_choice': request.POST.get(f'row_{index}__match_choice', ''),
        }
        for col in CONTACT_IMPORT_COLUMNS:
            row[col] = request.POST.get(f'row_{index}__{col}', '')
        rows.append(row)
    return rows


def staged_contact_upload_view(request):
    _require_contact_import_perm(request)
    form = ContactStagedUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        try:
            rows = parse_spreadsheet(form.cleaned_data['file'])
            _clear_session(request)
            validated, summary, _extra = _full_preview(rows, request)
            _save_rows_to_session(request, validated)
            messages.info(
                request,
                f'Загружено строк: {summary["total"]}. '
                f'Создать: {summary["create_count"]}, обновить: {summary["update_count"]}, '
                f'требуют подтверждения: {summary["confirm_count"]}. '
                f'Ошибок: {summary["error_rows"]}, предупреждений: {summary["warning_rows"]}.',
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

    row_count = len(stored)

    if request.method == 'POST':
        action = request.POST.get('action', 'validate')
        rows = _rows_from_post(request, row_count)
        _update_confirmed_refs_from_post(request)
        validated, summary, extra = _full_preview(rows, request)
        _save_rows_to_session(request, validated)

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
                    result = import_contact_rows(validated, request.user, confirmed_refs=confirmed_refs)
                    _clear_session(request)
                    messages.success(
                        request,
                        f'Загрузка завершена: новых {result.totals.get("new", 0)}, '
                        f'обновлено {result.totals.get("update", 0)}, '
                        f'без изменений {result.totals.get("skip", 0)}.',
                    )
                    return HttpResponseRedirect(reverse('admin:event_contact_changelist'))
                except Exception as exc:
                    messages.error(request, f'Ошибка при загрузке: {exc}')
        else:
            messages.info(request, 'Данные обновлены. Проверьте таблицу.')

        stored = validated

    else:
        stored, summary, extra = _full_preview(stored, request)

    context = {
        'title': 'Проверка данных перед загрузкой',
        'table_rows': _prepare_table_rows(stored),
        'column_labels': [CONTACT_COLUMN_LABELS[col] for col in CONTACT_IMPORT_COLUMNS],
        'summary': summary,
        'new_reference_panels': extra['new_reference_panels'],
        'unresolved_producers': extra['unresolved_producers'],
        'reference_datalists': _reference_datalists(),
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
    file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'import_cont.xlsx')
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='import_cont.xlsx')


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

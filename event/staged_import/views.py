import json
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .contact_columns import CONTACT_COLUMN_LABELS, CONTACT_IMPORT_COLUMNS
from .contact_import import import_contact_rows
from .contact_preview import annotate_import_actions
from .contact_validation import validate_contact_rows
from .forms import ContactStagedUploadForm
from .parsers import parse_spreadsheet

SESSION_KEY = 'staged_contact_import_rows'


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
        serializable.append(item)
    request.session[SESSION_KEY] = json.dumps(serializable, ensure_ascii=False)
    request.session.modified = True


def _clear_session(request):
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


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
            })
        table_rows.append({
            'index': index,
            'row_number': row.get('_row_number'),
            'excluded': row.get('excluded'),
            'has_errors': row.get('has_errors'),
            'import_action': row.get('import_action'),
            'import_action_label': row.get('import_action_label', '—'),
            'import_action_url': row.get('import_action_url'),
            'cells': cells,
        })
    return table_rows


def _validated_with_preview(rows):
    validated, summary = validate_contact_rows(rows)
    validated, action_summary = annotate_import_actions(validated)
    summary['create_count'] = action_summary['create']
    summary['update_count'] = action_summary['update']
    return validated, summary


def _rows_from_post(request, row_count):
    rows = []
    for index in range(row_count):
        row = {
            '_row_number': request.POST.get(f'row_{index}__row_number', index + 2),
            'excluded': request.POST.get(f'row_{index}__excluded') == 'on',
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
            validated, summary = _validated_with_preview(rows)
            _save_rows_to_session(request, validated)
            messages.info(
                request,
                f'Загружено строк: {summary["total"]}. '
                f'Создать: {summary["create_count"]}, обновить: {summary["update_count"]}. '
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
        validated, summary = _validated_with_preview(rows)
        _save_rows_to_session(request, validated)

        if action == 'import':
            if not summary['can_import']:
                messages.error(
                    request,
                    'Исправьте ошибки в активных строках или исключите их перед загрузкой.',
                )
            else:
                try:
                    result = import_contact_rows(validated, request.user)
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
        summary = summary

    else:
        validated, summary = _validated_with_preview(stored)
        stored = validated

    context = {
        'title': 'Проверка данных перед загрузкой',
        'table_rows': _prepare_table_rows(stored),
        'column_labels': [CONTACT_COLUMN_LABELS[col] for col in CONTACT_IMPORT_COLUMNS],
        'summary': summary,
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

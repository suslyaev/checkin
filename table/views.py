import json

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .decorators import table_staff_required
from .tabs import DEFAULT_TAB, get_tab, get_visible_tabs


@table_staff_required
def workspace(request, tab_id=None):
    if not getattr(settings, 'ATTENDLY_TABLE_ENABLED', True):
        return HttpResponseRedirect(reverse('admin:index'))

    tabs = get_visible_tabs(request.user)
    if not tabs:
        return HttpResponseRedirect(reverse('admin:index'))

    active = get_tab(tab_id, request.user) if tab_id else None
    if not active:
        active = get_tab(DEFAULT_TAB, request.user) or tabs[0]
        if tab_id:
            return HttpResponseRedirect(reverse('table:workspace', args=[active['id']]))

    grid_configs = _grid_configs()
    context = {
        'title': 'Attendly Table',
        'tabs': tabs,
        'active_tab': active,
        'grid_config_json': json.dumps(grid_configs.get(active['dataset'], {}), ensure_ascii=False),
        'user_label': request.user.get_short_name() or request.user.phone,
    }
    return render(request, 'table/workspace.html', context)


@table_staff_required
def workspace_root(request):
    return workspace(request, tab_id=None)


def _grid_configs():
    return {
        'contacts': {
            'columns': [
                {'title': '', 'field': '_actions', 'width': 72, 'frozen': True},
                {'title': 'ID', 'field': 'id', 'width': 60, 'visible': False},
                {'title': 'Фамилия', 'field': 'last_name', 'editor': 'input', 'width': 140},
                {'title': 'Имя', 'field': 'first_name', 'editor': 'input', 'width': 120},
                {'title': 'Отчество', 'field': 'middle_name', 'editor': 'input', 'width': 130},
                {'title': 'Никнейм', 'field': 'nickname', 'editor': 'input', 'width': 120},
                {'title': 'Компания', 'field': 'company', 'editor': 'autocomplete', 'ref': 'company', 'width': 150},
                {'title': 'Категория', 'field': 'category', 'editor': 'autocomplete', 'ref': 'category', 'width': 130},
                {'title': 'Тип гостя', 'field': 'type_guest', 'editor': 'autocomplete', 'ref': 'type_guest', 'width': 130},
                {'title': 'Продюсер', 'field': 'producer', 'editor': 'autocomplete', 'ref': 'producer', 'width': 150},
                {'title': 'Комментарий', 'field': 'comment', 'editor': 'input', 'width': 200},
            ],
            'exportUrl': '/table/api/contacts/export/',
        },
        'events': {
            'columns': [
                {'title': '', 'field': '_actions', 'width': 72, 'frozen': True},
                {'title': 'ID', 'field': 'id', 'width': 60, 'visible': False},
                {'title': 'Название', 'field': 'name', 'editor': 'input', 'width': 220},
                {'title': 'Адрес', 'field': 'address', 'editor': 'input', 'width': 200},
                {'title': 'Начало', 'field': 'date_start', 'editor': False, 'width': 150},
                {'title': 'Окончание', 'field': 'date_end', 'editor': False, 'width': 150},
                {'title': 'Видимость', 'field': 'is_visible', 'editor': 'list', 'editorParams': {'values': ['Да', 'Нет']}, 'width': 100},
            ],
        },
        'companies': {
            'columns': [
                {'title': '', 'field': '_actions', 'width': 72, 'frozen': True},
                {'title': 'ID', 'field': 'id', 'visible': False},
                {'title': 'Название', 'field': 'name', 'editor': 'input', 'width': 220},
                {'title': 'Описание', 'field': 'comment', 'editor': 'input', 'width': 260},
            ],
        },
        'categories': {
            'columns': [
                {'title': '', 'field': '_actions', 'width': 72, 'frozen': True},
                {'title': 'ID', 'field': 'id', 'visible': False},
                {'title': 'Название', 'field': 'name', 'editor': 'input', 'width': 220},
                {'title': 'Описание', 'field': 'comment', 'editor': 'input', 'width': 260},
            ],
        },
        'type_guests': {
            'columns': [
                {'title': '', 'field': '_actions', 'width': 72, 'frozen': True},
                {'title': 'ID', 'field': 'id', 'visible': False},
                {'title': 'Название', 'field': 'name', 'editor': 'input', 'width': 220},
                {'title': 'Описание', 'field': 'comment', 'editor': 'input', 'width': 260},
            ],
        },
    }

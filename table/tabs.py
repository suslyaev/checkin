"""Конфигурация вкладок нижней панели /table/."""

TABS = [
    {
        'id': 'contacts',
        'label': 'Люди',
        'permission': 'event.view_contact',
        'dataset': 'contacts',
    },
    {
        'id': 'events',
        'label': 'Мероприятия',
        'permission': 'event.view_moduleinstance',
        'dataset': 'events',
    },
    {
        'id': 'companies',
        'label': 'Компании',
        'permission': 'event.view_companycontact',
        'dataset': 'companies',
    },
    {
        'id': 'categories',
        'label': 'Категории',
        'permission': 'event.view_categorycontact',
        'dataset': 'categories',
    },
    {
        'id': 'type_guests',
        'label': 'Типы гостя',
        'permission': 'event.view_typeguestcontact',
        'dataset': 'type_guests',
    },
]

DEFAULT_TAB = 'contacts'


def get_visible_tabs(user):
    visible = []
    for tab in TABS:
        if user.has_perm(tab['permission']):
            visible.append(tab)
    return visible


def get_tab(tab_id, user):
    for tab in TABS:
        if tab['id'] == tab_id and user.has_perm(tab['permission']):
            return tab
    return None

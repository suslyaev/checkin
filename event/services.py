from django.urls import reverse
# Отображение кнопок Сохранить, Сохранить и продолжить, Удалить, Закрыть
def get_params_visible_buttons_save(request, obj):
    button_save = obj is None
    return {
        'show_save_and_continue': False if request.user.is_superuser == True else False,
        'show_save': button_save or request.user.is_superuser == True if request.user.is_superuser or request.user.is_staff == True else False,
        'show_save_and_add_another': False if request.user.is_superuser == True else False,
        'show_delete': True if request.user.is_superuser == True else False
    }

def get_contact_link(a):
    contact_url = reverse('admin:event_contact_change', args=[a.contact.pk])
    contact_name = a.contact.get_fio() or f"Контакт #{a.contact.pk}"

    # Форматируем дату, например, в формате "YYYY-MM-DD HH:MM"
    action_date_str = a.update_date.strftime('%Y-%m-%d %H:%M') if a.update_date else ''

    # Ссылка с popup-открытием
    link = f"""
    <a href="{contact_url}" 
    onclick="window.open(this.href, 'popup', 'width=900,height=600'); return false;">
    {contact_name}
    </a>
    """

    # Добавляем дату после имени, например, в круглых скобках
    return f'<li>{link} <span style="color: #888;">({action_date_str})</span></li>'

# Получение имени действия
def get_name_action(action_type, contact, event, action_date):
    from django.utils.timezone import localtime
    from django.utils import formats
    return f'{action_type} ({contact}) - {event} - {formats.date_format(localtime(action_date), "DATETIME_FORMAT")}'

# Получение имени события
def get_name_instance(module, date_start):
    from django.utils.timezone import localtime
    from django.utils import formats
    return f'{module} - {formats.date_format(localtime(date_start), "DATETIME_FORMAT")}'

# Получение короткого имени события
def get_short_name_event(event):
    from django.utils.timezone import localtime
    d_date = localtime(event.date_start).strftime('%d.%m.%Y')
    return f'{event.module.event.name} {d_date}'

# Проверка создания действий
def check_create_action(record):
    result = {
        "error" : False,
        "error_message" : ""
    }
    import event
    if record.action_type is None:
        record.action_type = 'new'
    
    if record.is_last_state == True:
        action = event.models.Action.objects.filter(contact=record.contact, event=record.event, action_type=record.action_type, is_last_state=True).exclude(id=record.id)
        if len(action) == 0:
            action_type_open = 'new'
            action_type_cheсkin = 'checkin'
            action_type_close = 'cancel'
            # Если чекин, то проверяю, чтобы была регистрация
            if (record.action_type == action_type_cheсkin):
                actions_open = event.models.Action.objects.filter(contact=record.contact, event=record.event, action_type=action_type_open, is_last_state=True)
                if len(actions_open) == 0:
                    result["error"] = True
                    result["error_message"] = "Нельзя делать чекин без регистрации"
            # Если регистрация
            elif (record.action_type == action_type_open):
                actions_checkin = event.models.Action.objects.filter(contact=record.contact, event=record.event, action_type=action_type_cheсkin, is_last_state=True)
                if len(actions_checkin) > 0:
                    result["error"] = True
                    result["error_message"] = "Нельзя зарегистрироваться после чекина"
            # Если отмена регистрации, то должна быть регистрация. Нельзя отменить, если уже есть чекин
            elif (record.action_type == action_type_close):
                actions_cheсkin = event.models.Action.objects.filter(contact=record.contact, event=record.event, action_type=action_type_cheсkin, is_last_state=True)
                if len(actions_cheсkin) > 0:
                    result["error"] = True
                    result["error_message"] = "Нельзя отменить регистрацию после посещения"
                else:
                    actions_open = event.models.Action.objects.filter(contact=record.contact, event=record.event, action_type=action_type_open, is_last_state=True)
                    if len(actions_open) == 0:
                        result["error"] = True
                        result["error_message"] = "Нельзя делать отмену без регистрации"
        else:
            result["error"] = True
            result["error_message"] = "Нельзя создавать несколько одинаковых записей"
    return result

def do_after_add_action(action):
    import event
    action_type_open = 'new'
    action_type_cheсkin = 'checkin'
    action_type_close = 'cancel'
    # Если регистрация, то надо проверить отмену регистрации
    if (action.action_type == action_type_open):
        actions_close = event.models.Action.objects.filter(contact=action.contact, event=action.event, action_type=action_type_close, is_last_state=True)
        # Если регистрация и найдена предыдущая отмена, снимаю текущее состояние с отмены
        if len(actions_close) > 0:
            for action_close in actions_close:
                action_close.is_last_state = False
                action_close.save(force_update=True)
    # Если отмена регистрации или чекин, то должна быть регистрация
    elif (action.action_type == action_type_close or action.action_type == action_type_cheсkin):
        actions_open = event.models.Action.objects.filter(contact=action.contact, event=action.event, action_type=action_type_open, is_last_state=True)
        if len(actions_open) > 0:
            # Если отмена регистрации или чекин, снимаю текущее состояние в регистрации
            for action_open in actions_open:
                action_open.is_last_state = False
                action_open.save(force_update=True)

# Чекин или отмена регистрации
def update_actions(action_type, queryset):
    for action_rec in queryset:
        action_rec.action_type = action_type
        action_rec.save()

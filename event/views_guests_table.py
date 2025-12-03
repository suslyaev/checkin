"""
Представления для работы с таблицей гостей мероприятия
Интерактивная таблица с редактированием в стиле Google Sheets
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_http_methods
import json

from .models import ModuleInstance, Action, Contact, CompanyContact, CategoryContact, TypeGuestContact


def guests_table_view(request, event_id):
    """
    Страница с интерактивной таблицей гостей
    """
    event = get_object_or_404(ModuleInstance, pk=event_id)
    
    context = {
        'event': event,
        'title': f'Список гостей: {event.name}',
        'opts': ModuleInstance._meta,
    }
    
    return render(request, 'admin/event/guests_table.html', context)


@require_http_methods(["GET"])
def guests_data_api(request, event_id):
    """
    API для получения данных гостей в JSON формате
    Используется таблицей Tabulator для загрузки данных
    """
    # Проверяем существование мероприятия
    event = get_object_or_404(ModuleInstance, pk=event_id)
    
    # Получаем все регистрации для мероприятия
    actions = Action.objects.filter(event=event).select_related(
        'contact',
        'contact__company',
        'contact__category',
        'contact__type_guest',
        'contact__producer'
    ).order_by('contact__last_name', 'contact__first_name')
    
    # Формируем данные для таблицы
    data = []
    for action in actions:
        contact = action.contact
        if not contact:
            continue
            
        data.append({
            'id': action.id,
            'contact_id': contact.id,
            'last_name': contact.last_name or '',
            'first_name': contact.first_name or '',
            'middle_name': contact.middle_name or '',
            'nickname': contact.nickname or '',
            'company': contact.company.name if contact.company else '',
            'company_id': contact.company.id if contact.company else None,
            'category': contact.category.name if contact.category else '',
            'category_id': contact.category.id if contact.category else None,
            'type_guest': contact.type_guest.name if contact.type_guest else '',
            'type_guest_id': contact.type_guest.id if contact.type_guest else None,
            'producer': f"{contact.producer.last_name} {contact.producer.first_name}" if contact.producer else '',
            'action_type': action.action_type,
            'action_type_display': action.get_action_type_display(),
            'comment': action.comment or '',
        })
    
    return JsonResponse({'data': data})


@require_http_methods(["GET"])
def autocomplete_api(request, event_id, field):
    """
    API для автокомплита справочников
    field: company, category, type_guest, producer
    """
    term = request.GET.get('term', '')
    
    if field == 'company':
        items = CompanyContact.objects.filter(name__icontains=term).order_by('name')[:20]
        results = [{'id': item.id, 'name': item.name} for item in items]
    elif field == 'category':
        items = CategoryContact.objects.filter(name__icontains=term).order_by('name')[:20]
        results = [{'id': item.id, 'name': item.name} for item in items]
    elif field == 'type_guest':
        items = TypeGuestContact.objects.filter(name__icontains=term).order_by('name')[:20]
        results = [{'id': item.id, 'name': item.name} for item in items]
    elif field == 'producer':
        from .models import CustomUser
        # Ищем только продюсеров
        items = CustomUser.objects.filter(
            groups__name='Продюсер'
        ).filter(
            Q(last_name__icontains=term) | Q(first_name__icontains=term)
        ).order_by('last_name', 'first_name')[:20]
        results = [{'id': item.id, 'name': f"{item.last_name} {item.first_name}"} for item in items]
    else:
        return JsonResponse({'error': 'Invalid field'}, status=400)
    
    return JsonResponse({'results': results})


@require_http_methods(["POST"])
def guest_save_api(request, event_id):
    """
    API для сохранения изменений гостя
    Создает или обновляет Contact и Action
    """
    event = get_object_or_404(ModuleInstance, pk=event_id)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    action_id = data.get('id')
    
    # Валидация обязательных полей
    if not data.get('last_name') or not data.get('first_name'):
        return JsonResponse({'error': 'Фамилия и Имя обязательны'}, status=400)
    
    try:
        with transaction.atomic():
            if action_id:
                # Обновление существующей записи
                action = Action.objects.select_related('contact').get(
                    id=action_id, 
                    event=event
                )
                contact = action.contact
            else:
                # Создание новой записи
                contact = Contact()
                action = Action(event=event, create_user=request.user, update_user=request.user)
            
            # Обновляем данные контакта
            contact.last_name = data.get('last_name', '').strip()
            contact.first_name = data.get('first_name', '').strip()
            contact.middle_name = data.get('middle_name', '').strip()
            contact.nickname = data.get('nickname', '').strip()
            
            # Справочники - get_or_create
            company_name = data.get('company', '').strip()
            if company_name:
                contact.company, _ = CompanyContact.objects.get_or_create(
                    name=company_name
                )
            else:
                contact.company = None
            
            category_name = data.get('category', '').strip()
            if category_name:
                contact.category, _ = CategoryContact.objects.get_or_create(
                    name=category_name
                )
            else:
                contact.category = None
            
            type_guest_name = data.get('type_guest', '').strip()
            if type_guest_name:
                contact.type_guest, _ = TypeGuestContact.objects.get_or_create(
                    name=type_guest_name
                )
            else:
                contact.type_guest = None
            
            # Продюсер - ищем по ФИО
            producer_name = data.get('producer', '').strip()
            if producer_name:
                # Пытаемся найти продюсера по ФИО
                parts = producer_name.split()
                if len(parts) >= 2:
                    from .models import CustomUser
                    producer = CustomUser.objects.filter(
                        last_name__iexact=parts[0],
                        first_name__iexact=parts[1],
                        groups__name='Продюсер'
                    ).first()
                    if producer:
                        contact.producer = producer
            else:
                contact.producer = None
            
            contact.save()
            
            # Обновляем действие
            action.contact = contact
            action.action_type = data.get('action_type', 'announced')
            action.comment = data.get('comment', '').strip()
            action.update_user = request.user
            action.save()
            
            return JsonResponse({
                'success': True,
                'id': action.id,
                'contact_id': contact.id,
                'message': 'Данные сохранены'
            })
            
    except Action.DoesNotExist:
        return JsonResponse({'error': 'Запись не найдена'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Ошибка сохранения: {str(e)}'}, status=400)


@require_http_methods(["POST"])
def guest_delete_api(request, event_id):
    """
    API для удаления регистрации гостя
    """
    event = get_object_or_404(ModuleInstance, pk=event_id)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    action_id = data.get('id')
    
    if not action_id:
        return JsonResponse({'error': 'ID не указан'}, status=400)
    
    try:
        Action.objects.filter(id=action_id, event=event).delete()
        return JsonResponse({'success': True, 'message': 'Запись удалена'})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка удаления: {str(e)}'}, status=400)


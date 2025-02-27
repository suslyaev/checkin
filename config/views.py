import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.db.models import Q
from django.contrib.auth import logout
from django.utils.decorators import method_decorator
from django.views import View

from event.models import ModuleInstance, Action, Contact, SocialNetwork, InfoContact, CompanyContact, CategoryContact, TypeGuestContact


def home(request):
    if request.user.is_authenticated:
        return render(request, 'front/index.html')
    else:
        # Если не авторизован -> логин
        if request.method == "POST":
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect('home')
        else:
            form = AuthenticationForm()
        return render(request, 'front/login.html', {'form': form})


@login_required
def get_user_events(request):
    user = request.user

    # Получаем события в зависимости от роли пользователя
    if user.is_superuser or user.groups.filter(name='Администратор').exists():
        # Суперпользователь или Администратор видят все события
        events = ModuleInstance.objects.filter(is_visible=True).all()
    else:
        # Остальные пользователи видят только свои события
        events = ModuleInstance.objects.filter(
            Q(managers=user) | Q(checkers=user), is_visible=True
        ).distinct()

    data = []
    for event in events:
        data.append({
            "id": event.id,
            "name": event.name,
            "address": event.address,
            "date_start": event.date_start,
            "date_end": event.date_end,
        })

    return JsonResponse(data, safe=False)


@method_decorator(login_required, name='dispatch')
class ActionView(View):
    """Обработка действий (GET/POST) с проверкой прав доступа"""

    def get(self, request):
        # Фильтруем по доступным событиям и параметру event_id
        event_id = request.GET.get('event_id')
        actions = Action.objects.filter(
            event__in=self._get_user_events(request.user)
        ).select_related('contact', 'event', 'contact__category')

        if event_id:
            actions = actions.filter(event_id=event_id)

        return JsonResponse(
            [self._serialize_action(action) for action in actions],
            safe=False
        )

    def post(self, request):
        try:
            data = json.loads(request.body)
            contact_id = data.get('contact')
            event_id = data.get('event')
            action_type = data.get('action_type')

            if not all([contact_id, event_id]):
                return JsonResponse(
                    {"error": "Не указан контакт или событие"},
                    status=400
                )

            # Проверка доступа к событию
            if not self._get_user_events(request.user).filter(id=event_id).exists():
                return JsonResponse(
                    {"error": "Нет прав для работы с этим мероприятием"},
                    status=403
                )

            if action_type == 'checkin':
                # Проверяем существующий чекин
                existing_action = Action.objects.filter(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='checkin'
                ).first()

                if existing_action:
                    return JsonResponse(
                        {"error": "Гость уже зарегистрирован"},
                        status=400
                    )

                # Создаем новый чекин
                action = Action(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='checkin',
                    operator=request.user
                )

            elif action_type == 'new':
                # Создаем новую запись с типом 'new'
                action = Action(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='new',
                    operator=request.user
                )

            elif action_type == 'cancel':
                # Находим и удаляем существующий чекин
                existing_checkin = Action.objects.filter(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='checkin'
                ).first()

                if existing_checkin:
                    existing_checkin.delete()

                # Создаем новую запись с типом 'new'
                action = Action(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='new',
                    operator=request.user
                )

            elif action_type == 'delete':
                # Находим и удаляем существующий чекин
                existing_checkin = Action.objects.filter(
                    contact_id=contact_id,
                    event_id=event_id,
                    action_type='new'
                ).first()

                if existing_checkin:
                    existing_checkin.delete()
                else:
                    existing_checkin = Action.objects.filter(
                        contact_id=contact_id,
                        event_id=event_id,
                        action_type='checkin'
                    ).first()
                    if existing_checkin:
                        existing_checkin.delete()

            action.full_clean()
            action.save()

            return JsonResponse(
                self._serialize_action(action),
                status=201
            )

        except Exception as e:
            print(f"Ошибка при создании действия: {str(e)}")
            return JsonResponse(
                {"error": str(e)},
                status=500
            )

    def _get_user_events(self, user):
        """Возвращает QuerySet доступных мероприятий"""
        if user.is_superuser or user.groups.filter(name='Администратор').exists():
            return ModuleInstance.objects.all()

        return ModuleInstance.objects.filter(
            models.Q(managers=user) |
            models.Q(checkers=user)
        ).distinct()

    def _serialize_action(self, action):
        """Формат ответа как в старом DRF-сериализаторе"""
        return {
            "id": action.id,
            "contact": action.contact.id,
            "contact_obj": {
                "id": action.contact.id,
                "fio": action.contact.get_fio(),
                "photo_link": action.contact.photo_link(),
                "category_obj": {
                    "name": action.contact.category.name if action.contact.category else None,
                    "color": action.contact.category.color if action.contact.category else None,
                    "comment": action.contact.category.comment if action.contact.category else None,
                },
                "type_guest_obj": {
                    "name": action.contact.type_guest.name if action.contact.type_guest else None,
                    "color": action.contact.type_guest.color if action.contact.type_guest else None,
                    "comment": action.contact.type_guest.comment if action.contact.type_guest else None,
                },
                "social_networks": [
                    {
                        "network_type": info.social_network.name,
                        "username": info.external_id,
                        "link": info.external_id
                    } for info in InfoContact.objects.filter(
                        contact=action.contact,
                        social_network__isnull=False
                    )
                ]
            },
            "event": action.event.id,
            "module_instance": action.event.id,
            "module_instance_obj": {
                "id": action.event.id,
                "name": action.event.name,
                "date_start": action.event.date_start.isoformat()
            },
            "action_type": action.action_type,
            "action_date": action.action_date.isoformat(),
            "operator_obj": {
                "full_name": f"{action.operator.first_name} {action.operator.last_name}".strip() or action.operator.username
            } if action.operator else None
        }


def custom_logout(request):
    logout(request)
    return redirect('home')


class AvailableContactsView(View):
    def get(self, request):
        event_id = request.GET.get('event_id')
        if not event_id:
            return JsonResponse({"error": "Не указан ID события"}, status=400)

        # Получаем всех гостей, которые уже есть в мероприятии
        existing_guests = Action.objects.filter(
            event_id=event_id,
            action_type__in=['new', 'checkin']
        ).values_list('contact_id', flat=True)

        # Получаем всех доступных гостей, которых нет в мероприятии
        available_contacts = Contact.objects.exclude(
            id__in=existing_guests
        )

        # Сериализуем данные
        contacts_data = [{
            'id': contact.id,
            'fio': contact.get_fio(),
            'photo_link': contact.photo_link(),
        } for contact in available_contacts]

        return JsonResponse(contacts_data, safe=False)


class DirectoryView(View):
    model = None

    def get(self, request):
        items = self.model.objects.all()
        data = [{
            'id': item.id,
            'name': item.name,
        } for item in items]
        return JsonResponse(data, safe=False)


class CompaniesView(DirectoryView):
    model = CompanyContact


class CategoriesView(DirectoryView):
    model = CategoryContact


class TypeGuestView(DirectoryView):
    model = TypeGuestContact


class ContactCreateView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)

            print("Приступили к созданию")
            print(data)
            
            # Создаем контакт
            contact = Contact.objects.create(
                last_name=data['last_name'],
                first_name=data['first_name'],
                middle_name=data.get('middle_name'),
                company_id=data.get('company'),
                category_id=data.get('category'),
                type_guest_id=data.get('type_guest'),
                comment=data.get('comment')
            )
            print(f"Создан контакт {contact.last_name} {contact.first_name}")
            # Создаем действие для события
            if data.get('event'):
                Action.objects.create(
                    contact=contact,
                    event_id=data['event'],
                    action_type='new',
                    operator=request.user
                )
            
            return JsonResponse({
                'id': contact.id,
                'fio': contact.get_fio()
            }, status=201)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

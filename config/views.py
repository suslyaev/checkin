import json

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.db.models import Q
from django.contrib.auth import logout
from django.utils.decorators import method_decorator
from django.views import View

from event.models import ModuleInstance, Action, Contact, SocialNetwork, InfoContact, CompanyContact, CategoryContact, \
    TypeGuestContact


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
        events = ModuleInstance.objects.filter().all()
    else:
        # Остальные пользователи видят только свои события
        events = ModuleInstance.objects.filter(
            Q(managers=user) | Q(checkers=user) | Q(producers=user)).distinct()

    data = []
    for event in events:
        # Подсчитываем количество уникальных гостей для события
        guests_count = Action.objects.filter(
            event=event,
            action_type__in=['new', 'checkin']  # Учитываем только действия регистрации и чекина
        ).values('contact').distinct().count()  # Считаем уникальных гостей

        data.append({
            "id": event.id,
            "name": event.name,
            "address": event.address,
            "date_start": event.date_start,
            "date_end": event.date_end,
            "is_visible": event.is_visible,
            'guests_count': guests_count
        })
    return JsonResponse(data, safe=False)

@login_required
def get_admin_info(request):
    user = request.user.groups.first()

    data = [{
        "admin": user.name
    }]
    return JsonResponse(data, safe=False)


@method_decorator(login_required, name='dispatch')
class ActionView(View):
    """Обработка действий (GET/POST) с проверкой прав доступа"""

    def get(self, request):
        # Фильтруем по доступным событиям и параметру event_id
        event_id = request.GET.get('event_id')
        if not event_id:
            return JsonResponse([], safe=False)

        actions = Action.objects.filter(event_id=event_id).select_related(
            'contact',
            'contact__category',
            'contact__company',
            'contact__type_guest',
            'event',
            'operator'
        ).prefetch_related(
            'contact__infocontact_set__social_network'
        ).order_by('contact__last_name', 'contact__first_name')

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
            models.Q(checkers=user) |
            models.Q(producers=user)
        ).distinct()

    def _serialize_action(self, action):
        """Полная сериализация со всеми полями, но с оптимизациями"""
        contact = action.contact
        event = action.event

        # Основная структура данных
        data = {
            "id": action.id,
            "contact": contact.id,
            "contact_obj": {
                "id": contact.id,
                "fio": f"{contact.last_name} {contact.first_name}",  # Оптимизация: замена get_fio()
                "nickname": contact.nickname,
                "photo_link": contact.photo.url if contact.photo else "-",
                "category_obj": self._serialize_category(contact.category),
                "company_obj": self._serialize_company(contact.company),
                "type_guest_obj": self._serialize_type_guest(contact.type_guest),
                "social_networks": self._serialize_social_networks(contact)
            },
            "event": event.id,
            "module_instance": event.id,
            "module_instance_obj": {
                "id": event.id,
                "name": event.name,
                "date_start": event.date_start.isoformat()
            },
            "action_type": action.action_type,
            "action_date": action.action_date.isoformat(),
            "operator_obj": self._serialize_operator(action.operator)
        }

        return data

    def _serialize_category(self, category):
        return {
            "name": category.name if category else None,
            "color": category.color if category else None,
            "comment": category.comment if category else None
        } if category else None

    def _serialize_company(self, company):
        return {
            "name": company.name if company else None,
            "comment": company.comment if company else None
        } if company else None

    def _serialize_type_guest(self, type_guest):
        return {
            "name": type_guest.name if type_guest else None,
            "color": type_guest.color if type_guest else None,
            "comment": type_guest.comment if type_guest else None
        } if type_guest else None

    def _serialize_social_networks(self, contact):
        return [{
            "network_type": info.social_network.name,
            "username": info.external_id,
            "link": info.external_id
        } for info in contact.infocontact_set.all() if info.social_network]

    def _serialize_operator(self, operator):
        return {
            "full_name": f"{operator.first_name} {operator.last_name}".strip() or operator.username
        } if operator else None


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

            # Создаем действие для события
            action = None
            if data.get('event'):
                action = Action.objects.create(
                    contact=contact,
                    event_id=data['event'],
                    action_type='new',
                    operator=request.user
                )

            # Получаем социальные сети
            social_networks = [
                {
                    "network_type": info.social_network.name,
                    "username": info.external_id,
                    "link": info.external_id
                } for info in InfoContact.objects.filter(
                    contact=contact,
                    social_network__isnull=False
                )
            ]

            # Возвращаем расширенные данные о госте
            return JsonResponse({
                'id': contact.id,
                'contact_obj': {
                    'id': contact.id,
                    'fio': contact.get_fio(),
                    'photo_link': contact.photo_link(),
                    'category_obj': {
                        'name': contact.category.name if contact.category else None,
                        'color': contact.category.color if contact.category else None,
                        'comment': contact.category.comment if contact.category else None,
                    },
                    'type_guest_obj': {
                        'name': contact.type_guest.name if contact.type_guest else None,
                        'color': contact.type_guest.color if contact.type_guest else None,
                        'comment': contact.type_guest.comment if contact.type_guest else None,
                    },
                    'social_networks': social_networks
                },
                'operator_obj': {
                    'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
                } if request.user else None
            }, status=201)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

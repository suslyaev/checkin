import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth import logout
from django.utils.decorators import method_decorator
from django.views import View

from event.models import ModuleInstance, Action, Contact


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
        events = ModuleInstance.objects.all()
    else:
        # Остальные пользователи видят только свои события
        events = ModuleInstance.objects.filter(
            Q(managers=user) | Q(checkers=user)
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
            event_id = data.get('event')

            # Проверка доступа к событию
            if not self._get_user_events(request.user).filter(id=event_id).exists():
                return JsonResponse(
                    {"error": "Нет прав для работы с этим мероприятием"},
                    status=403
                )

            # Создание действия
            action = Action(
                contact=Contact.objects.get(id=data['contact']),
                event=ModuleInstance.objects.get(id=event_id),
                action_type=data['action_type'],
                operator=request.user
            )
            action.full_clean()
            action.save()

            return JsonResponse(self._serialize_action(action), status=201)

        except (ObjectDoesNotExist, KeyError) as e:
            return JsonResponse({"error": "Неверные данные"}, status=400)
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            return JsonResponse({"error": "Ошибка сервера"}, status=500)

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
                }
            },
            "event": action.event.id,
            "module_instance": action.event.id,  # Для совместимости со старым фронтом
            "module_instance_obj": {
                "id": action.event.id,
                "name": action.event.name,
                "date_start": action.event.date_start.isoformat()
            },
            "action_type": action.action_type,
            "action_date": action.action_date.isoformat()
        }


def custom_logout(request):
    logout(request)
    return redirect('home')

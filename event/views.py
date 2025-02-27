from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Checkin, Action, CustomUser, ModuleInstance
from django.http import JsonResponse

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower


@login_required
def checkin_list(request, pk):
    # Проверяем, есть ли такое мероприятие
    inst = get_object_or_404(ModuleInstance, pk=pk)

    # Фильтруем checkin: is_last_state=True, action_type='new', event=inst
    qs = Checkin.objects.filter(
        is_last_state=True,
        action_type='new',
        event=inst
    )

    # Если пользователь - проверяющий, проверяем, что inst.checkers=user
    # (или если в админке get_queryset требует event.checkers=user)
    if request.user.groups.filter(name='Модератор').exists():
        # Если мероприятие вообще не связано с этим user, можно запретить доступ
        if not inst.checkers.filter(pk=request.user.pk).exists():
            return render(request, 'front/no_access.html')
        # Иначе qs уже правильно отфильтрован

    # Поиск (опционально)
    search_term = request.GET.get('q', '')
    if search_term:
        term_lower = search_term.lower()
        qs = qs.annotate(
            last_name_lower=Lower('contact__last_name')
        ).filter(
            Q(last_name_lower__contains=term_lower)
        )

    return render(request, 'front/checkin_list.html', {
        'instance': inst,
        'checkins': qs,
        'search_term': search_term,
    })


@login_required
def checkin_detail(request, pk):
    """
    Отображает детальную страницу для одного Checkin.
    Содержит информацию о мероприятии, человеке, 
    и кнопки "Подтвердить"/"Отменить".
    """
    checkin = get_object_or_404(Checkin, pk=pk)

    # Доп. проверка: если "Модератор", убедиться, что checkin.event.checkers содержит user
    if request.user.groups.filter(name='Модератор').exists():
        if not checkin.event.checkers.filter(pk=request.user.pk).exists():
            return render(request, 'front/no_access.html')

    return render(request, 'front/checkin_detail.html', {
        'checkin': checkin,
    })



def confirm_checkin(request, pk):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        checkin = get_object_or_404(Checkin, pk=pk)
        action_type_confirm = 'checkin'  # ID типа действия для подтверждения
        Action.objects.create(
            contact=checkin.contact,
            event=checkin.event,
            action_type=action_type_confirm,
            operator = request.user,
            is_last_state=True
        )
        return JsonResponse({'status': 'success', 'message': 'Подтверждено'})


def cancel_checkin(request, pk):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        checkin = get_object_or_404(Checkin, pk=pk)
        action_type_cancel = 'cancel'  # ID типа действия для отмены
        Action.objects.create(
            contact=checkin.contact,
            event=checkin.event,
            action_type=action_type_cancel,
            operator = request.user,
            is_last_state=True
        )
        return JsonResponse({'status': 'success', 'message': 'Отменено'})


def telegram_admin_auth(request):
    token = request.GET.get('token')
    if not token:
        return redirect('/')

    try:
        user = CustomUser.objects.get(auth_token=token)
        if user.token_expires < timezone.now():
            return redirect('/')

        # Авторизуем пользователя
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        user.auth_token = None
        user.token_expires = None
        user.save(update_fields=['auth_token', 'token_expires'])
        return redirect('/')

    except CustomUser.DoesNotExist:
        return redirect('/')

from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from .models import Checkin, Action, CustomUser
from django.http import JsonResponse

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower

@login_required
def checkin_list(request):
    qs = Checkin.objects.filter(is_last_state=True, action_type='new')

    # Если пользователь в группе "Проверяющий" — фильтруем
    if request.user.groups.filter(name='Проверяющий').exists():
        qs = qs.filter(module_instance__checkers=request.user)

    # Опционально: поиск
    search_term = request.GET.get('q', '')
    if search_term:
        term_lower = search_term.lower()
        qs = qs.annotate(
            fio_lower=Lower('contact__fio'),
            module_lower=Lower('module_instance__name')
        ).filter(
            Q(fio_lower__contains=term_lower) | Q(module_lower__contains=term_lower)
        )

    return render(request, 'front/checkin_list.html', {
        'checkins': qs,
        'search_term': search_term,
    })



def confirm_checkin(request, pk):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        checkin = get_object_or_404(Checkin, pk=pk)
        action_type_confirm = 'checkin'  # ID типа действия для подтверждения
        Action.objects.create(
            contact=checkin.contact,
            module_instance=checkin.module_instance,
            action_type=action_type_confirm,
            is_last_state=True
        )
        return JsonResponse({'status': 'success', 'message': 'Подтверждено'})


def cancel_checkin(request, pk):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        checkin = get_object_or_404(Checkin, pk=pk)
        action_type_cancel = 'cancel'  # ID типа действия для отмены
        Action.objects.create(
            contact=checkin.contact,
            module_instance=checkin.module_instance,
            action_type=action_type_cancel,
            is_last_state=True
        )
        return JsonResponse({'status': 'success', 'message': 'Отменено'})


def telegram_admin_auth(request):
    token = request.GET.get('token')
    if not token:
        return redirect('admin:login')

    try:
        user = CustomUser.objects.get(auth_token=token)
        if user.token_expires < timezone.now():
            return redirect('admin:login')

        # Авторизуем пользователя
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        user.auth_token = None
        user.token_expires = None
        user.save(update_fields=['auth_token', 'token_expires'])
        return redirect('admin:index')

    except CustomUser.DoesNotExist:
        return redirect('admin:login')

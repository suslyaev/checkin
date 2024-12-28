from django.shortcuts import get_object_or_404
from .models import Checkin, Action
from django.http import JsonResponse

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


from django.http import HttpResponse
from event.models import Event, ModuleInstance, Action, ActionType, Contact
from django.utils.timezone import now
from django.shortcuts import render, get_object_or_404
from event.forms import Registration


def index(request):
    event_list = ModuleInstance.objects.filter(visible=True, date_start__gte=now()).values_list('module__event__id', flat=True) | ModuleInstance.objects.filter(visible=True, date_end__gte=now()).values_list('module__event__id', flat=True)
    events = Event.objects.filter(id__in=event_list).distinct()
    context = {'event_list': events}
    return render(request, 'event/index.html', context)

def parent_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    instance_list = ModuleInstance.objects.filter(visible=True, date_start__gte=now(), module__event__id=event_id) | ModuleInstance.objects.filter(visible=True, date_end__gte=now(), module__event__id=event_id)
    return render(request, 'event/parent_detail.html', {'event_detail': event, 'instance_list': instance_list})

def instance_detail(request, instance_id):
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = Registration(request.POST)
        # check whether it's valid:
        if form.is_valid():
            last_name = request.POST.get("last_name", "Undefined")
            first_name = request.POST.get("first_name", "Undefined")
            middle_name = request.POST.get("middle_name", "Undefined")
            email = request.POST.get("email", "Undefined")
            phone = request.POST.get("phone", 1)
            try:
                contact = Contact.objects.get(email=email)
            except Exception:
                contact = None
            if contact is None:
                contact = Contact.objects.create(last_name=last_name,
                                                 first_name=first_name,
                                                 middle_name=middle_name,
                                                 email=email,
                                                 phone=phone)
            reg = Action.objects.create(contact=contact,
                                        module_instance=ModuleInstance.objects.get(pk=instance_id),
                                        action_type=ActionType.objects.get(pk=1))
            
            link_qr = 'https://hg-portal.ru/admin/event/checkin/'+str(reg.pk)+'/change/'

            return render(request, 'event/registration_done.html', {
                'last_name': last_name,
                'first_name': first_name,
                'middle_name': middle_name,
                'email': email,
                'phone': phone,
                'instance_id': reg.pk,
                'link_qr': link_qr
            })
            return HttpResponse(f"<h2>Имя: {last_name} {first_name}  email: {email} телефон: {phone}</h2> Регается на мероприятие: {instance_id}")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = Registration()
    event = get_object_or_404(ModuleInstance, pk=instance_id)
    return render(request, 'event/instance_detail.html', {'event_detail': event, 'form': form})


from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Checkin, ActionType, Action

def confirm_checkin(request, pk):
    checkin = get_object_or_404(Checkin, pk=pk)
    action_type_confirm = ActionType.objects.get(pk=2)  # ID типа действия для подтверждения
    new_action = Action.objects.create(
        contact=checkin.contact,
        module_instance=checkin.module_instance,
        action_type=action_type_confirm,
        is_last_state=True
    )
    messages.success(request, "Посещение успешно подтверждено.")
    return redirect(reverse('admin:event_action_change', args=[new_action.pk]))

def cancel_checkin(request, pk):
    checkin = get_object_or_404(Checkin, pk=pk)
    action_type_cancel = ActionType.objects.get(pk=3)  # ID типа действия для отмены
    new_action = Action.objects.create(
        contact=checkin.contact,
        module_instance=checkin.module_instance,
        action_type=action_type_cancel,
        is_last_state=True
    )
    messages.success(request, "Регистрация успешно отменена.")
    return redirect(reverse('admin:event_action_change', args=[new_action.pk]))

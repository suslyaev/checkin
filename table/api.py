import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from event.models import Action, Contact, ModuleInstance, CompanyContact, CategoryContact, TypeGuestContact
from event.resources import ContactExport, ActionExport

from .decorators import table_staff_required
from .services import (
    serialize_contact,
    save_contact,
    serialize_event,
    save_event,
    serialize_reference,
    save_reference,
    serialize_action,
    save_action,
    autocomplete_reference,
    autocomplete_producers,
    autocomplete_events,
)

REFERENCE_MODELS = {
    'companies': CompanyContact,
    'categories': CategoryContact,
    'type_guests': TypeGuestContact,
}


def _parse_json(request):
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


@table_staff_required
@require_http_methods(['GET'])
def dataset_list(request, dataset):
    if dataset == 'actions' and request.user.has_perm('event.view_action'):
        qs = Action.objects.select_related(
            'contact',
            'contact__company',
            'contact__category',
            'contact__type_guest',
            'contact__producer',
            'event',
        ).order_by('-event__date_start', 'contact__last_name', 'contact__first_name')
        data = [serialize_action(a) for a in qs[:10000]]
        return JsonResponse({'data': data, 'total': qs.count()})

    if dataset == 'contacts' and request.user.has_perm('event.view_contact'):
        qs = Contact.objects.select_related(
            'company', 'category', 'type_guest', 'producer'
        ).order_by('last_name', 'first_name')
        data = [serialize_contact(c) for c in qs[:5000]]
        return JsonResponse({'data': data, 'total': qs.count()})

    if dataset == 'events' and request.user.has_perm('event.view_moduleinstance'):
        qs = ModuleInstance.objects.order_by('-date_start', 'name')
        data = [serialize_event(e) for e in qs[:2000]]
        return JsonResponse({'data': data, 'total': qs.count()})

    if dataset in REFERENCE_MODELS and request.user.has_perm(
        f'event.view_{REFERENCE_MODELS[dataset]._meta.model_name}'
    ):
        model = REFERENCE_MODELS[dataset]
        qs = model.objects.order_by('name')
        data = [serialize_reference(i) for i in qs[:2000]]
        return JsonResponse({'data': data, 'total': qs.count()})

    return JsonResponse({'error': 'Not found'}, status=404)


@table_staff_required
@require_http_methods(['GET'])
def dataset_detail(request, dataset, pk):
    if dataset == 'actions' and request.user.has_perm('event.view_action'):
        action = get_object_or_404(
            Action.objects.select_related(
                'contact',
                'contact__company',
                'contact__category',
                'contact__type_guest',
                'contact__producer',
                'event',
            ),
            pk=pk,
        )
        return JsonResponse({'row': serialize_action(action)})

    if dataset == 'contacts' and request.user.has_perm('event.view_contact'):
        contact = get_object_or_404(
            Contact.objects.select_related('company', 'category', 'type_guest', 'producer'),
            pk=pk,
        )
        return JsonResponse({'row': serialize_contact(contact)})

    if dataset == 'events' and request.user.has_perm('event.view_moduleinstance'):
        event = get_object_or_404(ModuleInstance, pk=pk)
        return JsonResponse({'row': serialize_event(event)})

    if dataset in REFERENCE_MODELS and request.user.has_perm(
        f'event.view_{REFERENCE_MODELS[dataset]._meta.model_name}'
    ):
        model = REFERENCE_MODELS[dataset]
        item = get_object_or_404(model, pk=pk)
        return JsonResponse({'row': serialize_reference(item)})

    return JsonResponse({'error': 'Not found'}, status=404)


@table_staff_required
@require_http_methods(['POST'])
def dataset_save(request, dataset):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    item_id = data.get('id')

    try:
        if dataset == 'actions':
            if not request.user.has_perm('event.change_action'):
                return JsonResponse({'error': 'Forbidden'}, status=403)
            action = save_action(data, action_id=item_id, user=request.user)
            return JsonResponse({'success': True, 'row': serialize_action(action)})

        if dataset == 'contacts':
            if not request.user.has_perm('event.change_contact'):
                return JsonResponse({'error': 'Forbidden'}, status=403)
            contact = save_contact(data, contact_id=item_id)
            return JsonResponse({'success': True, 'row': serialize_contact(contact)})

        if dataset == 'events':
            if not request.user.has_perm('event.change_moduleinstance'):
                return JsonResponse({'error': 'Forbidden'}, status=403)
            event = save_event(data, event_id=item_id)
            return JsonResponse({'success': True, 'row': serialize_event(event)})

        if dataset in REFERENCE_MODELS:
            model = REFERENCE_MODELS[dataset]
            if not request.user.has_perm(f'event.change_{model._meta.model_name}'):
                return JsonResponse({'error': 'Forbidden'}, status=403)
            item = save_reference(model, data, item_id=item_id)
            return JsonResponse({'success': True, 'row': serialize_reference(item)})

        return JsonResponse({'error': 'Not found'}, status=404)
    except Action.DoesNotExist:
        return JsonResponse({'error': 'Запись не найдена'}, status=404)
    except Contact.DoesNotExist:
        return JsonResponse({'error': 'Запись не найдена'}, status=404)
    except ModuleInstance.DoesNotExist:
        return JsonResponse({'error': 'Запись не найдена'}, status=404)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@table_staff_required
@require_http_methods(['POST'])
def dataset_delete(request, dataset):
    data = _parse_json(request)
    if not data or not data.get('id'):
        return JsonResponse({'error': 'id required'}, status=400)

    item_id = data['id']

    if dataset == 'actions' and request.user.has_perm('event.delete_action'):
        get_object_or_404(Action, pk=item_id).delete()
        return JsonResponse({'success': True})

    if dataset == 'contacts' and request.user.has_perm('event.delete_contact'):
        get_object_or_404(Contact, pk=item_id).delete()
        return JsonResponse({'success': True})

    if dataset == 'events' and request.user.has_perm('event.delete_moduleinstance'):
        get_object_or_404(ModuleInstance, pk=item_id).delete()
        return JsonResponse({'success': True})

    if dataset in REFERENCE_MODELS:
        model = REFERENCE_MODELS[dataset]
        if request.user.has_perm(f'event.delete_{model._meta.model_name}'):
            get_object_or_404(model, pk=item_id).delete()
            return JsonResponse({'success': True})

    return JsonResponse({'error': 'Forbidden'}, status=403)


@table_staff_required
@require_http_methods(['GET'])
def autocomplete(request, field):
    term = request.GET.get('term', '').strip()
    if field in ('company', 'category', 'type_guest'):
        model_map = {
            'company': CompanyContact,
            'category': CategoryContact,
            'type_guest': TypeGuestContact,
        }
        return JsonResponse({'results': autocomplete_reference(model_map[field], term)})
    if field == 'producer':
        return JsonResponse({'results': autocomplete_producers(term)})
    if field == 'event':
        return JsonResponse({'results': autocomplete_events(term)})
    return JsonResponse({'error': 'Invalid field'}, status=400)


@table_staff_required
@require_http_methods(['GET'])
def export_contacts(request):
    if not request.user.has_perm('event.view_contact'):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    resource = ContactExport()
    dataset = resource.export(Contact.objects.all())
    response = HttpResponse(
        dataset.xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="contacts.xlsx"'
    return response


@table_staff_required
@require_http_methods(['GET'])
def export_actions(request):
    if not request.user.has_perm('event.view_action'):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    resource = ActionExport()
    dataset = resource.export(
        Action.objects.select_related(
            'contact', 'contact__company', 'contact__category',
            'contact__type_guest', 'contact__producer', 'event',
        ).all()
    )
    response = HttpResponse(
        dataset.xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="actions.xlsx"'
    return response

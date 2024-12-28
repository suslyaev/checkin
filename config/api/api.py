from event.models import ModuleInstance, Action, Contact
from rest_framework import viewsets, permissions
from django.utils.timezone import now
from .serializers import ModuleInstanceSerializer, ActionSerializer, ContactSerializer

class ModuleInstanceViewSet(viewsets.ModelViewSet):
    queryset = ModuleInstance.objects.filter(date_start__gte=now()) | ModuleInstance.objects.filter(date_end__gte=now())
    serializer_class = ModuleInstanceSerializer
    permission_classes = [
        permissions.DjangoModelPermissions
    ]
    def get_queryset(self):
        queryset = ModuleInstance.objects.filter(date_start__gte=now()) | ModuleInstance.objects.filter(date_end__gte=now())
        id_portal = self.request.query_params.get('id', None)
        if id_portal is not None:
            queryset = ModuleInstance.objects.filter(id=int(id_portal))
        return queryset[:50]

class ActionSerializerViewSet(viewsets.ModelViewSet):
    queryset = Action.objects.filter(is_last_state=True)
    serializer_class = ActionSerializer
    permission_classes = [
        permissions.DjangoModelPermissions
    ]

    def get_queryset(self):
        queryset = Action.objects.filter(is_last_state=True)
        contact_portal = self.request.query_params.get('contact', None)
        action_type_portal = self.request.query_params.get('action_type', None)
        module_instance_portal = self.request.query_params.get('module_instance', None)
        if contact_portal is not None:
            queryset = queryset.filter(contact=int(contact_portal))
        if action_type_portal is not None:
            queryset = queryset.filter(action_type=str(action_type_portal))
        if module_instance_portal is not None:
            queryset = queryset.filter(module_instance=int(module_instance_portal))
        return queryset[:50]
    

class ContactSerializerViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [
        permissions.DjangoModelPermissions
    ]
    
    def get_queryset(self):
        queryset = Contact.objects.all()
        user_id_portal = self.request.query_params.get('id', None)
        fio_portal = self.request.query_params.get('fio', None)
        if user_id_portal is not None:
            queryset = queryset.filter(id=int(user_id_portal))
        if fio_portal is not None:
            queryset = queryset.filter(fio__iexact=fio_portal.title())
        return queryset[:50]

from rest_framework import serializers
from event.models import ModuleInstance, Action, Contact, Company, CategoryContact

class ModuleInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleInstance
        fields = ['id', 'name', 'date_start', 'date_end', 'address']
        read_only_fields = ('id',)

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'comment']
        read_only_fields = ('id',)

class CategoryContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryContact
        fields = ['id', 'name', 'color', 'comment']
        read_only_fields = ('id',)

class ContactSerializer(serializers.ModelSerializer):
    company_obj = CompanySerializer(source='company', read_only=True)
    category_obj = CategoryContactSerializer(source='category', read_only=True)
    class Meta:
        model = Contact
        fields = ['id', 'fio', 'company', 'company_obj', 'category', 'category_obj', 'photo_link']
        read_only_fields = ('id', 'photo_link')

class ActionSerializer(serializers.ModelSerializer):
    contact_obj = ContactSerializer(source='contact', read_only=True)
    module_instance_obj = ModuleInstanceSerializer(source='module_instance', read_only=True)
    class Meta:
        model = Action
        fields = ['id', 'contact', 'contact_obj', 'module_instance', 'module_instance_obj', 'action_type', 'action_date']
        read_only_fields = ('id', 'operator')

    def validate(self, data):
        """
        Check that the start is before the stop.
        """
        instance = Action(**data)
        instance.clean()
        return data
    
    def create(self, validated_data):
        request = self.context.get('request', None)
        if request and request.user.is_authenticated:
            validated_data['operator'] = request.user
        return super().create(validated_data)

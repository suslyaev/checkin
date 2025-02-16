from django import forms
from .models import Action, ModuleInstance, CustomUser
from .models import Action, CategoryContact
from django.core.validators import RegexValidator

class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ('contact', 'module_instance', 'action_type',)


class CategoryContactForm(forms.ModelForm):
    color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),  # HTML-виджет выбора цвета
        max_length=7
    )

    class Meta:
        model = CategoryContact
        fields = "__all__"


class CheckinOrCancelForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)


class ModuleInstanceForm(forms.ModelForm):
    class Meta:
        model = ModuleInstance
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        # Вытаскиваем request, который передадим из админ-класса
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Если объект ещё не создан (нет pk) → это создание, а не редактирование
        if not self.instance.pk and self.request:
            # Проверяем, состоит ли пользователь в группе «Менеджер»
            if self.request.user.groups.filter(name='Менеджер').exists():
                # Если прокси-модель без AUTH_USER_MODEL:
                # Преобразуем request.user → CustomUser
                custom_user = CustomUser.objects.get(pk=self.request.user.pk)
                # Устанавливаем initial для поля 'managers'
                self.fields['managers'].initial = [custom_user]

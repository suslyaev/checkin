from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from .models import Action, ModuleInstance, CustomUser

class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ('contact', 'event', 'action_type',)


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

class CustomUserForm(UserCreationForm):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, widget=forms.Select, label="Роль")

    class Meta:
        model = CustomUser
        fields = ['phone', 'first_name', 'last_name', 'group']

class CustomUserChangeForm(UserChangeForm):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, widget=forms.Select, label="Роль")

    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput,
        required=False  # НЕобязательно
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
        required=False  # НЕобязательно
    )

    class Meta:
        model = CustomUser
        fields = ['phone', 'first_name', 'last_name', 'group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Устанавливаем текущую группу как значение по умолчанию
            self.fields['group'].initial = self.instance.groups.first() if self.instance.groups.exists() else None

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password1')
        p2 = cleaned_data.get('new_password2')

        # Если оба поля пустые, пропускаем
        if not p1 and not p2:
            return cleaned_data

        # Иначе, если заполнили хотя бы одно, проверяем совпадение
        if p1 != p2:
            self.add_error('new_password2', "Пароли не совпадают!")
        return cleaned_data

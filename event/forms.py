from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from .models import (
    ModuleInstance,
    CustomUser,
    Contact,
    CompanyContact,
    CategoryContact,
    TypeGuestContact,
)

class CheckinOrCancelForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)


class ContactMergeForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    primary_contact = forms.ModelChoiceField(
        queryset=Contact.objects.none(),
        label='Основная запись',
        widget=forms.RadioSelect,
        required=True,
    )
    last_name = forms.CharField(max_length=300, label='Фамилия')
    first_name = forms.CharField(max_length=300, label='Имя')
    middle_name = forms.CharField(max_length=300, label='Отчество', required=False)
    nickname = forms.CharField(max_length=300, label='Никнейм', required=False)
    company = forms.ModelChoiceField(
        queryset=CompanyContact.objects.all(),
        label='Компания',
        required=False,
    )
    category = forms.ModelChoiceField(
        queryset=CategoryContact.objects.all(),
        label='Категория',
        required=False,
    )
    type_guest = forms.ModelChoiceField(
        queryset=TypeGuestContact.objects.all(),
        label='Тип гостя',
        required=False,
    )
    producer = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        label='Продюсер',
        required=False,
    )
    comment = forms.CharField(
        label='Комментарий',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'cols': 60, 'style': 'width: 400px;'}),
    )
    photo_source = forms.ChoiceField(
        label='Фото',
        required=False,
        widget=forms.RadioSelect,
        choices=[],
    )

    def __init__(self, *args, contacts=None, **kwargs):
        self.contacts = list(contacts or [])
        super().__init__(*args, **kwargs)
        contact_qs = Contact.objects.filter(pk__in=[c.pk for c in self.contacts])
        self.fields['primary_contact'].queryset = contact_qs

        photo_choices = [('', 'Без фото')]
        for contact in self.contacts:
            if contact.photo:
                photo_choices.append((str(contact.pk), contact.get_fio()))
        self.fields['photo_source'].choices = photo_choices

        if not self.is_bound and self.contacts:
            primary = self.contacts[0]
            self.fields['primary_contact'].initial = primary.pk
            self._apply_contact_initial(primary)
            default_photo = ''
            if primary.photo:
                default_photo = str(primary.pk)
            else:
                for contact in self.contacts:
                    if contact.photo:
                        default_photo = str(contact.pk)
                        break
            self.fields['photo_source'].initial = default_photo

    def _apply_contact_initial(self, contact):
        self.fields['last_name'].initial = contact.last_name
        self.fields['first_name'].initial = contact.first_name
        self.fields['middle_name'].initial = contact.middle_name or ''
        self.fields['nickname'].initial = contact.nickname or ''
        self.fields['company'].initial = contact.company_id
        self.fields['category'].initial = contact.category_id
        self.fields['type_guest'].initial = contact.type_guest_id
        self.fields['producer'].initial = contact.producer_id
        self.fields['comment'].initial = contact.comment or ''

    def clean_middle_name(self):
        value = self.cleaned_data.get('middle_name')
        return value or None

    def clean_nickname(self):
        value = self.cleaned_data.get('nickname')
        return value or None

    def clean_comment(self):
        value = self.cleaned_data.get('comment')
        return value or None

    def clean_photo_source(self):
        value = self.cleaned_data.get('photo_source')
        if value in (None, ''):
            return ''
        valid_ids = {str(c.pk) for c in self.contacts}
        if value not in valid_ids:
            raise forms.ValidationError('Выберите фото из объединяемых карточек.')
        return value


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

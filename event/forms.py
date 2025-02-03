from django import forms
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

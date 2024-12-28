from django import forms
from .models import Action
from django.core.validators import RegexValidator

class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ('contact', 'module_instance', 'action_type',)

class CheckinOrCancelForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)

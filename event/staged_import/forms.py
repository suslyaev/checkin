from django import forms


class ContactStagedUploadForm(forms.Form):
    file = forms.FileField(
        label='Файл',
        help_text='Формат как в шаблоне import_cont.xlsx (.xlsx или .csv)',
    )

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        name = (uploaded.name or '').lower()
        if not (name.endswith('.xlsx') or name.endswith('.csv')):
            raise forms.ValidationError('Загрузите файл .xlsx или .csv')
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Файл слишком большой (максимум 10 МБ)')
        return uploaded

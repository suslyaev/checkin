"""
Mixin для ModuleInstanceAdmin - добавляет функциональность таблицы гостей
Подключить в admin.py:

from .admin_guests_table_mixin import GuestsTableMixin

class ModuleInstanceAdmin(GuestsTableMixin, BaseAdminPage, ExportActionModelAdmin):
    ...
"""

from django.urls import path, include
from django.utils.html import format_html
from django.urls import reverse


class GuestsTableMixin:
    """
    Mixin для добавления интерактивной таблицы гостей в ModuleInstanceAdmin
    """
    
    def get_urls(self):
        """Добавляем URL для таблицы гостей"""
        urls = super().get_urls()
        
        # Импортируем URL конфигурацию для таблицы гостей
        from .urls_guests_table import urlpatterns as guests_urls
        
        custom_urls = [
            # Подключаем все URL из guests_table
            *[path(url.pattern._route, 
                   self.admin_site.admin_view(url.callback), 
                   name=url.name) 
              for url in guests_urls],
        ]
        
        return custom_urls + urls
    
    def guests_table_button(self, obj):
        """Кнопка для перехода к таблице гостей"""
        if not obj.pk:
            return "-"
        
        url = reverse('admin:event_guests_table', args=[obj.pk])
        
        return format_html(
            '<a href="{}" class="button" style="'
            'padding: 10px 20px; '
            'background: #417690; '
            'color: white; '
            'border-radius: 4px; '
            'text-decoration: none; '
            'display: inline-block; '
            'font-weight: 500; '
            'transition: all 0.3s;">'
            '📊 Управление списком гостей</a>',
            url
        )
    
    guests_table_button.short_description = "Список гостей"
    
    def get_readonly_fields(self, request, obj=None):
        """Добавляем кнопку в readonly_fields"""
        readonly = list(super().get_readonly_fields(request, obj))
        
        if 'guests_table_button' not in readonly:
            readonly.append('guests_table_button')
        
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Добавляем раздел с кнопкой в fieldsets"""
        fieldsets = list(super().get_fieldsets(request, obj))
        
        # Проверяем, есть ли уже раздел "Управление гостями"
        has_guests_section = any(
            fieldset[0] == 'Управление гостями' 
            for fieldset in fieldsets
        )
        
        if not has_guests_section and obj and obj.pk:
            # Добавляем раздел с кнопкой
            fieldsets.append((
                'Управление гостями', {
                    'fields': [('guests_table_button',)],
                    'description': 'Интерактивная таблица для работы со списком гостей мероприятия'
                }
            ))
        
        return fieldsets


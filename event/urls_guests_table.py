"""
URL конфигурация для интерактивной таблицы гостей
"""

from django.urls import path
from . import views_guests_table

# Эти URL будут добавлены к admin/event/moduleinstance/
urlpatterns = [
    # Страница с таблицей
    path('<int:event_id>/guests-table/', 
         views_guests_table.guests_table_view,
         name='event_guests_table'),
    
    # API для получения данных
    path('<int:event_id>/guests-data/', 
         views_guests_table.guests_data_api,
         name='event_guests_data'),
    
    # API для сохранения
    path('<int:event_id>/guest-save/', 
         views_guests_table.guest_save_api,
         name='event_guest_save'),
    
    # API для удаления
    path('<int:event_id>/guest-delete/', 
         views_guests_table.guest_delete_api,
         name='event_guest_delete'),
    
    # API для автокомплита справочников
    path('<int:event_id>/autocomplete/<str:field>/', 
         views_guests_table.autocomplete_api,
         name='event_guest_autocomplete'),
    
    # API для поиска существующих контактов
    path('<int:event_id>/search-contacts/', 
         views_guests_table.search_contacts_api,
         name='event_search_contacts'),
]


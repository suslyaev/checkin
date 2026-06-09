from django.urls import path

from . import api, views

app_name = 'table'

urlpatterns = [
    path('api/contacts/export/', api.export_contacts, name='api_contacts_export'),
    path('api/autocomplete/<slug:field>/', api.autocomplete, name='api_autocomplete'),
    path('api/<slug:dataset>/save/', api.dataset_save, name='api_save'),
    path('api/<slug:dataset>/delete/', api.dataset_delete, name='api_delete'),
    path('api/<slug:dataset>/', api.dataset_list, name='api_list'),
    path('', views.workspace_root, name='workspace_root'),
    path('<slug:tab_id>/', views.workspace, name='workspace'),
]

from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from config import views

urlpatterns = [
    path('', views.home, name='home'),
    path('logout/', views.custom_logout, name='logout'),
    path('admin/', admin.site.urls),
    path('event/', include('event.urls')),
    path('events-list/', views.get_user_events, name='events-list'),
    path('admin-info/', views.get_admin_info, name='admin-info'),
    path('actions/', views.ActionView.as_view(), name='actions'),
    path('available-contacts/', views.AvailableContactsView.as_view(), name='available_contacts'),
    path('api/contacts/', views.ContactCreateView.as_view(), name='contact_create'),
    path('api/companies/', views.CompaniesView.as_view(), name='companies'),
    path('api/categories/', views.CategoriesView.as_view(), name='categories'),
    path('api/types/', views.TypeGuestView.as_view(), name='types'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_ROOT, document_root=settings.STATIC_ROOT)

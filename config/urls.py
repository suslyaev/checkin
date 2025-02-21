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
    path('actions/', views.ActionView.as_view(), name='actions'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_ROOT, document_root=settings.STATIC_ROOT)
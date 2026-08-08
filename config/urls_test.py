from django.http import HttpResponse
from django.urls import include, path

from config import views


def admin_index(request):
    return HttpResponse('Test admin placeholder')


admin_patterns = (
    [path('', admin_index, name='index')],
    'admin',
)

urlpatterns = [
    path('', views.home, name='home'),
    path('logout/', views.custom_logout, name='logout'),
    path('events-list/', views.get_user_events, name='events-list'),
    path('admin-info/', views.get_admin_info, name='admin-info'),
    path('event/', include('event.urls')),
    path('admin/', include(admin_patterns, namespace='admin')),
]

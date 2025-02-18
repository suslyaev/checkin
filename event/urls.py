from django.urls import path
from .views import checkin_list, confirm_checkin, cancel_checkin, checkin_detail
from . import views

urlpatterns = [
    # Маршруты для действий Checkin
    path('checkin-confirm/<int:pk>/', views.confirm_checkin, name='checkin_confirm'),
    path('checkin-cancel/<int:pk>/', views.cancel_checkin, name='checkin_cancel'),
    path('telegram-auth/', views.telegram_admin_auth, name='telegram_admin_auth'),

    #path('checkins/', checkin_list, name='checkin_list'),
    path('checkins/<int:pk>/confirm/', confirm_checkin, name='confirm_checkin'),
    path('checkins/<int:pk>/cancel/', cancel_checkin, name='cancel_checkin'),
    path('checkins/<int:pk>/detail/', checkin_detail, name='checkin_detail'),
    path('instance/<int:pk>/checkins/', checkin_list, name='checkin_list'),
]

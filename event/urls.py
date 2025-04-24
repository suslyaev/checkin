from django.urls import path
from .views import checkin_list, confirm_checkin, cancel_checkin, checkin_detail, action_invited, action_cancelled, action_registered, action_visited
from . import views

urlpatterns = [
    # Маршруты для действий на портале
    path('action-invited/<int:pk>/', action_invited, name='action_invited'),
    path('action-cancelled/<int:pk>/', action_cancelled, name='action_cancelled'),
    path('action-registered/<int:pk>/', action_registered, name='action_registered'),
    path('action-visited/<int:pk>/', action_visited, name='action_visited'),

    # Маршруты для действий в приложении
    path('telegram-auth/', views.telegram_admin_auth, name='telegram_admin_auth'),
    path('checkins/<int:pk>/confirm/', confirm_checkin, name='confirm_checkin'),
    path('checkins/<int:pk>/cancel/', cancel_checkin, name='cancel_checkin'),
    path('checkins/<int:pk>/detail/', checkin_detail, name='checkin_detail'),
    path('instance/<int:pk>/checkins/', checkin_list, name='checkin_list'),
]

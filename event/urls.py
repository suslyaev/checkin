from django.urls import path
from django.urls import reverse
from . import views

urlpatterns = [
    # Маршруты для действий Checkin
    path('checkin-confirm/<int:pk>/', views.confirm_checkin, name='checkin_confirm'),
    path('checkin-cancel/<int:pk>/', views.cancel_checkin, name='checkin_cancel'),
]

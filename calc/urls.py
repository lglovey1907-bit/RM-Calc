# calc/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    path('api/update-settings/', views.update_settings, name='update_settings'),
    path('api/save-calculation/', views.save_calculation, name='save_calculation'),
    path('api/get-history/', views.get_history, name='get_history'),
    path('api/clear-history/', views.clear_history, name='clear_history'),
]

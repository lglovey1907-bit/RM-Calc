# subscription/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/register/', views.register_device, name='register_device'),
    path('api/check-access/', views.check_access, name='check_access'),
]

# calc/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('', views.user_login, name='login'),  # Root URL redirects to login
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    
    # Main Application URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('calculator/', views.dashboard, name='calculator'),  # Alias for dashboard
    
    # API Endpoints
    path('api/update-settings/', views.update_settings, name='update_settings'),
    path('api/save-calculation/', views.save_calculation, name='save_calculation'),
    path('api/get-history/', views.get_history, name='get_history'),
    path('api/clear-history/', views.clear_history, name='clear_history'),
    path('api/stocks/search/', views.search_stocks, name='search_stocks'),
    
    # Payment URLs (if using Razorpay)
    path('payment/create-order/', views.create_order, name='create_order'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failed/', views.payment_failed, name='payment_failed'),
]

# main project urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('subscription.urls')),
    path('', include('calc.urls')),
    # ... your other URLs
]

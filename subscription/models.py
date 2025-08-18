# subscription/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.utils import timezone

class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    trial_start = models.DateTimeField(auto_now_add=True)
    trial_days = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def trial_end_date(self):
        return self.trial_start + timedelta(days=self.trial_days)
    
    @property
    def is_trial_expired(self):
        return timezone.now() > self.trial_end_date

class AppControl(models.Model):
    version = models.CharField(max_length=20, default="1.0.0")
    maintenance_mode = models.BooleanField(default=False)
    force_payment = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)  # Fixed this line

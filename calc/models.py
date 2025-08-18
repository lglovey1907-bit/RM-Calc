# calc/models.py
from django.db import models
from django.contrib.auth.models import User

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='risk_settings')
    capital = models.DecimalField(max_digits=15, decimal_places=2, default=2000000)  # Default 20,00,000
    risk_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)  # Default 1%
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - Capital: {self.capital}, Risk: {self.risk_percent}%"
    
    class Meta:
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"


class CalculationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calculations')
    symbol = models.CharField(max_length=50)
    entry_price = models.DecimalField(max_digits=10, decimal_places=2)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=2)
    risk_per_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    targets = models.TextField()
    direction = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.symbol} - {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']

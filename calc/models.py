# calc/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    capital = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    risk_percent = models.DecimalField(max_digits=5, decimal_places=2, default=2.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} Settings"


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='calc_subscription')
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {'Paid' if self.is_paid else 'Free'}"


class CalculationHistory(models.Model):
    DIRECTION_CHOICES = [
        ('Buy (Long)', 'Buy (Long)'),
        ('Sell (Short)', 'Sell (Short)'),
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calculations')
    symbol = models.CharField(max_length=40)
    entry_price = models.DecimalField(max_digits=12, decimal_places=4)
    stop_loss = models.DecimalField(max_digits=12, decimal_places=4)
    quantity = models.IntegerField()
    direction = models.CharField(max_length=15, choices=DIRECTION_CHOICES, default="Buy (Long)")
    risk_amount = models.DecimalField(max_digits=12, decimal_places=2)
    risk_per_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0.00)
    targets = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.symbol} {self.direction}"
    
    class Meta:
        verbose_name_plural = "Calculation Histories"
        ordering = ['-timestamp']


class StockData(models.Model):
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    company_name = models.CharField(max_length=200)
    last_price = models.DecimalField(max_digits=12, decimal_places=2)
    change = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pchange = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    volume = models.BigIntegerField(default=0)
    market_cap = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['symbol']
        verbose_name = 'Stock Data'
        verbose_name_plural = 'Stock Data'
    
    def __str__(self):
        return f"{self.symbol} - {self.company_name}"
    
    @property
    def formatted_price(self):
        return f"₹{self.last_price:,.2f}"
    
    @property
    def change_color(self):
        return 'green' if self.change >= 0 else 'red'


class Calculation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=50)
    entry_price = models.DecimalField(max_digits=10, decimal_places=2)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    direction = models.CharField(max_length=10)  # 'Buy' or 'Sell'
    targets = models.TextField(blank=True)
    trade_type = models.CharField(max_length=20, default='stocks')
    created_at = models.DateTimeField(auto_now_add=True)


class TradingJournalEntry(models.Model):
    MARKET_TYPES = [
        ('Equity', 'Equity'),
        ('Commodity', 'Commodity'),
        ('Currency', 'Currency'),
        ('Options', 'Options'),
        ('Futures', 'Futures'),
        ('Other', 'Other'),
    ]
    
    POSITION_TYPES = [
        ('Buy', 'Buy'),
        ('Short', 'Short'),
    ]
    
    TIME_FRAMES = [
        ('Intraday', 'Intraday'),
        ('Swing', 'Swing'),
        ('Positional', 'Positional'),
        ('Long Term', 'Long Term'),
    ]
    
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Closed', 'Closed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    strategy_name = models.CharField(max_length=100)
    market_type = models.CharField(max_length=20, choices=MARKET_TYPES)
    instrument_name = models.CharField(max_length=50)
    position = models.CharField(max_length=10, choices=POSITION_TYPES)
    trade_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)
    time_frame = models.CharField(max_length=20, choices=TIME_FRAMES)
    invested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    risk_percent = models.DecimalField(max_digits=5, decimal_places=2)
    risk_rs = models.DecimalField(max_digits=12, decimal_places=2)
    entry_price = models.DecimalField(max_digits=10, decimal_places=2)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    exit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    profit_loss = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.instrument_name} - {self.position} - {self.trade_date}"


# Create profile automatically when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        UserSettings.objects.create(user=instance)
        UserSubscription.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    if hasattr(instance, 'settings'):
        instance.settings.save()

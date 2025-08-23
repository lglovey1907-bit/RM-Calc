# calc/admin.py
from django.contrib import admin
from .models import UserProfile, UserSettings, UserSubscription, CalculationHistory

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'company_name', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone', 'company_name')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'capital', 'risk_percent', 'updated_at']
    search_fields = ['user__username', 'user__email']
    list_filter = ['updated_at', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_paid', 'payment_date', 'amount', 'created_at')
    list_filter = ('is_paid', 'payment_date', 'created_at')
    search_fields = ('user__username', 'user__email', 'razorpay_payment_id', 'razorpay_order_id')
    readonly_fields = ('created_at',)

@admin.register(CalculationHistory)
class CalculationHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'symbol', 'entry_price', 'stop_loss', 'quantity', 'direction', 'risk_amount', 'timestamp']
    search_fields = ['user__username', 'user__email', 'symbol']
    list_filter = ['timestamp', 'direction', 'symbol']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']

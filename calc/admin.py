# calc/admin.py
from django.contrib import admin
from .models import UserSettings, CalculationHistory

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'capital', 'risk_percent', 'updated_at']
    search_fields = ['user__username']
    list_filter = ['updated_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CalculationHistory)
class CalculationHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'symbol', 'entry_price', 'stop_loss', 'quantity', 'direction', 'timestamp']
    search_fields = ['user__username', 'symbol']
    list_filter = ['timestamp', 'direction']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp']

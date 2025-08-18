# subscription/admin.py
from django.contrib import admin
from .models import UserSubscription, AppControl

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'user', 'is_active', 'is_paid', 'trial_start', 'is_trial_expired']
    list_filter = ['is_active', 'is_paid']
    search_fields = ['device_id', 'user__username']
    
    actions = ['activate_users', 'deactivate_users', 'mark_as_paid']
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_users.short_description = "Deactivate selected users"
    
    def mark_as_paid(self, request, queryset):
        queryset.update(is_paid=True)
    mark_as_paid.short_description = "Mark as paid"

@admin.register(AppControl)
class AppControlAdmin(admin.ModelAdmin):
    list_display = ['version', 'maintenance_mode', 'force_payment', 'updated_at']

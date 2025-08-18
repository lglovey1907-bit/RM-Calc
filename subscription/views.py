# subscription/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import UserSubscription, AppControl
import json

@api_view(['POST'])
def register_device(request):
    device_id = request.data.get('device_id')
    email = request.data.get('email', '')
    
    if not device_id:
        return Response({'error': 'Device ID required'}, status=400)
    
    # Create or get user
    user, created = User.objects.get_or_create(
        username=device_id,
        defaults={'email': email}
    )
    
    # Create or get subscription
    subscription, created = UserSubscription.objects.get_or_create(
        device_id=device_id,
        defaults={'user': user}
    )
    
    return Response({
        'device_id': device_id,
        'trial_days_left': max(0, (subscription.trial_end_date - timezone.now()).days),
        'is_paid': subscription.is_paid,
        'is_active': subscription.is_active
    })

@api_view(['POST'])
def check_access(request):
    device_id = request.data.get('device_id')
    
    # Check app control settings
    app_control = AppControl.objects.first()
    if app_control and app_control.maintenance_mode:
        return Response({
            'access': False,
            'reason': 'maintenance',
            'message': app_control.message or 'App is under maintenance'
        })
    
    try:
        subscription = UserSubscription.objects.get(device_id=device_id)
        
        # Check if account is disabled
        if not subscription.is_active:
            return Response({
                'access': False,
                'reason': 'account_disabled',
                'message': 'Your account has been disabled'
            })
        
        # Check trial/payment
        if subscription.is_trial_expired and not subscription.is_paid:
            if app_control and app_control.force_payment:
                return Response({
                    'access': False,
                    'reason': 'payment_required',
                    'message': 'Trial expired. Payment required to continue'
                })
            else:
                # Still in grace period
                return Response({
                    'access': True,
                    'warning': 'Trial expired. Please consider subscribing',
                    'trial_expired': True
                })
        
        return Response({
            'access': True,
            'is_paid': subscription.is_paid,
            'trial_days_left': max(0, (subscription.trial_end_date - timezone.now()).days)
        })
        
    except UserSubscription.DoesNotExist:
        return Response({
            'access': False,
            'reason': 'not_registered',
            'message': 'Device not registered'
        })

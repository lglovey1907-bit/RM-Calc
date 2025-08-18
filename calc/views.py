# calc/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import UserSettings, CalculationHistory
import json

@login_required
def dashboard(request):
    """Main dashboard view with user-specific settings"""
    # Get or create user settings
    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user,
        defaults={'capital': 2000000, 'risk_percent': 1.00}
    )
    
    # Calculate risk in rupees
    risk_rs = (user_settings.capital * user_settings.risk_percent) / 100
    
    context = {
        'user': request.user,
        'user_capital': user_settings.capital,
        'user_risk_percent': user_settings.risk_percent,
        'risk_rs': risk_rs,
    }
    
    return render(request, 'calc/calculator.html', context)


@login_required
def update_settings(request):
    """Update user capital and risk settings"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            capital = float(data.get('capital', 2000000))
            risk_percent = float(data.get('risk_percent', 1))
            
            # Validate inputs
            if capital < 0:
                return JsonResponse({'success': False, 'message': 'Capital cannot be negative'})
            
            if risk_percent < 0 or risk_percent > 100:
                return JsonResponse({'success': False, 'message': 'Risk percent must be between 0 and 100'})
            
            # Get or create user settings
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user,
                defaults={'capital': capital, 'risk_percent': risk_percent}
            )
            
            # Update settings
            if not created:
                user_settings.capital = capital
                user_settings.risk_percent = risk_percent
                user_settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Settings updated successfully',
                'capital': float(user_settings.capital),
                'risk_percent': float(user_settings.risk_percent)
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def save_calculation(request):
    """Save calculation to history"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            calculation = CalculationHistory.objects.create(
                user=request.user,
                symbol=data.get('symbol', 'N/A'),
                entry_price=float(data.get('entry_price', 0)),
                stop_loss=float(data.get('stop_loss', 0)),
                risk_per_quantity=float(data.get('risk_per_quantity', 0)),
                quantity=int(data.get('quantity', 0)),
                targets=data.get('targets', ''),
                direction=data.get('direction', 'Buy (Long)')
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Calculation saved successfully',
                'calculation': {
                    'id': calculation.id,
                    'symbol': calculation.symbol,
                    'entry_price': float(calculation.entry_price),
                    'stop_loss': float(calculation.stop_loss),
                    'risk_per_quantity': float(calculation.risk_per_quantity),
                    'quantity': calculation.quantity,
                    'targets': calculation.targets,
                    'direction': calculation.direction,
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def get_history(request):
    """Get calculation history for the user"""
    try:
        history = CalculationHistory.objects.filter(user=request.user).order_by('-timestamp')[:50]
        
        history_data = []
        for calc in history:
            history_data.append({
                'id': calc.id,
                'symbol': calc.symbol,
                'entry_price': float(calc.entry_price),
                'stop_loss': float(calc.stop_loss),
                'risk_per_quantity': float(calc.risk_per_quantity),
                'quantity': calc.quantity,
                'targets': calc.targets,
                'direction': calc.direction,
            })
        
        return JsonResponse({
            'success': True,
            'history': history_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def clear_history(request):
    """Clear all calculation history for the user"""
    if request.method == 'POST':
        try:
            CalculationHistory.objects.filter(user=request.user).delete()
            return JsonResponse({'success': True, 'message': 'History cleared successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def user_login(request):
    """User login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'calc/login.html')


def user_logout(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('login')


def user_register(request):
    """User registration view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Basic validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match')
            return render(request, 'calc/register.html')
        
        # Check if username exists
        from django.contrib.auth.models import User
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'calc/register.html')
        
        # Create user
        try:
            user = User.objects.create_user(username=username, email=email, password=password1)
            user.save()
            
            # Create default settings for new user
            UserSettings.objects.create(
                user=user,
                capital=2000000,  # Default 20,00,000
                risk_percent=1.00  # Default 1%
            )
            
            # Log the user in
            login(request, user)
            messages.success(request, f'Welcome {username}! Your account has been created.')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'calc/register.html')
    
    return render(request, 'calc/register.html')

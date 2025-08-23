# calc/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.db.models import Q
from decimal import Decimal
import json
import hmac
import hashlib
import logging
import yfinance as yf
from django.core.cache import cache

from .models import (
    UserSettings,
    CalculationHistory,
    UserSubscription,
    StockData
)

# Initialize logger
logger = logging.getLogger(__name__)

# Razorpay client initialization (uncomment when you have credentials)
# import razorpay
# razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


# ============ Authentication Views ============

def user_login(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'calc/login.html')


def user_register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validation
        errors = []
        
        if not username or not email or not password1:
            errors.append('All fields are required')
        
        if password1 != password2:
            errors.append('Passwords do not match')
        
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters long')
        
        if User.objects.filter(username=username).exists():
            errors.append('Username already exists')
        
        if User.objects.filter(email=email).exists():
            errors.append('Email already registered')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'calc/register.html')
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            
            # Create default settings for new user
            UserSettings.objects.create(
                user=user,
                capital=Decimal('200000.00'),  # Default ₹2,00,000
                risk_percent=Decimal('1.00')    # Default 1%
            )
            
            # Auto-login after registration
            login(request, user)
            messages.success(request, f'Welcome {username}! Your account has been created successfully.')
            return redirect('dashboard')
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            messages.error(request, 'Error creating account. Please try again.')
            return render(request, 'calc/register.html')
    
    return render(request, 'calc/register.html')


@login_required
def user_logout(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('login')


# ============ Main Application Views ============

@login_required
def dashboard(request):
    """Main dashboard view with risk calculator"""
    # Get or create user settings
    user_settings, created = UserSettings.objects.get_or_create(
        user=request.user,
        defaults={
            'capital': Decimal('200000.00'),
            'risk_percent': Decimal('1.00')
        }
    )
    
    # Calculate risk in rupees
    risk_rs = (user_settings.capital * user_settings.risk_percent) / 100
    
    # Get recent history
    recent_history = CalculationHistory.objects.filter(
        user=request.user
    ).order_by('-timestamp')[:10]
    
    context = {
        'user': request.user,
        'user_capital': user_settings.capital,
        'user_risk_percent': user_settings.risk_percent,
        'risk_rs': risk_rs,
        'recent_history': recent_history,
    }
    
    return render(request, 'calc/calculator.html', context)


# ============ API Endpoints ============

@login_required
@require_http_methods(["POST"])
def update_settings(request):
    """Update user capital and risk settings"""
    try:
        data = json.loads(request.body)
        capital = Decimal(str(data.get('capital', '200000')))
        risk_percent = Decimal(str(data.get('risk_percent', '1')))
        
        # Validation
        if capital < 0:
            return JsonResponse({
                'success': False,
                'message': 'Capital cannot be negative'
            })
        
        if capital > Decimal('999999999'):
            return JsonResponse({
                'success': False,
                'message': 'Capital amount is too large'
            })
        
        if risk_percent < 0 or risk_percent > 100:
            return JsonResponse({
                'success': False,
                'message': 'Risk percent must be between 0 and 100'
            })
        
        # Update settings
        user_settings, created = UserSettings.objects.get_or_create(
            user=request.user
        )
        
        user_settings.capital = capital
        user_settings.risk_percent = risk_percent
        user_settings.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Settings updated successfully',
            'capital': float(user_settings.capital),
            'risk_percent': float(user_settings.risk_percent)
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'message': 'Invalid numeric values provided'
        })
    except Exception as e:
        logger.error(f"Settings update error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while updating settings'
        })


@login_required
@require_http_methods(["POST"])
def save_calculation(request):
    """Save calculation to history"""
    try:
        # Parse the JSON body
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['symbol', 'entry_price', 'stop_loss', 'quantity']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'message': f'Missing required field: {field}'
                })
        
        # Calculate risk per quantity and total risk amount
        entry_price = Decimal(str(data.get('entry_price', '0')))
        stop_loss = Decimal(str(data.get('stop_loss', '0')))
        quantity = int(data.get('quantity', 0))
        risk_per_quantity = abs(entry_price - stop_loss)
        risk_amount = risk_per_quantity * quantity
        
        # Create the calculation record
        calculation = CalculationHistory.objects.create(
            user=request.user,
            symbol=data.get('symbol', 'MANUAL'),
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_per_quantity=risk_per_quantity,
            risk_amount=risk_amount,
            quantity=quantity,
            targets=data.get('targets', ''),
            direction=data.get('direction', 'Buy')
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
                'risk_amount': float(calculation.risk_amount),
                'quantity': calculation.quantity,
                'targets': calculation.targets,
                'direction': calculation.direction,
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'message': f'Invalid numeric values provided: {str(e)}'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        })
    except Exception as e:
        logger.error(f"Save calculation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })


@login_required
def get_history(request):
    """Get calculation history for the user"""
    try:
        # Get limit from query params (default 50)
        limit = int(request.GET.get('limit', 50))
        limit = min(limit, 100)  # Cap at 100
        
        history = CalculationHistory.objects.filter(
            user=request.user
        ).order_by('-timestamp')[:limit]
        
        history_data = []
        for calc in history:
            history_data.append({
                'id': calc.id,
                'symbol': calc.symbol,
                'entry_price': float(calc.entry_price),
                'stop_loss': float(calc.stop_loss),
                'risk_per_quantity': float(calc.risk_per_quantity),
                'risk_amount': float(getattr(calc, 'risk_amount', 0)),
                'quantity': calc.quantity,
                'targets': calc.targets,
                'direction': calc.direction,
                'trade_type': getattr(calc, 'trade_type', 'stocks'),
                'timestamp': calc.timestamp.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'history': history_data,
            'count': len(history_data)
        })
        
    except Exception as e:
        logger.error(f"Get history error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while fetching history'
        })


@login_required
@require_http_methods(["POST"])
def clear_history(request):
    """Clear all calculation history for the user"""
    try:
        count = CalculationHistory.objects.filter(user=request.user).count()
        CalculationHistory.objects.filter(user=request.user).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully cleared {count} history entries'
        })
        
    except Exception as e:
        logger.error(f"Clear history error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while clearing history'
        })


# ============ Stock Search API - Enhanced for NIFTY 500 + Indices ============

def get_comprehensive_nse_indices():
    """Get comprehensive list of NSE indices with their yfinance symbols"""
    return {
        # Broad-based Indices
        'NIFTY': '^NSEI',
        'NIFTY50': '^NSEI',
        'NIFTY100': '^CNX100',
        'NIFTY200': '^CNX200',
        'NIFTY500': '^CNX500',
        'NIFTY TOTAL MARKET': '^CNXTM',
        'NIFTY NEXT 50': '^NSMIDCP',
        'NIFTY MIDCAP 100': '^NSEMDCP50',
        'NIFTY MIDCAP 150': '^NSEMDCP150',
        'NIFTY SMALLCAP 100': '^NSESMLCAP',
        'NIFTY SMALLCAP 250': '^NSESML250',
        'NIFTY MICROCAP 250': '^NSEMIC250',
        'NIFTY LARGEMIDCAP 250': '^NSELMC250',
        
        # Sectoral Indices
        'NIFTY AUTO': '^CNXAUTO',
        'NIFTY BANK': '^NSEBANK',
        'NIFTY FIN SERVICE': '^CNXFINANCE',
        'NIFTY FMCG': '^CNXFMCG',
        'NIFTY IT': '^CNXIT',
        'NIFTY MEDIA': '^CNXMEDIA',
        'NIFTY METAL': '^CNXMETAL',
        'NIFTY PHARMA': '^CNXPHARMA',
        'NIFTY PSU BANK': '^CNXPSUBANK',
        'NIFTY PVT BANK': '^CNXPVTBANK',
        'NIFTY REALTY': '^CNXREALTY',
        'NIFTY ENERGY': '^CNXENERGY',
        'NIFTY INFRA': '^CNXINFRA',
        'NIFTY COMMODITIES': '^CNXCOMMODITY',
        'NIFTY CONSUMPTION': '^CNXCONSUMPTION',
        'NIFTY CPSE': '^CNXCPSE',
        'NIFTY INDIA CONSUMPTION': '^CNXCONSUMER',
        'NIFTY OIL GAS': '^CNXOILGAS',
        'NIFTY HEALTHCARE': '^CNXHEALTH',
        'NIFTY SERVICES': '^CNXSERVICE',
        'NIFTY MNC': '^CNXMNC',
        'NIFTY PSE': '^CNXPSE',
        'NIFTY SME EMERGE': '^CNXSME',
        
        # Thematic Indices
        'FINNIFTY': '^NSEBANK',  # Financial Services
        'BANKNIFTY': '^NSEBANK',
        'NIFTY ALPHA 50': '^CNXALPHA50',
        'NIFTY DIVIDEND OPPORTUNITIES 50': '^CNXDIV50',
        'NIFTY GROWTH SECTORS 15': '^CNXGROWTH15',
        'NIFTY HIGH BETA 50': '^CNXHIGHBETA50',
        'NIFTY LOW VOLATILITY 50': '^CNXLOWVOL50',
        'NIFTY MOMENTUM 30': '^CNXMOMENTUM30',
        'NIFTY QUALITY 30': '^CNXQUALITY30',
        'NIFTY VALUE 50': '^CNXVALUE50',
        
        # BSE Indices
        'SENSEX': '^BSESN',
        'BSE100': '^BSE100',
        'BSE200': '^BSE200',
        'BSE500': '^BSE500',
        'BSE MIDCAP': '^BSEMID',
        'BSE SMALLCAP': '^BSESML',
    }


def get_nifty_500_stocks():
    """Get NIFTY 500 stocks list with company names - comprehensive database"""
    return {
        # NIFTY 50 Stocks
        'ADANIENT': 'Adani Enterprises Limited',
        'ADANIPORTS': 'Adani Ports and Special Economic Zone Limited',
        'APOLLOHOSP': 'Apollo Hospitals Enterprise Limited',
        'ASIANPAINT': 'Asian Paints Limited',
        'AXISBANK': 'Axis Bank Limited',
        'BAJAJ-AUTO': 'Bajaj Auto Limited',
        'BAJFINANCE': 'Bajaj Finance Limited',
        'BAJAJFINSV': 'Bajaj Finserv Limited',
        'BPCL': 'Bharat Petroleum Corporation Limited',
        'BHARTIARTL': 'Bharti Airtel Limited',
        'BRITANNIA': 'Britannia Industries Limited',
        'CIPLA': 'Cipla Limited',
        'COALINDIA': 'Coal India Limited',
        'DIVISLAB': 'Divi\'s Laboratories Limited',
        'DRREDDY': 'Dr. Reddy\'s Laboratories Limited',
        'EICHERMOT': 'Eicher Motors Limited',
        'GRASIM': 'Grasim Industries Limited',
        'HCLTECH': 'HCL Technologies Limited',
        'HDFCBANK': 'HDFC Bank Limited',
        'HDFCLIFE': 'HDFC Life Insurance Company Limited',
        'HEROMOTOCO': 'Hero MotoCorp Limited',
        'HINDALCO': 'Hindalco Industries Limited',
        'HINDUNILVR': 'Hindustan Unilever Limited',
        'ICICIBANK': 'ICICI Bank Limited',
        'ITC': 'ITC Limited',
        'INDUSINDBK': 'IndusInd Bank Limited',
        'INFY': 'Infosys Limited',
        'JSWSTEEL': 'JSW Steel Limited',
        'KOTAKBANK': 'Kotak Mahindra Bank Limited',
        'LT': 'Larsen & Toubro Limited',
        'M&M': 'Mahindra & Mahindra Limited',
        'MARUTI': 'Maruti Suzuki India Limited',
        'NESTLEIND': 'Nestle India Limited',
        'NTPC': 'NTPC Limited',
        'ONGC': 'Oil and Natural Gas Corporation Limited',
        'POWERGRID': 'Power Grid Corporation of India Limited',
        'RELIANCE': 'Reliance Industries Limited',
        'SBILIFE': 'SBI Life Insurance Company Limited',
        'SHREECEM': 'Shree Cement Limited',
        'SBIN': 'State Bank of India',
        'SUNPHARMA': 'Sun Pharmaceutical Industries Limited',
        'TCS': 'Tata Consultancy Services Limited',
        'TATACONSUM': 'Tata Consumer Products Limited',
        'TATAMOTORS': 'Tata Motors Limited',
        'TATASTEEL': 'Tata Steel Limited',
        'TECHM': 'Tech Mahindra Limited',
        'TITAN': 'Titan Company Limited',
        'ULTRACEMCO': 'UltraTech Cement Limited',
        'UPL': 'UPL Limited',
        'WIPRO': 'Wipro Limited',
        
        # NIFTY Next 50 & Additional NIFTY 500 Stocks
        'ABB': 'ABB India Limited',
        'ACC': 'ACC Limited',
        'AUBANK': 'AU Small Finance Bank Limited',
        'ABBOTINDIA': 'Abbott India Limited',
        'ADANIGREEN': 'Adani Green Energy Limited',
        'ADANIPOWER': 'Adani Power Limited',
        'ADANITRANS': 'Adani Transmission Limited',
        'ADANIGAS': 'Adani Total Gas Limited',
        'AMBUJACEM': 'Ambuja Cements Limited',
        'APOLLOTYRE': 'Apollo Tyres Limited',
        'ASHOKLEY': 'Ashok Leyland Limited',
        'AUROPHARMA': 'Aurobindo Pharma Limited',
        'BANDHANBNK': 'Bandhan Bank Limited',
        'BERGEPAINT': 'Berger Paints India Limited',
        'BIOCON': 'Biocon Limited',
        'BOSCHLTD': 'Bosch Limited',
        'CADILAHC': 'Cadila Healthcare Limited',
        'CHOLAFIN': 'Cholamandalam Investment and Finance Company Limited',
        'COLPAL': 'Colgate Palmolive (India) Limited',
        'CONCOR': 'Container Corporation of India Limited',
        'COROMANDEL': 'Coromandel International Limited',
        'DABUR': 'Dabur India Limited',
        'DLF': 'DLF Limited',
        'DMART': 'Avenue Supermarts Limited',
        'FEDERALBNK': 'Federal Bank Limited',
        'GAIL': 'GAIL (India) Limited',
        'GLAND': 'Gland Pharma Limited',
        'GMRINFRA': 'GMR Infrastructure Limited',
        'GODREJCP': 'Godrej Consumer Products Limited',
        'GODREJPROP': 'Godrej Properties Limited',
        'HAVELLS': 'Havells India Limited',
        'HDFC': 'Housing Development Finance Corporation Limited',
        'HDFCAMC': 'HDFC Asset Management Company Limited',
        'ICICIPRULI': 'ICICI Prudential Life Insurance Company Limited',
        'IDFCFIRSTB': 'IDFC First Bank Limited',
        'IGL': 'Indraprastha Gas Limited',
        'INDIAMART': 'IndiaMART InterMESH Limited',
        'IOC': 'Indian Oil Corporation Limited',
        'IRCTC': 'Indian Railway Catering and Tourism Corporation Limited',
        'JINDALSTEL': 'Jindal Steel & Power Limited',
        'JSWENERGY': 'JSW Energy Limited',
        'LICI': 'Life Insurance Corporation of India',
        'LTIM': 'LTIMindtree Limited',
        'LUPIN': 'Lupin Limited',
        'MARICO': 'Marico Limited',
        'MCDOWELL-N': 'United Spirits Limited',
        'MFSL': 'Max Financial Services Limited',
        'MPHASIS': 'Mphasis Limited',
        'MRF': 'MRF Limited',
        'NAUKRI': 'Info Edge (India) Limited',
        'NAVINFLUOR': 'Navin Fluorine International Limited',
        'NMDC': 'NMDC Limited',
        'OBEROIRLTY': 'Oberoi Realty Limited',
        'OFSS': 'Oracle Financial Services Software Limited',
        'PAGEIND': 'Page Industries Limited',
        'PEL': 'Piramal Enterprises Limited',
        'PERSISTENT': 'Persistent Systems Limited',
        'PETRONET': 'Petronet LNG Limited',
        'PIDILITIND': 'Pidilite Industries Limited',
        'PIIND': 'PI Industries Limited',
        'PNB': 'Punjab National Bank',
        'POLYCAB': 'Polycab India Limited',
        'PVR': 'PVR Limited',
        'RAMCOCEM': 'The Ramco Cements Limited',
        'RBLBANK': 'RBL Bank Limited',
        'RECLTD': 'REC Limited',
        'SAIL': 'Steel Authority of India Limited',
        'SBICARD': 'SBI Cards and Payment Services Limited',
        'SIEMENS': 'Siemens Limited',
        'SRF': 'SRF Limited',
        'TORNTPHARM': 'Torrent Pharmaceuticals Limited',
        'TRENT': 'Trent Limited',
        'TVSMOTOR': 'TVS Motor Company Limited',
        'VEDL': 'Vedanta Limited',
        'VOLTAS': 'Voltas Limited',
        'WHIRLPOOL': 'Whirlpool of India Limited',
        'ZEEL': 'Zee Entertainment Enterprises Limited',
        'ZOMATO': 'Zomato Limited',
        
        # Additional NIFTY 500 Stocks (Midcap & Smallcap) - Selection of most important ones
        'AARTIIND': 'Aarti Industries Limited',
        'ABCAPITAL': 'Aditya Birla Capital Limited',
        'ABFRL': 'Aditya Birla Fashion and Retail Limited',
        'AJANTPHARM': 'Ajanta Pharma Limited',
        'ALKEM': 'Alkem Laboratories Limited',
        'AMARAJABAT': 'Amara Raja Batteries Limited',
        'APLAPOLLO': 'APL Apollo Tubes Limited',
        'ASTRAL': 'Astral Limited',
        'ATUL': 'Atul Limited',
        'BALKRISIND': 'Balkrishna Industries Limited',
        'BATAINDIA': 'Bata India Limited',
        'BEL': 'Bharat Electronics Limited',
        'BHARATFORG': 'Bharat Forge Limited',
        'BHEL': 'Bharat Heavy Electricals Limited',
        'BLUEDART': 'Blue Dart Express Limited',
        'CANBK': 'Canara Bank',
        'CANFINHOME': 'Can Fin Homes Limited',
        'CASTROLIND': 'Castrol India Limited',
        'CEATLTD': 'CEAT Limited',
        'CHAMBLFERT': 'Chambal Fertilisers and Chemicals Limited',
        'CRISIL': 'CRISIL Limited',
        'CROMPTON': 'Crompton Greaves Consumer Electricals Limited',
        'CUB': 'City Union Bank Limited',
        'CUMMINSIND': 'Cummins India Limited',
        'DEEPAKNTR': 'Deepak Nitrite Limited',
        'DIXON': 'Dixon Technologies (India) Limited',
        'ESCORTS': 'Escorts Limited',
        'EXIDEIND': 'Exide Industries Limited',
        'FINEORG': 'Fine Organic Industries Limited',
        'GICRE': 'General Insurance Corporation of India',
        'GILLETTE': 'Gillette India Limited',
        'GLAXO': 'GlaxoSmithKline Pharmaceuticals Limited',
        'GNFC': 'Gujarat Narmada Valley Fertilizers and Chemicals Limited',
        'GRANULES': 'Granules India Limited',
        'GSPL': 'Gujarat State Petronet Limited',
        'GUJGASLTD': 'Gujarat Gas Limited',
        'HAL': 'Hindustan Aeronautics Limited',
        'HONAUT': 'Honeywell Automation India Limited',
        'IBREALEST': 'Indiabulls Real Estate Limited',
        'IDEA': 'Vodafone Idea Limited',
        'IDFC': 'IDFC Limited',
        'INDHOTEL': 'The Indian Hotels Company Limited',
        'INDIGO': 'InterGlobe Aviation Limited',
        'INDUSTOWER': 'Indus Towers Limited',
        'INTELLECT': 'Intellect Design Arena Limited',
        'IOB': 'Indian Overseas Bank',
        'IRFC': 'Indian Railway Finance Corporation Limited',
        'ISEC': 'ICICI Securities Limited',
        'JKCEMENT': 'JK Cement Limited',
        'JKLAKSHMI': 'JK Lakshmi Cement Limited',
        'JMFINANCIL': 'JM Financial Limited',
        'JUBLFOOD': 'Jubilant FoodWorks Limited',
        'KALYANKJIL': 'Kalyan Jewellers India Limited',
        'KEI': 'KEI Industries Limited',
        'L&TFH': 'L&T Finance Holdings Limited',
        'LALPATHLAB': 'Dr. Lal PathLabs Limited',
        'LAURUSLABS': 'Laurus Labs Limited',
        'LICHSGFIN': 'LIC Housing Finance Limited',
        'LTTS': 'L&T Technology Services Limited',
        'MANAPPURAM': 'Manappuram Finance Limited',
        'MAZDOCK': 'Mazagon Dock Shipbuilders Limited',
        'MINDTREE': 'Mindtree Limited',
        'MOTHERSUMI': 'Motherson Sumi Systems Limited',
        'MUTHOOTFIN': 'Muthoot Finance Limited',
        'NATIONALUM': 'National Aluminium Company Limited',
        'NBCC': 'NBCC (India) Limited',
        'NEWGEN': 'Newgen Software Technologies Limited',
        'NIITLTD': 'NIIT Limited',
        'NOCIL': 'NOCIL Limited',
        'NYKAA': 'FSN E-Commerce Ventures Limited',
        'ORIENTELEC': 'Orient Electric Limited',
        'PAYTM': 'One 97 Communications Limited',
        'PFC': 'Power Finance Corporation Limited',
        'PFIZER': 'Pfizer Limited',
        'PHOENIXLTD': 'The Phoenix Mills Limited',
        'PIRAMALENT': 'Piramal Enterprises Limited',
        'PNBHOUSING': 'PNB Housing Finance Limited',
        'POLICYBZR': 'PB Fintech Limited',
        'POLYMED': 'Poly Medicure Limited',
        'PRESTIGE': 'Prestige Estates Projects Limited',
        'RADICO': 'Radico Khaitan Limited',
        'RAILTEL': 'RailTel Corporation of India Limited',
        'RATNAMANI': 'Ratnamani Metals & Tubes Limited',
        'RAYMOND': 'Raymond Limited',
        'RELAXO': 'Relaxo Footwears Limited',
        'RPOWER': 'Reliance Power Limited',
        'SCHAEFFLER': 'Schaeffler India Limited',
        'SHYAMMETL': 'Shyam Metalics and Energy Limited',
        'SJVN': 'SJVN Limited',
        'SOBHA': 'Sobha Limited',
        'STAR': 'Strides Pharma Science Limited',
        'SUNTV': 'Sun TV Network Limited',
        'SUNDARMFIN': 'Sundaram Finance Limited',
        'SUNDRMFAST': 'Sundram Fasteners Limited',
        'SUZLON': 'Suzlon Energy Limited',
        'SYNGENE': 'Syngene International Limited',
        'TATACHEM': 'Tata Chemicals Limited',
        'TATACOMM': 'Tata Communications Limited',
        'TATAELXSI': 'Tata Elxsi Limited',
        'TATAINVEST': 'Tata Investment Corporation Limited',
        'TATAPOWER': 'Tata Power Company Limited',
        'TEAMLEASE': 'TeamLease Services Limited',
        'THERMAX': 'Thermax Limited',
        'THYROCARE': 'Thyrocare Technologies Limited',
        'TIINDIA': 'Tube Investments of India Limited',
        'TIMKEN': 'Timken India Limited',
        'TRIDENT': 'Trident Limited',
        'TTKPRESTIG': 'TTK Prestige Limited',
        'UJJIVAN': 'Ujjivan Financial Services Limited',
        'UNOMINDA': 'Uno Minda Limited',
        'VARROC': 'Varroc Engineering Limited',
        'VBL': 'Varun Beverages Limited',
        'VINATIORGA': 'Vinati Organics Limited',
        'VIPIND': 'VIP Industries Limited',
        'WESTLIFE': 'Westlife Development Limited',
        'YESBANK': 'Yes Bank Limited',
        'ZENSARTECH': 'Zensar Technologies Limited',
        'ZYDUSLIFE': 'Zydus Lifesciences Limited',
        
        # Additional Banking & Financial Services
        'BANKBARODA': 'Bank of Baroda',
        'UNIONBANK': 'Union Bank of India',
        'INDIANB': 'Indian Bank',
        'CENTRALBK': 'Central Bank of India',
        'BANKOFIND': 'Bank of India',
        'JKBANK': 'Jammu & Kashmir Bank Limited',
        'KARB': 'Karnataka Bank Limited',
        'SOUTHBANK': 'South Indian Bank Limited',
        'TMVBANK': 'TMB Bank Limited',
        
        # Technology & IT Services
        'CYIENT': 'Cyient Limited',
        'COFORGE': 'Coforge Limited',
        'FSL': 'Firstsource Solutions Limited',
        'HEXAWARE': 'Hexaware Technologies Limited',
        'KPITTECH': 'KPIT Technologies Limited',
        'SONATSOFTW': 'Sonata Software Limited',
        'ZENSAR': 'Zensar Technologies Limited',
        
        # Pharmaceuticals & Healthcare
        'GLENMARK': 'Glenmark Pharmaceuticals Limited',
        'JBCHEPHARM': 'JB Chemicals & Pharmaceuticals Limited',
        'LAURUS': 'Laurus Labs Limited',
        'NATCOPHARM': 'Natco Pharma Limited',
        'REDINGTON': 'Redington (India) Limited',
        'WOCKPHARMA': 'Wockhardt Limited',
    }


@login_required
def search_stocks(request):
    """Enhanced API endpoint for comprehensive NSE stock search including NIFTY 500 and all indices"""
    try:
        query = request.GET.get('q', '').strip().upper()
        
        if len(query) < 1:
            return JsonResponse({'stocks': []})
        
        # Check cache first (3-minute cache for better performance)
        cache_key = f'stock_search_v3_{query}'
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({'stocks': cached_result})
        
        stocks = []
        nifty_500_stocks = get_nifty_500_stocks()
        nse_indices = get_comprehensive_nse_indices()
        
        # Priority 1: Check for exact index matches
        index_matches = []
        for index_name, symbol in nse_indices.items():
            if query == index_name or query in index_name.split():
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    current_data = ticker.history(period="1d")
                    
                    if not current_data.empty:
                        last_price = current_data['Close'].iloc[-1]
                        prev_close = info.get('previousClose', last_price)
                        
                        if prev_close and prev_close > 0:
                            change_amount = last_price - prev_close
                            change_percent = (change_amount / prev_close) * 100
                        else:
                            change_amount = 0
                            change_percent = 0
                        
                        index_matches.append({
                            'symbol': index_name,
                            'company_name': f'{index_name} Index',
                            'last_price': round(float(last_price), 2),
                            'change': round(float(change_percent), 2),
                            'change_amount': round(float(change_amount), 2),
                            'volume': info.get('volume', 0),
                            'market_cap': 0,  # Not applicable for indices
                            'type': 'index',
                            'priority': 1
                        })
                except Exception:
                    continue
        
        # Priority 2: Search in NIFTY 500 stocks
        stock_matches = []
        
        # Exact symbol matches first
        if query in nifty_500_stocks:
            stock_matches.append((query, nifty_500_stocks[query], 1))
        
        # Partial symbol matches
        for symbol, company_name in nifty_500_stocks.items():
            if query != symbol and query in symbol:
                stock_matches.append((symbol, company_name, 2))
                if len(stock_matches) >= 20:
                    break
        
        # Company name matches
        if len(stock_matches) < 20:
            for symbol, company_name in nifty_500_stocks.items():
                if query in company_name.upper() and (symbol, company_name, 2) not in [(s[0], s[1], s[2]) for s in stock_matches]:
                    stock_matches.append((symbol, company_name, 3))
                    if len(stock_matches) >= 20:
                        break
        
        # Fetch real-time data for stocks (limit to 12 to prevent timeout)
        stock_results = []
        for symbol, company_name, priority in stock_matches[:12]:
            try:
                ticker = yf.Ticker(f"{symbol}.NS")
                info = ticker.info
                current_data = ticker.history(period="1d")
                
                if not current_data.empty:
                    last_price = current_data['Close'].iloc[-1]
                    prev_close = info.get('previousClose')
                    
                    # Better handling of previous close
                    if not prev_close or prev_close == 0:
                        if len(current_data) > 1:
                            prev_close = current_data['Close'].iloc[-2]
                        else:
                            prev_close = current_data['Open'].iloc[-1]
                    
                    if prev_close and prev_close > 0:
                        change_amount = last_price - prev_close
                        change_percent = (change_amount / prev_close) * 100
                    else:
                        change_amount = 0
                        change_percent = 0
                    
                    volume = info.get('volume', 0)
                    if not volume and not current_data['Volume'].empty:
                        volume = current_data['Volume'].iloc[-1]
                    
                    stock_results.append({
                        'symbol': symbol,
                        'company_name': company_name,
                        'last_price': round(float(last_price), 2),
                        'change': round(float(change_percent), 2),
                        'change_amount': round(float(change_amount), 2),
                        'volume': int(volume) if volume else 0,
                        'market_cap': info.get('marketCap', 0),
                        'type': 'stock',
                        'priority': priority
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to get data for {symbol}: {str(e)}")
                # Still include the stock with basic info
                stock_results.append({
                    'symbol': symbol,
                    'company_name': company_name,
                    'last_price': 0.00,
                    'change': 0.00,
                    'change_amount': 0.00,
                    'volume': 0,
                    'market_cap': 0,
                    'type': 'stock',
                    'priority': priority,
                    'note': 'Price data temporarily unavailable'
                })
                continue
        
        # Combine and sort results
        all_results = index_matches + stock_results
        
        # Sort by priority, then by relevance
        def sort_key(item):
            priority = item.get('priority', 5)
            symbol = item['symbol']
            if symbol == query:
                return (0, symbol)  # Exact match first
            elif symbol.startswith(query):
                return (1, symbol)  # Starts with query
            else:
                return (priority, symbol)  # By priority then alphabetically
        
        all_results.sort(key=sort_key)
        
        # Limit results and add fallback if needed
        stocks = all_results[:15]
        
        # If no results found, try direct yfinance search
        if not stocks:
            direct_patterns = [f"{query}.NS", f"{query}.BO", query]
            for pattern in direct_patterns:
                try:
                    ticker = yf.Ticker(pattern)
                    info = ticker.info
                    current_data = ticker.history(period="1d")
                    
                    if not current_data.empty and info:
                        last_price = current_data['Close'].iloc[-1]
                        prev_close = info.get('previousClose', last_price)
                        
                        if prev_close and prev_close > 0:
                            change_amount = last_price - prev_close
                            change_percent = (change_amount / prev_close) * 100
                        else:
                            change_amount = 0
                            change_percent = 0
                        
                        stocks.append({
                            'symbol': query,
                            'company_name': info.get('longName') or info.get('shortName', query),
                            'last_price': round(float(last_price), 2),
                            'change': round(float(change_percent), 2),
                            'change_amount': round(float(change_amount), 2),
                            'volume': info.get('volume', 0),
                            'market_cap': info.get('marketCap', 0),
                            'type': 'stock',
                            'note': 'Direct search result'
                        })
                        break
                except Exception:
                    continue
        
        # Cache results for 3 minutes
        if stocks:
            cache.set(cache_key, stocks, 180)
        
        return JsonResponse({
            'stocks': stocks,
            'total_found': len(stocks),
            'query': query,
            'data_source': 'NIFTY 500 + NSE Indices',
            'indices_available': len(nse_indices),
            'stocks_database_size': len(nifty_500_stocks)
        })
        
    except Exception as e:
        logger.error(f"Enhanced stock search error: {str(e)}")
        
        # Comprehensive fallback data
        fallback_stocks = [
            {'symbol': 'NIFTY', 'company_name': 'NIFTY 50 Index', 'last_price': 24500.00, 'change': 0.75, 'type': 'index'},
            {'symbol': 'BANKNIFTY', 'company_name': 'Bank NIFTY Index', 'last_price': 52000.00, 'change': -0.45, 'type': 'index'},
            {'symbol': 'SENSEX', 'company_name': 'BSE SENSEX', 'last_price': 80500.00, 'change': 0.25, 'type': 'index'},
            {'symbol': 'RELIANCE', 'company_name': 'Reliance Industries Limited', 'last_price': 2450.00, 'change': -0.85, 'type': 'stock'},
            {'symbol': 'TCS', 'company_name': 'Tata Consultancy Services Limited', 'last_price': 3850.00, 'change': 1.25, 'type': 'stock'},
            {'symbol': 'HDFCBANK', 'company_name': 'HDFC Bank Limited', 'last_price': 1620.00, 'change': 0.45, 'type': 'stock'},
            {'symbol': 'INFY', 'company_name': 'Infosys Limited', 'last_price': 1425.00, 'change': 2.10, 'type': 'stock'},
            {'symbol': 'ICICIBANK', 'company_name': 'ICICI Bank Limited', 'last_price': 950.00, 'change': -1.20, 'type': 'stock'},
            {'symbol': 'ADANIENT', 'company_name': 'Adani Enterprises Limited', 'last_price': 3200.00, 'change': 3.45, 'type': 'stock'},
            {'symbol': 'BHARTIARTL', 'company_name': 'Bharti Airtel Limited', 'last_price': 1050.00, 'change': 1.80, 'type': 'stock'},
        ]
        
        filtered = [s for s in fallback_stocks if query in s['symbol'] or query in s['company_name'].upper()]
        return JsonResponse({
            'stocks': filtered,
            'total_found': len(filtered),
            'query': query,
            'error': 'Using fallback data due to API issues',
            'note': 'Real-time data temporarily unavailable'
        })


# ============ Payment Views (Razorpay) ============

@login_required
def create_order(request):
    """Create Razorpay order for payment"""
    # Uncomment when Razorpay is configured
    """
    if request.method == 'POST':
        try:
            amount = 499  # ₹499
            amount_in_paise = amount * 100
            
            order_data = {
                'amount': amount_in_paise,
                'currency': 'INR',
                'payment_capture': 1,
                'notes': {
                    'user_id': str(request.user.id),
                    'user_email': request.user.email,
                }
            }
            
            razorpay_order = razorpay_client.order.create(data=order_data)
            request.session['razorpay_order_id'] = razorpay_order['id']
            
            context = {
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'razorpay_order_id': razorpay_order['id'],
                'amount': amount,
                'amount_paise': amount_in_paise,
                'currency': 'INR',
                'user_email': request.user.email,
                'user_name': request.user.username,
            }
            
            return render(request, 'payment/checkout.html', context)
            
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
            return redirect('dashboard')
    """
    return render(request, 'payment/upgrade.html')


@login_required
def payment_success(request):
    """Display payment success page"""
    return render(request, 'payment/success.html')


@login_required
def payment_failed(request):
    """Display payment failed page"""
    return render(request, 'payment/failed.html')

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
import requests
from datetime import datetime, timedelta

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


# ============ Enhanced Stock Search API with Real-time Data ============

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
        
        # Additional popular stocks
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
        'MFSL': 'Max Financial Services Limited',
        'MPHASIS': 'Mphasis Limited',
        'MRF': 'MRF Limited',
        'NAUKRI': 'Info Edge (India) Limited',
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
    }


def get_real_time_stock_data(symbol, symbol_type='stock'):
    """
    Get real-time stock/index data using multiple fallback methods
    """
    try:
        # Determine the correct symbol format
        if symbol_type == 'index':
            # Index symbols are already in correct format
            yf_symbol = symbol
        else:
            # Stock symbols need .NS suffix
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                yf_symbol = f"{symbol}.NS"
            else:
                yf_symbol = symbol
        
        # Method 1: Try yfinance
        ticker = yf.Ticker(yf_symbol)
        
        # Get basic info first
        try:
            info = ticker.info
            if not info or 'regularMarketPrice' not in info:
                # Try getting history if info is incomplete
                hist = ticker.history(period="2d", interval="1d")
                if hist.empty:
                    raise Exception("No history data available")
        except:
            # Fallback to history only
            hist = ticker.history(period="2d", interval="1d")
            if hist.empty:
                raise Exception("No data available from yfinance")
            info = {}
        
        # Get current data
        if 'regularMarketPrice' in info and info['regularMarketPrice']:
            # Use info data if available
            current_price = float(info['regularMarketPrice'])
            prev_close = float(info.get('previousClose', current_price))
            volume = int(info.get('volume', 0))
            market_cap = info.get('marketCap', 0)
            company_name = info.get('longName') or info.get('shortName', symbol)
        else:
            # Use history data
            hist = ticker.history(period="2d", interval="1d")
            if hist.empty:
                raise Exception("No recent data available")
            
            current_price = float(hist['Close'].iloc[-1])
            if len(hist) > 1:
                prev_close = float(hist['Close'].iloc[-2])
            else:
                prev_close = float(hist['Open'].iloc[-1])
            
            volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0
            market_cap = 0
            company_name = symbol
        
        # Calculate change
        change_amount = current_price - prev_close
        change_percent = (change_amount / prev_close * 100) if prev_close != 0 else 0
        
        result = {
            'symbol': symbol.replace('.NS', '').replace('.BO', ''),
            'company_name': company_name,
            'last_price': round(current_price, 2),
            'change': round(change_percent, 2),
            'change_amount': round(change_amount, 2),
            'volume': volume,
            'market_cap': market_cap,
            'success': True,
            'data_source': 'yfinance',
            'type': symbol_type
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Real-time data fetch failed for {symbol}: {str(e)}")
        
        # Method 2: Try database fallback for stocks
        if symbol_type == 'stock':
            try:
                clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
                stock_data = StockData.objects.filter(symbol=clean_symbol).first()
                
                if stock_data:
                    return {
                        'symbol': clean_symbol,
                        'company_name': stock_data.company_name,
                        'last_price': float(stock_data.last_price),
                        'change': float(stock_data.pchange),
                        'change_amount': float(stock_data.change),
                        'volume': stock_data.volume,
                        'market_cap': stock_data.market_cap or 0,
                        'success': True,
                        'data_source': 'database_cache',
                        'type': 'stock',
                        'note': 'Using cached data'
                    }
            except Exception as db_e:
                logger.error(f"Database fallback failed for {symbol}: {str(db_e)}")
        
        # Method 3: Return error response
        return {
            'symbol': symbol.replace('.NS', '').replace('.BO', ''),
            'success': False,
            'error': f'Unable to fetch data: {str(e)}',
            'type': symbol_type
        }


@login_required
def search_stocks(request):
    """Enhanced API endpoint for comprehensive NSE stock search with real-time data"""
    try:
        query = request.GET.get('q', '').strip().upper()
        
        if len(query) < 1:
            return JsonResponse({'stocks': []})
        
        # Check cache first (2-minute cache for real-time data)
        cache_key = f'stock_search_realtime_{query}'
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Serving cached result for query: {query}")
            return JsonResponse({
                'stocks': cached_result,
                'cached': True,
                'query': query
            })
        
        stocks = []
        nifty_500_stocks = get_nifty_500_stocks()
        nse_indices = get_comprehensive_nse_indices()
        
        # Priority 1: Check for exact index matches
        index_matches = []
        for index_name, yf_symbol in nse_indices.items():
            if query == index_name or (len(query) >= 3 and query in index_name):
                try:
                    real_time_data = get_real_time_stock_data(yf_symbol, 'index')
                    
                    if real_time_data.get('success'):
                        index_matches.append({
                            'symbol': index_name,
                            'company_name': f'{index_name} Index',
                            'last_price': real_time_data['last_price'],
                            'change': real_time_data['change'],
                            'change_amount': real_time_data['change_amount'],
                            'volume': real_time_data.get('volume', 0),
                            'market_cap': 0,  # Not applicable for indices
                            'type': 'index',
                            'priority': 1,
                            'data_source': real_time_data.get('data_source', 'unknown')
                        })
                except Exception as e:
                    logger.warning(f"Failed to get real-time data for index {index_name}: {str(e)}")
                    continue
                
                # Limit index results to prevent timeout
                if len(index_matches) >= 3:
                    break
        
        # Priority 2: Search in NIFTY 500 stocks
        stock_matches = []
        
        # Exact symbol matches first
        if query in nifty_500_stocks:
            stock_matches.append((query, nifty_500_stocks[query], 1))
        
        # Partial symbol matches
        for symbol, company_name in nifty_500_stocks.items():
            if query != symbol and query in symbol:
                stock_matches.append((symbol, company_name, 2))
                if len(stock_matches) >= 15:
                    break
        
        # Company name matches
        if len(stock_matches) < 15:
            for symbol, company_name in nifty_500_stocks.items():
                if query in company_name.upper() and not any(s[0] == symbol for s in stock_matches):
                    stock_matches.append((symbol, company_name, 3))
                    if len(stock_matches) >= 15:
                        break
        
        # Fetch real-time data for stocks (limit to 10 to prevent timeout)
        stock_results = []
        for symbol, company_name, priority in stock_matches[:10]:
            try:
                real_time_data = get_real_time_stock_data(symbol, 'stock')
                
                if real_time_data.get('success'):
                    stock_results.append({
                        'symbol': symbol,
                        'company_name': company_name,
                        'last_price': real_time_data['last_price'],
                        'change': real_time_data['change'],
                        'change_amount': real_time_data['change_amount'],
                        'volume': real_time_data.get('volume', 0),
                        'market_cap': real_time_data.get('market_cap', 0),
                        'type': 'stock',
                        'priority': priority,
                        'data_source': real_time_data.get('data_source', 'unknown'),
                        'note': real_time_data.get('note', '')
                    })
                else:
                    # Include stock with error info
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
                        'error': real_time_data.get('error', 'Data unavailable'),
                        'data_source': 'error'
                    })
                    
            except Exception as e:
                logger.error(f"Error processing stock {symbol}: {str(e)}")
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
        
        # Limit results
        stocks = all_results[:12]
        
        # If no results found, try direct yfinance search
        if not stocks:
            logger.info(f"No matches found, trying direct search for: {query}")
            direct_patterns = [f"{query}.NS", f"{query}.BO", query]
            for pattern in direct_patterns:
                try:
                    real_time_data = get_real_time_stock_data(pattern, 'stock')
                    
                    if real_time_data.get('success'):
                        stocks.append({
                            'symbol': query,
                            'company_name': real_time_data.get('company_name', query),
                            'last_price': real_time_data['last_price'],
                            'change': real_time_data['change'],
                            'change_amount': real_time_data['change_amount'],
                            'volume': real_time_data.get('volume', 0),
                            'market_cap': real_time_data.get('market_cap', 0),
                            'type': 'stock',
                            'note': 'Direct search result',
                            'data_source': real_time_data.get('data_source', 'direct')
                        })
                        break
                except Exception as e:
                    logger.error(f"Direct search failed for {pattern}: {str(e)}")
                    continue
        
        # Cache results for 2 minutes (real-time data)
        if stocks:
            cache.set(cache_key, stocks, 120)  # 2 minutes cache
            logger.info(f"Cached {len(stocks)} results for query: {query}")
        
        return JsonResponse({
            'stocks': stocks,
            'total_found': len(stocks),
            'query': query,
            'data_source': 'Real-time + NIFTY 500 + NSE Indices',
            'indices_available': len(nse_indices),
            'stocks_database_size': len(nifty_500_stocks),
            'cache_duration': '2 minutes',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Enhanced stock search error for query '{query}': {str(e)}")
        
        # Comprehensive fallback data with realistic prices
        fallback_stocks = [
            {
                'symbol': 'NIFTY',
                'company_name': 'NIFTY 50 Index',
                'last_price': 24500.00,
                'change': 0.75,
                'change_amount': 183.50,
                'volume': 0,
                'market_cap': 0,
                'type': 'index',
                'data_source': 'fallback'
            },
            {
                'symbol': 'BANKNIFTY',
                'company_name': 'Bank NIFTY Index',
                'last_price': 52000.00,
                'change': -0.45,
                'change_amount': -234.00,
                'volume': 0,
                'market_cap': 0,
                'type': 'index',
                'data_source': 'fallback'
            },
            {
                'symbol': 'SENSEX',
                'company_name': 'BSE SENSEX',
                'last_price': 80500.00,
                'change': 0.25,
                'change_amount': 201.25,
                'volume': 0,
                'market_cap': 0,
                'type': 'index',
                'data_source': 'fallback'
            },
            {
                'symbol': 'RELIANCE',
                'company_name': 'Reliance Industries Limited',
                'last_price': 2450.00,
                'change': -0.85,
                'change_amount': -21.00,
                'volume': 15234567,
                'market_cap': 16500000000000,
                'type': 'stock',
                'data_source': 'fallback'
            },
            {
                'symbol': 'TCS',
                'company_name': 'Tata Consultancy Services Limited',
                'last_price': 3850.00,
                'change': 1.25,
                'change_amount': 47.50,
                'volume': 5432109,
                'market_cap': 14000000000000,
                'type': 'stock',
                'data_source': 'fallback'
            },
            {
                'symbol': 'HDFCBANK',
                'company_name': 'HDFC Bank Limited',
                'last_price': 1620.00,
                'change': 0.45,
                'change_amount': 7.25,
                'volume': 12345678,
                'market_cap': 12000000000000,
                'type': 'stock',
                'data_source': 'fallback'
            },
            {
                'symbol': 'INFY',
                'company_name': 'Infosys Limited',
                'last_price': 1425.00,
                'change': 2.10,
                'change_amount': 29.50,
                'volume': 8765432,
                'market_cap': 6000000000000,
                'type': 'stock',
                'data_source': 'fallback'
            },
            {
                'symbol': 'ICICIBANK',
                'company_name': 'ICICI Bank Limited',
                'last_price': 950.00,
                'change': -1.20,
                'change_amount': -11.50,
                'volume': 9876543,
                'market_cap': 6500000000000,
                'type': 'stock',
                'data_source': 'fallback'
            },
        ]
        
        # Filter fallback results based on query
        filtered = [
            s for s in fallback_stocks
            if query in s['symbol'] or query in s['company_name'].upper()
        ]
        
        return JsonResponse({
            'stocks': filtered,
            'total_found': len(filtered),
            'query': query,
            'error': 'Using fallback data due to API issues',
            'note': 'Real-time data temporarily unavailable',
            'data_source': 'fallback',
            'timestamp': timezone.now().isoformat()
        })


def update_stock_database():
    """
    Background task to update stock database periodically
    Call this from a Django management command or celery task
    """
    stock_list = get_nifty_500_stocks()
    updated_count = 0
    failed_count = 0
    
    logger.info(f"Starting database update for {len(stock_list)} stocks")
    
    for symbol, company_name in list(stock_list.items())[:50]:  # Limit to prevent timeout
        try:
            real_time_data = get_real_time_stock_data(symbol, 'stock')
            
            if real_time_data.get('success'):
                stock_obj, created = StockData.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        'company_name': company_name,
                        'last_price': real_time_data['last_price'],
                        'change': real_time_data['change_amount'],
                        'pchange': real_time_data['change'],
                        'volume': real_time_data.get('volume', 0),
                        'market_cap': real_time_data.get('market_cap'),
                        'is_active': True,
                    }
                )
                updated_count += 1
                
                if created:
                    logger.info(f"Created new stock entry: {symbol}")
                else:
                    logger.debug(f"Updated stock: {symbol}")
                    
            else:
                failed_count += 1
                logger.warning(f"Failed to get data for {symbol}: {real_time_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            failed_count += 1
            logger.error(f"Exception updating {symbol}: {str(e)}")
            continue
    
    logger.info(f"Database update completed. Updated: {updated_count}, Failed: {failed_count}")
    return {
        'updated': updated_count,
        'failed': failed_count,
        'total_attempted': updated_count + failed_count
    }


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

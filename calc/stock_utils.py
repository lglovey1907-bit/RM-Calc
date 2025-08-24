import yfinance as yf
import time
import requests
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RateLimitedStockFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.last_request_time = 0
        self.min_delay = 0.5  # 500ms between requests
        
    def _rate_limit(self):
        """Ensure minimum delay between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_stock_data(self, symbol, symbol_type='stock'):
        """Get stock data with caching and rate limiting"""
        # Check cache first (cache for 2 minutes)
        cache_key = f"stock_data_{symbol}_{symbol_type}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            logger.info(f"Returning cached data for {symbol}")
            return cached_data
        
        # Rate limit API calls
        self._rate_limit()
        
        try:
            # Format symbol for Yahoo Finance
            if symbol_type == 'index':
                yf_symbol = symbol
            else:
                if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                    yf_symbol = f"{symbol}.NS"
                else:
                    yf_symbol = symbol
            
            logger.info(f"Fetching live data for {yf_symbol}")
            
            ticker = yf.Ticker(yf_symbol, session=self.session)
            
            # Try multiple methods to get current price
            current_price = None
            prev_close = None
            volume = 0
            company_name = symbol.replace('.NS', '').replace('.BO', '')
            
            # Method 1: Try fast_info first
            try:
                fast_info = ticker.fast_info
                if hasattr(fast_info, 'last_price') and fast_info.last_price:
                    current_price = float(fast_info.last_price)
                    prev_close = float(fast_info.previous_close) if hasattr(fast_info, 'previous_close') else current_price
                    logger.info(f"Got price from fast_info: {current_price}")
            except Exception as e:
                logger.warning(f"fast_info failed for {symbol}: {e}")
            
            # Method 2: Try ticker.info
            if not current_price:
                try:
                    info = ticker.info
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if current_price:
                        current_price = float(current_price)
                        prev_close = float(info.get('previousClose', current_price))
                        company_name = info.get('longName', company_name)
                        volume = int(info.get('volume', 0))
                        logger.info(f"Got price from info: {current_price}")
                except Exception as e:
                    logger.warning(f"ticker.info failed for {symbol}: {e}")
            
            # Method 3: Try history as fallback
            if not current_price:
                try:
                    hist = ticker.history(period='2d', timeout=15)
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                        volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0
                        logger.info(f"Got price from history: {current_price}")
                except Exception as e:
                    logger.warning(f"history failed for {symbol}: {e}")
            
            if not current_price:
                raise Exception("No price data available from any method")
            
            # Calculate changes
            change_amount = current_price - prev_close if prev_close else 0
            change_percent = (change_amount / prev_close * 100) if prev_close and prev_close != 0 else 0
            
            result = {
                'symbol': symbol.replace('.NS', '').replace('.BO', ''),
                'company_name': company_name,
                'last_price': round(current_price, 2),
                'change': round(change_amount, 2),
                'change_percent': round(change_percent, 2),
                'volume': volume,
                'success': True,
                'data_source': 'yahoo_finance_live',
                'type': symbol_type,
                'timestamp': time.time()
            }
            
            # Cache successful result for 2 minutes
            cache.set(cache_key, result, 120)
            logger.info(f"Successfully fetched and cached data for {symbol}: ₹{current_price}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {str(e)}")
            
            # Return error result instead of mock data
            return {
                'symbol': symbol.replace('.NS', '').replace('.BO', ''),
                'company_name': f"{symbol} Limited",
                'last_price': 0.00,
                'change': 0.00,
                'change_percent': 0.00,
                'volume': 0,
                'success': False,
                'error': str(e),
                'data_source': 'api_error',
                'type': symbol_type
            }

# Global instance
stock_fetcher = RateLimitedStockFetcher()

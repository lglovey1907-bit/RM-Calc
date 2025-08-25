import time
import requests
import os
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class RateLimitedStockFetcher:
    def __init__(self):
        self.api_key = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_delay = 12.0  # 12 seconds between requests (5 per minute limit)
        
    def _rate_limit(self):
        """Enforce Alpha Vantage rate limit of 5 calls per minute"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_stock_data(self, symbol, symbol_type="stock"):
        """Get stock data from Alpha Vantage API"""
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()
        
        # Check cache first (cache for 15 minutes to reduce API calls)
        cache_key = f"av_stock_{clean_symbol}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Rate limit API calls
        self._rate_limit()
        
        try:
            # Alpha Vantage uses different suffixes for Indian stocks
            # Try both .BSE and .NS formats
            symbols_to_try = [
                f"{clean_symbol}.BSE",  # Bombay Stock Exchange
                f"{clean_symbol}.NSE",  # National Stock Exchange
                clean_symbol  # Sometimes works without suffix
            ]
            
            for av_symbol in symbols_to_try:
                params = {
                    'function': 'GLOBAL_QUOTE',
                    'symbol': av_symbol,
                    'apikey': self.api_key
                }
                
                response = self.session.get(self.base_url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle API limit exceeded
                    if "Note" in data:
                        logger.warning("Alpha Vantage API limit exceeded")
                        break
                    
                    quote = data.get("Global Quote", {})
                    
                    if quote and quote.get("05. price"):
                        price = float(quote.get("05. price", 0))
                        change = float(quote.get("09. change", 0))
                        change_percent_str = quote.get("10. change percent", "0%")
                        change_percent = float(change_percent_str.replace("%", ""))
                        
                        result = {
                            "symbol": clean_symbol,
                            "company_name": f"{clean_symbol} Limited",
                            "last_price": round(price, 2),
                            "change": round(change, 2),
                            "change_percent": round(change_percent, 2),
                            "volume": int(quote.get("06. volume", 0)),
                            "success": True,
                            "data_source": "alpha_vantage_live",
                            "type": symbol_type,
                            "av_symbol": av_symbol
                        }
                        
                        # Cache successful result for 15 minutes
                        cache.set(cache_key, result, 900)
                        logger.info(f"Alpha Vantage: {clean_symbol} = ₹{price}")
                        return result
            
            # If Alpha Vantage fails, fall back to realistic estimates
            return self._get_fallback_data(clean_symbol, symbol_type)
            
        except Exception as e:
            logger.error(f"Alpha Vantage error for {clean_symbol}: {str(e)}")
            return self._get_fallback_data(clean_symbol, symbol_type)
    
    def _get_fallback_data(self, clean_symbol, symbol_type):
        """Fallback to realistic price estimates"""
        mock_prices = {
            "RELIANCE": 2445.50, "TCS": 3842.75, "HDFCBANK": 1615.30, "INFY": 1420.85,
            "ICICIBANK": 948.60, "HINDUNILVR": 2655.40, "BHARTIARTL": 885.25,
            "ITC": 412.80, "SBIN": 718.45, "BAJFINANCE": 7195.30, "ASIANPAINT": 3198.75
        }
        
        base_price = mock_prices.get(clean_symbol, 150.00)
        
        result = {
            "symbol": clean_symbol,
            "company_name": f"{clean_symbol} Limited",
            "last_price": base_price,
            "change": 0.00,
            "change_percent": 0.00,
            "volume": 0,
            "success": True,
            "data_source": "fallback_estimate",
            "type": symbol_type,
            "note": "API limit reached - using estimates"
        }
        
        # Cache fallback data for 5 minutes
        cache.set(f"av_stock_{clean_symbol}", result, 300)
        return result

stock_fetcher = RateLimitedStockFetcher()

import requests
import json
import time
from datetime import datetime
import random

class NSELiveFetcher:
    def __init__(self):
        self.base_url = "https://www.nseindia.com/api"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.nseindia.com/',
        }
        self.session.headers.update(self.headers)
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize session by visiting NSE homepage"""
        try:
            response = self.session.get('https://www.nseindia.com', timeout=10)
            print(f"Session initialized: {response.status_code}")
        except Exception as e:
            print(f"Session initialization failed: {e}")
    
    def get_all_symbols(self):
        """Get all NSE symbols from equity list"""
        try:
            url = f"{self.base_url}/equity-stockIndices?index=NIFTY%20500"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                symbols = [stock['symbol'] for stock in data.get('data', [])]
                print(f"Found {len(symbols)} symbols from NIFTY 500")
                return symbols
            else:
                print(f"Failed to get symbols: {response.status_code}")
                return self._get_fallback_symbols()
                
        except Exception as e:
            print(f"Error getting symbols: {e}")
            return self._get_fallback_symbols()
    
    def _get_fallback_symbols(self):
        """Fallback list of popular NSE stocks"""
        return [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 'ICICIBANK',
            'KOTAKBANK', 'BHARTIARTL', 'ITC', 'SBIN', 'BAJFINANCE', 'ASIANPAINT',
            'MARUTI', 'HCLTECH', 'WIPRO', 'ADANIPORTS', 'APOLLOHOSP', 'AXISBANK',
            'BAJAJ-AUTO', 'BAJAJFINSV', 'BPCL', 'BRITANNIA', 'CIPLA', 'COALINDIA',
            'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM', 'HEROMOTOCO', 'HINDALCO',
            'HDFC', 'INDUSINDBK', 'IOC', 'JSWSTEEL', 'M&M', 'NESTLEIND', 'NTPC',
            'ONGC', 'POWERGRID', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 'TECHM',
            'TITAN', 'ULTRACEMCO', 'UPL', 'LT', 'ADANIENT', 'ADANIGREEN',
            'AMBUJACEM', 'APOLLOTYRE', 'ASHOKLEY', 'AUROPHARMA', 'BANKINDIA',
            'BERGEPAINT', 'BIOCON', 'BOSCHLTD', 'CADILAHC', 'CANBK', 'CHAMBLFERT',
            'COLPAL', 'CONCOR', 'CUMMINSIND', 'DABUR', 'DALBHARAT', 'DEEPAKNTR',
            'DELTACORP', 'DLF', 'FEDERALBNK', 'GAIL', 'GLENMARK', 'GMRINFRA',
            'GODREJCP', 'GODREJPROP', 'HATHWAY', 'HAVELLS', 'HDFCLIFE', 'HINDZINC',
            'IBULHSGFIN', 'IDEA', 'IDFCFIRSTB', 'IGL', 'INDIANB', 'INDIGO',
            'INFRATEL', 'JINDALSTEL', 'JSWENERGY', 'JUBLFOOD', 'JUSTDIAL',
            'LICHSGFIN', 'LUPIN', 'MARICO', 'MCDOWELL-N', 'MFSL', 'MGL',
            'MINDTREE', 'MOTHERSUMI', 'MRF', 'MUTHOOTFIN', 'NATIONALUM',
            'NAUKRI', 'NMDC', 'OFSS', 'OIL', 'PAGEIND', 'PEL', 'PETRONET',
            'PFC', 'PIDILITIND', 'PNB', 'POLYCAB', 'PVR', 'RAMCOCEM',
            'RBLBANK', 'RECLTD', 'SAIL', 'SHREECEM', 'SIEMENS', 'SRF',
            'STAR', 'SUNTV', 'TATACOMM', 'TATACONSUM', 'TATAPOWER', 'TORNTPHARM',
            'TORNTPOWER', 'TRENT', 'TVSMOTOR', 'UBL', 'UNIONBANK', 'VEDL',
            'VOLTAS', 'WHIRLPOOL', 'YESBANK', 'ZEEL'
        ]
    
    def get_stock_data(self, symbol):
        """Get individual stock data"""
        try:
            url = f"{self.base_url}/quote-equity?symbol={symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'company_name': data.get('companyName', symbol),
                    'last_price': float(data.get('lastPrice', 0)),
                    'change': float(data.get('change', 0)),
                    'pchange': float(data.get('pChange', 0)),
                    'volume': int(data.get('totalTradedVolume', 0)),
                    'market_cap': data.get('marketCap', 0),
                }
            else:
                print(f"Failed to get data for {symbol}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting data for {symbol}: {e}")
            return None
    
    def fetch_all_stocks(self, max_stocks=200):
        """Fetch data for multiple stocks"""
        symbols = self.get_all_symbols()[:max_stocks]
        stocks = []
        
        print(f"Fetching data for {len(symbols)} stocks...")
        
        for i, symbol in enumerate(symbols):
            try:
                stock_data = self.get_stock_data(symbol)
                if stock_data:
                    stocks.append(stock_data)
                    print(f"[{i+1}/{len(symbols)}] Fetched: {symbol} - ₹{stock_data['last_price']:.2f}")
                
                time.sleep(random.uniform(0.1, 0.3))
                
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                continue
        
        print(f"Successfully fetched {len(stocks)} stocks")
        return stocks

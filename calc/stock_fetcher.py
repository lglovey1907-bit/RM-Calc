import requests
import json
from datetime import datetime
import time

class NSEStockDataFetcher:
    """
    NSE Stock Data Fetcher with fallback mechanisms
    """
    
    def __init__(self):
        self.base_url = "https://www.nseindia.com/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def get_all_stocks(self):
        """Fetch all NSE stocks with current prices"""
        try:
            return self.get_nse_data()
        except Exception as e:
            print(f"NSE API failed: {e}")
            return self.get_fallback_data()
    
    def get_nse_data(self):
        """Try to fetch from NSE API"""
        try:
            url = f"{self.base_url}/equity-stockIndices?index=NIFTY%20500"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                stocks = data.get('data', [])
                
                stock_list = []
                for stock in stocks:
                    stock_info = {
                        'symbol': stock.get('symbol', ''),
                        'company_name': stock.get('companyName', ''),
                        'last_price': float(stock.get('lastPrice', 0)),
                        'change': float(stock.get('change', 0)),
                        'pchange': float(stock.get('pChange', 0)),
                        'volume': int(stock.get('totalTradedVolume', 0)),
                        'market_cap': stock.get('marketCap', 0),
                    }
                    stock_list.append(stock_info)
                
                return stock_list
            else:
                raise Exception(f"NSE API returned status {response.status_code}")
                
        except Exception as e:
            raise Exception(f"NSE data fetch failed: {e}")
    
    def get_fallback_data(self):
        """Fallback to static data"""
        print("Using fallback static data...")
        return [
            {
                'symbol': 'RELIANCE',
                'company_name': 'Reliance Industries Ltd',
                'last_price': 2450.50,
                'change': 25.30,
                'pchange': 1.04,
                'volume': 1500000,
                'market_cap': 1658000000000
            },
            {
                'symbol': 'TCS',
                'company_name': 'Tata Consultancy Services Ltd',
                'last_price': 3850.75,
                'change': -15.25,
                'pchange': -0.39,
                'volume': 800000,
                'market_cap': 1400000000000
            },
            {
                'symbol': 'HDFCBANK',
                'company_name': 'HDFC Bank Ltd',
                'last_price': 1678.90,
                'change': 12.45,
                'pchange': 0.75,
                'volume': 2000000,
                'market_cap': 950000000000
            },
            {
                'symbol': 'INFY',
                'company_name': 'Infosys Ltd',
                'last_price': 1567.25,
                'change': 8.75,
                'pchange': 0.56,
                'volume': 1200000,
                'market_cap': 650000000000
            },
            {
                'symbol': 'ICICIBANK',
                'company_name': 'ICICI Bank Ltd',
                'last_price': 945.60,
                'change': -5.40,
                'pchange': -0.57,
                'volume': 1800000,
                'market_cap': 660000000000
            },
            {
                'symbol': 'BHARTIARTL',
                'company_name': 'Bharti Airtel Ltd',
                'last_price': 1234.80,
                'change': 18.90,
                'pchange': 1.55,
                'volume': 900000,
                'market_cap': 680000000000
            },
            {
                'symbol': 'ITC',
                'company_name': 'ITC Ltd',
                'last_price': 456.25,
                'change': -2.15,
                'pchange': -0.47,
                'volume': 2500000,
                'market_cap': 570000000000
            },
            {
                'symbol': 'KOTAKBANK',
                'company_name': 'Kotak Mahindra Bank Ltd',
                'last_price': 1789.40,
                'change': 23.60,
                'pchange': 1.34,
                'volume': 700000,
                'market_cap': 355000000000
            },
            {
                'symbol': 'LT',
                'company_name': 'Larsen & Toubro Ltd',
                'last_price': 3456.70,
                'change': 45.80,
                'pchange': 1.34,
                'volume': 400000,
                'market_cap': 485000000000
            },
            {
                'symbol': 'SBIN',
                'company_name': 'State Bank of India',
                'last_price': 678.95,
                'change': -8.25,
                'pchange': -1.20,
                'volume': 3000000,
                'market_cap': 605000000000
            },
            {
                'symbol': 'WIPRO',
                'company_name': 'Wipro Ltd',
                'last_price': 567.80,
                'change': 12.30,
                'pchange': 2.22,
                'volume': 1100000,
                'market_cap': 310000000000
            },
            {
                'symbol': 'HCLTECH',
                'company_name': 'HCL Technologies Ltd',
                'last_price': 1456.25,
                'change': 19.50,
                'pchange': 1.36,
                'volume': 650000,
                'market_cap': 395000000000
            },
            {
                'symbol': 'MARUTI',
                'company_name': 'Maruti Suzuki India Ltd',
                'last_price': 11234.50,
                'change': 125.75,
                'pchange': 1.13,
                'volume': 200000,
                'market_cap': 340000000000
            },
            {
                'symbol': 'ASIANPAINT',
                'company_name': 'Asian Paints Ltd',
                'last_price': 3245.60,
                'change': -18.40,
                'pchange': -0.56,
                'volume': 300000,
                'market_cap': 311000000000
            },
            {
                'symbol': 'BAJFINANCE',
                'company_name': 'Bajaj Finance Ltd',
                'last_price': 6789.30,
                'change': 89.70,
                'pchange': 1.34,
                'volume': 180000,
                'market_cap': 419000000000
            }
        ]
    
    def get_stock_quote(self, symbol):
        """Get detailed quote for a specific stock"""
        try:
            url = f"{self.base_url}/quote-equity?symbol={symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'last_price': float(data.get('lastPrice', 0)),
                    'open': float(data.get('open', 0)),
                    'high': float(data.get('dayHigh', 0)),
                    'low': float(data.get('dayLow', 0)),
                    'volume': int(data.get('totalTradedVolume', 0)),
                    'timestamp': datetime.now()
                }
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return None

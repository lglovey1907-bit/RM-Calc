import yfinance as yf
import pandas as pd
import time
from decimal import Decimal
from datetime import datetime
import requests

class YahooNSEFetcher:
    def __init__(self):
        # NSE symbols need .NS suffix for Yahoo Finance
        self.nse_symbols = self._get_comprehensive_nse_list()
    
    def _get_comprehensive_nse_list(self):
        """Get comprehensive list of NSE stocks with .NS suffix"""
        # Major NSE stocks - you can expand this list
        symbols = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 'ICICIBANK',
            'KOTAKBANK', 'BHARTIARTL', 'ITC', 'SBIN', 'BAJFINANCE', 'ASIANPAINT',
            'MARUTI', 'HCLTECH', 'WIPRO', 'ADANIPORTS', 'APOLLOHOSP', 'AXISBANK',
            'BAJAJ-AUTO', 'BAJAJFINSV', 'BPCL', 'BRITANNIA', 'CIPLA', 'COALINDIA',
            'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM', 'HEROMOTOCO', 'HINDALCO',
            'HDFC', 'INDUSINDBK', 'IOC', 'JSWSTEEL', 'M&M', 'NESTLEIND', 'NTPC',
            'ONGC', 'POWERGRID', 'SUNPHARMA', 'TATAMOTORS', 'TATASTEEL', 'TECHM',
            'TITAN', 'ULTRACEMCO', 'UPL', 'LT', 'ADANIENT', 'ADANIGREEN',
            'AMBUJACEM', 'APOLLOTYRE', 'ASHOKLEY', 'AUROPHARMA', 'BANKINDIA',
            'BERGEPAINT', 'BIOCON', 'BOSCHLTD', 'CANBK', 'COLPAL', 'CONCOR',
            'CUMMINSIND', 'DABUR', 'DALBHARAT', 'DLF', 'FEDERALBNK', 'GAIL',
            'GLENMARK', 'GODREJCP', 'HAVELLS', 'HDFCLIFE', 'HINDZINC', 'IBULHSGFIN',
            'IDEA', 'IDFCFIRSTB', 'IGL', 'INDIANB', 'INDIGO', 'JINDALSTEL',
            'JSWENERGY', 'JUBLFOOD', 'LICHSGFIN', 'LUPIN', 'MARICO', 'MINDTREE',
            'MOTHERSUMI', 'MRF', 'MUTHOOTFIN', 'NATIONALUM', 'NAUKRI', 'NMDC',
            'OFSS', 'OIL', 'PAGEIND', 'PEL', 'PETRONET', 'PFC', 'PIDILITIND',
            'PNB', 'POLYCAB', 'PVR', 'RAMCOCEM', 'RBLBANK', 'RECLTD', 'SAIL',
            'SHREECEM', 'SIEMENS', 'SRF', 'SUNTV', 'TATACOMM', 'TATACONSUM',
            'TATAPOWER', 'TORNTPHARM', 'TRENT', 'TVSMOTOR', 'UBL', 'UNIONBANK',
            'VEDL', 'VOLTAS', 'WHIRLPOOL', 'YESBANK', 'ZEEL', 'ACC', 'ADANIPOWER',
            'ALBK', 'AMARAJABAT', 'ARVIND', 'ASHOKLEY', 'ASTRAZEN', 'ATUL',
            'AUROPHARMA', 'BALRAMCHIN', 'BANDHANBNK', 'BANKBARODA', 'BATAINDIA',
            'BEL', 'BHARATFORG', 'BHARTIARTL', 'BHEL', 'BIOCON', 'BLISSGVS',
            'BOSCHLTD', 'BSOFT', 'CADILAHC', 'CANBK', 'CANFINHOME', 'CHAMBLFERT',
            'CHOLAFIN', 'CROMPTON', 'CUB', 'DELTACORP', 'DIXON', 'EQUITAS',
            'ESCORTS', 'EXIDEIND', 'FEDERALBNK', 'FORTIS', 'FSL', 'GICRE',
            'GMRINFRA', 'GNFC', 'GODREJPROP', 'GRANULES', 'GRAPHITE', 'GSPL',
            'GUJGASLTD', 'HEIDELBERG', 'HONAUT', 'IBREALEST', 'IDBI', 'IDFC',
            'IFCI', 'IIFL', 'INDHOTEL', 'INDUSTOWER', 'INFIBEAM', 'IRB',
            'IRCTC', 'ISEC', 'ITC', 'JETAIRWAYS', 'JINDALSTEL', 'JKCEMENT',
            'JKLAKSHMI', 'JMFINANCIL', 'JSWENERGY', 'JUSTDIAL', 'KAJARIACER',
            'KANSAINER', 'KTKBANK', 'L&TFH', 'LALPATHLAB', 'LAURUSLABS',
            'LICI', 'LTIM', 'MANAPPURAM', 'MAZDOCK', 'METROPOLIS', 'MFSL',
            'MGL', 'MHRIL', 'MIDHANI', 'MOTILALOFS', 'MPHASIS', 'MSM',
            'NBCC', 'NETWORK18', 'NIACL', 'NLCINDIA', 'OBEROIRLTY', 'OFSS',
            'ORIENTREF', 'PAYTM', 'PERSISTENT', 'POLICYBZR', 'POONAWALLA',
            'PRAJIND', 'PRESTIGE', 'RAIN', 'RAJESHEXPO', 'REDINGTON',
            'RELAXO', 'RNAM', 'ROUTE', 'RPOWER', 'RVNL', 'SCHAEFFLER',
            'SHILPAMED', 'SHOPERSTOP', 'SOBHA', 'SPANDANA', 'STARHEALTH',
            'SUNTECK', 'SUPRAJIT', 'SUZLON', 'SYMPHONY', 'TEAMLEASE',
            'TIINDIA', 'TIMKEN', 'TIPSINDLTD', 'TITAGARH', 'TRIDENT',
            'TRITURBINE', 'UJJIVAN', 'UNICHEMLAB', 'UNOMINDA', 'VGUARD',
            'VINATIORGA', 'VSTIND', 'WELCORP', 'WELSPUNIND', 'WESTLIFE',
            'ZENTEC', 'ZOMATO', 'ZYDUSLIFE'
        ]
        
        # Add .NS suffix for Yahoo Finance
        return [f"{symbol}.NS" for symbol in symbols]
    
    def fetch_stock_data(self, symbol):
        """Fetch data for a single stock"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="1d")
            
            if hist.empty:
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            change = current_price - prev_close
            pchange = (change / prev_close) * 100 if prev_close > 0 else 0
            
            return {
                'symbol': symbol.replace('.NS', ''),
                'company_name': info.get('longName', symbol.replace('.NS', '')),
                'last_price': float(current_price),
                'change': float(change),
                'pchange': float(pchange),
                'volume': int(hist['Volume'].iloc[-1]) if not hist['Volume'].empty else 0,
                'market_cap': info.get('marketCap', 0),
                'open': float(hist['Open'].iloc[-1]) if not hist['Open'].empty else 0,
                'high': float(hist['High'].iloc[-1]) if not hist['High'].empty else 0,
                'low': float(hist['Low'].iloc[-1]) if not hist['Low'].empty else 0,
            }
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None
    
    def fetch_all_stocks(self, max_stocks=None):
        """Fetch data for all stocks"""
        symbols_to_fetch = self.nse_symbols[:max_stocks] if max_stocks else self.nse_symbols
        stocks = []
        
        print(f"Fetching live data for {len(symbols_to_fetch)} stocks from Yahoo Finance...")
        
        for i, symbol in enumerate(symbols_to_fetch):
            try:
                stock_data = self.fetch_stock_data(symbol)
                if stock_data:
                    stocks.append(stock_data)
                    print(f"[{i+1}/{len(symbols_to_fetch)}] ✓ {stock_data['symbol']} - ₹{stock_data['last_price']:.2f}")
                else:
                    print(f"[{i+1}/{len(symbols_to_fetch)}] ✗ {symbol} - No data")
                
                # Rate limiting to avoid being blocked
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue
        
        print(f"\nSuccessfully fetched live data for {len(stocks)} stocks!")
        return stocks
    
    def get_stock_by_symbol(self, symbol):
        """Get live data for a specific stock"""
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        
        return self.fetch_stock_data(symbol)

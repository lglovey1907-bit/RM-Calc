from django.core.management.base import BaseCommand
from calc.yahoo_nse_fetcher import YahooNSEFetcher
from calc.models import StockData
from decimal import Decimal

class Command(BaseCommand):
    help = 'Fetch live NSE stock data from Yahoo Finance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-stocks',
            type=int,
            default=200,
            help='Maximum number of stocks to fetch'
        )
        parser.add_argument(
            '--update-prices-only',
            action='store_true',
            help='Only update prices for existing stocks'
        )
    
    def handle(self, *args, **options):
        fetcher = YahooNSEFetcher()
        max_stocks = options['max_stocks']
        update_only = options['update_prices_only']
        
        if update_only:
            # Update existing stocks only
            existing_symbols = list(StockData.objects.values_list('symbol', flat=True))
            self.stdout.write(f"Updating prices for {len(existing_symbols)} existing stocks...")
            
            updated_count = 0
            for symbol in existing_symbols:
                try:
                    stock_data = fetcher.get_stock_by_symbol(symbol)
                    if stock_data:
                        StockData.objects.filter(symbol=symbol).update(
                            last_price=Decimal(str(stock_data['last_price'])),
                            change=Decimal(str(stock_data['change'])),
                            pchange=Decimal(str(stock_data['pchange'])),
                            volume=stock_data['volume'],
                        )
                        updated_count += 1
                        self.stdout.write(f"Updated: {symbol} - ₹{stock_data['last_price']:.2f}")
                except Exception as e:
                    self.stdout.write(f"Error updating {symbol}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(f'Updated prices for {updated_count} stocks')
            )
        else:
            # Fetch new stocks
            stocks = fetcher.fetch_all_stocks(max_stocks)
            
            created_count = 0
            updated_count = 0
            
            for stock_data in stocks:
                try:
                    stock, created = StockData.objects.update_or_create(
                        symbol=stock_data['symbol'],
                        defaults={
                            'company_name': stock_data['company_name'],
                            'last_price': Decimal(str(stock_data['last_price'])),
                            'change': Decimal(str(stock_data['change'])),
                            'pchange': Decimal(str(stock_data['pchange'])),
                            'volume': stock_data['volume'],
                            'market_cap': stock_data.get('market_cap', 0),
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    self.stdout.write(f"Error saving {stock_data['symbol']}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {len(stocks)} stocks: '
                    f'{created_count} created, {updated_count} updated'
                )
            )

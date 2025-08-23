from django.core.management.base import BaseCommand
from calc.stock_fetcher import NSEStockDataFetcher
from calc.models import StockData

class Command(BaseCommand):
    help = 'Update NSE stock data'
    
    def handle(self, *args, **options):
        fetcher = NSEStockDataFetcher()
        stocks = fetcher.get_all_stocks()
        
        updated_count = 0
        for stock_data in stocks:
            stock, created = StockData.objects.update_or_create(
                symbol=stock_data['symbol'],
                defaults={
                    'company_name': stock_data['company_name'],
                    'last_price': stock_data['last_price'],
                    'change': stock_data['change'],
                    'pchange': stock_data['pchange'],
                    'volume': stock_data['volume'],
                    'market_cap': stock_data.get('market_cap', 0),
                }
            )
            updated_count += 1
            
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} stocks')
        )

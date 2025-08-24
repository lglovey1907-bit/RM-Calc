# calc/management/commands/update_stocks.py
# Create directories: calc/management/ and calc/management/commands/
# Add __init__.py files in both directories

from django.core.management.base import BaseCommand
from django.utils import timezone
from calc.views import update_stock_database
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update stock prices from external APIs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if recently updated',
        )
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of specific symbols to update',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'Starting stock update at {timezone.now()}')
        )
        
        try:
            if options['symbols']:
                # Update specific symbols
                symbols = [s.strip().upper() for s in options['symbols'].split(',')]
                self.stdout.write(f'Updating specific symbols: {symbols}')
                # Add logic for specific symbols here
                updated_count = len(symbols)  # Placeholder
            else:
                # Update all stocks
                updated_count = update_stock_database()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} stocks at {timezone.now()}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Stock update failed: {str(e)}')
            )
            logger.error(f'Stock update command failed: {str(e)}')
            raise

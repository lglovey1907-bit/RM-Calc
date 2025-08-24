# Create: calc/migrations/0003_add_missing_fields.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calc', '0002_initial'),  # Replace with your actual last migration
    ]

    operations = [
        # Add missing risk_amount field to CalculationHistory
        migrations.AddField(
            model_name='calculationhistory',
            name='risk_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
            preserve_default=False,
        ),
        
        # Ensure StockData table exists
        migrations.CreateModel(
            name='StockData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20, unique=True)),
                ('company_name', models.CharField(max_length=200)),
                ('last_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('change', models.DecimalField(decimal_places=2, max_digits=12)),
                ('pchange', models.DecimalField(decimal_places=2, max_digits=8)),
                ('volume', models.BigIntegerField(default=0)),
                ('market_cap', models.BigIntegerField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Stock Data',
                'verbose_name_plural': 'Stock Data',
                'ordering': ['symbol'],
            },
        ),
    ]

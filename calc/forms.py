from django import forms
from .models import UserSettings, CalculationHistory

class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ['capital', 'risk_percent']
        widgets = {
            'capital': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter capital amount',
                'step': '0.01',
                'min': '0'
            }),
            'risk_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter risk percentage',
                'step': '0.01',
                'min': '0',
                'max': '100'
            })
        }
        labels = {
            'capital': 'Capital Invested (₹)',
            'risk_percent': 'Risk per Trade (%)'
        }

class CalculationForm(forms.Form):
    TRADE_DIRECTIONS = [
        ('Buy (Long)', 'Buy (Long)'),
        ('Sell (Short)', 'Sell (Short)'),
    ]
    
    direction = forms.ChoiceField(
        choices=TRADE_DIRECTIONS,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='Buy (Long)'
    )
    
    entry_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter entry price',
            'step': '0.01',
            'min': '0'
        }),
        label='Entry Price (₹)'
    )
    
    stop_loss = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter stop loss price',
            'step': '0.01',
            'min': '0'
        }),
        label='Stop Loss Price (₹)'
    )
    
    custom_ratio = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 10 or 1:10'
        }),
        label='Custom Target Ratio (Optional)'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        entry_price = cleaned_data.get('entry_price')
        stop_loss = cleaned_data.get('stop_loss')
        direction = cleaned_data.get('direction')
        
        if entry_price and stop_loss:
            if direction == 'Buy (Long)' and entry_price <= stop_loss:
                raise forms.ValidationError("For Long trades, entry price must be higher than stop loss.")
            elif direction == 'Sell (Short)' and entry_price >= stop_loss:
                raise forms.ValidationError("For Short trades, entry price must be lower than stop loss.")
                
        return cleaned_data

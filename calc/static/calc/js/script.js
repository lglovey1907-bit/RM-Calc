document.addEventListener('DOMContentLoaded', function() {
    // Form elements
    const form = document.getElementById('calculator-form');
    const capitalInput = document.getElementById('id_capital');
    const riskPercentInput = document.getElementById('id_risk_percent');
    const entryPriceInput = document.getElementById('id_entry_price');
    const stopLossInput = document.getElementById('id_stop_loss');
    const directionRadios = document.querySelectorAll('input[name="direction"]');
    
    // Result elements
    const riskRsOutput = document.getElementById('risk-rs');
    const perShareRiskOutput = document.getElementById('per-share-risk');
    const quantityOutput = document.getElementById('quantity');
    const targetsOutput = document.getElementById('targets-output');
    const customRatioInput = document.getElementById('id_custom_ratio');
    const customTargetOutput = document.getElementById('custom-target');
    
    // Add event listeners to all relevant inputs
    [capitalInput, riskPercentInput, entryPriceInput, stopLossInput].forEach(input => {
        input.addEventListener('input', calculate);
    });
    
    directionRadios.forEach(radio => {
        radio.addEventListener('change', calculate);
    });
    
    // Main calculation function
    function calculate() {
        const capital = parseFloat(capitalInput.value) || 0;
        const riskPercent = parseFloat(riskPercentInput.value) || 0;
        const entryPrice = parseFloat(entryPriceInput.value) || 0;
        const stopLoss = parseFloat(stopLossInput.value) || 0;
        const direction = document.querySelector('input[name="direction"]:checked').value;
        
        // Calculate risk in rupees
        const riskRs = (capital * riskPercent) / 100;
        riskRsOutput.value = riskRs.toFixed(2);
        
        // Calculate per share risk and quantity
        const perShareRisk = Math.abs(entryPrice - stopLoss);
        const quantity = perShareRisk > 0 ? Math.floor(riskRs / perShareRisk) : 0;
        
        perShareRiskOutput.value = perShareRisk.toFixed(2);
        quantityOutput.value = quantity;
        
        // Calculate targets
        let targetsText = '';
        [2, 3, 4, 5].forEach(ratio => {
            const target = direction === 'BUY'
                ? entryPrice + (perShareRisk * ratio)
                : entryPrice - (perShareRisk * ratio);
            targetsText += `🎯 Target ${ratio-1} (1:${ratio}): ${target.toFixed(2)}\n`;
        });
        targetsOutput.textContent = targetsText;
        
        // Calculate custom target if ratio provided
        if (customRatioInput && customRatioInput.value) {
            try {
                const ratio = parseFloat(customRatioInput.value.split(':').pop());
                const customTarget = direction === 'BUY'
                    ? entryPrice + (perShareRisk * ratio)
                    : entryPrice - (perShareRisk * ratio);
                customTargetOutput.value = customTarget.toFixed(2);
            } catch (e) {
                customTargetOutput.value = 'Invalid ratio';
            }
        }
    }
    
    // Save calculation handler
    document.getElementById('save-btn').addEventListener('click', saveCalculation);
    
    function saveCalculation() {
        const formData = new FormData(form);
        formData.append('risk_rs', riskRsOutput.value);
        formData.append('per_share_risk', perShareRiskOutput.value);
        formData.append('quantity', quantityOutput.value);
        
        fetch('/calc/save/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Calculation saved successfully!');
                window.location.reload();
            } else {
                alert('Error saving calculation: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error saving calculation');
        });
    }
    
    // Initialize calculation if values exist
    if (capitalInput.value && riskPercentInput.value) {
        calculate();
    }
});

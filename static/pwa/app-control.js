// static/js/app-control.js
class AppController {
    constructor() {
        this.deviceId = this.getDeviceId();
        this.checkInterval = null;
        this.init();
    }

    getDeviceId() {
        let deviceId = localStorage.getItem('device_id');
        if (!deviceId) {
            deviceId = 'device_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('device_id', deviceId);
        }
        return deviceId;
    }

    async init() {
        // Register device
        await this.registerDevice();
        
        // Check access immediately
        await this.checkAccess();
        
        // Check every 5 minutes
        this.checkInterval = setInterval(() => {
            this.checkAccess();
        }, 5 * 60 * 1000);
    }

    async registerDevice() {
        try {
            const response = await fetch('/api/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    device_id: this.deviceId,
                    email: '' // Optional: get from user
                })
            });
            const data = await response.json();
            console.log('Device registered:', data);
        } catch (error) {
            console.error('Registration failed:', error);
        }
    }

    async checkAccess() {
        try {
            const response = await fetch('/api/check-access/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    device_id: this.deviceId
                })
            });
            
            const data = await response.json();
            
            if (!data.access) {
                this.handleAccessDenied(data);
            } else if (data.warning) {
                this.showWarning(data.warning);
            }
            
        } catch (error) {
            console.error('Access check failed:', error);
            // Allow offline usage
        }
    }

    handleAccessDenied(data) {
        // Disable app functionality
        document.body.innerHTML = `
            <div style="padding: 20px; text-align: center;">
                <h2>Access Denied</h2>
                <p>${data.message}</p>
                ${data.reason === 'payment_required' ?
                    '<button onclick="location.reload()">Retry</button>' : ''}
            </div>
        `;
        
        // Clear interval
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }
    }

    showWarning(message) {
        // Show non-intrusive warning
        const warning = document.createElement('div');
        warning.style.cssText = 'position:fixed;top:0;width:100%;background:#ff9800;color:white;padding:10px;text-align:center;z-index:9999';
        warning.textContent = message;
        document.body.appendChild(warning);
        
        setTimeout(() => warning.remove(), 5000);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.appController = new AppController();
});

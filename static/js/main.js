/**
 * Main JavaScript file for Green Hydrogen Platform
 * Handles common functionality, WebSocket connections, and UI interactions
 */

// Global variables
let socket = null;
let connectionStatus = 'disconnected';

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    initializeGlobalEventListeners();
    initializeConnectionIndicator();
    initializeFormValidations();
});

/**
 * Initialize WebSocket connection
 */
function initializeWebSocket() {
    if (typeof io === 'undefined') {
        console.log('Socket.IO not available');
        return;
    }
    
    socket = io();
    
    // Connection events
    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus('connected');
        
        // Auto-join relevant rooms based on current page
        const currentPage = getCurrentPage();
        if (currentPage === 'blockchain') {
            socket.emit('join_blockchain_room');
        } else if (currentPage === 'marketplace') {
            socket.emit('join_marketplace_room');
        }
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus('disconnected');
    });
    
    socket.on('connect_error', function(error) {
        console.error('Connection error:', error);
        updateConnectionStatus('error');
    });
    
    // Global event handlers
    socket.on('error', function(data) {
        console.error('Socket error:', data);
        showNotification('Connection Error', data.message || 'Unknown error occurred', 'danger');
    });
    
    socket.on('pong', function(data) {
        console.log('Pong received:', data);
    });
}

/**
 * Initialize global event listeners
 */
function initializeGlobalEventListeners() {
    // Global form submission handling
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (form.classList.contains('needs-validation')) {
            e.preventDefault();
            e.stopPropagation();
            
            if (form.checkValidity()) {
                handleFormSubmission(form);
            }
            
            form.classList.add('was-validated');
        }
    });
    
    // Global click handlers
    document.addEventListener('click', function(e) {
        // Copy to clipboard functionality
        if (e.target.classList.contains('copy-btn') || e.target.closest('.copy-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.copy-btn');
            const textToCopy = btn.dataset.copy || btn.textContent;
            copyToClipboard(textToCopy);
        }
        
        // Toast dismiss functionality
        if (e.target.classList.contains('toast-dismiss')) {
            e.preventDefault();
            const toast = e.target.closest('.toast-notification');
            if (toast) {
                dismissToast(toast);
            }
        }
    });
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for search (if search exists)
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            const searchInput = document.querySelector('input[type="search"], input[name="search"]');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
        
        // Escape key to close modals
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                const modal = bootstrap.Modal.getInstance(openModal);
                if (modal) {
                    modal.hide();
                }
            }
        }
    });
}

/**
 * Initialize connection status indicator
 */
function initializeConnectionIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'connection-indicator';
    indicator.className = 'connection-status disconnected';
    indicator.innerHTML = '<i class="fas fa-wifi me-1"></i>Connecting...';
    document.body.appendChild(indicator);
    
    // Hide indicator after a few seconds when connected
    setTimeout(() => {
        if (connectionStatus === 'connected') {
            indicator.style.opacity = '0';
        }
    }, 3000);
}

/**
 * Initialize form validations
 */
function initializeFormValidations() {
    // Add custom validation for credit amounts
    const creditInputs = document.querySelectorAll('input[name="amount"]');
    creditInputs.forEach(input => {
        input.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value <= 0) {
                this.setCustomValidity('Amount must be greater than 0');
            } else if (value > 999999) {
                this.setCustomValidity('Amount is too large');
            } else {
                this.setCustomValidity('');
            }
        });
    });
    
    // Email validation
    const emailInputs = document.querySelectorAll('input[type="email"]');
    emailInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value && !isValidEmail(this.value)) {
                this.setCustomValidity('Please enter a valid email address');
            } else {
                this.setCustomValidity('');
            }
        });
    });
}

/**
 * Update connection status
 */
function updateConnectionStatus(status) {
    connectionStatus = status;
    const indicator = document.getElementById('connection-indicator');
    
    if (indicator) {
        indicator.className = `connection-status ${status}`;
        
        switch (status) {
            case 'connected':
                indicator.innerHTML = '<i class="fas fa-wifi me-1"></i>Connected';
                break;
            case 'disconnected':
                indicator.innerHTML = '<i class="fas fa-wifi-slash me-1"></i>Disconnected';
                break;
            case 'error':
                indicator.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Connection Error';
                break;
        }
        
        indicator.style.opacity = '1';
        
        // Auto-hide when connected
        if (status === 'connected') {
            setTimeout(() => {
                indicator.style.opacity = '0';
            }, 3000);
        }
    }
}

/**
 * Show notification/toast
 */
function showNotification(title, message, type = 'info', duration = 5000) {
    const toast = document.createElement('div');
    toast.className = `toast-notification alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '1060';
    toast.style.minWidth = '300px';
    toast.innerHTML = `
        <div class="d-flex align-items-start">
            <div class="flex-grow-1">
                <strong>${title}</strong>
                <div>${message}</div>
            </div>
            <button type="button" class="btn-close toast-dismiss ms-2" aria-label="Close"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 10);
    
    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => {
            dismissToast(toast);
        }, duration);
    }
    
    return toast;
}

/**
 * Dismiss toast notification
 */
function dismissToast(toast) {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('Copied', 'Text copied to clipboard', 'success', 2000);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            fallbackCopyToClipboard(text);
        });
    } else {
        fallbackCopyToClipboard(text);
    }
}

/**
 * Fallback copy to clipboard method
 */
function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showNotification('Copied', 'Text copied to clipboard', 'success', 2000);
    } catch (err) {
        console.error('Fallback: Failed to copy text: ', err);
        showNotification('Error', 'Failed to copy text', 'danger');
    }
    
    document.body.removeChild(textArea);
}

/**
 * Handle form submission with loading state
 */
function handleFormSubmission(form) {
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="loading-spinner me-2"></span>Processing...';
        submitBtn.disabled = true;
        
        // Reset button after 3 seconds (form will likely redirect before this)
        setTimeout(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }, 3000);
    }
}

/**
 * Get current page identifier
 */
function getCurrentPage() {
    const path = window.location.pathname;
    if (path.includes('/blockchain')) return 'blockchain';
    if (path.includes('/marketplace')) return 'marketplace';
    if (path.includes('/certificates')) return 'certificates';
    if (path.includes('/credits')) return 'credits';
    if (path.includes('/analytics')) return 'analytics';
    if (path.includes('/notifications')) return 'notifications';
    if (path.includes('/dashboard')) return 'dashboard';
    return 'home';
}

/**
 * Email validation
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Format currency
 */
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

/**
 * Format date
 */
function formatDate(date, options = {}) {
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    const formatOptions = { ...defaultOptions, ...options };
    return new Intl.DateTimeFormat('en-US', formatOptions).format(new Date(date));
}

/**
 * Debounce function for search inputs
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

/**
 * Initialize search functionality
 */
function initializeSearch() {
    const searchInputs = document.querySelectorAll('input[type="search"]');
    
    searchInputs.forEach(input => {
        const debouncedSearch = debounce(function(query) {
            performSearch(query, input);
        }, 300);
        
        input.addEventListener('input', function() {
            debouncedSearch(this.value);
        });
    });
}

/**
 * Perform search (to be implemented per page)
 */
function performSearch(query, input) {
    console.log('Searching for:', query);
    // Implementation depends on the specific page
}

/**
 * WebSocket helper functions
 */
const WebSocketHelper = {
    emit: function(event, data) {
        if (socket && socket.connected) {
            socket.emit(event, data);
        } else {
            console.warn('Socket not connected, cannot emit:', event);
        }
    },
    
    on: function(event, callback) {
        if (socket) {
            socket.on(event, callback);
        }
    },
    
    off: function(event, callback) {
        if (socket) {
            socket.off(event, callback);
        }
    },
    
    isConnected: function() {
        return socket && socket.connected;
    }
};

/**
 * Utility functions for charts
 */
const ChartHelper = {
    getDefaultOptions: function(isDark = true) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: isDark ? '#ffffff' : '#000000'
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: isDark ? '#ffffff' : '#000000'
                    },
                    grid: {
                        color: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'
                    }
                },
                x: {
                    ticks: {
                        color: isDark ? '#ffffff' : '#000000'
                    },
                    grid: {
                        color: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'
                    }
                }
            }
        };
    },
    
    colors: {
        primary: '#0d6efd',
        success: '#198754',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#0dcaf0',
        secondary: '#6c757d'
    }
};

// Export for use in other scripts
window.HydrogenPlatform = {
    WebSocketHelper,
    ChartHelper,
    showNotification,
    copyToClipboard,
    formatCurrency,
    formatDate,
    getCurrentPage,
    debounce
};

// Initialize search when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
});

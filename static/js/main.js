// IT Support Ticket System - Main JS

// Execute when the document is ready
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize tooltips (Bootstrap)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle status filter changes - auto-submit form when changed
    const statusFilter = document.getElementById('status');
    const categoryFilter = document.getElementById('category');
    
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            if (this.form) {
                this.form.submit();
            }
        });
    }
    
    if (categoryFilter) {
        categoryFilter.addEventListener('change', function() {
            if (this.form) {
                this.form.submit();
            }
        });
    }
    
    // Add confirmation for critical actions
    const confirmActions = document.querySelectorAll('.confirm-action');
    
    confirmActions.forEach(function(button) {
        button.addEventListener('click', function(event) {
            const message = this.getAttribute('data-confirm-message') || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                event.preventDefault();
            }
        });
    });
    
    // Auto-resize textareas as content is typed
    const autoResizeTextareas = document.querySelectorAll('textarea.auto-resize');
    
    autoResizeTextareas.forEach(function(textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        
        // Trigger resize on load
        textarea.dispatchEvent(new Event('input'));
    });
    
    // Convert timestamps to relative time (e.g., "2 hours ago")
    const relativeTimeElements = document.querySelectorAll('.relative-time');
    
    relativeTimeElements.forEach(function(element) {
        const timestamp = element.getAttribute('data-timestamp');
        if (timestamp) {
            const date = new Date(timestamp);
            element.textContent = getRelativeTimeString(date);
        }
    });
    
    // Helper function to format relative time
    function getRelativeTimeString(date) {
        const now = new Date();
        const diffInMilliseconds = now - date;
        const diffInSeconds = Math.floor(diffInMilliseconds / 1000);
        const diffInMinutes = Math.floor(diffInSeconds / 60);
        const diffInHours = Math.floor(diffInMinutes / 60);
        const diffInDays = Math.floor(diffInHours / 24);
        
        if (diffInDays > 7) {
            return date.toLocaleDateString();
        } else if (diffInDays > 0) {
            return diffInDays + ' day' + (diffInDays > 1 ? 's' : '') + ' ago';
        } else if (diffInHours > 0) {
            return diffInHours + ' hour' + (diffInHours > 1 ? 's' : '') + ' ago';
        } else if (diffInMinutes > 0) {
            return diffInMinutes + ' minute' + (diffInMinutes > 1 ? 's' : '') + ' ago';
        } else {
            return 'just now';
        }
    }
    
    // Toggle internal comment checkbox based on role for new comments
    const internalCommentCheckbox = document.getElementById('internal_only');
    const commentContent = document.getElementById('content');
    
    if (internalCommentCheckbox && commentContent) {
        internalCommentCheckbox.addEventListener('change', function() {
            if (this.checked) {
                commentContent.classList.add('internal-comment-input');
            } else {
                commentContent.classList.remove('internal-comment-input');
            }
        });
    }
    
    // Add dynamic counters to text inputs with maxlength
    const textInputs = document.querySelectorAll('input[type="text"][maxlength], textarea[maxlength]');
    
    textInputs.forEach(function(input) {
        const maxLength = input.getAttribute('maxlength');
        if (!maxLength) return;
        
        // Create counter element
        const counter = document.createElement('div');
        counter.className = 'text-muted small text-end mt-1';
        counter.textContent = `${input.value.length} / ${maxLength} characters`;
        
        // Insert counter after input
        input.parentNode.insertBefore(counter, input.nextSibling);
        
        // Update counter on input
        input.addEventListener('input', function() {
            counter.textContent = `${this.value.length} / ${maxLength} characters`;
        });
    });
});

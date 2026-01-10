/**
 * Gojo Trip Planner - Main JavaScript
 * Core functionality and utilities
 */

// ===== Toast Notifications =====
class ToastManager {
  constructor() {
    this.container = this.createContainer();
  }

  createContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div style="display: flex; align-items: start; gap: 12px;">
        <span style="font-size: 20px;">${this.getIcon(type)}</span>
        <div style="flex: 1;">
          <strong style="display: block; margin-bottom: 4px;">${this.getTitle(type)}</strong>
          <span>${message}</span>
        </div>
      </div>
    `;

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideInRight 0.3s ease-out reverse';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  getIcon(type) {
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };
    return icons[type] || icons.info;
  }

  getTitle(type) {
    const titles = {
      success: 'Success',
      error: 'Error',
      warning: 'Warning',
      info: 'Info'
    };
    return titles[type] || titles.info;
  }
}

const toast = new ToastManager();

// ===== Form Validation =====
function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function validatePassword(password) {
  return password.length >= 8;
}

function validateForm(formElement) {
  const inputs = formElement.querySelectorAll('[required]');
  let isValid = true;

  inputs.forEach(input => {
    const errorElement = input.parentElement.querySelector('.form-error');
    if (errorElement) {
      errorElement.remove();
    }

    if (!input.value.trim()) {
      showFieldError(input, 'This field is required');
      isValid = false;
    } else if (input.type === 'email' && !validateEmail(input.value)) {
      showFieldError(input, 'Please enter a valid email address');
      isValid = false;
    } else if (input.type === 'password' && !validatePassword(input.value)) {
      showFieldError(input, 'Password must be at least 8 characters');
      isValid = false;
    }
  });

  return isValid;
}

function showFieldError(input, message) {
  const error = document.createElement('span');
  error.className = 'form-error';
  error.textContent = message;
  input.parentElement.appendChild(error);
  input.style.borderColor = 'var(--color-error)';
}

// ===== Modal Management =====
class ModalManager {
  constructor() {
    this.activeModal = null;
  }

  open(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    this.activeModal = modal;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        this.close(modalId);
      }
    });

    // Close on escape key
    const escapeHandler = (e) => {
      if (e.key === 'Escape') {
        this.close(modalId);
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);
  }

  close(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.style.display = 'none';
    document.body.style.overflow = '';
    this.activeModal = null;
  }
}

const modal = new ModalManager();

// ===== Loading States =====
function showLoading(button) {
  button.disabled = true;
  button.dataset.originalText = button.innerHTML;
  button.innerHTML = '<span class="spinner"></span> Loading...';
}

function hideLoading(button) {
  button.disabled = false;
  button.innerHTML = button.dataset.originalText || button.innerHTML;
}

// ===== AJAX Helpers =====
async function fetchJSON(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Fetch error:', error);
    toast.show('An error occurred. Please try again.', 'error');
    throw error;
  }
}

// ===== Date Formatting =====
function formatDate(dateString) {
  const date = new Date(dateString);
  const options = { year: 'numeric', month: 'short', day: 'numeric' };
  return date.toLocaleDateString('en-US', options);
}

function formatDateTime(dateString) {
  const date = new Date(dateString);
  const dateOptions = { year: 'numeric', month: 'short', day: 'numeric' };
  const timeOptions = { hour: '2-digit', minute: '2-digit' };
  return `${date.toLocaleDateString('en-US', dateOptions)} at ${date.toLocaleTimeString('en-US', timeOptions)}`;
}

// ===== Smooth Scroll =====
function smoothScroll(target) {
  const element = document.querySelector(target);
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ===== File Upload Preview =====
function setupFilePreview(inputElement, previewElement) {
  inputElement.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewElement.src = e.target.result;
        previewElement.style.display = 'block';
      };
      reader.readAsDataURL(file);
    }
  });
}

// ===== Password Toggle =====
function setupPasswordToggle() {
  document.querySelectorAll('[data-password-toggle]').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.querySelector(button.dataset.passwordToggle);
      if (input) {
        const type = input.type === 'password' ? 'text' : 'password';
        input.type = type;
        button.textContent = type === 'password' ? '👁' : '👁‍🗨';
      }
    });
  });
}

// ===== Initialize on DOM Load =====
document.addEventListener('DOMContentLoaded', () => {
  // Setup password toggles
  setupPasswordToggle();

  // Add form validation to all forms with data-validate attribute
  document.querySelectorAll('form[data-validate]').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!validateForm(form)) {
        e.preventDefault();
      }
    });
  });

  // Add loading states to submit buttons
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', (e) => {
      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton && !form.dataset.noLoading) {
        showLoading(submitButton);
      }
    });
  });

  // Setup floating labels
  document.querySelectorAll('.form-floating input, .form-floating textarea').forEach(input => {
    // Add placeholder for CSS selector to work
    if (!input.placeholder) {
      input.placeholder = ' ';
    }
  });

  // Animate elements on scroll
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-fade-in');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  document.querySelectorAll('.card, .trip-card, .stat-card').forEach(el => {
    observer.observe(el);
  });
});

// ===== Export for use in other scripts =====
window.GojoApp = {
  toast,
  modal,
  validateForm,
  showLoading,
  hideLoading,
  fetchJSON,
  formatDate,
  formatDateTime,
  smoothScroll
};

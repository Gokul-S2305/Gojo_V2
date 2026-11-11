// Gojo Toast Notification Utility
(function () {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  window.showToast = function (message, type = 'info', duration = 3500) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  };

  // Auto-display flash messages from URL query params (e.g. ?msg=..., ?error=...)
  document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('msg')) {
      showToast(params.get('msg'), 'success');
    }
    if (params.has('error')) {
      showToast(params.get('error'), 'error');
    }
  });
})();

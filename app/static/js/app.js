/* LexOffice Main JavaScript */

document.addEventListener('DOMContentLoaded', function() {

    // ── Dark Mode Toggle ──
    const darkToggle = document.getElementById('darkModeToggle');
    const html = document.documentElement;

    // Apply saved theme on load (default: light)
    const saved = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-bs-theme', saved);
    if (darkToggle) {
        darkToggle.innerHTML = saved === 'dark'
            ? '<i class="bi bi-sun-fill"></i>'
            : '<i class="bi bi-moon-fill"></i>';
    }

    if (darkToggle) {
        darkToggle.addEventListener('click', function() {
            const current = html.getAttribute('data-bs-theme') || 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-bs-theme', next);
            localStorage.setItem('theme', next);
            this.innerHTML = next === 'dark'
                ? '<i class="bi bi-sun-fill"></i>'
                : '<i class="bi bi-moon-fill"></i>';
        });
    }

    // ── Mobile Sidebar Toggle ──
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
            if (overlay) overlay.classList.toggle('show');
        });
        if (overlay) {
            overlay.addEventListener('click', function() {
                sidebar.classList.remove('show');
                overlay.classList.remove('show');
            });
        }
    }

    // ── CSRF Token for AJAX ──
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        const csrfToken = csrfMeta.getAttribute('content');
        // Set default header for fetch
        const origFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (options.method && options.method !== 'GET') {
                options.headers = options.headers || {};
                if (!(options.headers instanceof Headers)) {
                    options.headers['X-CSRFToken'] = csrfToken;
                }
            }
            return origFetch.call(this, url, options);
        };
    }

    // ── Flatpickr Arabic Init ──
    document.querySelectorAll('.datepicker').forEach(function(el) {
        if (typeof flatpickr !== 'undefined') {
            flatpickr(el, {
                locale: 'ar',
                dateFormat: 'Y-m-d',
                allowInput: true
            });
        }
    });

    document.querySelectorAll('.datetimepicker').forEach(function(el) {
        if (typeof flatpickr !== 'undefined') {
            flatpickr(el, {
                locale: 'ar',
                dateFormat: 'Y-m-d H:i',
                enableTime: true,
                time_24hr: true,
                allowInput: true
            });
        }
    });

    // ── Flash Message Auto-dismiss ──
    document.querySelectorAll('.flash-message .alert').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });

    // ── Confirm Delete ──
    // Two-step prompt: first ask "are you sure?", then require typing
    // "تأكيد" (confirm) on truly destructive actions. Forms tagged with
    // data-confirm-danger="true" trigger the strict path; anything else
    // uses a single confirm() like before.
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            var msg = this.dataset.confirm || 'هل أنت متأكد؟';
            if (!confirm(msg)) { e.preventDefault(); return; }
            if (this.dataset.confirmDanger === 'true') {
                var typed = prompt('للتأكيد النهائي، اكتب كلمة: تأكيد');
                if ((typed || '').trim() !== 'تأكيد') {
                    e.preventDefault();
                    alert('تم إلغاء الحذف.');
                }
            }
        });
    });

    // ── Active Sidebar Link ──
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(function(link) {
        const href = link.getAttribute('href');
        if (href && currentPath.startsWith(href) && href !== '/') {
            link.classList.add('active');
        }
    });
});

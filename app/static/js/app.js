/**
 * app.js — Theme toggle, SSE scan events, and notification bell logic.
 * Loaded on every page via base.html.
 */
(function() {
    'use strict';

    // ─── Utility ─────────────────────────────────────────────────────────────────
    function esc(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ─── Theme Toggle ────────────────────────────────────────────────────────────
    var toggleDark = document.getElementById('theme-toggle-dark');
    var toggleLight = document.getElementById('theme-toggle-light');
    var toggleDarkMobile = document.getElementById('theme-toggle-dark-mobile');
    var toggleLightMobile = document.getElementById('theme-toggle-light-mobile');

    function setTheme(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
    }

    if (toggleDark) {
        toggleDark.addEventListener('click', function(e) { e.preventDefault(); setTheme('dark'); });
    }
    if (toggleLight) {
        toggleLight.addEventListener('click', function(e) { e.preventDefault(); setTheme('light'); });
    }
    if (toggleDarkMobile) {
        toggleDarkMobile.addEventListener('click', function(e) { e.preventDefault(); setTheme('dark'); });
    }
    if (toggleLightMobile) {
        toggleLightMobile.addEventListener('click', function(e) { e.preventDefault(); setTheme('light'); });
    }

    // ─── SSE Scan Events ─────────────────────────────────────────────────────────
    var toastContainer = document.getElementById('scan-toasts');
    if (!window.EventSource || !toastContainer) return;

    // Service worker for mobile notification support
    var swReg = null;
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js').then(function(reg) { swReg = reg; });
    }

    // Browser notification permission — requested on first actionable scan (not page load)
    var notifPermAsked = false;
    function ensureNotifPermission() {
        if (notifPermAsked) return;
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
            notifPermAsked = true;
        }
    }

    var esRetryDelay = 1000;
    var es;
    function connectSSE() {
        es = new EventSource('/events');
        es.addEventListener('open', function() { esRetryDelay = 1000; });
        es.onerror = function() {
            es.close();
            setTimeout(connectSSE, esRetryDelay);
            esRetryDelay = Math.min(esRetryDelay * 2, 30000);
        };
        es.addEventListener('scan', onScanEvent);
    }
    function onScanEvent(e) {
        var data = JSON.parse(e.data);
        var barcode = data.barcode;
        var result = data.result;
        var food = data.food;

        var color, title, desc;
        if (result === 'added') {
            color = 'success';
            title = 'Added to shopping list';
            desc = food ? esc(food) + ' (' + esc(barcode) + ')' : esc(barcode);
        } else if (result === 'added_as_note') {
            color = 'info';
            title = 'Added as note';
            desc = food ? esc(food) + ' (' + esc(barcode) + ')' : esc(barcode);
        } else if (result === 'queued') {
            color = 'warning';
            title = 'Queued for retry';
            desc = esc(food || barcode);
        } else if (result === 'retry_failed') {
            color = 'danger';
            title = 'Retry failed';
            desc = esc(food || barcode) + ' — could not reach Mealie';
        } else {
            color = 'danger';
            title = 'Unknown barcode';
            desc = esc(barcode);
        }

        var link = '/barcodes/' + encodeURIComponent(barcode);
        var toastEl = document.createElement('div');
        toastEl.className = 'toast';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = '<div class="toast-header">'
            + '<span class="avatar avatar-xs me-2 bg-' + color + '">'
            + '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm text-white" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">'
            + '<path stroke="none" d="M0 0h24v24H0z" fill="none"/>'
            + '<path d="M4 7v-1a2 2 0 0 1 2 -2h2"/><path d="M4 17v1a2 2 0 0 0 2 2h2"/>'
            + '<path d="M16 4h2a2 2 0 0 1 2 2v1"/><path d="M16 20h2a2 2 0 0 0 2 -2v-1"/>'
            + '<path d="M5 11h1v2h-1z"/><path d="M10 11v2"/><path d="M14 11h1v2h-1z"/><path d="M19 11v2"/>'
            + '</svg></span>'
            + '<strong class="me-auto">' + title + '</strong>'
            + '<button type="button" class="ms-2 btn-close" data-bs-dismiss="toast" aria-label="Close"></button>'
            + '</div>'
            + '<div class="toast-body">'
            + desc + ' &mdash; <a href="' + link + '">View</a>'
            + '</div>';

        toastContainer.prepend(toastEl);

        // Initialize via Bootstrap Toast API (enables data-bs-dismiss and auto-hide)
        var bsToast = new bootstrap.Toast(toastEl, { delay: 8000 });
        bsToast.show();
        toastEl.addEventListener('hidden.bs.toast', function() { toastEl.remove(); });

        // Browser notification — only for actionable results
        var isActionable = (result !== 'added' && result !== 'queued');
        if (isActionable) {
            ensureNotifPermission();
            if ('Notification' in window && Notification.permission === 'granted') {
                var body = food ? food + ' (' + barcode + ')' : barcode;
                if (swReg) {
                    swReg.showNotification(title, { body: body, tag: barcode, data: { url: link } });
                } else {
                    var n = new Notification(title, { body: body, tag: barcode });
                    n.onclick = function() { window.focus(); window.location.href = link; };
                }
            }
        }

        // Partial dashboard update
        if (window.location.pathname === '/') {
            clearTimeout(window._dashRefresh);
            window._dashRefresh = setTimeout(function() { refreshDashboard(); }, 2000);
        }

        // Live-refresh barcodes table
        if (window.location.pathname === '/barcodes') {
            clearTimeout(window._barcodesRefresh);
            window._barcodesRefresh = setTimeout(function() { refreshBarcodes(); }, 1500);
        }

        // Add to notification bell for actionable items
        if (result !== 'added' && result !== 'queued') {
            var notifTitle = result === 'added_as_note' ? 'Mapping needed' :
                             result === 'unknown' ? 'Unknown barcode' : title;
            var notifMsg = food ? food + ' (' + barcode + ')' : barcode;
            var notifResult = result === 'unknown' ? 'unknown' :
                              result === 'added_as_note' ? 'needs_mapping' : result;
            addNotifItem({barcode: barcode, title: notifTitle, message: notifMsg, result: notifResult});
        }
    }
    connectSSE();

    // ─── Dashboard partial refresh ──────────────────────────────────────────────
    function refreshDashboard() {
        fetch('/api/dashboard').then(function(r) { return r.json(); }).then(function(d) {
            var el;
            el = document.getElementById('stat-total');
            if (el) el.textContent = d.total_barcodes;
            el = document.getElementById('stat-mapped');
            if (el) {
                el.textContent = d.mapped_count;
                el.className = 'h1 mb-0' + (d.mapped_count > 0 ? ' text-green' : '');
            }
            el = document.getElementById('stat-pending');
            if (el) {
                el.textContent = d.pending_count;
                el.className = 'h1 mb-0 text-' + (d.pending_count === 0 ? 'green' : 'yellow');
            }
            el = document.getElementById('stat-unknown');
            if (el) {
                el.textContent = d.unknown_count;
                el.className = 'h1 mb-0 text-' + (d.unknown_count === 0 ? 'green' : 'red');
            }
            el = document.getElementById('stat-queue');
            if (el) {
                el.textContent = d.queue_depth;
                el.className = 'h1 mb-0 text-' + (d.queue_depth === 0 ? 'green' : 'red');
            }
            var tbody = document.getElementById('recent-scans-body');
            if (tbody && d.recent_items) {
                var badgeMap = {mapped: 'green', queued: 'orange', unknown: 'red', pending: 'yellow'};
                var labelMap = {mapped: 'Mapped', queued: 'Queued', unknown: 'Unknown', pending: 'Pending'};
                var rows = '';
                d.recent_items.forEach(function(item) {
                    var bg = badgeMap[item.status] || 'secondary';
                    var foodCol = item.food_name
                        ? '<a href="/items/' + esc(item.food_id) + '">' + esc(item.food_name) + '</a>'
                        : esc(item.title);
                    rows += '<tr>'
                        + '<td><a href="/barcodes/' + esc(item.barcode) + '">' + esc(item.barcode) + '</a></td>'
                        + '<td>' + foodCol + '</td>'
                        + '<td>' + esc(item.source) + '</td>'
                        + '<td><span class="badge bg-' + bg + ' text-' + bg + '-fg">' + labelMap[item.status] + '</span></td>'
                        + '<td>' + esc(item.created_at) + '</td>'
                        + '</tr>';
                });
                if (!rows) rows = '<tr><td colspan="5" class="text-center text-secondary">No scans yet</td></tr>';
                tbody.innerHTML = rows;
            }
        });
    }

    // ─── Barcodes table live refresh ────────────────────────────────────────────
    function refreshBarcodes() {
        var params = new URLSearchParams(window.location.search);
        var status = params.get('status') || 'all';
        fetch('/api/barcodes?status=' + encodeURIComponent(status)).then(function(r) { return r.json(); }).then(function(d) {
            var tbody = document.getElementById('barcodes-tbody');
            if (!tbody || !d.items) return;
            var rows = '';
            d.items.forEach(function(item) {
                rows += '<tr>'
                    + '<td><a href="/barcodes/' + esc(item.barcode) + '">' + esc(item.barcode) + '</a></td>'
                    + '<td>' + esc(item.title) + '</td>'
                    + '<td>' + esc(item.brand) + '</td>'
                    + '<td>' + esc(item.source) + '</td>'
                    + '<td>';
                if (item.food_name) {
                    rows += '<a href="/items/' + esc(item.food_id) + '">' + esc(item.food_name) + '</a>'
                        + ' <span class="badge bg-azure text-azure-fg ms-1">' + esc(item.mapped_by) + '</span>';
                } else {
                    rows += '<span class="text-secondary">\u2014</span>';
                }
                rows += '</td><td>' + esc(item.created_at) + '</td></tr>';
            });
            if (!rows) rows = '<tr><td colspan="6" class="text-center text-secondary">No barcodes cached yet</td></tr>';
            tbody.innerHTML = rows;
        });
    }

    // ─── Notification Bell ──────────────────────────────────────────────────────
    var badge = document.getElementById('notif-badge');
    var notifDropdown = document.getElementById('notif-dropdown');
    var notifClose = document.getElementById('notif-close');
    if (notifClose && notifDropdown) {
        notifClose.addEventListener('click', function() {
            var dd = bootstrap.Dropdown.getOrCreateInstance(notifDropdown.querySelector('[data-bs-toggle="dropdown"]'));
            dd.hide();
        });
    }

    var list = document.getElementById('notif-list');
    var empty = document.getElementById('notif-empty');
    var markAllBtn = document.getElementById('notif-mark-all');
    var count = 0;

    function updateBadge() {
        if (count > 0) {
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
        empty.style.display = count > 0 ? 'none' : '';
    }

    function statusDotClass(result) {
        if (result === 'retry_failed' || result === 'broken') return 'bg-red';
        if (result === 'unknown') return 'bg-red';
        if (result === 'needs_mapping') return 'bg-yellow';
        if (result === 'auto_mapped') return 'bg-azure';
        return 'bg-secondary';
    }

    function priorityIcon(result) {
        if (result === 'retry_failed' || result === 'broken') return '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm text-danger" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/></svg>';
        if (result === 'unknown') return '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm text-danger" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M12 17l0 .01"/><path d="M12 13.5a1.5 1.5 0 0 1 1 -1.5a2.6 2.6 0 1 0 -3 -4"/></svg>';
        if (result === 'needs_mapping') return '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm text-warning" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 12h1m8 -9v1m8 8h1m-15.4 -6.4l.7 .7m12.1 -.7l-.7 .7"/><path d="M9 16a5 5 0 1 1 6 0a3.5 3.5 0 0 0 -1 3a2 2 0 0 1 -4 0a3.5 3.5 0 0 0 -1 -3"/><path d="M9.7 17l4.6 0"/></svg>';
        if (result === 'auto_mapped') return '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm text-azure" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M5 12l5 5l10 -10"/></svg>';
        return '';
    }

    function timeAgo(isoStr) {
        if (!isoStr) return '';
        var then = new Date(isoStr + (isoStr.endsWith('Z') ? '' : 'Z'));
        var now = new Date();
        var diff = Math.floor((now - then) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
        return then.toLocaleDateString();
    }

    function addNotifItem(n) {
        var link = '/barcodes/' + encodeURIComponent(n.barcode);
        var dotClass = statusDotClass(n.result);
        var icon = priorityIcon(n.result);
        var timeStr = timeAgo(n.created_at);
        var item = document.createElement('a');
        item.className = 'list-group-item list-group-item-action';
        item.href = link;
        if (n.id) item.dataset.id = n.id;
        item.dataset.barcode = n.barcode;
        item.innerHTML = '<div class="row align-items-center gx-2">'
            + '<div class="col-auto">' + icon + '</div>'
            + '<div class="col text-truncate">'
            + '<div class="d-flex justify-content-between align-items-center">'
            + '<span class="text-body fw-medium">' + esc(n.title) + '</span>'
            + (timeStr ? '<small class="text-secondary ms-2 text-nowrap">' + timeStr + '</small>' : '')
            + '</div>'
            + '<div class="d-block text-secondary text-truncate mt-n1 small">' + esc(n.message) + '</div>'
            + '</div>'
            + '<div class="col-auto"><span class="status-dot ' + dotClass + ' d-block"></span></div>'
            + '</div>';
        item.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications/read-barcode/' + encodeURIComponent(n.barcode), { method: 'POST' });
            item.remove();
            count--;
            updateBadge();
            window.location.href = link;
        });
        list.insertBefore(item, list.firstChild);
        count++;
        updateBadge();
    }

    // Expose for SSE handler
    window.addNotifItem = addNotifItem;

    // Load existing unread notifications
    fetch('/api/notifications').then(function(r) { return r.json(); }).then(function(items) {
        items.reverse().forEach(function(n) { addNotifItem(n); });
    });

    // Mark all as read
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications/read-all', { method: 'POST' }).then(function() {
                var items = list.querySelectorAll('.list-group-item:not(#notif-empty)');
                items.forEach(function(el) { el.remove(); });
                count = 0;
                updateBadge();
            });
        });
    }
})();

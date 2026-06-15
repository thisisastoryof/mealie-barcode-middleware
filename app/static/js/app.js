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

    // ─── Flash Toasts (URL-param driven) ───────────────────────────────────────
    // Show a toast when the page loads with ?saved=1 (or similar flags).
    // Cleans the URL param afterwards so refresh doesn't re-trigger.
    (function() {
        var params = new URLSearchParams(window.location.search);
        if (!params.has('saved')) return;
        var container = document.getElementById('scan-toasts');
        if (!container) return;

        var toast = document.createElement('div');
        toast.className = 'toast show';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.innerHTML = '<div class="toast-header">'
            + '<span class="avatar avatar-xs me-2 bg-success">'
            + '<i class="ti ti-check icon-sm text-white"></i></span>'
            + '<strong class="me-auto">Settings saved</strong>'
            + '<button type="button" class="ms-2 btn-close" data-bs-dismiss="toast" aria-label="Close"></button>'
            + '</div>'
            + '<div class="toast-body">Changes take effect immediately — no restart needed.</div>';
        container.prepend(toast);
        setTimeout(function() { if (toast.parentNode) toast.remove(); }, 6000);

        // Clean URL so refresh won't re-show
        params.delete('saved');
        var clean = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState(null, '', clean);
    })();

    // ─── Theme Toggle ────────────────────────────────────────────────────────────
    var toggleDark = document.getElementById('theme-toggle-dark');
    var toggleLight = document.getElementById('theme-toggle-light');
    var toggleDarkMobile = document.getElementById('theme-toggle-dark-mobile');
    var toggleLightMobile = document.getElementById('theme-toggle-light-mobile');

    function setTheme(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        // Persist to DB via API (fire-and-forget)
        fetch('/api/theme/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: theme })
        });
        // Clear any localStorage override since we're saving to DB
        localStorage.removeItem('theme-mode-override');
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
    // Close SSE cleanly before page unload to avoid console warnings
    window.addEventListener('beforeunload', function() {
        if (es) es.close();
    });
    function onScanEvent(e) {
        var data = JSON.parse(e.data);
        var barcode = data.barcode;
        var result = data.result;
        var item = data.item;

        var color, title, desc;
        if (result === 'added') {
            color = 'success';
            title = 'Added to shopping list';
            desc = item ? esc(item) + ' (' + esc(barcode) + ')' : esc(barcode);
        } else if (result === 'added_as_note') {
            color = 'success';
            title = 'Added to shopping list';
            desc = (item ? esc(item) + ' (' + esc(barcode) + ')' : esc(barcode)) + ' (via note)';
        } else if (result === 'queued') {
            color = 'warning';
            title = 'Queued for retry';
            desc = esc(item || barcode);
        } else if (result === 'needs_mapping') {
            color = 'warning';
            title = 'Not linked';
            desc = (item ? esc(item) + ' (' + esc(barcode) + ')' : esc(barcode)) + ' — tap to link';
        } else if (result === 'retry_failed') {
            color = 'danger';
            title = 'Retry failed';
            desc = esc(item || barcode) + ' — could not reach Mealie';
        } else {
            color = 'danger';
            title = 'Unknown barcode';
            desc = esc(barcode);
        }

        var link = '/barcodes/' + encodeURIComponent(barcode);
        var toastEl = document.createElement('div');
        toastEl.className = 'toast show';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.setAttribute('data-bs-autohide', 'false');
        toastEl.setAttribute('data-bs-toggle', 'toast');
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

        // Auto-dismiss after 8s (remove from DOM)
        setTimeout(function() { if (toastEl.parentNode) toastEl.remove(); }, 8000);

        // Browser notification — only for actionable results
        var isActionable = (result !== 'added' && result !== 'queued');
        if (isActionable) {
            ensureNotifPermission();
            if ('Notification' in window && Notification.permission === 'granted') {
                var body = item ? item + ' (' + barcode + ')' : barcode;
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
            window._barcodesRefresh = setTimeout(function() {
                // If empty state is showing and no real rows exist, reload
                var tbody = document.getElementById('barcodes-tbody');
                if (tbody && tbody.querySelector('.barcodes-empty-row') && !tbody.querySelector('tr:not(.barcodes-empty-row)')) {
                    window.location.reload();
                } else {
                    refreshBarcodes();
                }
            }, 1500);
        }

        // Live-refresh activities table
        if (window.location.pathname === '/activities') {
            clearTimeout(window._activitiesRefresh);
            window._activitiesRefresh = setTimeout(function() {
                var tbody = document.getElementById('activity-tbody');
                if (tbody && tbody.querySelector('.activity-empty-row') && !tbody.querySelector('tr:not(.activity-empty-row)')) {
                    window.location.reload();
                } else {
                    refreshActivities();
                }
            }, 1500);
        }

        // Refresh notification bell from server (debounced)
        clearTimeout(window._notifRefresh);
        window._notifRefresh = setTimeout(function() {
            if (window.refreshNotifications) window.refreshNotifications();
        }, 2000);
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

            // If no recent items from API, nothing to do for the table
            if (!d.recent_items || d.recent_items.length === 0) return;

            var tbody = document.getElementById('recent-scans-body');
            var badgeMap = {mapped: 'green', queued: 'orange', unknown: 'red', pending: 'yellow'};
            var labelMap = {mapped: 'Linked', queued: 'Queued', unknown: 'Unknown', pending: 'Pending'};

            // Build rows HTML
            var rows = '';
            d.recent_items.forEach(function(item) {
                var bg = badgeMap[item.status] || 'secondary';
                var itemCol = item.item_name
                    ? '<a href="/items/' + esc(item.item_id) + '">' + esc(item.item_name) + '</a>'
                    : esc(item.title);
                rows += '<tr>'
                    + '<td><a href="/barcodes/' + encodeURIComponent(item.barcode) + '">' + esc(item.barcode) + '</a></td>'
                    + '<td>' + itemCol + '</td>'
                    + '<td>' + esc(item.source) + '</td>'
                    + '<td><span class="badge bg-' + bg + ' text-' + bg + '-fg">' + labelMap[item.status] + '</span></td>'
                    + '<td>' + esc(item.created_at) + '</td>'
                    + '</tr>';
            });

            if (tbody) {
                // Table already exists — just update rows
                tbody.innerHTML = rows;
            } else {
                // Getting Started card is showing — replace it with the table
                var card = document.querySelector('.row-deck:last-child .card');
                if (card) {
                    card.innerHTML = '<div class="card-header"><h3 class="card-title">Recent Scans</h3></div>'
                        + '<div class="table-responsive"><table class="table table-vcenter card-table">'
                        + '<thead><tr><th>Barcode</th><th>Item</th><th>Source</th><th>Status</th><th>Scanned</th></tr></thead>'
                        + '<tbody id="recent-scans-body">' + rows + '</tbody>'
                        + '</table></div>';
                }
            }
        });
    }

    // ─── Barcodes table live refresh ────────────────────────────────────────────
    function refreshBarcodes() {
        var params = new URLSearchParams(window.location.search);
        var status = params.get('status') || 'all';
        var showMapped = (status !== 'pending' && status !== 'unknown');
        var colCount = showMapped ? 7 : 6;
        var statusBadge = {mapped: 'green', queued: 'orange', unknown: 'red', pending: 'yellow'};
        var statusLabel = {mapped: 'Linked', queued: 'Queued', unknown: 'Unknown', pending: 'Pending'};
        fetch('/api/barcodes?status=' + encodeURIComponent(status)).then(function(r) { return r.json(); }).then(function(d) {
            var tbody = document.getElementById('barcodes-tbody');
            if (!tbody || !d.items) return;
            var countEl = document.getElementById('barcodes-count');
            if (countEl) countEl.textContent = d.items.length + ' barcode' + (d.items.length !== 1 ? 's' : '');
            var rows = '';
            d.items.forEach(function(item) {
                var sColor = statusBadge[item.status] || 'yellow';
                var sText = statusLabel[item.status] || 'Pending';
                rows += '<tr>'
                    + '<td class="sort-barcode"><a href="/barcodes/' + encodeURIComponent(item.barcode) + '">' + esc(item.barcode) + '</a></td>'
                    + '<td class="sort-status"><span class="badge bg-' + sColor + ' text-' + sColor + '-fg">' + sText + '</span></td>'
                    + '<td class="sort-title">' + esc(item.title) + '</td>'
                    + '<td class="sort-brand">' + esc(item.brand) + '</td>';
                if (showMapped) {
                    rows += '<td class="sort-mapped">';
                    if (item.item_name) {
                        rows += '<a href="/items/' + esc(item.item_id) + '">' + esc(item.item_name) + '</a>';
                    } else {
                        rows += '<span class="text-secondary">\u2014</span>';
                    }
                    rows += '</td>';
                }
                rows += '<td class="sort-source">' + esc(item.source) + '</td>'
                    + '<td class="sort-scanned">' + esc(item.created_at) + '</td></tr>';
            });
            if (!rows) rows = '<tr class="barcodes-empty-row"><td colspan="' + colCount + '" class="text-center text-secondary">No barcodes cached yet</td></tr>';
            tbody.innerHTML = rows;
            if (window._barcodesTable) window._barcodesTable.reload();
        });
    }

    // ─── Activities table live refresh ──────────────────────────────────────────
    function refreshActivities() {
        var params = new URLSearchParams(window.location.search);
        var result = params.get('result') || 'all';
        fetch('/api/activities?result=' + encodeURIComponent(result)).then(function(r) { return r.json(); }).then(function(d) {
            var tbody = document.getElementById('activity-tbody');
            if (!tbody || !d.items) return;
            var badgeMap = {
                retry_failed: 'red', broken: 'red', unknown: 'red',
                needs_mapping: 'yellow', auto_mapped: 'azure',
                added: 'green', added_as_note: 'green', queued: 'purple'
            };
            var labelMap = {
                retry_failed: 'Retry Failed', broken: 'Broken', unknown: 'Unknown',
                needs_mapping: 'Not Linked', auto_mapped: 'Auto-linked',
                added: 'Added', added_as_note: 'Added', queued: 'Queued'
            };
            var rows = '';
            d.items.forEach(function(item) {
                var bg = badgeMap[item.result] || 'secondary';
                var label = labelMap[item.result] || item.result;
                var rowClass = item.is_read ? '' : ' table-active';
                rows += '<tr class="cursor-pointer' + rowClass + '" data-href="/barcodes/' + encodeURIComponent(item.barcode) + '">'
                    + '<td class="sort-status"><span class="badge bg-' + bg + ' text-' + bg + '-fg">' + esc(label) + '</span></td>'
                    + '<td class="sort-barcode">' + esc(item.barcode) + '</td>'
                    + '<td class="sort-title">' + esc(item.title) + '</td>'
                    + '<td class="sort-message text-secondary text-truncate col-message">' + esc(item.message) + '</td>'
                    + '<td class="sort-time text-secondary text-nowrap">' + esc(item.created_at) + '</td>'
                    + '</tr>';
            });
            if (!rows) rows = '<tr class="activity-empty-row"><td colspan="5" class="text-center text-secondary">No activity yet</td></tr>';
            tbody.innerHTML = rows;
            // Re-bind click handlers
            document.querySelectorAll('#activity-table tr[data-href]').forEach(function(row) {
                row.addEventListener('click', function() {
                    window.location.href = this.dataset.href;
                });
            });
            if (window._activitiesTable) window._activitiesTable.reload();
        });
    }

    // ─── Notification Bell ──────────────────────────────────────────────────────
    var badge = document.getElementById('notif-badge');

    var list = document.getElementById('notif-list');
    var empty = document.getElementById('notif-empty');
    var markAllBtn = document.getElementById('notif-mark-all');
    var clearReadBtn = document.getElementById('notif-clear-read');
    var unreadCount = 0;

    function updateBadge() {
        if (unreadCount > 0) {
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
        var totalItems = list.querySelectorAll('.list-group-item:not(#notif-empty)').length;
        empty.style.display = totalItems > 0 ? 'none' : '';
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
        var isRead = !!n.is_read;
        var item = document.createElement('a');
        item.className = 'list-group-item list-group-item-action' + (isRead ? ' text-secondary' : '');
        item.href = link;
        if (n.id) item.dataset.id = n.id;
        item.dataset.barcode = n.barcode;
        item.innerHTML = '<div class="row align-items-center gx-2">'
            + '<div class="col-auto">' + icon + '</div>'
            + '<div class="col text-truncate">'
            + '<div class="d-flex justify-content-between align-items-center">'
            + '<span class="' + (isRead ? 'text-secondary' : 'text-body fw-medium') + '">' + esc(n.title) + '</span>'
            + (timeStr ? '<small class="text-secondary ms-2 text-nowrap">' + timeStr + '</small>' : '')
            + '</div>'
            + '<div class="d-block text-secondary text-truncate mt-n1">' + esc(n.message) + '</div>'
            + '</div>'
            + '<div class="col-auto d-flex align-items-center gap-1">'
            + (isRead ? '' : '<span class="status-dot ' + dotClass + ' d-block"></span>')
            + '<span class="notif-dismiss" title="Dismiss">'
            + '<i class="ti ti-x icon icon-sm text-secondary"></i>'
            + '</span>'
            + '</div>'
            + '</div>';

        // Click notification → mark as read, navigate
        item.addEventListener('click', function(e) {
            // Don't navigate if dismiss button was clicked
            if (e.target.closest('.notif-dismiss')) return;
            e.preventDefault();
            if (!isRead) {
                fetch('/api/notifications/read-barcode/' + encodeURIComponent(n.barcode), { method: 'POST' });
                markItemRead(item);
                isRead = true;
                unreadCount--;
                updateBadge();
            }
            window.location.href = link;
        });

        // Dismiss button → remove from bell
        var dismissBtn = item.querySelector('.notif-dismiss');
        dismissBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (n.id) {
                fetch('/api/notifications/' + n.id + '/dismiss', { method: 'POST' });
            }
            if (!isRead) unreadCount--;
            item.remove();
            updateBadge();
        });

        list.insertBefore(item, list.firstChild);
        if (!isRead) unreadCount++;
        updateBadge();
    }

    function markItemRead(item) {
        item.classList.add('text-secondary');
        var title = item.querySelector('.text-body.fw-medium');
        if (title) {
            title.classList.remove('text-body', 'fw-medium');
            title.classList.add('text-secondary');
        }
        var dot = item.querySelector('.status-dot');
        if (dot) dot.remove();
    }

    // Expose for SSE handler
    window.addNotifItem = addNotifItem;

    // Reload bell from server (called on SSE events as failsafe)
    function reloadNotifications() {
        fetch('/api/notifications').then(function(r) { return r.json(); }).then(function(items) {
            // Clear existing
            var existing = list.querySelectorAll('.list-group-item:not(#notif-empty)');
            existing.forEach(function(el) { el.remove(); });
            unreadCount = 0;
            // Repopulate
            items.reverse().forEach(function(n) { addNotifItem(n); });
        });
    }
    window.refreshNotifications = reloadNotifications;

    // Load existing notifications
    reloadNotifications();

    // Mark all as read — dim all items but keep them visible
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications/read-all', { method: 'POST' }).then(function() {
                var items = list.querySelectorAll('.list-group-item:not(#notif-empty)');
                items.forEach(function(el) { markItemRead(el); });
                unreadCount = 0;
                updateBadge();
            });
        });
    }

    // Clear read — dismiss all read notifications from bell
    if (clearReadBtn) {
        clearReadBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications/dismiss-read', { method: 'POST' }).then(function() {
                var items = list.querySelectorAll('.list-group-item.text-secondary:not(#notif-empty)');
                items.forEach(function(el) { el.remove(); });
                updateBadge();
            });
        });
    }

    // Close button — remove "show" from the dropdown
    var closeBtn = document.getElementById('notif-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            var menu = closeBtn.closest('.dropdown-menu');
            if (menu) menu.classList.remove('show');
            var toggle = document.querySelector('#notif-dropdown [data-bs-toggle="dropdown"]');
            if (toggle) toggle.classList.remove('show');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        });
    }
})();

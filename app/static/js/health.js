/**
 * health.js — Dashboard health status polling with visibility awareness.
 */
(function() {
    'use strict';

    var indicator = document.getElementById('health-indicator');
    var statusEl = document.getElementById('health-status');
    if (!indicator || !statusEl) return;

    var timer = null;

    function pollHealth() {
        fetch('/health').then(function(r) { return r.json(); }).then(function(d) {
            var up = d.mealie_reachable;
            indicator.className = 'status-indicator status-' + (up ? 'green' : 'red') + (up ? ' status-indicator-animated' : '');
            statusEl.className = 'text-' + (up ? 'green' : 'red');
            statusEl.textContent = up ? 'Connected' : 'Unreachable';
        }).catch(function() {
            indicator.className = 'status-indicator status-red';
            statusEl.className = 'text-red';
            statusEl.textContent = 'Error';
        });
    }

    function start() {
        pollHealth();
        timer = setInterval(pollHealth, 30000);
    }

    function stop() {
        if (timer) { clearInterval(timer); timer = null; }
    }

    document.addEventListener('visibilitychange', function() {
        if (document.hidden) { stop(); } else { start(); }
    });

    start();
})();

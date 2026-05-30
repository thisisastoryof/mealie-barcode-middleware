/**
 * confirm-actions.js — Progressive enhancement for confirm dialogs and clipboard.
 * Replaces inline onsubmit/onclick handlers to comply with strict CSP.
 */
(function() {
    // Confirm before submit — any form with [data-confirm]
    document.querySelectorAll('form[data-confirm]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var msg = form.dataset.confirm;
            // Interpolate {name} from data-name attribute if present
            if (form.dataset.name) {
                msg = msg.replace('{name}', form.dataset.name);
            }
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

    // Clipboard copy — any button with [data-copy-target]
    document.querySelectorAll('[data-copy-target]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var target = document.getElementById(btn.dataset.copyTarget);
            if (target) navigator.clipboard.writeText(target.value);
        });
    });
})();

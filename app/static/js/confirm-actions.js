/**
 * confirm-actions.js — Tabler modal confirmations and clipboard.
 * Replaces browser confirm() with a styled modal dialog.
 */
(function() {
    var modalEl = document.getElementById('modal-confirm');
    if (!modalEl) return;
    var msgEl = document.getElementById('modal-confirm-msg');
    var okBtn = document.getElementById('modal-confirm-ok');
    var pendingAction = null;

    function getModal() {
        return bootstrap.Modal.getOrCreateInstance(modalEl);
    }

    okBtn.addEventListener('click', function() {
        getModal().hide();
        if (pendingAction) {
            pendingAction();
            pendingAction = null;
        }
    });

    function showConfirm(message, onConfirm) {
        msgEl.textContent = message;
        pendingAction = onConfirm;
        getModal().show();
    }

    // Confirm before submit — any form with [data-confirm]
    document.querySelectorAll('form[data-confirm]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            var msg = form.dataset.confirm;
            if (form.dataset.name) {
                msg = msg.replace('{name}', form.dataset.name);
            }
            showConfirm(msg, function() { form.submit(); });
        });
    });

    // Confirm + POST via dynamic form — any button with [data-confirm-post]
    document.querySelectorAll('[data-confirm-post]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var msg = btn.dataset.confirmMsg || 'Are you sure?';
            showConfirm(msg, function() {
                var f = document.createElement('form');
                f.method = 'post';
                f.action = btn.dataset.confirmPost;
                f.style.display = 'none';
                document.body.appendChild(f);
                f.submit();
            });
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

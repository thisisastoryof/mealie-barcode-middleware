/**
 * confirm-actions.js — Tabler modal confirmations and clipboard.
 * Replaces browser confirm() with a styled modal dialog.
 * Uses a hidden trigger + data-bs-toggle so Tabler handles the modal lifecycle.
 */
(function() {
    var modalEl = document.getElementById('modal-confirm');
    if (!modalEl) return;
    var titleEl = document.getElementById('modal-confirm-title');
    var msgEl = document.getElementById('modal-confirm-msg');
    var okBtn = document.getElementById('modal-confirm-ok');
    var pendingAction = null;

    // Hidden trigger that Tabler's built-in handler will pick up
    var trigger = document.createElement('button');
    trigger.setAttribute('data-bs-toggle', 'modal');
    trigger.setAttribute('data-bs-target', '#modal-confirm');
    trigger.style.display = 'none';
    document.body.appendChild(trigger);

    okBtn.addEventListener('click', function() {
        // Close the modal via the dismiss mechanism
        okBtn.setAttribute('data-bs-dismiss', 'modal');
        // Let Tabler close it, then run the action
        if (pendingAction) {
            var action = pendingAction;
            pendingAction = null;
            // Small delay to let modal close before navigation
            setTimeout(action, 50);
        }
    });

    // Remove the dismiss attribute after modal is hidden so it doesn't
    // auto-close next time the modal opens
    modalEl.addEventListener('hidden.bs.modal', function() {
        okBtn.removeAttribute('data-bs-dismiss');
        pendingAction = null;
    });

    function showConfirm(title, detail, onConfirm) {
        titleEl.textContent = title;
        msgEl.textContent = detail || '';
        pendingAction = onConfirm;
        trigger.click();
    }

    // Confirm before submit — any form with [data-confirm]
    document.querySelectorAll('form[data-confirm]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            var title = form.dataset.confirm;
            var detail = form.dataset.confirmDetail || '';
            showConfirm(title, detail, function() { form.submit(); });
        });
    });

    // Confirm + POST via dynamic form — any button with [data-confirm-post]
    document.querySelectorAll('[data-confirm-post]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var title = btn.dataset.confirmMsg || 'Are you sure?';
            var detail = btn.dataset.confirmDetail || '';
            showConfirm(title, detail, function() {
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

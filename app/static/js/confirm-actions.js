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
    var dismissBtn = modalEl.querySelector('[data-bs-dismiss="modal"]');
    var pendingAction = null;

    // Hidden trigger that Tabler's built-in handler will pick up
    var trigger = document.createElement('button');
    trigger.setAttribute('data-bs-toggle', 'modal');
    trigger.setAttribute('data-bs-target', '#modal-confirm');
    trigger.style.display = 'none';
    document.body.appendChild(trigger);

    okBtn.addEventListener('click', function() {
        if (pendingAction) {
            var action = pendingAction;
            pendingAction = null;
            // Close the modal via existing dismiss button, then run action
            dismissBtn.click();
            setTimeout(action, 50);
        }
    });

    // Reset state after modal is hidden
    modalEl.addEventListener('hidden.bs.modal', function() {
        pendingAction = null;
        okBtn.textContent = 'Delete';
    });

    function showConfirm(title, detail, onConfirm, btnLabel) {
        titleEl.textContent = title;
        msgEl.textContent = detail || '';
        okBtn.textContent = btnLabel || 'Delete';
        pendingAction = onConfirm;
        trigger.click();
    }

    // Expose for use by other page scripts
    window.showConfirm = showConfirm;

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
            if (target) {
                navigator.clipboard.writeText(target.value.trim()).then(function() {
                    // Brief visual feedback
                    var icon = btn.querySelector('.ti');
                    if (icon) {
                        icon.className = 'ti ti-check icon';
                        setTimeout(function() { icon.className = 'ti ti-copy icon'; }, 1500);
                    }
                });
            }
        });
    });
})();

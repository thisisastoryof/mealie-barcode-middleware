/**
 * settings-page.js — Client-side reset logic for the settings form.
 *
 * Every editable field has a data-default attribute with the env/default value.
 * A .btn-reset button sits next to it (inside an input-group or inline).
 * - Clicking reset restores the field to its default (client-side only).
 * - The reset button is disabled when the current value already matches the default.
 * - All changes (including resets) are persisted via the single Save button.
 */
(function () {
    'use strict';

    /**
     * Get the current value of a field in a comparable string form.
     */
    function fieldValue(el) {
        if (el.type === 'checkbox') return el.checked ? 'True' : 'False';
        return el.value;
    }

    /**
     * Update the disabled state of the reset button for a field.
     */
    function syncResetButton(field, btn) {
        var def = field.dataset.default;
        if (def === undefined) return;
        btn.disabled = (fieldValue(field) === def);
    }

    /**
     * Reset a field to its data-default value.
     */
    function resetField(field) {
        var def = field.dataset.default;
        if (def === undefined) return;
        if (field.type === 'checkbox') {
            field.checked = (def === 'True');
        } else if (field.tagName === 'SELECT') {
            field.value = def;
        } else {
            field.value = def;
        }
    }

    // Find all reset buttons and wire them up
    document.querySelectorAll('.btn-reset').forEach(function (btn) {
        // The field is the sibling input/select/checkbox in the same parent group
        var container = btn.parentElement;
        var field = container.querySelector('input, select');
        if (!field) return;

        // Initial state
        syncResetButton(field, btn);

        // On field change → update button state
        field.addEventListener('input', function () { syncResetButton(field, btn); });
        field.addEventListener('change', function () { syncResetButton(field, btn); });

        // On reset click → restore default, update button
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            resetField(field);
            syncResetButton(field, btn);
            // Trigger change event so any other listeners are notified
            field.dispatchEvent(new Event('change', { bubbles: true }));
        });
    });
})();

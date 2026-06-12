/**
 * settings-page.js — Client-side reset logic for the settings form.
 *
 * Every editable field has a data-default attribute with the env/default value.
 * A .btn-reset button sits next to it (separated layout or inline for toggles).
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
        // Walk up to the row/flex container and find the field inside it
        var container = btn.closest('.row, .d-flex');
        var field = container ? container.querySelector('input, select') : null;
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

    // ─── Appearance tab: live preview ────────────────────────────────────────
    // When the user changes a theme radio, apply the CSS custom properties
    // immediately so the page reflects the change before saving.
    var themeForm = document.querySelector('form[action="/settings/theme"]');
    if (themeForm) {
        // CSS lookup maps (from Tabler's :root definitions)
        var COLOR_CSS = {
            blue:   {hex:'#066fd1', rgb:'6,111,209'},
            azure:  {hex:'#4299e1', rgb:'66,153,225'},
            indigo: {hex:'#4263eb', rgb:'66,99,235'},
            purple: {hex:'#ae3ec9', rgb:'174,62,201'},
            pink:   {hex:'#d6336c', rgb:'214,51,108'},
            red:    {hex:'#d63939', rgb:'214,57,57'},
            orange: {hex:'#f76707', rgb:'247,103,7'},
            yellow: {hex:'#f59f00', rgb:'245,159,0'},
            lime:   {hex:'#74b816', rgb:'116,184,22'},
            green:  {hex:'#2fb344', rgb:'47,179,68'},
            teal:   {hex:'#0ca678', rgb:'12,166,120'},
            cyan:   {hex:'#17a2b8', rgb:'23,162,184'}
        };
        var FONT_CSS = {
            'sans-serif': '"Inter Var",Inter,-apple-system,BlinkMacSystemFont,San Francisco,Segoe UI,Roboto,Helvetica Neue,sans-serif',
            'serif':      'Georgia,Times New Roman,times,serif',
            'monospace':  'Monaco,Consolas,Liberation Mono,Courier New,monospace',
            'comic':      'Comic Sans MS,Comic Sans,Chalkboard SE,Comic Neue,sans-serif,cursive'
        };
        var GRAY_CSS = {
            gray:    null,
            slate:   {50:'#f8fafc',100:'#f1f5f9',200:'#e2e8f0',300:'#cbd5e1',400:'#94a3b8',500:'#64748b',600:'#475569',700:'#334155',800:'#1e293b',900:'#0f172a',950:'#020617'},
            zinc:    {50:'#fafafa',100:'#f4f4f5',200:'#e4e4e7',300:'#d4d4d8',400:'#a1a1aa',500:'#71717a',600:'#52525b',700:'#3f3f46',800:'#27272a',900:'#18181b',950:'#09090b'},
            neutral: {50:'#fafafa',100:'#f5f5f5',200:'#e5e5e5',300:'#d4d4d4',400:'#a3a3a3',500:'#737373',600:'#525252',700:'#404040',800:'#262626',900:'#171717',950:'#0a0a0a'},
            stone:   {50:'#fafaf9',100:'#f5f5f4',200:'#e7e5e4',300:'#d6d3d1',400:'#a8a29e',500:'#78716c',600:'#57534e',700:'#44403c',800:'#292524',900:'#1c1917',950:'#0c0a09'}
        };
        // Default values (Tabler stock)
        var DEFAULTS = {color:'blue', font:'sans-serif', base:'gray', radius:'1'};
        // Tabler default grays (to restore when switching back to "gray")
        var DEFAULT_GRAYS = {50:'#f9fafb',100:'#f3f4f6',200:'#e5e7eb',300:'#d1d5db',400:'#9ca3af',500:'#6b7280',600:'#4b5563',700:'#374151',800:'#1f2937',900:'#111827',950:'#030712'};

        var root = document.documentElement;

        function applyColor(name) {
            var c = COLOR_CSS[name];
            if (!c) return;
            root.style.setProperty('--tblr-primary', c.hex);
            root.style.setProperty('--tblr-primary-rgb', c.rgb);
        }

        function applyFont(name) {
            var stack = FONT_CSS[name];
            if (!stack) return;
            root.style.setProperty('--tblr-body-font-family', stack);
        }

        function applyBase(name) {
            var grays = GRAY_CSS[name];
            var vals = grays || DEFAULT_GRAYS;
            for (var step in vals) {
                root.style.setProperty('--tblr-gray-' + step, vals[step]);
            }
        }

        function applyRadius(val) {
            root.style.setProperty('--tblr-border-radius-scale', val);
        }

        function applyMode(val) {
            root.setAttribute('data-bs-theme', val);
        }

        themeForm.addEventListener('change', function(e) {
            var el = e.target;
            if (!el.name || el.type !== 'radio' || !el.checked) return;

            switch (el.name) {
                case 'theme_mode':  applyMode(el.value);   break;
                case 'theme_color': applyColor(el.value);  break;
                case 'theme_font':  applyFont(el.value);   break;
                case 'theme_base':  applyBase(el.value);   break;
                case 'theme_radius':applyRadius(el.value); break;
            }
        });
    }
})();

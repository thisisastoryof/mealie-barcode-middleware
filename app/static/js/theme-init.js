/* Apply theme before render to prevent FOUC.
 * Server renders the correct data-bs-theme* attributes on <html>,
 * so this script only needs to handle the navbar quick-toggle override
 * stored in localStorage (if the user toggled dark/light without saving).
 */
(function() {
    var override = localStorage.getItem('theme-mode-override');
    if (override) {
        document.documentElement.setAttribute('data-bs-theme', override);
    }
})();

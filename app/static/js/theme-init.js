/* Apply saved theme before render to prevent FOUC */
(function() {
    var t = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', t);
})();

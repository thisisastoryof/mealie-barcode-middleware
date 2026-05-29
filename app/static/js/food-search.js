/**
 * food-search.js — Autocomplete dropdown for barcode→food mapping.
 */
(function() {
    'use strict';

    var searchInput = document.getElementById('food-search');
    var resultsDiv = document.getElementById('food-results');
    var foodIdInput = document.getElementById('food-id-input');
    var mapBtn = document.getElementById('map-btn');
    var selectedDiv = document.getElementById('selected-food');
    var timeout = null;

    if (!searchInput) return;

    searchInput.addEventListener('input', function() {
        clearTimeout(timeout);
        var q = this.value.trim();
        if (q.length < 2) { resultsDiv.classList.remove('show'); resultsDiv.innerHTML = ''; return; }
        timeout = setTimeout(function() {
            fetch('/barcodes-search?q=' + encodeURIComponent(q))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    resultsDiv.innerHTML = '';
                    if (data.length === 0) { resultsDiv.classList.remove('show'); return; }
                    data.forEach(function(f) {
                        var a = document.createElement('a');
                        a.href = '#';
                        a.className = 'dropdown-item';
                        a.textContent = f.name;
                        a.addEventListener('click', function(e) {
                            e.preventDefault();
                            foodIdInput.value = f.id;
                            mapBtn.disabled = false;
                            selectedDiv.textContent = 'Selected: ' + f.name;
                            selectedDiv.classList.remove('d-none');
                            resultsDiv.classList.remove('show');
                            resultsDiv.innerHTML = '';
                            searchInput.value = f.name;
                        });
                        resultsDiv.appendChild(a);
                    });
                    resultsDiv.classList.add('show');
                });
        }, 300);
    });
})();

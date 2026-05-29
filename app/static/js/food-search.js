/**
 * food-search.js — Search foods and show results in the assign table.
 * Fuzzy candidates are shown by default; typing replaces them with search results.
 */
(function() {
    'use strict';

    var searchInput = document.getElementById('food-search');
    var tbody = document.getElementById('food-assign-tbody');
    var table = document.getElementById('food-assign-table');
    var timeout = null;

    if (!searchInput || !tbody || !table) return;

    var barcode = table.dataset.barcode;
    var originalRows = tbody.innerHTML;

    function buildRow(food) {
        var tr = document.createElement('tr');
        var tdName = document.createElement('td');
        var a = document.createElement('a');
        a.href = '/foods/' + food.id;
        a.textContent = food.name;
        tdName.appendChild(a);

        var tdScore = document.createElement('td');
        tdScore.innerHTML = '<span class="text-secondary">—</span>';

        var tdAction = document.createElement('td');
        tdAction.innerHTML = '<form method="post" action="/barcodes/' + barcode + '/map" class="d-inline">' +
            '<input type="hidden" name="food_id" value="' + food.id + '">' +
            '<button type="submit" class="btn btn-sm btn-primary">Map</button></form>';

        tr.appendChild(tdName);
        tr.appendChild(tdScore);
        tr.appendChild(tdAction);
        return tr;
    }

    searchInput.addEventListener('input', function() {
        clearTimeout(timeout);
        var q = this.value.trim();
        if (q.length < 2) {
            tbody.innerHTML = originalRows;
            return;
        }
        timeout = setTimeout(function() {
            fetch('/barcodes-search?q=' + encodeURIComponent(q))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-secondary">No foods found</td></tr>';
                        return;
                    }
                    data.forEach(function(f) {
                        tbody.appendChild(buildRow(f));
                    });
                });
        }, 300);
    });
})();

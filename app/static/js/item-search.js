/**
 * item-search.js — Search items and show results in the assign table.
 * Fuzzy candidates are shown by default; typing replaces them with search results.
 * Always shows a "Create & Map" row at the bottom when there's text in the search box.
 */
(function() {
    'use strict';

    var searchInput = document.getElementById('item-search');
    var tbody = document.getElementById('item-assign-tbody');
    var table = document.getElementById('item-assign-table');
    var timeout = null;

    if (!searchInput || !tbody || !table) return;

    var barcode = table.dataset.barcode;
    var originalRows = tbody.innerHTML;

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function buildCreateRow(query) {
        var tr = document.createElement('tr');
        tr.className = 'table-active';
        tr.innerHTML = '<td colspan="3" class="text-muted">' +
            '<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 5l0 14"/><path d="M5 12l14 0"/></svg>' +
            'Create <strong>"' + esc(query) + '"</strong> as new item' +
            '</td>' +
            '<td>' +
            '<form method="post" action="/barcodes/' + esc(barcode) + '/create-and-map" class="d-inline">' +
            '<input type="hidden" name="name" value="' + esc(query) + '">' +
            '<button type="submit" class="btn btn-sm btn-success">Create &amp; Link</button>' +
            '</form></td>';
        return tr;
    }

    function buildRow(item) {
        var tr = document.createElement('tr');
        var tdName = document.createElement('td');
        var a = document.createElement('a');
        a.href = '/items/' + item.id;
        a.textContent = item.name;
        tdName.appendChild(a);

        var tdSource = document.createElement('td');
        tdSource.className = 'text-secondary';
        tdSource.textContent = item.source === 'mealie' ? 'Mealie' : 'Custom';

        var tdScore = document.createElement('td');
        tdScore.innerHTML = '<span class="text-secondary">—</span>';

        var tdAction = document.createElement('td');
        tdAction.innerHTML = '<form method="post" action="/barcodes/' + barcode + '/map" class="d-inline">' +
            '<input type="hidden" name="item_id" value="' + item.id + '">' +
            '<button type="submit" class="btn btn-sm btn-primary">Link</button></form>';

        tr.appendChild(tdName);
        tr.appendChild(tdSource);
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
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No matching items</td></tr>';
                    } else {
                        data.forEach(function(f) {
                            tbody.appendChild(buildRow(f));
                        });
                    }
                    // Always append the create row as escape hatch
                    tbody.appendChild(buildCreateRow(q));
                });
        }, 300);
    });
})();

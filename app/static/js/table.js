/**
 * table.js — Reusable client-side sort, filter, and pagination for Tabler tables.
 *
 * Usage: call initAdvancedTable(options) with:
 *   tableId:      ID of the <table>
 *   searchId:     ID of the search <input>
 *   paginationId: ID of the pagination <ul>
 *   pageSizeId:   ID of the page-size label <span>
 *   defaultSort:  data-sort value for initial column (e.g. 'sort-name')
 *   numericCols:  array of data-sort values that should sort numerically
 *   emptyRowClass: class on the "no data" row to exclude from sorting
 */
function initAdvancedTable(opts) {
    'use strict';

    var table = document.getElementById(opts.tableId);
    if (!table) return;

    var tbody = table.querySelector('.table-tbody') || table.querySelector('tbody');
    var searchInput = document.getElementById(opts.searchId);
    var pagination = document.getElementById(opts.paginationId);
    var pageSizeLabel = document.getElementById(opts.pageSizeId);
    var emptyRowClass = opts.emptyRowClass || 'empty-row';
    var numericCols = opts.numericCols || [];

    var allRows = Array.from(tbody.querySelectorAll('tr:not(.' + emptyRowClass + ')'));
    var filteredRows = allRows.slice();
    var pageSize = 20;
    var currentPage = 1;
    var sortCol = opts.defaultSort || '';
    var sortAsc = opts.defaultAsc !== undefined ? opts.defaultAsc : true;

    function getText(row, col) {
        var td = row.querySelector('.' + col);
        return td ? td.textContent.trim().toLowerCase() : '';
    }

    function getNumeric(row, col) {
        var txt = getText(row, col);
        var n = parseFloat(txt);
        return isNaN(n) ? 0 : n;
    }

    function sortRows() {
        if (!sortCol) return;
        var isNumeric = numericCols.indexOf(sortCol) !== -1;
        filteredRows.sort(function(a, b) {
            var av, bv;
            if (isNumeric) {
                av = getNumeric(a, sortCol);
                bv = getNumeric(b, sortCol);
            } else {
                av = getText(a, sortCol);
                bv = getText(b, sortCol);
            }
            if (av < bv) return sortAsc ? -1 : 1;
            if (av > bv) return sortAsc ? 1 : -1;
            return 0;
        });
    }

    function filterRows() {
        var q = searchInput ? searchInput.value.toLowerCase() : '';
        filteredRows = allRows.filter(function(row) {
            if (!q) return true;
            return row.textContent.toLowerCase().indexOf(q) !== -1;
        });
        currentPage = 1;
        sortRows();
    }

    function render() {
        var totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
        if (currentPage > totalPages) currentPage = totalPages;

        // Hide all, show current page
        tbody.querySelectorAll('tr').forEach(function(r) { r.style.display = 'none'; });
        var start = (currentPage - 1) * pageSize;
        var end = start + pageSize;
        filteredRows.slice(start, end).forEach(function(r) { r.style.display = ''; });

        // Render pagination
        if (!pagination) return;
        pagination.innerHTML = '';
        if (totalPages <= 1) return;
        for (var i = 1; i <= totalPages; i++) {
            if (totalPages > 7 && i > 2 && i < totalPages - 1 && Math.abs(i - currentPage) > 1) {
                if (pagination.lastChild && !pagination.lastChild.classList.contains('disabled')) {
                    var ellipsis = document.createElement('li');
                    ellipsis.className = 'page-item disabled';
                    ellipsis.innerHTML = '<a class="page-link">\u2026</a>';
                    pagination.appendChild(ellipsis);
                }
                continue;
            }
            var li = document.createElement('li');
            li.className = 'page-item' + (i === currentPage ? ' active' : '');
            var a = document.createElement('a');
            a.className = 'page-link cursor-pointer';
            a.textContent = i;
            a.onclick = (function(page) { return function() { currentPage = page; render(); }; })(i);
            li.appendChild(a);
            pagination.appendChild(li);
        }
    }

    // Sort handlers on th buttons
    table.querySelectorAll('.table-sort').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var col = btn.dataset.sort;
            if (sortCol === col) {
                sortAsc = !sortAsc;
            } else {
                sortCol = col;
                sortAsc = true;
            }
            table.querySelectorAll('.table-sort').forEach(function(b) {
                b.classList.remove('active', 'asc', 'desc');
            });
            btn.classList.add('active', sortAsc ? 'asc' : 'desc');
            sortRows();
            currentPage = 1;
            render();
        });
    });

    // Search
    if (searchInput) {
        searchInput.addEventListener('input', function() { filterRows(); render(); });
    }

    // Page size
    document.querySelectorAll('[data-page-size]').forEach(function(a) {
        // Scope to the table's container
        if (table.closest('.card') && !table.closest('.card').contains(a)) return;
        a.addEventListener('click', function(e) {
            e.preventDefault();
            pageSize = parseInt(a.dataset.pageSize);
            if (pageSizeLabel) pageSizeLabel.textContent = pageSize;
            currentPage = 1;
            render();
        });
    });

    // Initial sort + render
    sortRows();
    render();
}

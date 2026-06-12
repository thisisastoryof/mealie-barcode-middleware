initAdvancedTable({
    tableId: 'items-table',
    searchId: 'items-table-search',
    paginationId: 'items-pagination',
    pageSizeId: 'page-size-label',
    defaultSort: 'sort-name',
    numericCols: ['sort-mappings'],
    emptyRowClass: 'items-empty-row'
});

// Focus the name input when the add-item modal opens
(function() {
    var modal = document.getElementById('modal-add-item');
    var input = document.getElementById('item-name');
    if (modal && input) {
        modal.addEventListener('shown.bs.modal', function() { input.focus(); });
    }
})();

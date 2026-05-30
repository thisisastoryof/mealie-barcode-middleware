window._activitiesTable = initAdvancedTable({
    tableId: 'activity-table',
    searchId: 'activity-table-search',
    paginationId: 'activity-pagination',
    pageSizeId: 'activity-page-size-label',
    defaultSort: 'sort-time',
    defaultAsc: false,
    numericCols: [],
    emptyRowClass: 'activity-empty-row'
});
// Make rows clickable
document.querySelectorAll('#activity-table tr[data-href]').forEach(function(row) {
    row.addEventListener('click', function() {
        window.location.href = this.dataset.href;
    });
});

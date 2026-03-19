const DatabaseExplorer = (() => {
    const TABLE_DEFINITIONS = [
        {
            key: 'games',
            label: 'games',
            path: 'data/backend/games.json',
            grain: 'One row per game',
            description: 'Canonical match register with squad, date, competition, result, score, and leadership fields.',
            sourceNote: 'Defined in backend.py and built from Google Sheets team sheets plus historical Pitchero reconciliation.'
        },
        {
            key: 'player_appearances',
            label: 'player_appearances',
            path: 'data/backend/player_appearances.json',
            grain: 'One row per player per game',
            description: 'Canonical appearance table with shirt number, position, unit, starter flag, and captaincy metadata.',
            sourceNote: 'Defined in backend.py and derived from canonical selections linked back to games.'
        },
        {
            key: 'lineouts',
            label: 'lineouts',
            path: 'data/backend/lineouts.json',
            grain: 'One row per lineout event',
            description: 'Detailed lineout event log including call, setup, thrower, jumper, and outcome.',
            sourceNote: 'Defined in backend.py; coverage depends on seasons where detailed lineout coding exists.'
        },
        {
            key: 'set_piece',
            label: 'set_piece',
            path: 'data/backend/set_piece.json',
            grain: 'One row per team per game',
            description: 'Per-match set piece summary including lineout, scrum, and 22m-entry conversion metrics.',
            sourceNote: 'Defined in backend.py; completeness depends on the underlying analysis sheets being filled in.'
        },
        {
            key: 'season_scorers',
            label: 'season_scorers',
            path: 'data/backend/season_scorers.json',
            grain: 'One row per player-season-squad',
            description: 'Seasonal scoring summary with tries, conversions, penalties, drop goals, and total points.',
            sourceNote: 'Defined in backend.py and blends modern canonical records with Pitchero-era scoring inputs.'
        },
        {
            key: 'players',
            label: 'players',
            path: 'data/backend/players.json',
            grain: 'One row per player',
            description: 'Player master table with roster metadata, first appearance context, totals, sponsor, and photo fields.',
            sourceNote: 'Defined in backend.py and assembled from appearances, games, lineouts, scorers, and reconciliation outputs.'
        },
    ];

    const state = {
        initialized: false,
        selectpickersInitialized: false,
        currentTableKey: TABLE_DEFINITIONS[0].key,
        columnGuideCollapsed: true,
        pageSize: 25,
        page: 1,
        sortColumn: null,
        sortDirection: 'asc',
        filters: {
            season: 'All',
            squad: 'All',
            gameType: 'All',
            search: ''
        }
    };

    const cache = new Map();
    const elements = {};
    const COLUMN_GUIDE_STORAGE_KEY = 'databaseColumnGuideCollapsed';

    const SELECTPICKER_OPTIONS = {
        dropupAuto: true,
        size: 'auto',
        width: '100%',
        maxOptions: false
    };

    function init() {
        if (state.initialized) {
            return;
        }

        elements.tableSelect = document.getElementById('databaseTableSelect');
        elements.seasonFilter = document.getElementById('databaseSeasonFilter');
        elements.squadFilter = document.getElementById('databaseSquadFilter');
        elements.gameTypeFilter = document.getElementById('databaseGameTypeFilter');
        elements.searchInput = document.getElementById('databaseSearchInput');
        elements.resetButton = document.getElementById('databaseResetFilters');
        elements.downloadButton = document.getElementById('databaseDownloadFiltered');
        elements.summaryCards = document.getElementById('databaseSummaryCards');
        elements.documentation = document.getElementById('databaseDocumentation');
        elements.tableBadge = document.getElementById('databaseTableBadge');
        elements.columnsSummary = document.getElementById('databaseColumnsSummary');
        elements.columnsTableBody = document.getElementById('databaseColumnsTableBody');
        elements.columnGuideToggle = document.getElementById('databaseColumnGuideToggle');
        elements.columnGuideContent = document.getElementById('databaseColumnGuideContent');
        elements.twoColumnGrid = document.querySelector('.database-two-column-grid');
        elements.tableHeading = document.getElementById('databaseTableHeading');
        elements.tableMeta = document.getElementById('databaseTableMeta');
        elements.tableHead = document.getElementById('databaseTableHead');
        elements.tableBody = document.getElementById('databaseTableBody');
        elements.paginationSummary = document.getElementById('databasePaginationSummary');
        elements.pageIndicator = document.getElementById('databasePageIndicator');
        elements.prevButton = document.getElementById('databasePrevPage');
        elements.nextButton = document.getElementById('databaseNextPage');

        initializeSelectpickers();
        populateTableSelect();
        restoreColumnGuideState();
        bindEvents();
        applyColumnGuideState();
        state.initialized = true;
    }

    async function load() {
        init();

        if (cache.has(state.currentTableKey)) {
            syncFilterControls();
            render();
            return;
        }

        await loadCurrentTable();
    }

    function bindEvents() {
        elements.tableSelect.addEventListener('change', async event => {
            state.currentTableKey = event.target.value;
            resetTableState();
            renderLoadingState('Loading table...');
            await loadCurrentTable();
        });

        elements.seasonFilter.addEventListener('change', event => {
            state.filters.season = event.target.value;
            state.page = 1;
            render();
        });

        elements.squadFilter.addEventListener('change', event => {
            state.filters.squad = event.target.value;
            state.page = 1;
            render();
        });

        elements.gameTypeFilter.addEventListener('change', event => {
            state.filters.gameType = event.target.value;
            state.page = 1;
            render();
        });

        elements.searchInput.addEventListener('input', event => {
            state.filters.search = event.target.value.trim();
            state.page = 1;
            render();
        });

        elements.resetButton.addEventListener('click', () => {
            resetFilters();
            syncFilterControls();
            render();
        });

        elements.downloadButton.addEventListener('click', () => {
            downloadFilteredRowsAsCsv();
        });

        if (elements.columnGuideToggle) {
            elements.columnGuideToggle.addEventListener('click', () => {
                state.columnGuideCollapsed = !state.columnGuideCollapsed;
                persistColumnGuideState();
                applyColumnGuideState();
            });
        }

        elements.prevButton.addEventListener('click', () => {
            if (state.page > 1) {
                state.page -= 1;
                render();
            }
        });

        elements.nextButton.addEventListener('click', () => {
            const totalPages = getTotalPages(getSortedRows(getFilteredRows()));
            if (state.page < totalPages) {
                state.page += 1;
                render();
            }
        });

        if (elements.tableHead) {
            elements.tableHead.addEventListener('click', event => {
            const button = event.target.closest('[data-sort-column]');
            if (!button) {
                return;
            }

            const column = button.getAttribute('data-sort-column');
            if (state.sortColumn === column) {
                state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                state.sortColumn = column;
                state.sortDirection = 'asc';
            }

            render();
            });
        }
    }

    function populateTableSelect() {
        elements.tableSelect.innerHTML = TABLE_DEFINITIONS.map(def => (
            `<option value="${escapeHtml(def.key)}">${escapeHtml(def.label)}</option>`
        )).join('');
        elements.tableSelect.value = state.currentTableKey;
        rebuildSelectpicker(elements.tableSelect);
    }

    async function loadCurrentTable() {
        const definition = getCurrentDefinition();

        try {
            if (!cache.has(definition.key)) {
                const response = await fetch(definition.path);
                if (!response.ok) {
                    throw new Error(`Failed to fetch ${definition.path} (${response.status})`);
                }
                const rows = await response.json();
                cache.set(definition.key, Array.isArray(rows) ? rows : []);
            }

            syncFilterControls();
            render();
        } catch (error) {
            console.error('Failed to load database table:', error);
            renderErrorState(`Unable to load ${definition.label}. ${error.message}`);
        }
    }

    function resetTableState() {
        state.page = 1;
        state.sortColumn = null;
        state.sortDirection = 'asc';
        resetFilters();
    }

    function resetFilters() {
        state.filters = {
            season: 'All',
            squad: 'All',
            gameType: 'All',
            search: ''
        };
    }

    function getCurrentDefinition() {
        return TABLE_DEFINITIONS.find(def => def.key === state.currentTableKey) || TABLE_DEFINITIONS[0];
    }

    function getCurrentRows() {
        return cache.get(state.currentTableKey) || [];
    }

    function getColumns(rows = getCurrentRows()) {
        const columnSet = new Set();
        rows.forEach(row => {
            Object.keys(row || {}).forEach(key => columnSet.add(key));
        });
        return Array.from(columnSet);
    }

    function syncFilterControls() {
        const rows = getCurrentRows();
        const definition = getCurrentDefinition();

        populateFilterSelect(elements.seasonFilter, getOptionsForColumn(rows, 'season'), state.filters.season, 'All seasons');
        populateFilterSelect(elements.squadFilter, getOptionsForColumn(rows, 'squad'), state.filters.squad, 'All squads');
        populateFilterSelect(elements.gameTypeFilter, getOptionsForColumn(rows, 'game_type'), state.filters.gameType, 'All game types');

        elements.searchInput.value = state.filters.search;
        setSelectpickerValue(elements.tableSelect, state.currentTableKey);

        if (elements.tableHeading) {
            elements.tableHeading.textContent = definition.label;
        }
    }

    function populateFilterSelect(select, options, selectedValue, allLabel) {
        const safeOptions = ['All', ...options];
        select.innerHTML = safeOptions.map(option => {
            const label = option === 'All' ? allLabel : option;
            return `<option value="${escapeAttribute(option)}">${escapeHtml(label)}</option>`;
        }).join('');

        const nextValue = safeOptions.includes(selectedValue) ? selectedValue : 'All';
        select.value = nextValue;

        if (select === elements.seasonFilter) {
            state.filters.season = nextValue;
        }
        if (select === elements.squadFilter) {
            state.filters.squad = nextValue;
        }
        if (select === elements.gameTypeFilter) {
            state.filters.gameType = nextValue;
        }

        rebuildSelectpicker(select);

    }

    function getOptionsForColumn(rows, column) {
        const values = rows
            .map(row => row?.[column])
            .filter(value => value !== null && value !== undefined && String(value).trim() !== '')
            .map(value => String(value));

        const uniqueValues = Array.from(new Set(values));
        const direction = column === 'season' || column === 'date' ? 'desc' : 'asc';
        return uniqueValues.sort((left, right) => compareValues(left, right, direction));
    }

    function render() {
        const rows = getCurrentRows();
        const columns = getColumns(rows);
        const filteredRows = getFilteredRows();
        const sortedRows = getSortedRows(filteredRows);
        const totalPages = getTotalPages(sortedRows);

        if (state.page > totalPages) {
            state.page = totalPages;
        }

        const pagedRows = getPagedRows(sortedRows);

        renderColumnsTable(rows, columns);
        renderMeta(rows, filteredRows, columns, totalPages);
        renderDataTable(columns, pagedRows);
        updatePagination(sortedRows, totalPages);
    }

    function renderColumnsTable(rows, columns) {
        if (!elements.columnsSummary || !elements.columnsTableBody) {
            return;
        }

        if (!columns.length) {
            elements.columnsSummary.textContent = 'No columns found for this table.';
            elements.columnsTableBody.innerHTML = '<tr><td colspan="3" class="database-empty-state">No column metadata available.</td></tr>';
            return;
        }

        elements.columnsSummary.textContent = `Completeness is based on non-empty values across ${formatNumber(rows.length)} rows.`;
        elements.columnsTableBody.innerHTML = columns.map(column => {
            const values = rows.map(row => row?.[column]);
            const populated = values.filter(value => value !== null && value !== undefined && String(value).trim() !== '');
            const completeness = rows.length ? `${Math.round((populated.length / rows.length) * 100)}%` : '0%';
            const example = populated.length ? formatCellValue(populated[0]) : 'No populated values';
            return `
                <tr>
                    <td><strong>${escapeHtml(column)}</strong></td>
                    <td>${escapeHtml(completeness)}</td>
                    <td title="${escapeAttribute(example)}">${escapeHtml(example)}</td>
                </tr>
            `;
        }).join('');

    }

    function restoreColumnGuideState() {
        try {
            const storedValue = window.localStorage.getItem(COLUMN_GUIDE_STORAGE_KEY);
            if (storedValue === 'true' || storedValue === 'false') {
                state.columnGuideCollapsed = storedValue === 'true';
            }
        } catch (error) {
            // Ignore storage failures and keep defaults.
        }
    }

    function persistColumnGuideState() {
        try {
            window.localStorage.setItem(COLUMN_GUIDE_STORAGE_KEY, String(state.columnGuideCollapsed));
        } catch (error) {
            // Ignore storage failures.
        }
    }

    function applyColumnGuideState() {
        const isCollapsed = state.columnGuideCollapsed;

        if (elements.columnGuideContent) {
            elements.columnGuideContent.hidden = isCollapsed;
        }

        if (elements.columnGuideToggle) {
            elements.columnGuideToggle.setAttribute('aria-expanded', String(!isCollapsed));
            elements.columnGuideToggle.textContent = isCollapsed ? 'Show Guide' : 'Hide Guide';
        }

        if (elements.twoColumnGrid) {
            elements.twoColumnGrid.classList.toggle('database-two-column-grid--guide-collapsed', isCollapsed);
        }
    }

    function renderMeta(rows, filteredRows) {
        if (!elements.tableMeta) {
            return;
        }

        const definition = getCurrentDefinition();

        elements.tableMeta.innerHTML = `
            <div>${escapeHtml(definition.grain)}.</div>
            <div class="database-muted">${escapeHtml(String(filteredRows.length))} of ${escapeHtml(String(rows.length))} rows match the current filters.</div>
        `;
    }

    function renderDataTable(columns, rows) {
        if (!elements.tableHead || !elements.tableBody) {
            return;
        }

        if (!columns.length) {
            elements.tableHead.innerHTML = '';
            elements.tableBody.innerHTML = '<tr><td class="database-empty-state">No rows available for this table.</td></tr>';
            return;
        }

        elements.tableHead.innerHTML = `
            <tr>
                ${columns.map(column => `
                    <th>
                        <button type="button" class="database-sort-button" data-sort-column="${escapeAttribute(column)}">
                            <span>${escapeHtml(column)}</span>
                            <span class="database-sort-indicator">${getSortIndicator(column)}</span>
                        </button>
                    </th>
                `).join('')}
            </tr>
        `;

        if (!rows.length) {
            elements.tableBody.innerHTML = `<tr><td colspan="${columns.length}" class="database-empty-state">No rows match the current filters.</td></tr>`;
            return;
        }

        elements.tableBody.innerHTML = rows.map(row => `
            <tr>
                ${columns.map(column => {
                    const cell = formatCellValue(row?.[column]);
                    return `<td title="${escapeAttribute(cell)}">${escapeHtml(cell)}</td>`;
                }).join('')}
            </tr>
        `).join('');
    }

    function updatePagination(sortedRows, totalPages) {
        if (!elements.paginationSummary || !elements.pageIndicator || !elements.prevButton || !elements.nextButton) {
            return;
        }

        const start = sortedRows.length ? ((state.page - 1) * state.pageSize) + 1 : 0;
        const end = Math.min(state.page * state.pageSize, sortedRows.length);
        elements.paginationSummary.textContent = `${formatNumber(sortedRows.length)} filtered rows`;
        elements.pageIndicator.textContent = totalPages ? `Page ${state.page} of ${totalPages} (${formatNumber(start)}-${formatNumber(end)})` : 'Page 1 of 1';
        elements.prevButton.disabled = state.page <= 1;
        elements.nextButton.disabled = state.page >= totalPages;
    }

    function getFilteredRows() {
        const rows = getCurrentRows();
        const query = state.filters.search.toLowerCase();

        return rows.filter(row => {
            if (state.filters.season !== 'All' && String(row?.season ?? '') !== state.filters.season) {
                return false;
            }

            if (state.filters.squad !== 'All' && String(row?.squad ?? '') !== state.filters.squad) {
                return false;
            }

            if (state.filters.gameType !== 'All' && String(row?.game_type ?? '') !== state.filters.gameType) {
                return false;
            }

            if (!query) {
                return true;
            }

            return Object.values(row || {}).some(value => String(value ?? '').toLowerCase().includes(query));
        });
    }

    function getSortedRows(rows) {
        const sorted = [...rows];
        const sortColumn = state.sortColumn || inferDefaultSortColumn(getColumns(rows));

        if (!sortColumn) {
            return sorted;
        }

        const direction = state.sortColumn ? state.sortDirection : inferDefaultSortDirection(sortColumn);
        sorted.sort((left, right) => compareValues(left?.[sortColumn], right?.[sortColumn], direction));
        return sorted;
    }

    function getPagedRows(rows) {
        const startIndex = (state.page - 1) * state.pageSize;
        return rows.slice(startIndex, startIndex + state.pageSize);
    }

    function getTotalPages(rows) {
        return Math.max(1, Math.ceil(rows.length / state.pageSize));
    }

    function downloadFilteredRowsAsCsv() {
        const columns = getColumns();
        const rows = getSortedRows(getFilteredRows());

        if (!rows.length || !columns.length) {
            return;
        }

        const csvLines = [
            columns.map(escapeCsvValue).join(','),
            ...rows.map(row => columns.map(column => escapeCsvValue(formatCellValue(row?.[column]))).join(','))
        ];

        const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${state.currentTableKey}-filtered.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    function renderLoadingState(message) {
        if (elements.summaryCards) elements.summaryCards.innerHTML = '';
        if (elements.documentation) elements.documentation.innerHTML = '';
        if (elements.columnsSummary) elements.columnsSummary.textContent = '';
        if (elements.columnsTableBody) elements.columnsTableBody.innerHTML = '';
        if (elements.tableMeta) elements.tableMeta.innerHTML = `<div class="database-empty-state">${escapeHtml(message)}</div>`;
        if (elements.tableHead) elements.tableHead.innerHTML = '';
        if (elements.tableBody) elements.tableBody.innerHTML = '';
        if (elements.paginationSummary) elements.paginationSummary.textContent = '';
        if (elements.pageIndicator) elements.pageIndicator.textContent = '';
    }

    function renderErrorState(message) {
        if (elements.summaryCards) elements.summaryCards.innerHTML = '';
        if (elements.documentation) elements.documentation.innerHTML = `<div class="database-doc-card"><h3>Load Error</h3><p>${escapeHtml(message)}</p></div>`;
        if (elements.columnsSummary) elements.columnsSummary.textContent = '';
        if (elements.columnsTableBody) elements.columnsTableBody.innerHTML = '';
        if (elements.tableMeta) elements.tableMeta.innerHTML = `<div class="database-empty-state">${escapeHtml(message)}</div>`;
        if (elements.tableHead) elements.tableHead.innerHTML = '';
        if (elements.tableBody) elements.tableBody.innerHTML = '';
        if (elements.paginationSummary) elements.paginationSummary.textContent = '';
        if (elements.pageIndicator) elements.pageIndicator.textContent = '';
    }

    function inferDefaultSortColumn(columns) {
        if (columns.includes('date')) {
            return 'date';
        }
        if (columns.includes('season')) {
            return 'season';
        }
        if (columns.includes('player')) {
            return 'player';
        }
        if (columns.includes('name')) {
            return 'name';
        }
        return columns[0] || null;
    }

    function inferDefaultSortDirection(column) {
        return column === 'date' || column === 'season' ? 'desc' : 'asc';
    }

    function compareValues(left, right, direction) {
        const leftValue = normalizeSortValue(left);
        const rightValue = normalizeSortValue(right);

        if (leftValue < rightValue) {
            return direction === 'asc' ? -1 : 1;
        }
        if (leftValue > rightValue) {
            return direction === 'asc' ? 1 : -1;
        }
        return 0;
    }

    function normalizeSortValue(value) {
        if (value === null || value === undefined || value === '') {
            return '';
        }

        const numberValue = Number(value);
        if (!Number.isNaN(numberValue) && String(value).trim() !== '') {
            return numberValue;
        }

        const dateValue = Date.parse(value);
        if (!Number.isNaN(dateValue) && typeof value === 'string' && value.includes('-')) {
            return dateValue;
        }

        return String(value).toLowerCase();
    }

    function getSortIndicator(column) {
        if (state.sortColumn !== column) {
            return '↕';
        }
        return state.sortDirection === 'asc' ? '↑' : '↓';
    }

    function formatCellValue(value) {
        if (value === null || value === undefined || value === '') {
            return '—';
        }
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        return String(value);
    }

    function formatNumber(value) {
        if (value === null || value === undefined || value === '') {
            return '0';
        }
        return new Intl.NumberFormat('en-GB').format(Number(value));
    }

    function setSelectpickerValue(select, value) {
        if (!select) {
            return;
        }

        if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.selectpicker) {
            select.value = value;
            return;
        }

        const $select = window.jQuery(select);
        if ($select.data('selectpicker')) {
            $select.selectpicker('val', value);
            return;
        }

        select.value = value;
    }

    function rebuildSelectpicker(select) {
        if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.selectpicker || !select) {
            return;
        }

        const $select = window.jQuery(select);
        const currentValue = select.value;

        if ($select.data('selectpicker')) {
            $select.selectpicker('destroy');
        }

        $select.selectpicker(SELECTPICKER_OPTIONS);
        if (currentValue !== null && currentValue !== undefined) {
            $select.selectpicker('val', currentValue);
        }
    }

    function initializeSelectpickers() {
        if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.selectpicker || state.selectpickersInitialized) {
            return;
        }

        [
            elements.tableSelect,
            elements.seasonFilter,
            elements.squadFilter,
            elements.gameTypeFilter,
        ].filter(Boolean).forEach(select => {
            rebuildSelectpicker(select);
        });

        state.selectpickersInitialized = true;
    }

    function escapeCsvValue(value) {
        return `"${String(value).replace(/"/g, '""')}"`;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, '&#96;');
    }

    return {
        load
    };
})();

window.DatabaseExplorer = DatabaseExplorer;
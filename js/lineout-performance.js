(function () {
    const LINEOUT_H2H_SPEC_PATH = 'data/charts/lineout_h2h.json';
    const LINEOUT_BREAKDOWN_SOURCE_PATH = 'data/charts/lineout_breakdown_source.json';
    const BREAKDOWN_MIN_ATTEMPTS = 10;

    const PANEL_SPECS = [
        {
            field: 'numbers',
            fieldLabel: 'Numbers',
            containerId: 'lineoutPerfBreakdownNumbersChart',
            tableHeadId: 'lineoutPerfBreakdownNumbersTableHead',
            tableBodyId: 'lineoutPerfBreakdownNumbersTableBody',
            path: 'data/charts/lineout_breakdown_numbers.json',
            trendContainerId: 'lineoutTrendNumbersChart',
            trendPath: 'data/charts/lineout_trend_numbers.json',
            emptyMessage: 'Numbers breakdown unavailable.',
            emptyTableMessage: 'No numbers breakdown rows match the current filters.',
            sort: ['4', '5', '6', '7'],
        },
        {
            field: 'area',
            fieldLabel: 'Zone',
            containerId: 'lineoutPerfBreakdownAreaChart',
            tableHeadId: 'lineoutPerfBreakdownAreaTableHead',
            tableBodyId: 'lineoutPerfBreakdownAreaTableBody',
            path: 'data/charts/lineout_breakdown_area.json',
            trendContainerId: 'lineoutTrendAreaChart',
            trendPath: 'data/charts/lineout_trend_area.json',
            emptyMessage: 'Zone breakdown unavailable.',
            emptyTableMessage: 'No zone breakdown rows match the current filters.',
            sort: ['Front', 'Middle', 'Back'],
        },
        {
            field: 'jumper',
            fieldLabel: 'Jumper',
            containerId: 'lineoutPerfBreakdownJumperChart',
            tableHeadId: 'lineoutPerfBreakdownJumperTableHead',
            tableBodyId: 'lineoutPerfBreakdownJumperTableBody',
            path: 'data/charts/lineout_breakdown_jumper.json',
            trendContainerId: 'lineoutTrendJumperChart',
            trendPath: 'data/charts/lineout_trend_jumper.json',
            emptyMessage: 'Jumper breakdown unavailable.',
            emptyTableMessage: 'No jumper breakdown rows match the current filters.',
            sort: '-y',
            fullNameField: 'jumper_name',
        },
        {
            field: 'thrower',
            fieldLabel: 'Thrower',
            containerId: 'lineoutPerfBreakdownThrowerChart',
            tableHeadId: 'lineoutPerfBreakdownThrowerTableHead',
            tableBodyId: 'lineoutPerfBreakdownThrowerTableBody',
            path: 'data/charts/lineout_breakdown_thrower.json',
            trendContainerId: 'lineoutTrendThrowerChart',
            trendPath: 'data/charts/lineout_trend_thrower.json',
            emptyMessage: 'Thrower breakdown unavailable.',
            emptyTableMessage: 'No thrower breakdown rows match the current filters.',
            sort: '-y',
            fullNameField: 'thrower_name',
        },
        {
            field: 'play',
            fieldLabel: 'Play',
            containerId: 'lineoutPerfBreakdownPlayChart',
            tableHeadId: 'lineoutPerfBreakdownPlayTableHead',
            tableBodyId: 'lineoutPerfBreakdownPlayTableBody',
            path: 'data/charts/lineout_breakdown_play.json',
            trendContainerId: 'lineoutTrendPlayChart',
            trendPath: 'data/charts/lineout_trend_play.json',
            emptyMessage: 'Play breakdown unavailable.',
            emptyTableMessage: 'No play breakdown rows match the current filters.',
            sort: ['Hot', 'Cold', 'Lost'],
            attemptsOnly: true,
        },
        {
            field: 'season',
            fieldLabel: 'Season',
            containerId: 'lineoutPerfBreakdownSeasonChart',
            tableHeadId: 'lineoutPerfBreakdownSeasonTableHead',
            tableBodyId: 'lineoutPerfBreakdownSeasonTableBody',
            path: 'data/charts/lineout_breakdown_season.json',
            trendContainerId: null,
            trendPath: null,
            emptyMessage: 'Season breakdown unavailable.',
            emptyTableMessage: 'No season breakdown rows match the current filters.',
            sort: 'season_asc',
        },
    ];

    const ANALYSIS_SIGNAL_IDS = {
        loSquad: 'lineoutFilterSquad',
        loSeason: 'lineoutFilterSeason',
        loGameType: 'lineoutFilterGameType',
        loThrower: 'lineoutFilterThrower',
        loJumper: 'lineoutFilterJumper',
        loArea: 'lineoutFilterArea',
        loNumbers: 'lineoutFilterNumbers',
    };

    const H2H_SIGNAL_IDS = {
        h2hSquadFilter: 'lineoutFilterSquad',
        h2hSeasonFilter: 'lineoutFilterSeason',
        h2hGameTypeFilter: 'lineoutFilterGameType',
        h2hOppositionFilter: 'h2hFilterOpposition',
        h2hTeamHighlight: 'h2hFilterTeamHighlight',
        h2hOutcomeHighlight: 'h2hFilterOutcomeHighlight',
    };

    const views = new Map();
    let lineoutH2HBaseSpec = null;
    let lineoutH2HLayoutKey = null;
    let lineoutBreakdownSourceRows = [];

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, '&#96;');
    }

    async function fetchJson(path) {
        const separator = path.includes('?') ? '&' : '?';
        const requestPath = `${path}${separator}v=${encodeURIComponent(String(Date.now()))}`;
        const response = await fetch(requestPath, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Failed to fetch ${path} (${response.status})`);
        }
        return response.json();
    }

    function populateSelect(id, values, allLabel) {
        const select = document.getElementById(id);
        if (!select) return;
        const currentValue = select.value;
        select.innerHTML = '';
        const allOption = document.createElement('option');
        allOption.value = 'All';
        allOption.textContent = allLabel;
        select.appendChild(allOption);
        values.forEach((value) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
        select.value = Array.from(select.options).some((option) => option.value === currentValue) ? currentValue : 'All';
        rebuildBootstrapSelect(select);
    }

    function seasonSort(a, b) {
        const ay = parseInt(String(a).slice(0, 4), 10);
        const by = parseInt(String(b).slice(0, 4), 10);
        return ay - by;
    }

    function toOppositionClubName(opposition) {
        const text = String(opposition || 'Unknown').trim();
        const club = text.replace(/\s+(?:I{1,6}|[1-6](?:st|nd|rd|th)?|A|B)(?:\s+XV)?$/i, '').trim();
        return club || 'Unknown';
    }

    function setSignalFromControl(view, signalName, controlId, fallback = 'All') {
        if (!view) return;
        const element = document.getElementById(controlId);
        view.signal(signalName, element ? element.value : fallback);
    }

    function enforceH2HFilterExclusivity(changedControlId) {
        const teamSelect = document.getElementById('h2hFilterTeamHighlight');
        const outcomeSelect = document.getElementById('h2hFilterOutcomeHighlight');
        if (!teamSelect || !outcomeSelect) return;

        if (changedControlId === 'h2hFilterTeamHighlight' && teamSelect.value !== 'All') {
            outcomeSelect.value = 'All';
        }

        if (changedControlId === 'h2hFilterOutcomeHighlight' && outcomeSelect.value !== 'All') {
            teamSelect.value = 'All';
        }
    }

    function getControlValue(id, fallback = 'All') {
        const element = document.getElementById(id);
        return element ? element.value : fallback;
    }

    function rowMatchesAnalysisFilters(row) {
        const squad = getControlValue('lineoutFilterSquad');
        if (squad !== 'All' && String(row?.squad || '') !== squad) return false;

        const season = getControlValue('lineoutFilterSeason');
        if (season !== 'All' && String(row?.season || '') !== season) return false;

        const gameType = getControlValue('lineoutFilterGameType');
        const allowedGameTypes = getAllowedGameTypes(gameType);
        if (allowedGameTypes && !allowedGameTypes.has(String(row?.game_type || 'Unknown'))) return false;
        if (!allowedGameTypes && gameType !== 'All' && String(row?.game_type || 'Unknown') !== gameType) return false;

        const thrower = getControlValue('lineoutFilterThrower');
        if (thrower !== 'All' && String(row?.thrower || '') !== thrower) return false;

        const jumper = getControlValue('lineoutFilterJumper');
        if (jumper !== 'All' && String(row?.jumper || '') !== jumper) return false;

        const area = getControlValue('lineoutFilterArea');
        if (area !== 'All' && String(row?.area || '') !== area) return false;

        const numbers = getControlValue('lineoutFilterNumbers');
        if (numbers !== 'All' && String(row?.numbers || '') !== numbers) return false;

        return true;
    }

    function sortBreakdownRows(rows, spec) {
        const sortedRows = [...rows];
        if (Array.isArray(spec.sort)) {
            const order = new Map(spec.sort.map((value, index) => [String(value), index]));
            sortedRows.sort((a, b) => {
                const orderA = order.has(a.value) ? order.get(a.value) : Number.MAX_SAFE_INTEGER;
                const orderB = order.has(b.value) ? order.get(b.value) : Number.MAX_SAFE_INTEGER;
                if (orderA !== orderB) return orderA - orderB;
                if (b.attempts !== a.attempts) return b.attempts - a.attempts;
                return a.value.localeCompare(b.value);
            });
            return sortedRows;
        }

        if (spec.sort === 'season_asc') {
            sortedRows.sort((a, b) => seasonSort(a.value, b.value));
            return sortedRows;
        }

        sortedRows.sort((a, b) => {
            if (b.attempts !== a.attempts) return b.attempts - a.attempts;
            return a.value.localeCompare(b.value);
        });
        return sortedRows;
    }

    function aggregateLineoutBreakdownRows(spec) {
        const grouped = new Map();

        lineoutBreakdownSourceRows.filter(rowMatchesAnalysisFilters).forEach((row) => {
            const value = String(row?.[spec.field] || 'Unknown');
            const fullNameValue = spec.fullNameField ? String(row?.[spec.fullNameField] || value) : null;
            const key = spec.fullNameField ? `${value}||${fullNameValue}` : value;
            if (!grouped.has(key)) {
                grouped.set(key, {
                    value,
                    fullNameValue,
                    attempts: 0,
                    won: 0,
                    bySeason: {},
                });
            }

            const entry = grouped.get(key);
            const season = String(row?.season || 'Unknown');
            entry.attempts += 1;
            entry.won += Number(row?.won || 0);
            if (!entry.bySeason[season]) {
                entry.bySeason[season] = { attempts: 0, won: 0 };
            }
            entry.bySeason[season].attempts += 1;
            entry.bySeason[season].won += Number(row?.won || 0);
        });

        return sortBreakdownRows(
            Array.from(grouped.values())
                .map((row) => ({
                    ...row,
                    successRate: row.attempts > 0 ? row.won / row.attempts : 0,
                }))
                .filter((row) => row.attempts >= BREAKDOWN_MIN_ATTEMPTS),
            spec,
        );
    }

    function formatPercentage(value) {
        return `${Math.round(Number(value || 0) * 100)}%`;
    }

    function formatWonAttempts(won, attempts) {
        return `${won}/${attempts}`;
    }

    const BREAKDOWN_BADGE_COLORS = {
        numbers: { '4': { bg: 'var(--accent-color)', fg: 'var(--primary-color)' }, '5': { bg: 'var(--primary-color)', fg: '#fff' }, '6': { bg: '#994C4C', fg: '#fff' }, '7': { bg: 'var(--red-color)', fg: '#fff' } },
        area: { 'Front': { bg: 'var(--red-color)', fg: '#fff' }, 'Middle': { bg: 'var(--amber-color)', fg: 'var(--primary-color)' }, 'Back': { bg: 'var(--green-color)', fg: '#fff' } },
        play: { 'Hot': { bg: '#fff', fg: '#000', border: true }, 'Cold': { bg: 'blue', fg: '#fff' }, 'Lost': { bg: 'var(--red-color)', fg: '#fff' } },
    };

    function renderBreakdownValueCell(spec, row) {
        const badgeColors = BREAKDOWN_BADGE_COLORS[spec.field];
        // If field is "numbers", append "-man" to value in badge, but not in tooltip or table sorting
        const valueForBadge = spec.field === 'numbers' ? `${row.value}-man` : row.value;

        if (badgeColors) {
            const colors = badgeColors[row.value];
            if (colors) {
                const style = `background:${colors.bg};color:${colors.fg};` + (colors.border ? 'border:1px solid #dee2e6;' : '');
                return `<span class="badge rounded-pill" style="${style}">${escapeHtml(valueForBadge)}</span>`;
            }
            return `<span class="badge rounded-pill bg-secondary">${escapeHtml(row.value)}</span>`;
        }

        if (spec.fullNameField) {
            return escapeHtml(row.fullNameValue || row.value);
        }

        return escapeHtml(row.value);
    }

    function renderBreakdownTable(spec) {
        const tableHead = document.getElementById(spec.tableHeadId);
        const tableBody = document.getElementById(spec.tableBodyId);
        if (!tableHead || !tableBody) return;
        tableHead.classList.add('table-dark');

        const rows = aggregateLineoutBreakdownRows(spec);
        const seasonColumns = spec.field === 'season'
            ? []
            : Array.from(
                new Set(
                    rows.flatMap((row) => Object.keys(row.bySeason || {})),
                ),
            ).sort(seasonSort);

        if (spec.attemptsOnly) {
            // Play table: show attempts only (no won/attempts ratio or success rate).
            const seasonHeaderCells = seasonColumns
                .map((season) => `<th class="text-center">${escapeHtml(season)}</th>`)
                .join('');

            tableHead.innerHTML = `
                <tr>
                    <th>${escapeHtml(spec.fieldLabel)}</th>
                    <th class="text-center">Total</th>
                    ${seasonHeaderCells}
                </tr>
            `;

            if (!rows.length) {
                const columnCount = 2 + seasonColumns.length;
                tableBody.innerHTML = `<tr><td colspan="${columnCount}" class="text-center">${escapeHtml(spec.emptyTableMessage)}</td></tr>`;
                return;
            }

            tableBody.innerHTML = rows.map((row) => `
                <tr>
                    <td>${renderBreakdownValueCell(spec, row)}</td>
                    <td class="text-end border-end fw-bold">${row.attempts}</td>
                    ${seasonColumns.map((season) => {
                        const stats = row.bySeason?.[season] || null;
                        if (!stats || !stats.attempts) {
                            return '<td class="text-end text-muted border-end">-</td>';
                        }
                        return `<td class="text-end border-end">${stats.attempts}</td>`;
                    }).join('')}
                </tr>
            `).join('');
            return;
        }

        const seasonHeaderCells = seasonColumns
            .map((season) => `<th class="text-center" colspan="2">${escapeHtml(season)}</th>`)
            .join('');

        tableHead.innerHTML = `
            <tr>
                <th>${escapeHtml(spec.fieldLabel)}</th>
                <th class="text-center" colspan="2">Total Success</th>
                ${seasonHeaderCells}
            </tr>
        `;

        if (!rows.length) {
            const columnCount = 3 + (seasonColumns.length * 2);
            tableBody.innerHTML = `<tr><td colspan="${columnCount}" class="text-center">${escapeHtml(spec.emptyTableMessage)}</td></tr>`;
            return;
        }

        tableBody.innerHTML = rows.map((row) => `
            <tr>
                <td>${renderBreakdownValueCell(spec, row)}</td>
                <td class="text-end">${row.won}/${row.attempts}</td>
                <td class="border-end text-end fw-bold" title="${escapeAttribute(formatPercentage(row.successRate))}">${escapeHtml(formatPercentage(row.successRate))}</td>
                ${seasonColumns.map((season) => {
                    const stats = row.bySeason?.[season] || null;
                    if (!stats || !stats.attempts) {
                        return '<td class="text-end text-muted">-</td><td class="text-end text-muted">-</td>';
                    }
                    const seasonSuccess = stats.won / stats.attempts;
                    return `<td class="text-end">${stats.won}/${stats.attempts}</td><td class="border-end text-end fw-bold" title="${escapeAttribute(formatPercentage(seasonSuccess))}">${escapeHtml(formatPercentage(seasonSuccess))}</td>`;
                }).join('')}
            </tr>
        `).join('');
    }

    function renderBreakdownTables() {
        PANEL_SPECS.forEach(renderBreakdownTable);
    }

    async function applyFiltersToViews() {
        const pending = [];

        PANEL_SPECS.forEach(({ containerId, trendContainerId }) => {
            [containerId, trendContainerId].forEach((id) => {
                if (!id) return;
                const view = views.get(id);
                if (!view) return;
                Object.entries(ANALYSIS_SIGNAL_IDS).forEach(([signalName, controlId]) => {
                    setSignalFromControl(view, signalName, controlId);
                });
                pending.push(view.runAsync());
            });
        });

        const successView = views.get('setPieceLineoutChart');
        if (successView) {
            setSignalFromControl(successView, 'spSquadParam', 'lineoutFilterSquad');
            pending.push(successView.runAsync());
        }

        await Promise.all(pending);
        renderBreakdownTables();
    }

    async function loadFilterOptions() {
        const lineoutSource = await fetchJson(LINEOUT_BREAKDOWN_SOURCE_PATH);
        lineoutBreakdownSourceRows = Array.isArray(lineoutSource) ? lineoutSource : [];

        populateSelect(
            'lineoutFilterSeason',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.season || '')).filter(Boolean))).sort(seasonSort).reverse(),
            'All Seasons',
        );
        populateSelect(
            'lineoutFilterThrower',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.thrower || 'Unknown')))).sort(),
            'All Throwers',
        );
        populateSelect(
            'lineoutFilterJumper',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.jumper || 'Unknown')))).sort(),
            'All Jumpers',
        );
        populateSelect(
            'lineoutFilterArea',
            ['Front', 'Middle', 'Back'].filter((value) => lineoutBreakdownSourceRows.some((row) => String(row?.area || '') === value)),
            'All Zones',
        );
        populateSelect(
            'lineoutFilterNumbers',
            ['4', '5', '6', '7'].filter((value) => lineoutBreakdownSourceRows.some((row) => String(row?.numbers || '') === value)),
            'All Numbers',
        );

        const h2hOppositionSelect = document.getElementById('h2hFilterOpposition');
        if (h2hOppositionSelect) {
            const [setPieceRaw, gamesRaw] = await Promise.all([
                fetchJson('data/backend/set_piece.json'),
                fetchJson('data/backend/games.json'),
            ]);
            const gamesById = new Map((Array.isArray(gamesRaw) ? gamesRaw : []).map((game) => [game.game_id, game]));
            const setPieceRows = (Array.isArray(setPieceRaw) ? setPieceRaw : []).map((row) => {
                const game = gamesById.get(row.game_id) || {};
                return { opposition_club: toOppositionClubName(row.opposition || game.opposition || 'Unknown') };
            });
            populateSelect('h2hFilterOpposition', Array.from(new Set(setPieceRows.map((row) => row.opposition_club))).sort(), 'All Opponents');
        }
    }

    async function loadInteractiveCharts() {
        await Promise.all(PANEL_SPECS.map(async ({ containerId, path, emptyMessage, trendContainerId, trendPath }) => {
            const view = await renderChartSpecFromPath(containerId, path, emptyMessage);
            if (view) views.set(containerId, view);

            if (trendContainerId && trendPath) {
                const trendView = await renderChartSpecFromPath(trendContainerId, trendPath, `${emptyMessage.replace('breakdown', 'trend')}`);
                if (trendView) views.set(trendContainerId, trendView);
            }
        }));
    }

    async function setupLineoutPage() {
        const controlIds = [
            'lineoutFilterSquad', 'lineoutFilterSeason', 'lineoutFilterGameType',
            'lineoutFilterThrower', 'lineoutFilterJumper', 'lineoutFilterArea',
            'lineoutFilterNumbers',
            'h2hFilterOpposition', 'h2hFilterTeamHighlight', 'h2hFilterOutcomeHighlight',
        ];

        await loadFilterOptions();
        controlIds.forEach((id) => {
            rebuildBootstrapSelect(document.getElementById(id));
        });
        await loadInteractiveCharts();
        await applyFiltersToViews();

        controlIds.forEach((id) => {
            const element = document.getElementById(id);
            if (!element) return;
            element.addEventListener('change', () => {
                enforceH2HFilterExclusivity(id);
                applyFiltersToViews().catch((error) => {
                    console.error('Unable to apply lineout page filters:', error);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        const lineoutSuccessView = await renderChartSpecFromPath('setPieceLineoutChart', 'data/charts/set_piece_success_lineout.json', 'Lineout success chart unavailable.');
        if (lineoutSuccessView) views.set('setPieceLineoutChart', lineoutSuccessView);

        await renderSplitSetPiecePanelsFromSingleSpec('data/charts/set_piece_success_lineout.json', [
            { containerId: 'setPiece1stLineoutChart', squad: '1st', emptyMessage: '1st XV lineout chart unavailable.' },
            { containerId: 'setPiece2ndLineoutChart', squad: '2nd', emptyMessage: '2nd XV lineout chart unavailable.' },
        ]);

        const hasLineoutFilters = Boolean(document.getElementById('lineoutFilterSquad') || document.getElementById('lineoutFilterSeason') || document.getElementById('lineoutFilterGameType'));
        const hasLineoutDeepDiveCharts = Boolean(document.getElementById('lineoutH2HChart') || document.getElementById('lineoutPerfBreakdownNumbersChart'));

        if (hasLineoutFilters || hasLineoutDeepDiveCharts) {
            await setupLineoutPage();
        }

        initialiseChartPanelToggles();
    });
})();
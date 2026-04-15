(function () {
    const LINEOUT_FIELDS = [
        { key: 'numbers', label: 'Numbers', breakdownId: 'lineoutPerfBreakdownNumbersChart', trendId: 'lineoutPerfTrendNumbersChart', order: ['4', '5', '6', '7'] },
        { key: 'area', label: 'Area / Zone', breakdownId: 'lineoutPerfBreakdownAreaChart', trendId: 'lineoutPerfTrendAreaChart', order: ['Front', 'Middle', 'Back'] },
        { key: 'call_combo', label: 'Call / Call Type', breakdownId: 'lineoutPerfBreakdownCallTypeChart', trendId: 'lineoutPerfTrendCallTypeChart' },
        { key: 'dummy', label: 'Dummy Jumps', breakdownId: 'lineoutPerfBreakdownDummyChart', trendId: 'lineoutPerfTrendDummyChart', order: ['Dummy', 'Live'] },
        { key: 'thrower', label: 'Thrower', breakdownId: 'lineoutPerfBreakdownThrowerChart', trendId: 'lineoutPerfTrendThrowerChart' },
        { key: 'jumper', label: 'Jumper', breakdownId: 'lineoutPerfBreakdownJumperChart', trendId: 'lineoutPerfTrendJumperChart' },
    ];

    let lineoutRows = [];
    let setPieceRows = [];

    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }

        try {
            const spec = await loadChartSpec(path);
            await embedChartSpec(container, spec, { containerId, emptyMessage });
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
        }
    }

    async function renderSpec(containerId, spec, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }
        if (!spec) {
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            return;
        }
        await embedChartSpec(container, spec, { containerId, emptyMessage });
    }

    function buildRedZoneSpec(setPieceSummaryRows) {
        const rows = setPieceSummaryRows
            .map((row) => ({ season: row.season, metric: 'Points per 22m entry', value: Number(row.avg_points_per_22m_entry) }))
            .concat(setPieceSummaryRows.map((row) => ({ season: row.season, metric: 'Tries per 22m entry', value: Number(row.avg_tries_per_22m_entry) })))
            .filter((row) => Number.isFinite(row.value));

        const orderedSeasons = Array.from(new Set(rows.map((row) => String(row.season)))).sort((a, b) => {
            const ay = parseInt(String(a).slice(0, 4), 10);
            const by = parseInt(String(b).slice(0, 4), 10);
            return ay - by;
        });

        return {
            $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
                title: { text: '1st XV Red Zone Efficiency', subtitle: 'How effectively 22m entries convert into points and tries.' },
            width: 520,
            height: 280,
            data: { values: rows },
            mark: { type: 'line', point: true, strokeWidth: 2.2 },
            encoding: {
                x: { field: 'season', type: 'ordinal', sort: orderedSeasons, title: 'Season' },
                y: { field: 'value', type: 'quantitative', title: 'Per 22m Entry' },
                color: { field: 'metric', type: 'nominal', title: null, scale: { domain: ['Points per 22m entry', 'Tries per 22m entry'], range: ['#202946', '#991515'] } },
                tooltip: [
                    { field: 'season', type: 'nominal', title: 'Season' },
                    { field: 'metric', type: 'nominal', title: 'Metric' },
                    { field: 'value', type: 'quantitative', title: 'Value', format: '.2f' },
                ],
            },
                config: {
                    axis: { labelFont: 'PT Sans Narrow', titleFont: 'PT Sans Narrow', labelFontSize: 12, titleFontSize: 12 },
                    legend: { labelFont: 'PT Sans Narrow', titleFont: 'PT Sans Narrow' },
                    title: { font: 'PT Sans Narrow', subtitleFont: 'PT Sans Narrow' },
                    view: { stroke: null },
                },
        };
    }

    async function renderRedZoneChart() {
        const container = document.getElementById('redZone1stChart');
        if (!container) {
            return;
        }

        try {
            const response = await fetch('data/backend/season_summary_enriched.json');
            if (!response.ok) {
                throw new Error(`Failed to fetch season summary (${response.status})`);
            }
            const summary = await response.json();
            const rows = (Array.isArray(summary) ? summary : [])
                .filter((row) => row && row.squad === '1st' && row.gameTypeMode === 'All games')
                .map((row) => ({
                    season: row.season,
                    avg_points_per_22m_entry: row.avgPointsPer22mEntry,
                    avg_tries_per_22m_entry: row.avgTriesPer22mEntry,
                }));

            if (rows.length === 0) {
                container.innerHTML = '<div class="text-center text-muted py-4">No red-zone data available.</div>';
                return;
            }

            const spec = buildRedZoneSpec(rows);
            await embedChartSpec(container, spec, {
                containerId: 'redZone1stChart',
                emptyMessage: 'Red-zone chart unavailable.'
            });
        } catch (error) {
            console.error('Unable to render red zone performance chart:', error);
            container.innerHTML = '<div class="text-center text-muted py-4">Red-zone chart unavailable.</div>';
        }
    }

    function seasonSort(a, b) {
        const ay = parseInt(String(a).slice(0, 4), 10);
        const by = parseInt(String(b).slice(0, 4), 10);
        return ay - by;
    }

    function normFieldValue(field, row) {
        if (field === 'call_combo') {
            const callType = row.call_type && row.call_type !== '' ? String(row.call_type) : 'Unknown Type';
            const call = row.call && row.call !== '' ? String(row.call) : 'Unknown Call';
            return `${callType} | ${call}`;
        }
        if (field === 'dummy') {
            return row.dummy ? 'Dummy' : 'Live';
        }
        const value = row[field];
        return value === null || value === undefined || value === '' ? 'Unknown' : String(value);
    }

    function readFilterState() {
        const get = (id, fallback = 'All') => {
            const el = document.getElementById(id);
            return el ? el.value : fallback;
        };
        return {
            squad: get('lineoutFilterSquad', '1st'),
            season: get('lineoutFilterSeason'),
            gameType: get('lineoutFilterGameType'),
            thrower: get('lineoutFilterThrower'),
            jumper: get('lineoutFilterJumper'),
            area: get('lineoutFilterArea'),
            numbers: get('lineoutFilterNumbers'),
            callType: get('lineoutFilterCallType'),
            h2hOpposition: get('h2hFilterOpposition'),
            teamHighlight: get('h2hFilterTeamHighlight'),
            outcomeHighlight: get('h2hFilterOutcomeHighlight'),
        };
    }

    function matchCommonFilters(row, filters, includeSeason) {
        if (row.squad !== filters.squad) {
            return false;
        }
        if (includeSeason && filters.season !== 'All' && row.season !== filters.season) {
            return false;
        }
        if (filters.gameType !== 'All' && row.game_type !== filters.gameType) {
            return false;
        }
        if (filters.thrower !== 'All' && String(row.thrower || 'Unknown') !== filters.thrower) {
            return false;
        }
        if (filters.jumper !== 'All' && String(row.jumper || 'Unknown') !== filters.jumper) {
            return false;
        }
        if (filters.area !== 'All' && String(row.area || 'Unknown') !== filters.area) {
            return false;
        }
        if (filters.numbers !== 'All' && String(row.numbers || 'Unknown') !== filters.numbers) {
            return false;
        }
        if (filters.callType !== 'All' && String(row.call_type || 'Unknown') !== filters.callType) {
            return false;
        }
        return true;
    }

    function aggregateBreakdown(rows, field) {
        const grouped = new Map();
        rows.forEach((row) => {
            const key = normFieldValue(field, row);
            if (!grouped.has(key)) {
                grouped.set(key, { category: key, attempts: 0, won: 0 });
            }
            const agg = grouped.get(key);
            agg.attempts += 1;
            agg.won += row.won ? 1 : 0;
        });

        const values = Array.from(grouped.values());
        const total = values.reduce((acc, row) => acc + row.attempts, 0);
        return values
            .map((row) => ({
                category: row.category,
                attempts: row.attempts,
                won: row.won,
                        subtitle: 'Outcome flow by game. Left = opposition retained, right = EGRFC retained.',
                success_rate: row.attempts > 0 ? row.won / row.attempts : 0,
            }))
            .sort((a, b) => b.attempts - a.attempts);
    }

    function buildBreakdownSpec(rows, cfg, filters) {
        if (rows.length === 0) {
            return null;
        }
        const sorted = cfg.order ? rows.slice().sort((a, b) => cfg.order.indexOf(a.category) - cfg.order.indexOf(b.category)) : rows;
        const xSort = sorted.map((row) => row.category);
        const highlightParamName = `breakdown${cfg.key.replace(/[^a-zA-Z0-9]/g, '')}Highlight`;

        return {
            $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
            title: {
                text: `${cfg.label} Breakdown`,
                subtitle: filters.season === 'All' ? 'All seasons combined. Click a value to highlight.' : `${filters.season} only. Click a value to highlight.`,
            },
            data: { values: sorted },
            width: 300,
            height: 220,
            params: [{ name: highlightParamName, select: { type: 'point', fields: ['category'], on: 'click', clear: 'dblclick' } }],
            layer: [
                {
                    mark: { type: 'bar', color: '#7d96e8', opacity: 0.55 },
                    encoding: {
                        x: { field: 'category', type: 'nominal', title: cfg.label, sort: xSort, axis: { labelAngle: -30 } },
                        y: { field: 'norm_count', type: 'quantitative', title: 'Normalised Count', axis: { format: '%', orient: 'left' }, scale: { domain: [0, 1] } },
                        opacity: {
                            condition: { param: highlightParamName, value: 0.95 },
                            value: 0.25,
                        },
                        tooltip: [
                            { field: 'category', type: 'nominal', title: cfg.label },
                            { field: 'attempts', type: 'quantitative', title: 'Attempts', format: ',.0f' },
                            { field: 'norm_count', type: 'quantitative', title: 'Normalised Count', format: '.1%' },
                        ],
                    },
                },
                {
                    mark: { type: 'line', point: true, color: '#202946', strokeWidth: 2.5 },
                    encoding: {
                        x: { field: 'category', type: 'nominal', title: cfg.label, sort: xSort, axis: { labelAngle: -30 } },
                        y: { field: 'success_rate', type: 'quantitative', title: 'Success Rate', axis: { format: '%', orient: 'right' }, scale: { domain: [0, 1] } },
                        opacity: {
                            condition: { param: highlightParamName, value: 1 },
                            value: 0.25,
                        },
                        tooltip: [
                            { field: 'category', type: 'nominal', title: cfg.label },
                            { field: 'won', type: 'quantitative', title: 'Won', format: ',.0f' },
                            { field: 'attempts', type: 'quantitative', title: 'Attempts', format: ',.0f' },
                            { field: 'success_rate', type: 'quantitative', title: 'Success Rate', format: '.1%' },
                        ],
                    },
                },
            ],
            resolve: { scale: { y: 'independent' } },
            config: { view: { stroke: null } },
        };
    }

    function aggregateTrend(rows, field) {
        const grouped = new Map();
        const seasonTotals = new Map();
        const categoryTotals = new Map();

        rows.forEach((row) => {
            const season = String(row.season);
            const category = normFieldValue(field, row);
            const key = `${season}||${category}`;
            if (!grouped.has(key)) {
                grouped.set(key, { season, category, attempts: 0, won: 0 });
            }
            const agg = grouped.get(key);
            agg.attempts += 1;
            agg.won += row.won ? 1 : 0;
            seasonTotals.set(season, (seasonTotals.get(season) || 0) + 1);
            categoryTotals.set(category, (categoryTotals.get(category) || 0) + 1);
        });

        const keepCategories = new Set(
            Array.from(categoryTotals.entries())
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([category]) => category)
        );

        return Array.from(grouped.values())
            .filter((row) => keepCategories.has(row.category))
            .map((row) => ({
                season: row.season,
                category: row.category,
                attempts: row.attempts,
                won: row.won,
                norm_count: row.attempts / (seasonTotals.get(row.season) || 1),
                success_rate: row.attempts > 0 ? row.won / row.attempts : 0,
            }));
    }

    function buildTrendSpec(rows, cfg) {
        if (rows.length === 0) {
            return null;
        }
        const seasons = Array.from(new Set(rows.map((row) => row.season))).sort(seasonSort);
        const highlightParamName = `trend${cfg.key.replace(/[^a-zA-Z0-9]/g, '')}Highlight`;

        return {
            $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
            title: { text: `${cfg.label} Trend`, subtitle: 'Normalised counts and success rates by season. Click a value to highlight.' },
            data: { values: rows },
            width: 300,
            height: 220,
            params: [{ name: highlightParamName, select: { type: 'point', fields: ['category'], on: 'click', clear: 'dblclick' } }],
            layer: [
                {
                    mark: { type: 'bar', opacity: 0.35 },
                    encoding: {
                        x: { field: 'season', type: 'nominal', title: 'Season', sort: seasons },
                        xOffset: { field: 'category', type: 'nominal' },
                        y: { field: 'norm_count', type: 'quantitative', title: 'Normalised Count', axis: { format: '%', orient: 'left' }, scale: { domain: [0, 1] } },
                        color: { field: 'category', type: 'nominal', title: cfg.label },
                        opacity: {
                            condition: { param: highlightParamName, value: 0.75 },
                            value: 0.12,
                        },
                        tooltip: [
                            { field: 'season', type: 'nominal', title: 'Season' },
                            { field: 'category', type: 'nominal', title: cfg.label },
                            { field: 'attempts', type: 'quantitative', title: 'Attempts', format: ',.0f' },
                            { field: 'norm_count', type: 'quantitative', title: 'Normalised Count', format: '.1%' },
                        ],
                    },
                },
                {
                    mark: { type: 'line', point: true, strokeWidth: 2 },
                    encoding: {
                        x: { field: 'season', type: 'nominal', title: 'Season', sort: seasons },
                        y: { field: 'success_rate', type: 'quantitative', title: 'Success Rate', axis: { format: '%', orient: 'right' }, scale: { domain: [0, 1] } },
                        color: { field: 'category', type: 'nominal', title: cfg.label },
                        detail: { field: 'category', type: 'nominal' },
                        opacity: {
                            condition: { param: highlightParamName, value: 1 },
                            value: 0.2,
                        },
                        tooltip: [
                            { field: 'season', type: 'nominal', title: 'Season' },
                            { field: 'category', type: 'nominal', title: cfg.label },
                            { field: 'won', type: 'quantitative', title: 'Won', format: ',.0f' },
                            { field: 'attempts', type: 'quantitative', title: 'Attempts', format: ',.0f' },
                            { field: 'success_rate', type: 'quantitative', title: 'Success Rate', format: '.1%' },
                        ],
                    },
                },
            ],
            resolve: { scale: { y: 'independent' } },
            config: { view: { stroke: null } },
        };
    }

    function buildH2HSpec(rows, setPieceLabel) {
        if (rows.length === 0) {
            return null;
        }

        const ySort = rows
            .slice()
            .sort((a, b) => new Date(b.date) - new Date(a.date))
            .map((row) => row.game_label)
            .filter((value, idx, arr) => arr.indexOf(value) === idx);

        const successRows = [];
        const uniqueSuccess = new Set();
        rows.forEach((row) => {
            const successKey = `${row.game_id}||${row.attacking_team}`;
            if (!uniqueSuccess.has(successKey)) {
                uniqueSuccess.add(successKey);
                successRows.push({
                    game_id: row.game_id,
                    game_label: row.game_label,
                    date: row.date,
                    attacking_team: row.attacking_team,
                    success_rate: row.success_rate,
                    won: row.won,
                    total: row.total,
                });
            }
        });

        const bars = {
            mark: { type: 'bar', size: 8 },
            encoding: {
                y: { field: 'game_label', type: 'nominal', sort: ySort, title: null, axis: { labelLimit: 180, ticks: false, domain: false } },
                x: {
                    field: 'signed_count',
                    type: 'quantitative',
                    title: 'Outcome Count',
                    axis: { format: 'd', labelExpr: 'abs(datum.value)' },
                },
                color: {
                    field: 'attacking_team',
                    type: 'nominal',
                    title: 'Attacking Team',
                    scale: { domain: ['EGRFC', 'Opposition'], range: ['#202946', '#991515'] },
                },
                opacity: { field: 'highlight_opacity', type: 'quantitative', legend: null },
                strokeWidth: {
                    condition: { param: 'h2hGameHighlight', value: 1.8 },
                    value: 0,
                },
                stroke: {
                    condition: { param: 'h2hGameHighlight', value: '#111111' },
                    value: null,
                },
                tooltip: [
                    { field: 'date', type: 'temporal', title: 'Date', format: '%d %b %Y' },
                    { field: 'game_label', type: 'nominal', title: 'Game' },
                    { field: 'attacking_team', type: 'nominal', title: 'Attacking Team' },
                    { field: 'outcome', type: 'nominal', title: 'Outcome' },
                    { field: 'winner_team', type: 'nominal', title: 'Set Piece Won By' },
                    { field: 'count', type: 'quantitative', title: 'Count', format: ',.0f' },
                ],
            },
        };

        const connectorRows = [];
        const grouped = new Map();
        successRows.forEach((row) => {
            const key = row.game_id;
            if (!grouped.has(key)) {
                grouped.set(key, { game_label: row.game_label, min: row.success_rate, max: row.success_rate });
            }
            const entry = grouped.get(key);
            entry.min = Math.min(entry.min, row.success_rate);
            entry.max = Math.max(entry.max, row.success_rate);
        });
        grouped.forEach((value) => connectorRows.push(value));

        return {
            $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
            title: {
                text: `${setPieceLabel} Turnover Head-to-Head`,
                subtitle: 'Outcome flow by game. Left = opposition retained, right = EGRFC retained.',
            },
            params: [{ name: 'h2hGameHighlight', select: { type: 'point', fields: ['game_label'], on: 'click', clear: 'dblclick' } }],
            hconcat: [
                {
                    width: 360,
                    height: { step: 14 },
                    data: { values: rows },
                    ...bars,
                },
                {
                    width: 230,
                    height: { step: 14 },
                    layer: [
                        {
                            data: { values: connectorRows },
                            mark: { type: 'rule', color: '#666', opacity: 0.45 },
                            encoding: {
                                y: { field: 'game_label', type: 'nominal', sort: ySort, title: null, axis: null },
                                x: { field: 'min', type: 'quantitative', title: 'Success %', axis: { format: '%' }, scale: { domain: [0, 1] } },
                                x2: { field: 'max' },
                            },
                        },
                        {
                            data: { values: successRows },
                            mark: { type: 'point', size: 70, filled: true },
                            encoding: {
                                y: { field: 'game_label', type: 'nominal', sort: ySort, title: null, axis: null },
                                x: { field: 'success_rate', type: 'quantitative', title: 'Success %', axis: { format: '%' }, scale: { domain: [0, 1] } },
                                color: {
                                    field: 'attacking_team',
                                    type: 'nominal',
                                    title: 'Team',
                                    scale: { domain: ['EGRFC', 'Opposition'], range: ['#202946', '#991515'] },
                                },
                                tooltip: [
                                    { field: 'game_label', type: 'nominal', title: 'Game' },
                                    { field: 'attacking_team', type: 'nominal', title: 'Attacking Team' },
                                    { field: 'won', type: 'quantitative', title: `${setPieceLabel}s Won`, format: ',.0f' },
                                    { field: 'total', type: 'quantitative', title: `${setPieceLabel}s Total`, format: ',.0f' },
                                    { field: 'success_rate', type: 'quantitative', title: 'Success Rate', format: '.1%' },
                                ],
                            },
                        },
                    ],
                },
            ],
            resolve: { scale: { y: 'shared' } },
            config: { view: { stroke: null } },
        };
    }

    function populateSelect(id, values, allLabel) {
        const select = document.getElementById(id);
        if (!select) {
            return;
        }
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
    }

    async function loadLineoutPerformanceData() {
        const [lineoutsRes, setPieceRes, gamesRes] = await Promise.all([
            fetch('data/backend/lineouts.json'),
            fetch('data/backend/set_piece.json'),
            fetch('data/backend/games.json'),
        ]);

        if (!lineoutsRes.ok || !setPieceRes.ok || !gamesRes.ok) {
            throw new Error('Failed to fetch backend datasets for lineout analysis.');
        }

        const [lineoutsRaw, setPieceRaw, gamesRaw] = await Promise.all([
            lineoutsRes.json(),
            setPieceRes.json(),
            gamesRes.json(),
        ]);

        const gamesById = new Map((Array.isArray(gamesRaw) ? gamesRaw : []).map((game) => [game.game_id, game]));

        lineoutRows = (Array.isArray(lineoutsRaw) ? lineoutsRaw : []).map((row) => {
            const game = gamesById.get(row.game_id) || {};
            return {
                ...row,
                squad: String(row.squad || game.squad || ''),
                season: String(row.season || game.season || ''),
                opposition: String(row.opposition || game.opposition || 'Unknown'),
                game_type: String(game.game_type || 'Unknown'),
                won: Boolean(row.won),
                dummy: Boolean(row.dummy),
                game_label: `${game.opposition || row.opposition || 'Unknown'} (${game.home_away || '?'})`,
            };
        });

        setPieceRows = (Array.isArray(setPieceRaw) ? setPieceRaw : []).map((row) => {
            const game = gamesById.get(row.game_id) || {};
            return {
                ...row,
                squad: String(row.squad || game.squad || ''),
                season: String(row.season || game.season || ''),
                opposition: String(row.opposition || game.opposition || 'Unknown'),
                game_type: String(game.game_type || 'Unknown'),
                home_away: String(game.home_away || '?'),
                game_label: `${game.opposition || row.opposition || 'Unknown'} (${game.home_away || '?'})`,
            };
        });

        const seasons = Array.from(new Set(lineoutRows.map((row) => row.season))).sort(seasonSort).reverse();
        const gameTypes = Array.from(new Set(lineoutRows.map((row) => row.game_type))).sort();
        const oppositions = Array.from(new Set(lineoutRows.map((row) => row.opposition))).sort();
        const throwers = Array.from(new Set(lineoutRows.map((row) => String(row.thrower || 'Unknown')))).sort();
        const jumpers = Array.from(new Set(lineoutRows.map((row) => String(row.jumper || 'Unknown')))).sort();
        const areas = Array.from(new Set(lineoutRows.map((row) => String(row.area || 'Unknown')))).sort();
        const numbers = Array.from(new Set(lineoutRows.map((row) => String(row.numbers || 'Unknown')))).sort();
        const callTypes = Array.from(new Set(lineoutRows.map((row) => String(row.call_type || 'Unknown')))).sort();
        populateSelect('lineoutFilterSeason', seasons, 'All Seasons');
        populateSelect('lineoutFilterGameType', gameTypes, 'All Games');
        populateSelect('h2hFilterOpposition', oppositions, 'All Opponents');
        populateSelect('lineoutFilterThrower', throwers, 'All Throwers');
        populateSelect('lineoutFilterJumper', jumpers, 'All Jumpers');
        populateSelect('lineoutFilterArea', areas, 'All Areas');
        populateSelect('lineoutFilterNumbers', numbers, 'All Numbers');
        populateSelect('lineoutFilterCallType', callTypes, 'All Call Types');
    }

    async function renderLineoutPerformanceCharts() {
        const filters = readFilterState();

        const breakdownRows = lineoutRows.filter((row) => matchCommonFilters(row, filters, true));
        const trendRows = lineoutRows.filter((row) => matchCommonFilters(row, filters, false));

        await Promise.all(LINEOUT_FIELDS.flatMap((cfg) => {
            const breakdownData = aggregateBreakdown(breakdownRows, cfg.key);
            const breakdownSpec = buildBreakdownSpec(breakdownData, cfg, filters);
            const trendData = aggregateTrend(trendRows, cfg.key);
            const trendSpec = buildTrendSpec(trendData, cfg);
            return [
                renderSpec(cfg.breakdownId, breakdownSpec, `No ${cfg.label.toLowerCase()} breakdown data for selected filters.`),
                renderSpec(cfg.trendId, trendSpec, `No ${cfg.label.toLowerCase()} trend data for selected filters.`),
            ];
        }));

        const renderH2H = async (setPieceType, containerId) => {
            const wonKey = setPieceType === 'Lineout' ? 'lineouts_won' : 'scrums_won';
            const totalKey = setPieceType === 'Lineout' ? 'lineouts_total' : 'scrums_total';

            const filtered = setPieceRows.filter((row) => {
                if (row.squad !== filters.squad) {
                    return false;
                }
                if (filters.season !== 'All' && row.season !== filters.season) {
                    return false;
                }
                if (filters.gameType !== 'All' && row.game_type !== filters.gameType) {
                    return false;
                }
                if (filters.h2hOpposition !== 'All' && row.opposition !== filters.h2hOpposition) {
                    return false;
                }
                return Number(row[totalKey] || 0) > 0;
            });

            const values = [];
            filtered.forEach((row) => {
                const attackingTeam = row.team === 'EGRFC' ? 'EGRFC' : 'Opposition';
                const otherTeam = attackingTeam === 'EGRFC' ? 'Opposition' : 'EGRFC';
                const won = Number(row[wonKey] || 0);
                const total = Number(row[totalKey] || 0);
                const lost = Math.max(0, total - won);
                const successRate = total > 0 ? won / total : 0;

                [
                    { outcome: 'Retained', winner: attackingTeam, count: won },
                    { outcome: 'Turnover', winner: otherTeam, count: lost },
                ].forEach((event) => {
                    const teamMatch = filters.teamHighlight === 'All' || attackingTeam === filters.teamHighlight;
                    const outcomeMatch = filters.outcomeHighlight === 'All' || event.outcome === filters.outcomeHighlight;
                    values.push({
                        game_id: row.game_id,
                        date: row.date,
                        game_label: row.game_label,
                        attacking_team: attackingTeam,
                        winner_team: event.winner,
                        outcome: event.outcome,
                        count: event.count,
                        signed_count: event.winner === 'EGRFC' ? event.count : -event.count,
                        highlight_opacity: teamMatch && outcomeMatch ? 1 : 0.18,
                        won,
                        total,
                        success_rate: successRate,
                    });
                });
            });

            const spec = buildH2HSpec(values, setPieceType);
            await renderSpec(containerId, spec, `${setPieceType} turnover chart unavailable for selected filters.`);
        };

        await Promise.all([
            renderH2H('Lineout', 'lineoutH2HChart'),
            renderH2H('Scrum', 'scrumH2HChart'),
        ]);
    }

    async function setupLineoutFiltersAndCharts() {
        const controls = [
            'lineoutFilterSquad',
            'lineoutFilterSeason',
            'lineoutFilterGameType',
            'lineoutFilterThrower',
            'lineoutFilterJumper',
            'lineoutFilterArea',
            'lineoutFilterNumbers',
            'lineoutFilterCallType',
            'h2hFilterOpposition',
            'h2hFilterTeamHighlight',
            'h2hFilterOutcomeHighlight',
        ];

        await loadLineoutPerformanceData();

        controls.forEach((id) => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', () => {
                    renderLineoutPerformanceCharts().catch((error) => {
                        console.error('Unable to rerender lineout performance charts:', error);
                    });
                });
            }
        });

        await renderLineoutPerformanceCharts();
    }

    document.addEventListener('DOMContentLoaded', async function () {
        await Promise.all([
            renderChartSpec('setPiece1stScrumChart', 'data/charts/set_piece_success_1st_scrum.json', '1st XV scrum chart unavailable.'),
            renderChartSpec('setPiece1stLineoutChart', 'data/charts/set_piece_success_1st_lineout.json', '1st XV lineout chart unavailable.'),
            renderChartSpec('setPiece2ndScrumChart', 'data/charts/set_piece_success_2nd_scrum.json', '2nd XV scrum chart unavailable.'),
            renderChartSpec('setPiece2ndLineoutChart', 'data/charts/set_piece_success_2nd_lineout.json', '2nd XV lineout chart unavailable.'),
            renderChartSpec('lineoutZoneChart', 'data/charts/lineout_success_by_zone.json', '1st XV lineout zone chart unavailable.'),
            renderChartSpec('lineoutBreakdown1stChart', 'data/charts/lineout_breakdown_1st.json', '1st XV lineout breakdown unavailable.'),
            renderChartSpec('lineoutBreakdown2ndChart', 'data/charts/lineout_breakdown_2nd.json', '2nd XV lineout breakdown unavailable.'),
            renderRedZoneChart(),
            setupLineoutFiltersAndCharts(),
        ]);
        initialiseChartPanelToggles();
    });
})();

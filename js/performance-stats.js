(function () {
    const FILTERS_OFFCANVAS_ID = 'performanceStatsFiltersOffcanvas';
    const CHART_PATHS = {
        lineout: 'data/charts/set_piece_success_lineout.json',
        scrum: 'data/charts/set_piece_success_scrum.json',
        setPieceAttackingLineoutVolume: 'data/charts/set_piece_attacking_volume_lineout.json',
        setPieceAttackingScrumVolume: 'data/charts/set_piece_attacking_volume_scrum.json',
        redZone: 'data/charts/red_zone_points.json',
        redZoneEntriesEfficiency: 'data/charts/red_zone_entries_efficiency.json',
    };
    const SET_PIECE_CHARTS = [
        {
            key: 'lineout',
            containerId: 'setPiece1stLineoutChart',
            path: CHART_PATHS.lineout,
            emptyMessage: 'Lineout chart unavailable.',
        },
        {
            key: 'scrum',
            containerId: 'setPiece1stScrumChart',
            path: CHART_PATHS.scrum,
            emptyMessage: 'Scrum chart unavailable.',
        },
        {
            key: 'setPieceAttackingLineoutVolume',
            containerId: 'setPieceAttackingLineoutVolumeChart',
            path: CHART_PATHS.setPieceAttackingLineoutVolume,
            emptyMessage: 'Lineout volume chart unavailable.',
        },
        {
            key: 'setPieceAttackingScrumVolume',
            containerId: 'setPieceAttackingScrumVolumeChart',
            path: CHART_PATHS.setPieceAttackingScrumVolume,
            emptyMessage: 'Scrum volume chart unavailable.',
        },
    ];

    const state = {
        views: {
            lineout: null,
            scrum: null,
            setPieceAttackingLineoutVolume: null,
            setPieceAttackingScrumVolume: null,
            redZone: null,
            redZoneEntriesEfficiency: null,
        },
        seasonalEfficiencyAxisTitle: null,
    };

    function getElement(id) {
        return document.getElementById(id);
    }

    function readSetPieceFilterState() {
        return {
            squad: getElement('performanceStatsSquad')?.value || '1st',
            gameType: getElement('performanceStatsGameType')?.value || 'League + Cup',
        };
    }

    function readRedZoneFilterState() {
        const select = getElement('redZoneSeason');
        const selectedSeasons = select ? Array.from(select.selectedOptions).map((opt) => opt.value) : ['2024/25', '2025/26'];
        return {
            squad: getElement('performanceStatsSquad')?.value || '1st',
            seasons: selectedSeasons.length > 0 ? selectedSeasons : ['2024/25', '2025/26'],
            gameType: getElement('performanceStatsGameType')?.value || 'League + Cup',
            efficiencyMetric: getElement('redZoneEfficiencyMetric')?.value || 'Points per 22m entry',
        };
    }

    function syncSegmentButtons(segmentId, value) {
        const segment = getElement(segmentId);
        if (!segment) return;
        if (window.sharedUi?.syncSegmentButtons) {
            window.sharedUi.syncSegmentButtons(segment, value);
            return;
        }
        // For multi-select segments (like redZoneSeasonSegment), value is an array
        if (Array.isArray(value)) {
            segment.querySelectorAll('.squad-filter-segment-btn').forEach((btn) => {
                btn.classList.toggle('is-active', value.includes(btn.dataset.value));
            });
        } else {
            // For single-select segments
            segment.querySelectorAll('.squad-filter-segment-btn').forEach((btn) => {
                btn.classList.toggle('is-active', btn.dataset.value === value);
            });
        }
    }

    function renderActiveFilterChips() {
        const setPieceHost = getElement('setPieceActiveFilters');
        const redZoneHost = getElement('redZoneActiveFilters');
        const { squad, gameType } = readSetPieceFilterState();
        const squadLabel = `${squad} XV`;

        const setPieceChips = [
            { label: 'Squad', value: squadLabel },
            { label: 'Game Type', value: gameType },
        ];

        if (setPieceHost) {
            if (window.sharedUi?.renderOffcanvasFilterChips) {
                window.sharedUi.renderOffcanvasFilterChips({
                    host: setPieceHost,
                    offcanvasId: FILTERS_OFFCANVAS_ID,
                    chips: setPieceChips,
                });
            } else {
                setPieceHost.innerHTML = [
                    `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${FILTERS_OFFCANVAS_ID}" aria-controls="${FILTERS_OFFCANVAS_ID}"><strong>Squad</strong> ${escapeHtml(squadLabel)}</button>`,
                    `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${FILTERS_OFFCANVAS_ID}" aria-controls="${FILTERS_OFFCANVAS_ID}"><strong>Game Type</strong> ${escapeHtml(gameType)}</button>`,
                ].join('');
            }
        }

        if (redZoneHost) {
            const redZoneChips = [
                { label: 'Squad', value: squadLabel },
                { label: 'Game Type', value: gameType },
            ];

            if (window.sharedUi?.renderOffcanvasFilterChips) {
                window.sharedUi.renderOffcanvasFilterChips({
                    host: redZoneHost,
                    offcanvasId: FILTERS_OFFCANVAS_ID,
                    chips: redZoneChips,
                });
            } else {
                redZoneHost.innerHTML = [
                    `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${FILTERS_OFFCANVAS_ID}" aria-controls="${FILTERS_OFFCANVAS_ID}"><strong>Squad</strong> ${escapeHtml(squadLabel)}</button>`,
                    `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${FILTERS_OFFCANVAS_ID}" aria-controls="${FILTERS_OFFCANVAS_ID}"><strong>Game Type</strong> ${escapeHtml(gameType)}</button>`,
                ].join('');
            }
        }
    }

    function formatPercent(value) {
        if (!Number.isFinite(value)) return '-';
        return `${(value * 100).toFixed(0)}%`;
    }

    function toNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num : 0;
    }

    async function updateHeroMetrics() {
        const setPieceValueEl = getElement('performanceHeroLineoutValue');
        const setPieceNoteEl = getElement('performanceHeroLineoutNote');
        const scrumValueEl = getElement('performanceHeroScrumValue');
        const scrumNoteEl = getElement('performanceHeroScrumNote');
        const redZoneValueEl = getElement('performanceHeroRedZoneValue');
        const redZoneNoteEl = getElement('performanceHeroRedZoneNote');
        const heroMetaEl = getElement('performanceStatsHeroMetricsMeta');

        if (!setPieceValueEl || !setPieceNoteEl || !scrumValueEl || !scrumNoteEl || !redZoneValueEl || !redZoneNoteEl || !heroMetaEl) {
            return;
        }

        try {
            const [setPieceResponse, redZoneResponse] = await Promise.all([
                fetch('data/backend/set_piece.json', { cache: 'no-store' }),
                fetch('data/backend/v_red_zone.json', { cache: 'no-store' }),
            ]);

            if (!setPieceResponse.ok || !redZoneResponse.ok) {
                throw new Error('Unable to load performance datasets');
            }

            const setPieceRows = await setPieceResponse.json();
            const redZoneRows = await redZoneResponse.json();

            const seasons = Array.from(new Set((Array.isArray(setPieceRows) ? setPieceRows : [])
                .filter((row) => String(row?.squad || '').trim() === '1st' && String(row?.season || '').trim())
                .map((row) => String(row.season).trim())))
                .sort((a, b) => parseInt(String(b).slice(0, 4), 10) - parseInt(String(a).slice(0, 4), 10));

            const currentSeason = seasons[0] || 'Current';
            heroMetaEl.textContent = `1st XV • ${currentSeason}`;

            const currentSetPiece = (Array.isArray(setPieceRows) ? setPieceRows : []).filter((row) =>
                String(row?.squad || '').trim() === '1st' && String(row?.season || '').trim() === currentSeason
            );

            const egrfcSetPiece = currentSetPiece.filter((row) => String(row?.team || '').trim() === 'EGRFC');
            const oppSetPiece = currentSetPiece.filter((row) => String(row?.team || '').trim() === 'Opposition');

            const sumBy = (rows, key) => rows.reduce((sum, row) => sum + toNumber(row?.[key]), 0);

            const egrfcLineoutRate = sumBy(egrfcSetPiece, 'lineouts_won') / Math.max(1, sumBy(egrfcSetPiece, 'lineouts_total'));
            const oppLineoutRate = sumBy(oppSetPiece, 'lineouts_won') / Math.max(1, sumBy(oppSetPiece, 'lineouts_total'));
            const egrfcScrumRate = sumBy(egrfcSetPiece, 'scrums_won') / Math.max(1, sumBy(egrfcSetPiece, 'scrums_total'));
            const oppScrumRate = sumBy(oppSetPiece, 'scrums_won') / Math.max(1, sumBy(oppSetPiece, 'scrums_total'));

            setPieceValueEl.textContent = formatPercent(egrfcLineoutRate);
            setPieceNoteEl.textContent = `Opposition ${formatPercent(oppLineoutRate)}`;
            scrumValueEl.textContent = formatPercent(egrfcScrumRate);
            scrumNoteEl.textContent = `Opposition ${formatPercent(oppScrumRate)}`;

            const currentRedZone = (Array.isArray(redZoneRows) ? redZoneRows : []).filter((row) =>
                String(row?.squad || '').trim() === '1st'
                && String(row?.season || '').trim() === currentSeason
            );
            const egrfcRedZone = currentRedZone.filter((row) => String(row?.team || '').trim() === 'EGRFC');
            const oppositionRedZone = currentRedZone.filter((row) => String(row?.team || '').trim() === 'Opposition');

            const egrfcPoints = sumBy(egrfcRedZone, 'points');
            const egrfcEntries = sumBy(egrfcRedZone, 'entries_22m');
            const avgPointsPerEntry = egrfcEntries > 0 ? (egrfcPoints / egrfcEntries) : NaN;

            const oppositionPoints = sumBy(oppositionRedZone, 'points');
            const oppositionEntries = sumBy(oppositionRedZone, 'entries_22m');
            const oppositionAvgPointsPerEntry = oppositionEntries > 0 ? (oppositionPoints / oppositionEntries) : NaN;

            redZoneValueEl.textContent = Number.isFinite(avgPointsPerEntry) ? avgPointsPerEntry.toFixed(1) : '-';
            redZoneNoteEl.textContent = `Opposition ${Number.isFinite(oppositionAvgPointsPerEntry) ? oppositionAvgPointsPerEntry.toFixed(1) : '-'}`;
        } catch (error) {
            console.warn('Unable to compute performance hero metrics:', error);
            setPieceValueEl.textContent = '-';
            setPieceNoteEl.textContent = 'Opposition -';
            scrumValueEl.textContent = '-';
            scrumNoteEl.textContent = 'Opposition -';
            redZoneValueEl.textContent = '-';
            redZoneNoteEl.textContent = 'Opposition -';
            heroMetaEl.textContent = '1st XV';
        }
    }

    async function fetchSeasons() {
        try {
            const response = await fetch('data/backend/games.json', { cache: 'no-store' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const rows = await response.json();
            return Array.from(new Set((Array.isArray(rows) ? rows : [])
                .map((row) => String(row?.season || '').trim())
                .filter(Boolean)))
                .sort((a, b) => {
                    const ay = parseInt(String(a).slice(0, 4), 10);
                    const by = parseInt(String(b).slice(0, 4), 10);
                    return by - ay;
                });
        } catch (error) {
            console.warn('Unable to load season options for performance filters:', error);
            return [];
        }
    }

    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = getElement(containerId);
        if (!container) return null;
        try {
            const spec = await loadChartSpec(path);
            return await embedChartSpec(container, spec, { containerId, emptyMessage });
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            return null;
        }
    }

    function getEfficiencyAxisTitle(efficiencyMetric) {
        return efficiencyMetric === 'Try-scoring efficiency (%)'
            ? 'Average try conversion %'
            : 'Average points per entry';
    }

    function applyEfficiencyAxisTitleToSpec(spec, axisTitle) {
        if (!spec || !Array.isArray(spec.layer)) return spec;

        spec.layer.forEach((layer) => {
            const yEncoding = layer?.encoding?.y;
            if (!yEncoding || typeof yEncoding !== 'object') return;
            const axis = yEncoding.axis;
            if (!axis || typeof axis !== 'object') return;
            if (axis.orient === 'right') {
                yEncoding.title = axisTitle;
            }
        });

        return spec;
    }

    async function ensureSeasonalEfficiencyView(efficiencyMetric) {
        const desiredTitle = getEfficiencyAxisTitle(efficiencyMetric);
        if (state.views.redZoneEntriesEfficiency && state.seasonalEfficiencyAxisTitle === desiredTitle) {
            return state.views.redZoneEntriesEfficiency;
        }

        const container = getElement('rzSeasonalEntriesEfficiencyChart');
        if (!container) return null;

        try {
            const spec = await loadChartSpec(CHART_PATHS.redZoneEntriesEfficiency);
            applyEfficiencyAxisTitleToSpec(spec, desiredTitle);
            const view = await embedChartSpec(container, spec, {
                containerId: 'rzSeasonalEntriesEfficiencyChart',
                emptyMessage: 'Red zone seasonal chart unavailable.',
            });
            state.views.redZoneEntriesEfficiency = view;
            state.seasonalEfficiencyAxisTitle = desiredTitle;
            return view;
        } catch (error) {
            console.error('Unable to render seasonal red-zone chart with dynamic axis title:', error);
            container.innerHTML = '<div class="text-center text-muted py-4">Red zone seasonal chart unavailable.</div>';
            state.views.redZoneEntriesEfficiency = null;
            return null;
        }
    }

    async function ensureViews() {
        for (const chart of SET_PIECE_CHARTS) {
            if (!state.views[chart.key]) {
                state.views[chart.key] = await renderChartSpec(chart.containerId, chart.path, chart.emptyMessage);
            }
        }
        if (!state.views.redZone) {
            state.views.redZone = await renderChartSpec('rzPointsChart', CHART_PATHS.redZone, 'Red zone chart unavailable.');
        }
        if (!state.views.redZoneEntriesEfficiency) {
            state.views.redZoneEntriesEfficiency = await renderChartSpec(
                'rzSeasonalEntriesEfficiencyChart',
                CHART_PATHS.redZoneEntriesEfficiency,
                'Red zone seasonal chart unavailable.',
            );
        }
    }

    async function applyLineoutAndScrumFilters() {
        const { squad, gameType } = readSetPieceFilterState();
        const runTasks = [];

        SET_PIECE_CHARTS.forEach(({ key }) => {
            const view = state.views[key];
            if (!view) return;
            view.signal('spSquadParam', squad);
            view.signal('spSeasonParam', 'All');
            view.signal('spGameTypeParam', gameType);
            runTasks.push(view.runAsync());
        });

        await Promise.all(runTasks);
    }

    async function applyRedZoneFilters() {
        const { squad, seasons, gameType, efficiencyMetric } = readRedZoneFilterState();
        const chartEl = getElement('rzPointsChart');
        const messageEl = getElement('rzPointsMessage');
        const seasonalChartEl = getElement('rzSeasonalEntriesEfficiencyChart');
        const seasonalMessageEl = getElement('rzSeasonalMessage');
        if (!chartEl || !messageEl || !seasonalChartEl || !seasonalMessageEl) return;

        if (squad === '2nd') {
            chartEl.style.display = 'none';
            seasonalChartEl.style.display = 'none';
            messageEl.hidden = false;
            seasonalMessageEl.hidden = false;
            messageEl.innerHTML = 'Red-zone stats are currently available for 1st XV only. Switch the squad filter to 1st XV to view this chart.';
            seasonalMessageEl.innerHTML = 'Red-zone stats are currently available for 1st XV only. Switch the squad filter to 1st XV to view this chart.';
            return;
        }

        chartEl.style.display = '';
        seasonalChartEl.style.display = '';
        messageEl.hidden = true;
        seasonalMessageEl.hidden = true;
        messageEl.innerHTML = '';
        seasonalMessageEl.innerHTML = '';

        const view = state.views.redZone;
        const seasonalView = await ensureSeasonalEfficiencyView(efficiencyMetric);
        const runTasks = [];

        if (view) {
            view.signal('rzSquad', squad);
            view.signal('rzSeason', seasons);
            view.signal('rzGameType', gameType);
            runTasks.push(view.runAsync());
        }

        if (seasonalView) {
            seasonalView.signal('rzSquad', squad);
            seasonalView.signal('rzSeason', seasons);
            seasonalView.signal('rzGameType', gameType);
            seasonalView.signal('rzEfficiencyMetricParam', efficiencyMetric);
            runTasks.push(seasonalView.runAsync());
        }

        await Promise.all(runTasks);
    }

    async function applyAllFilters() {
        renderActiveFilterChips();
        await applyLineoutAndScrumFilters();
        await applyRedZoneFilters();
    }

    async function initialiseControls() {
        // Single-select segment bindings (Squad, Game Type)
        const singleSelectBindings = [
            { segmentId: 'performanceStatsSquadSegment', selectId: 'performanceStatsSquad' },
            { segmentId: 'performanceStatsGameTypeSegment', selectId: 'performanceStatsGameType' },
            { segmentId: 'redZoneEfficiencyMetricSegment', selectId: 'redZoneEfficiencyMetric' },
        ];

        singleSelectBindings.forEach(({ segmentId, selectId }) => {
            const segment = getElement(segmentId);
            const select = getElement(selectId);
            if (!segment || !select) return;
            if (window.sharedUi?.bindSegmentToSelect) {
                window.sharedUi.bindSegmentToSelect({
                    segment,
                    select,
                });
            } else {
                segment.querySelectorAll('.squad-filter-segment-btn').forEach((btn) => {
                    btn.addEventListener('click', () => {
                        if (!btn.dataset.value) return;
                        select.value = btn.dataset.value;
                        syncSegmentButtons(segmentId, select.value);
                        applyAllFilters().catch((error) => {
                            console.error('Unable to apply performance filters:', error);
                        });
                    });
                });
                syncSegmentButtons(segmentId, select.value);
            }
        });

        // Multi-select segment binding (Red Zone Season)
        const redZoneSeasonSegment = getElement('redZoneSeasonSegment');
        const redZoneSeasonSelect = getElement('redZoneSeason');
        if (redZoneSeasonSegment && redZoneSeasonSelect) {
            redZoneSeasonSegment.querySelectorAll('.squad-filter-segment-btn').forEach((btn) => {
                btn.addEventListener('click', () => {
                    if (!btn.dataset.value) return;
                    const value = btn.dataset.value;
                    const isSelected = Array.from(redZoneSeasonSelect.selectedOptions).some((opt) => opt.value === value);
                    if (isSelected) {
                        // Remove from selection
                        Array.from(redZoneSeasonSelect.options).forEach((opt) => {
                            if (opt.value === value) opt.selected = false;
                        });
                    } else {
                        // Add to selection
                        Array.from(redZoneSeasonSelect.options).forEach((opt) => {
                            if (opt.value === value) opt.selected = true;
                        });
                    }
                    const selectedSeasons = Array.from(redZoneSeasonSelect.selectedOptions).map((opt) => opt.value);
                    syncSegmentButtons('redZoneSeasonSegment', selectedSeasons);
                    applyAllFilters().catch((error) => {
                        console.error('Unable to apply red zone filters:', error);
                    });
                });
            });
            const selectedSeasons = Array.from(redZoneSeasonSelect.selectedOptions).map((opt) => opt.value);
            syncSegmentButtons('redZoneSeasonSegment', selectedSeasons);
        }

        ['performanceStatsSquad', 'performanceStatsGameType', 'redZoneEfficiencyMetric'].forEach((id) => {
            const element = getElement(id);
            if (!element) return;
            element.addEventListener('change', () => {
                syncSegmentButtons('performanceStatsSquadSegment', getElement('performanceStatsSquad')?.value || '1st');
                syncSegmentButtons('performanceStatsGameTypeSegment', getElement('performanceStatsGameType')?.value || 'League + Cup');
                syncSegmentButtons('redZoneEfficiencyMetricSegment', getElement('redZoneEfficiencyMetric')?.value || 'Points per 22m entry');
                applyAllFilters().catch((error) => {
                    console.error('Unable to apply performance filters:', error);
                });
            });
        });
    }

    async function init() {
        await updateHeroMetrics();
        await initialiseControls();
        await ensureViews();
        await applyAllFilters();
    }

    document.addEventListener('DOMContentLoaded', () => {
        init().catch((error) => {
            console.error('Performance Stats page initialisation failed:', error);
        });
    });
})();

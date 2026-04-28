// Squad Stats + Player Stats page logic

let squadStatsWithThresholdsEnrichedData = null;
let squadContinuityEnrichedData = null;
let squadStatsData = null;
let squadSizeTrendTemplateSpec = null;
let squadContinuityTrendTemplateSpec = null;
let squadOverlapTemplateSpec = null;
let squadPositionCompositionTemplateSpec = null;
let squadStatsControlsInitialised = false;
let syncingSquadStatsControls = false;
let squadStatsAnalysisRailInitialised = false;
let suppressGameTypeSegmentSync = false;
const DEFAULT_GAME_TYPE_MODE = 'League + Cup';

async function loadSquadStatsCanonicalData() {
    if (squadStatsWithThresholdsEnrichedData && squadContinuityEnrichedData && squadPositionCompositionTemplateSpec) return;

    const [statsResponse, continuityResponse] = await Promise.all([
        fetch('data/backend/squad_stats_with_thresholds_enriched.json'),
        fetch('data/backend/squad_continuity_enriched.json')
    ]);

    if (!statsResponse.ok) throw new Error(`Failed to fetch squad stats export (${statsResponse.status})`);
    if (!continuityResponse.ok) throw new Error(`Failed to fetch squad continuity export (${continuityResponse.status})`);

    squadStatsWithThresholdsEnrichedData = await statsResponse.json();
    squadContinuityEnrichedData = await continuityResponse.json();

    if (!squadSizeTrendTemplateSpec) {
        try {
            const res = await fetch('data/charts/squad_size_trend.json');
            if (res.ok) squadSizeTrendTemplateSpec = await res.json();
        } catch (e) { console.warn('Unable to load squad size trend template spec:', e); }
    }

    if (!squadContinuityTrendTemplateSpec) {
        try {
            const res = await fetch('data/charts/squad_continuity_average.json');
            if (res.ok) squadContinuityTrendTemplateSpec = await res.json();
        } catch (e) { console.warn('Unable to load squad continuity trend template spec:', e); }
    }

    if (!squadOverlapTemplateSpec) {
        try {
            const res = await fetch('data/charts/squad_overlap.json');
            if (res.ok) squadOverlapTemplateSpec = await res.json();
        } catch (e) { console.warn('Unable to load squad overlap template spec:', e); }
    }

    if (!squadPositionCompositionTemplateSpec) {
        try {
            const res = await fetch('data/charts/squad_position_composition.json');
            if (res.ok) squadPositionCompositionTemplateSpec = await res.json();
        } catch (e) { console.warn('Unable to load squad position composition template spec:', e); }
    }
}

function createSquadMetricBucket() {
    return { playersByThreshold: {}, forwardsByThreshold: {}, backsByThreshold: {} };
}

function createSquadSeasonBucket() {
    return { '1st': createSquadMetricBucket(), '2nd': createSquadMetricBucket(), 'Total': createSquadMetricBucket() };
}

function buildSquadStatsDataFromThresholds(rows, gameTypeMode) {
    const bySeason = {};
    (rows || []).forEach(row => {
        const season = normalizeSeasonLabel(row?.season);
        const squad = row?.squad;
        const unit = row?.unit;
        const minimumAppearances = Math.max(0, Number(row?.minimumAppearances) || 0);
        const playerCount = Number(row?.playerCount) || 0;
        if (!season || row?.gameTypeMode !== gameTypeMode) return;
        if (!['1st', '2nd', 'Total'].includes(squad)) return;
        if (!['Total', 'Forwards', 'Backs'].includes(unit)) return;
        if (!bySeason[season]) bySeason[season] = createSquadSeasonBucket();
        const bucket = bySeason[season][squad];
        if (unit === 'Total') bucket.playersByThreshold[minimumAppearances] = playerCount;
        if (unit === 'Forwards') bucket.forwardsByThreshold[minimumAppearances] = playerCount;
        if (unit === 'Backs') bucket.backsByThreshold[minimumAppearances] = playerCount;
    });

    return bySeason;
}

async function loadSquadStatsPage() {
    try {
        await loadSquadStatsCanonicalData();
        initialiseSquadStatsControlsOnce();
        renderSquadStatsPage();
    } catch (err) {
        console.error('Error loading squad metrics data:', err);
        ['squadSizeTrendChart', 'squadContinuityTrendChart', 'leagueSquadSizeContextChart', 'leagueContinuityContextChart'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="text-center text-danger py-4">Unable to load chart.</div>';
        });
        const positionChartHost = document.getElementById('squadPositionCompositionChart');
        if (positionChartHost) positionChartHost.innerHTML = '<div class="text-center text-danger py-3">Unable to load position data.</div>';
    }
}

function renderSquadPositionCompositionChart(selectedSeason, minimumAppearances, positionCountMode, selectedUnit = 'Total') {
    const container = document.getElementById('squadPositionCompositionChart');
    if (!container) return;

    if (!squadPositionCompositionTemplateSpec) {
        container.innerHTML = '<div class="text-center text-muted py-4">Squad position composition chart template not available. Run <code>python update.py</code> to generate charts.</div>';
        return;
    }

    const mode = getSquadStatsGameTypeMode();
    const threshold = Math.max(0, Number(minimumAppearances) || 0);

    // Map game type mode to allowed game_type values
    const gameTypeFilters = {
        'All games': row => true,
        'League + Cup': row => ['League', 'Cup'].includes(row?.game_type),
        'League only': row => row?.game_type === 'League',
    };

    const rowFilter = row => (
        normalizeSeasonLabel(row?.season) === selectedSeason
        && (gameTypeFilters[mode] ? gameTypeFilters[mode](row) : true)
        && Number(row?.games || 0) >= threshold
        && (row?.countMode || 'appearance_position') === positionCountMode
        && (selectedUnit === 'Total' || row?.unit === selectedUnit)
        && Number(row?.players || 0) > 0
    );

    const spec = JSON.parse(JSON.stringify(squadPositionCompositionTemplateSpec));

    if (spec.data && Array.isArray(spec.data.values)) {
        spec.data.values = spec.data.values.filter(rowFilter);
    }

    if (spec.datasets) {
        Object.keys(spec.datasets).forEach(name => {
            const rows = spec.datasets[name];
            if (!Array.isArray(rows)) return;
            spec.datasets[name] = rows.filter(rowFilter);
        });
    }

    const filteredRows =
        (spec.data && Array.isArray(spec.data.values) ? spec.data.values.length : 0)
        + (spec.datasets ? Object.values(spec.datasets).reduce((n, rows) => n + (Array.isArray(rows) ? rows.length : 0), 0) : 0);

    if (!filteredRows) {
        container.innerHTML = '<div class="text-center text-muted py-4">No position composition data available for the selected filters.</div>';
        return;
    }

    renderStaticSpecChart('squadPositionCompositionChart', spec, 'No position composition data available for the selected filters.', { hideTitle: true });
}

function getSquadMetricValue(unit, bucket, minimumAppearances = 0) {
    if (!bucket) return 0;
    const threshold = Math.max(0, Number(minimumAppearances) || 0);
    const getValueAtThreshold = thresholdMap => Number(thresholdMap?.[threshold]) || 0;
    if (unit === 'Forwards') return getValueAtThreshold(bucket.forwardsByThreshold);
    if (unit === 'Backs') return getValueAtThreshold(bucket.backsByThreshold);
    return getValueAtThreshold(bucket.playersByThreshold);
}

function getSquadStatsGameTypeMode() {
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    return gameTypeSelect?.value || DEFAULT_GAME_TYPE_MODE;
}

function getSquadStatsMinimumAppearances() {
    const minAppsSelect = document.getElementById('squadStatsMinAppsSelect');
    const value = Number(minAppsSelect?.value ?? 0);
    if (!Number.isFinite(value)) return 0;
    return Math.max(0, Math.floor(value));
}

function getSquadStatsPositionCountMode() {
    const select = document.getElementById('squadStatsPositionCountModeSelect');
    return select?.value || 'appearance_position';
}

function getSquadStatsPositionCountModeLabel(value) {
    return value === 'primary_position' ? 'Player primary position' : 'Appearance position';
}

function getSquadStatsSelectedSeason() {
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    return seasonSelect?.value || getCurrentSeasonLabel();
}

function setSelectValue(selectEl, value) {
    if (!selectEl || value === undefined || value === null) return;
    selectEl.value = value;
}

function setMinAppsValue(inputEl, value) {
    if (!inputEl) return;
    inputEl.value = String(Math.max(0, Math.floor(Number(value) || 0)));
}

function applySquadStatsControlState({ season, gameType, minimumAppearances, positionCountMode, unit }) {
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const positionCountModeSelect = document.getElementById('squadStatsPositionCountModeSelect');
    const unitSelect = document.getElementById('squadStatsUnitSelect');

    syncingSquadStatsControls = true;
    try {
        setSelectValue(seasonSelect, season);
        setSelectValue(gameTypeSelect, gameType);
        setSelectValue(positionCountModeSelect, positionCountMode);
        setSelectValue(unitSelect, unit);
        setMinAppsValue(minAppsInput, minimumAppearances);
        syncSeasonStepperFromSelect();
        syncGameTypeSegmentFromSelect();
        syncPositionCountModeSegmentFromSelect();
        syncUnitSegmentFromSelect();
        updateMinAppsDisplay();
    } finally {
        syncingSquadStatsControls = false;
    }
}

function syncSeasonStepperFromSelect() {
    const select = document.getElementById('squadStatsSeasonSelect');
    const label = document.getElementById('squadStatsSeasonLabelOffcanvas');
    const prevBtn = document.getElementById('squadStatsSeasonPrevOffcanvas');
    const nextBtn = document.getElementById('squadStatsSeasonNextOffcanvas');
    if (!select || !label) return;
    label.textContent = select.value || '';
    // Left/back should move to older seasons, right should move to newer seasons.
    if (prevBtn) prevBtn.disabled = select.selectedIndex >= select.options.length - 1;
    if (nextBtn) nextBtn.disabled = select.selectedIndex <= 0;
}

function syncGameTypeSegmentFromSelect() {
    if (suppressGameTypeSegmentSync) return;
    const select = document.getElementById('squadStatsGameTypeSelect');
    const segment = document.getElementById('squadStatsGameTypeSegment');
    if (!select || !segment) return;
    const value = select.value || DEFAULT_GAME_TYPE_MODE;
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function syncPositionCountModeSegmentFromSelect() {
    const select = document.getElementById('squadStatsPositionCountModeSelect');
    const segment = document.getElementById('squadStatsPositionCountModeSegment');
    if (!select || !segment) return;
    const value = select.value || 'appearance_position';
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function updateMinAppsDisplay() {
    const valueEl = document.getElementById('squadStatsMinAppsValue');
    if (!valueEl) return;
    valueEl.textContent = String(getSquadStatsMinimumAppearances());
}

function syncUnitSegmentFromSelect() {
    const select = document.getElementById('squadStatsUnitSelect');
    const segment = document.getElementById('squadStatsUnitSegment');
    if (!select || !segment) return;
    const value = select.value || 'Total';
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function renderSquadStatsActiveFilterChips(targetId, selectedSeason, gameTypeMode, minimumAppearances, positionCountMode, unitMode, options = {}) {
    const host = document.getElementById(targetId);
    if (!host) return;
    const {
        includeSeason = true,
        includeGameType = true,
        includeMinAppearances = true,
        includeUnit = true,
    } = options;

    const chips = [];
    if (includeSeason) {
        const seasonShort = /^\d{4}\//.test(selectedSeason) ? selectedSeason.replace(/^20/, '') : selectedSeason;
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Season</strong> <span class="d-none d-md-inline">${selectedSeason}</span><span class="d-inline d-md-none">${seasonShort}</span></button>`);
    }
    if (includeGameType) {
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Game Type</strong> ${gameTypeMode}</button>`);
    }
    if (includeMinAppearances) {
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong><span class="d-none d-md-inline">Min Appearances</span><span class="d-inline d-md-none">Min Apps</span></strong> ${minimumAppearances}</button>`);
    }
    if (includeUnit) {
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Unit</strong> ${unitMode}</button>`);
    }
    
    host.innerHTML = chips.join('');
}

function syncOffcanvasFiltersFromMain() {
    // Since offcanvas controls are now the primary controls,
    // just ensure the UI state is consistent with the hidden select values
    
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const seasonLabelOffcanvas = document.getElementById('squadStatsSeasonLabelOffcanvas');
    if (seasonSelect && seasonLabelOffcanvas) {
        seasonLabelOffcanvas.textContent = seasonSelect.options[seasonSelect.selectedIndex]?.text || getCurrentSeasonLabel();
    }
    
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const gameTypeSegment = document.getElementById('squadStatsGameTypeSegment');
    if (gameTypeSelect && gameTypeSegment) {
        const activeValue = gameTypeSelect.value;
        gameTypeSegment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.value === activeValue);
        });
    }
    
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    if (minAppsInput) {
        const minAppsValue = document.getElementById('squadStatsMinAppsValue');
        if (minAppsValue) {
            minAppsValue.textContent = minAppsInput.value;
        }
    }
    
    const unitSelect = document.getElementById('squadStatsUnitSelect');
    const unitSegment = document.getElementById('squadStatsUnitSegment');
    if (unitSelect && unitSegment) {
        const activeValue = unitSelect.value;
        unitSegment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.value === activeValue);
        });
    }
}

function renderSquadStatsHeroStats() {
    const selectedSeason = getSquadStatsSelectedSeason() || getCurrentSeasonLabel();
    const mode = getSquadStatsGameTypeMode();
    const selectedUnit = getLeagueContextUnit();
    const minimumAppearances = getSquadStatsMinimumAppearances();
    const modeData = buildSquadStatsDataFromThresholds(squadStatsWithThresholdsEnrichedData || [], mode);
    const seasonKey = modeData[selectedSeason] ? selectedSeason : getCurrentSeasonLabel();
    const seasonData = modeData[seasonKey] || createSquadSeasonBucket();

    const value1st = getSquadMetricValue(selectedUnit, seasonData['1st'], minimumAppearances);
    const value2nd = getSquadMetricValue(selectedUnit, seasonData['2nd'], minimumAppearances);
    const valueTotal = getSquadMetricValue(selectedUnit, seasonData['Total'], minimumAppearances);

    const value1stEl = document.getElementById('squadStatsHeroValue1st');
    const value2ndEl = document.getElementById('squadStatsHeroValue2nd');
    const valueTotalEl = document.getElementById('squadStatsHeroValueTotal');
    const metaEl = document.getElementById('squadStatsHeroMeta');

    if (value1stEl) value1stEl.textContent = String(value1st);
    if (value2ndEl) value2ndEl.textContent = String(value2nd);
    if (valueTotalEl) valueTotalEl.textContent = String(valueTotal);
    if (metaEl) metaEl.textContent = `${seasonKey} • ${mode} • ${selectedUnit} • Min Apps ${minimumAppearances}`;
}

function getSquadStatsSeasonOptions() {
    const seasonSet = new Set();
    const addSeason = season => { const normalized = normalizeSeasonLabel(season); if (normalized) seasonSet.add(normalized); };
    (availableSeasons || []).forEach(addSeason);
    (squadStatsWithThresholdsEnrichedData || []).forEach(row => addSeason(row?.season));
    addSeason(getCurrentSeasonLabel());
    return getSortedSquadStatsSeasons(Object.fromEntries(Array.from(seasonSet).map(s => [s, true])));
}

function populateSquadStatsSeasonDropdownOptions() {
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    if (!seasonSelect) return [];
    const seasons = getSquadStatsSeasonOptions();
    const finalSeasons = seasons.length > 0 ? seasons : [getCurrentSeasonLabel()];
    seasonSelect.innerHTML = '';
    finalSeasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = season;
        seasonSelect.appendChild(option);
    });
    const currentSeason = getCurrentSeasonLabel();
    seasonSelect.value = finalSeasons.includes(currentSeason) ? currentSeason : finalSeasons[0];
    syncSeasonStepperFromSelect();
    return finalSeasons;
}

function refreshSquadStatsData() {
    if (!squadStatsWithThresholdsEnrichedData) { squadStatsData = {}; return; }
    const mode = getSquadStatsGameTypeMode();
    squadStatsData = buildSquadStatsDataFromThresholds(squadStatsWithThresholdsEnrichedData, mode);
}

function initialiseSquadStatsAnalysisRail() {
    if (squadStatsAnalysisRailInitialised) return;
    squadStatsAnalysisRailInitialised = initialiseAnalysisRail({
        railId: 'squadStatsAnalysisRail',
    });
}

function getUnitsForTrendCharts(selectedUnit) {
    if (selectedUnit === 'Forwards' || selectedUnit === 'Backs') return [selectedUnit];
    return ['Total', 'Forwards', 'Backs'];
}

function buildSquadSizeTrendRows(selectedSeason, minimumAppearances, selectedUnit, viewMode = 'faceted') {
    const seasons = getSortedSquadStatsSeasons(squadStatsData).slice().reverse();
    const rows = [];
    const toTrendValue = value => (value === 0 ? null : value);
    const unitsToInclude = getUnitsForTrendCharts(selectedUnit);
    const squadPanels = viewMode === 'aggregated'
        ? [{ bucketKey: 'Total', squad: 'Total' }]
        : [
            { bucketKey: '1st', squad: '1st' },
            { bucketKey: '2nd', squad: '2nd' }
        ];
    seasons.forEach(season => {
        const seasonData = squadStatsData?.[season];
        if (!seasonData) return;
        squadPanels.forEach(({ bucketKey, squad }) => {
            const bucket = seasonData[bucketKey];
            if (!bucket) return;
            const isSelected = season === selectedSeason;
            unitsToInclude.forEach(unit => {
                rows.push({
                    season,
                    squad,
                    unit,
                    players: toTrendValue(getSquadMetricValue(unit, bucket, minimumAppearances)),
                    isSelected
                });
            });
        });
    });
    return rows;
}

function renderSquadSizeTrendChart(selectedSeason, minimumAppearances, selectedUnit, viewMode) {
    const container = document.getElementById('squadSizeTrendChart');
    if (!container) return;
    if (!squadSizeTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad size trend template not available. Run <code>python update.py</code> to generate charts.</div>'; return; }
    const values = buildSquadSizeTrendRows(selectedSeason, minimumAppearances, selectedUnit, viewMode);
    if (!values.length) { container.innerHTML = '<div class="text-center text-muted py-4">No squad size trend data available for the selected filters.</div>'; return; }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadSizeTrendTemplateSpec));
    spec.data = { values };
    if (spec.datasets) delete spec.datasets;
    renderStaticSpecChart('squadSizeTrendChart', spec, 'No squad size trend data available for the selected filters.', { hideTitle: true });
}

function buildContinuityAverageTrendRows(selectedUnit, selectedSeason) {
    const mode = getSquadStatsGameTypeMode();
    const unitsToInclude = getUnitsForTrendCharts(selectedUnit);
    return (squadContinuityEnrichedData || [])
        .filter(row => row?.gameTypeMode === mode && ['1st', '2nd'].includes(row?.squad) && unitsToInclude.includes(row?.unit))
        .map(row => ({
            season: normalizeSeasonLabel(row?.season),
            squad: row?.squad,
            unit: row?.unit,
            retained: Number(row?.retained) || 0,
            isSelected: normalizeSeasonLabel(row?.season) === selectedSeason
        }));
}

function renderSquadContinuityTrendChart(selectedSeason, selectedUnit) {
    const container = document.getElementById('squadContinuityTrendChart');
    if (!container) return;
    if (!squadContinuityTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad returners trend template not available.</div>'; return; }
    const values = buildContinuityAverageTrendRows(selectedUnit, selectedSeason);
    if (!values.length) { container.innerHTML = '<div class="text-center text-muted py-4">No returners data available for the selected filters.</div>'; return; }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadContinuityTrendTemplateSpec));
    spec.data = { values };
    if (spec.datasets) delete spec.datasets;
    renderStaticSpecChart('squadContinuityTrendChart', spec, 'No returners data available for the selected filters.', { hideTitle: true });
}

function leagueSpecHasSeasonRows(spec, season) {
    if (!spec) return false;
    const rowHasSeason = row => normalizeSeasonLabel(row?.Season) === season;
    if (spec.datasets) {
        return Object.values(spec.datasets).some(rows => Array.isArray(rows) && rows.some(rowHasSeason));
    }
    if (spec.data && Array.isArray(spec.data.values)) {
        return spec.data.values.some(rowHasSeason);
    }
    return false;
}

function getLeagueContextUnit() {
    const select = document.getElementById('squadStatsUnitSelect');
    return select?.value || 'Total';
}

function getSquadSizeTrendViewMode() {
    const select = document.getElementById('squadSizeTrendViewSelect');
    return select?.value || 'faceted';
}

function syncSquadSizeTrendViewSegmentFromSelect() {
    const select = document.getElementById('squadSizeTrendViewSelect');
    const segment = document.getElementById('squadSizeTrendViewSegment');
    if (!select || !segment) return;
    const value = select.value || 'faceted';
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

async function renderLeagueContextCharts() {
    const selectedSeason = document.getElementById('squadStatsSeasonSelect')?.value || getCurrentSeasonLabel();
    const selectedUnit = getLeagueContextUnit();

    // Helper: inject isSelected into the trend panel's datasets based on Season field.
    const addIsSelectedToTrendDatasets = (filteredSpec) => {
        if (!Array.isArray(filteredSpec.hconcat) || filteredSpec.hconcat.length < 2) return filteredSpec;
        const trendDatasetNames = collectChartDatasetNames(filteredSpec.hconcat[1]);
        trendDatasetNames.forEach(name => {
            const rows = filteredSpec.datasets?.[name];
            if (Array.isArray(rows)) {
                filteredSpec.datasets[name] = rows.map(row => ({
                    ...row,
                    isSelected: row.Season === selectedSeason
                }));
            }
        });
        return filteredSpec;
    };

    const charts = [
        {
            containerId: 'leagueSquadSizeContextChart',
            path: 'data/charts/league_squad_size_context_1s.json',
            emptyMessage: `No league squad size data available for ${selectedSeason} (${selectedUnit}).`,
            filterSpec: spec => addIsSelectedToTrendDatasets(filterLeagueContextCombinedSpec(
                spec,
                row => row?.Season === selectedSeason && row?.Unit === selectedUnit,
                row => row?.Unit === selectedUnit
            ))
        },
        {
            containerId: 'leagueContinuityContextChart',
            path: 'data/charts/league_continuity_context_1s.json',
            emptyMessage: `No league returners data available for ${selectedSeason} (${selectedUnit}).`,
            filterSpec: spec => addIsSelectedToTrendDatasets(filterLeagueContextCombinedSpec(
                spec,
                row => row?.Season === selectedSeason && row?.Unit === selectedUnit,
                row => row?.Unit === selectedUnit
            ))
        }
    ];
    await Promise.all(charts.map(async chart => {
        try {
            const spec = await loadChartSpec(chart.path);
            if (!leagueSpecHasSeasonRows(spec, selectedSeason)) {
                renderStaticSpecChart(chart.containerId, null, `No league data available for ${selectedSeason}.`);
                return;
            }
            const filteredSpec = chart.filterSpec ? chart.filterSpec(spec) : spec;
            renderStaticSpecChart(chart.containerId, filteredSpec, chart.emptyMessage, { hideTitle: true });
        } catch (error) {
            console.warn(`Unable to load ${chart.path}:`, error);
            renderStaticSpecChart(chart.containerId, null, chart.emptyMessage);
        }
    }));
}

function renderSquadStatsCharts(selectedSeason, minimumAppearances, selectedUnit, trendViewMode) {
    renderSquadSizeTrendChart(selectedSeason, minimumAppearances, selectedUnit, trendViewMode);
    renderSquadContinuityTrendChart(selectedSeason, selectedUnit);
    renderSquadOverlapChart(selectedUnit);
    renderLeagueContextCharts();
}

function renderSquadOverlapChart(selectedUnit) {
    const container = document.getElementById('squadOverlapChart');
    if (!container) return;
    if (!squadOverlapTemplateSpec) {
        container.innerHTML = '<div class="text-center text-muted py-4">Squad overlap chart not available. Run <code>python update.py</code> to generate charts.</div>';
        return;
    }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadOverlapTemplateSpec));
    const unitFilterValue = selectedUnit || 'Total';
    const rowMatchesUnit = row => {
        const unit = row?.unit;
        if (unit === undefined || unit === null || unit === '') {
            return unitFilterValue === 'Total';
        }
        return unit === unitFilterValue;
    };

    if (spec.data && Array.isArray(spec.data.values)) {
        spec.data.values = spec.data.values.filter(rowMatchesUnit);
    }

    if (spec.datasets) {
        Object.keys(spec.datasets).forEach(name => {
            const rows = spec.datasets[name];
            if (!Array.isArray(rows)) return;
            spec.datasets[name] = rows.filter(rowMatchesUnit);
        });
    }

    renderStaticSpecChart('squadOverlapChart', spec, 'Squad overlap chart not available.', { hideTitle: true });
}

function renderSquadStatsPage() {
    if (!squadStatsWithThresholdsEnrichedData) return;
    refreshSquadStatsData();
    const seasons = getSortedSquadStatsSeasons(squadStatsData);
    if (seasons.length === 0) {
        const minimumAppearances = getSquadStatsMinimumAppearances();
        const gameTypeMode = getSquadStatsGameTypeMode();
        const positionCountMode = getSquadStatsPositionCountMode();
        const selectedUnit = getLeagueContextUnit();
        const trendViewMode = getSquadSizeTrendViewMode();
        const fallbackSeason = getCurrentSeasonLabel();
        renderSquadStatsHeroStats();
        renderSquadStatsActiveFilterChips('squadCompositionActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsActiveFilterChips('squadContinuityActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsActiveFilterChips('leagueContextActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit, {
            includeGameType: false,
            includeMinAppearances: false,
        });
        renderSquadPositionCompositionChart(fallbackSeason, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsCharts(fallbackSeason, minimumAppearances, selectedUnit, trendViewMode);
        return;
    }
    const selectedSeasonFromControls = getSquadStatsSelectedSeason();
    const selectedSeason = selectedSeasonFromControls || (seasons.includes(getCurrentSeasonLabel()) ? getCurrentSeasonLabel() : seasons[0]);
    const minimumAppearances = getSquadStatsMinimumAppearances();
    const gameTypeMode = getSquadStatsGameTypeMode();
    const positionCountMode = getSquadStatsPositionCountMode();
    const selectedUnit = getLeagueContextUnit();
    const trendViewMode = getSquadSizeTrendViewMode();
    applySquadStatsControlState({ season: selectedSeason, gameType: gameTypeMode, minimumAppearances, positionCountMode, unit: selectedUnit });
    renderSquadStatsHeroStats();
    renderSquadStatsActiveFilterChips('squadCompositionActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
    renderSquadStatsActiveFilterChips('squadContinuityActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
    renderSquadStatsActiveFilterChips('leagueContextActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit, {
        includeGameType: false,
        includeMinAppearances: false,
    });
    initialiseSquadStatsAnalysisRail();
    renderSquadPositionCompositionChart(selectedSeason, minimumAppearances, positionCountMode, selectedUnit);
    renderSquadStatsCharts(selectedSeason, minimumAppearances, selectedUnit, trendViewMode);
}

function initialiseSquadStatsControlsOnce() {
    if (squadStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const positionCountModeSelect = document.getElementById('squadStatsPositionCountModeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const squadStatsUnitSelect = document.getElementById('squadStatsUnitSelect');
    const squadSizeTrendViewSelect = document.getElementById('squadSizeTrendViewSelect');
    
    if (!seasonSelect || !gameTypeSelect || !positionCountModeSelect || !minAppsInput || !squadStatsUnitSelect) return;
    
    populateSquadStatsSeasonDropdownOptions();
    gameTypeSelect.value = DEFAULT_GAME_TYPE_MODE;
    positionCountModeSelect.value = 'appearance_position';
    minAppsInput.value = '0';
    squadStatsUnitSelect.value = 'Total';
    if (squadSizeTrendViewSelect) squadSizeTrendViewSelect.value = 'faceted';

    seasonSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        syncSeasonStepperFromSelect();
        applySquadStatsControlState({
            season: this.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || DEFAULT_GAME_TYPE_MODE,
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position',
            unit: squadStatsUnitSelect.value || 'Total'
        });
        renderSquadStatsPage();
        renderLeagueTables().catch(err => console.warn('League tables re-render on season change failed:', err));
    });

    const stepSeason = (direction) => {
        const newIndex = seasonSelect.selectedIndex + direction;
        if (newIndex < 0 || newIndex >= seasonSelect.options.length) return;
        seasonSelect.selectedIndex = newIndex;
        syncSeasonStepperFromSelect();
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || DEFAULT_GAME_TYPE_MODE,
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position',
            unit: squadStatsUnitSelect.value || 'Total'
        });
        renderSquadStatsPage();
        renderLeagueTables().catch(err => console.warn('League tables re-render on season step failed:', err));
    };

    // Offcanvas season stepper buttons
    const prevBtn = document.getElementById('squadStatsSeasonPrevOffcanvas');
    const nextBtn = document.getElementById('squadStatsSeasonNextOffcanvas');
    if (prevBtn) prevBtn.addEventListener('click', () => stepSeason(1));
    if (nextBtn) nextBtn.addEventListener('click', () => stepSeason(-1));

    gameTypeSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: this.value || DEFAULT_GAME_TYPE_MODE,
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position',
            unit: squadStatsUnitSelect.value || 'Total'
        });
        renderSquadStatsPage();
    });

    positionCountModeSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || DEFAULT_GAME_TYPE_MODE,
            minimumAppearances: minAppsInput.value,
            positionCountMode: this.value || 'appearance_position',
            unit: squadStatsUnitSelect.value || 'Total'
        });
        renderSquadStatsPage();
    });

    const gameTypeSegment = document.getElementById('squadStatsGameTypeSegment');
    if (gameTypeSegment) {
        gameTypeSegment.addEventListener('click', event => {
            const button = event.target.closest('.squad-filter-segment-btn');
            if (!button) return;
            const value = button.dataset.value;
            if (!value) return;
            suppressGameTypeSegmentSync = true;
            gameTypeSelect.value = value;
            suppressGameTypeSegmentSync = false;
            syncGameTypeSegmentFromSelect();
            renderSquadStatsPage();
        });
    }

    const positionCountModeSegment = document.getElementById('squadStatsPositionCountModeSegment');
    if (positionCountModeSegment) {
        positionCountModeSegment.addEventListener('click', event => {
            const button = event.target.closest('.squad-filter-segment-btn');
            if (!button) return;
            const value = button.dataset.value;
            if (!value) return;
            positionCountModeSelect.value = value;
            syncPositionCountModeSegmentFromSelect();
            renderSquadStatsPage();
        });
    }

    const onMinAppsChange = (sourceInput) => {
        let v = parseInt(sourceInput.value, 10);
        if (isNaN(v) || v < 0) v = 0;
        sourceInput.value = String(Math.floor(v));
        if (syncingSquadStatsControls) return;
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || DEFAULT_GAME_TYPE_MODE,
            minimumAppearances: v,
            positionCountMode: positionCountModeSelect.value || 'appearance_position',
            unit: squadStatsUnitSelect.value || 'Total'
        });
        renderSquadStatsPage();
    };

    minAppsInput.addEventListener('input', function () {
        onMinAppsChange(this);
        updateMinAppsDisplay();
    });
    minAppsInput.addEventListener('change', function () {
        onMinAppsChange(this);
        updateMinAppsDisplay();
    });

    squadStatsUnitSelect.addEventListener('change', function () {
        syncUnitSegmentFromSelect();
        renderSquadStatsPage();
    });

    const squadStatsUnitSegment = document.getElementById('squadStatsUnitSegment');
    if (squadStatsUnitSegment) {
        squadStatsUnitSegment.addEventListener('click', event => {
            const button = event.target.closest('.squad-filter-segment-btn');
            if (!button) return;
            const value = button.dataset.value;
            if (!value) return;
            squadStatsUnitSelect.value = value;
            syncUnitSegmentFromSelect();
            renderSquadStatsPage();
        });
    }

    if (squadSizeTrendViewSelect) {
        squadSizeTrendViewSelect.addEventListener('change', function () {
            syncSquadSizeTrendViewSegmentFromSelect();
            renderSquadStatsPage();
        });
    }

    const squadSizeTrendViewSegment = document.getElementById('squadSizeTrendViewSegment');
    if (squadSizeTrendViewSegment && squadSizeTrendViewSelect) {
        squadSizeTrendViewSegment.addEventListener('click', event => {
            const button = event.target.closest('.squad-filter-segment-btn');
            if (!button) return;
            const value = button.dataset.value;
            if (!value) return;
            squadSizeTrendViewSelect.value = value;
            syncSquadSizeTrendViewSegmentFromSelect();
            renderSquadStatsPage();
        });
    }

    syncGameTypeSegmentFromSelect();
    syncPositionCountModeSegmentFromSelect();
    syncUnitSegmentFromSelect();
    syncSquadSizeTrendViewSegmentFromSelect();
    updateMinAppsDisplay();

    syncOffcanvasFiltersFromMain();

    // Sync offcanvas when the offcanvas opens
    const offcanvas = document.getElementById('squadStatsFiltersOffcanvas');
    if (offcanvas) {
        offcanvas.addEventListener('show.bs.offcanvas', () => {
            syncOffcanvasFiltersFromMain();
        });
    }

    squadStatsControlsInitialised = true;
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    loadSquadStatsPage();
    initLeagueTablesEmbed().catch(err => console.error('League tables embed init failed:', err));
});
// Renders League Tables and League Results sections on Squad Stats page.
// Season is shared with the main squadStatsSeasonSelect.
// Squad filter is independent (leagueTablesSquadSelect / leagueTablesSquadSegment).

let _ltData = null;
let _ltResultsIndexData = null;
let _ltResultsScaleResizeBound = false;
const LT_RESULTS_COLOUR_UNEXPECTED = 'unexpected';
const LT_RESULTS_COLOUR_RESULT = 'result';

function _ltGetCurrentSeason() {
    const select = document.getElementById('squadStatsSeasonSelect');
    return select?.value || getCurrentSeasonLabel();
}

function _ltGetSelectedSquadFilter() {
    const select = document.getElementById('leagueTablesSquadSelect');
    return select?.value || 'All';
}

function _ltShouldIncludeSquad(squadLabel, selectedFilter) {
    if (selectedFilter === 'All') return true;
    return selectedFilter === squadLabel;
}

function _ltFormatSeasonShort(season) {
    if (!season || !season.includes('/')) return season || 'Unknown';
    const parts = season.split('/');
    if (parts.length !== 2) return season;
    return `${parts[0].slice(-2)}/${parts[1].slice(-2)}`;
}

function _ltGetSquadFilterLabel(value) {
    if (value === '1st') return '1st XV';
    if (value === '2nd') return '2nd XV';
    return 'Both squads';
}

function _ltGetOrdinalSuffix(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 'th';
    const mod100 = number % 100;
    if (mod100 >= 11 && mod100 <= 13) return 'th';
    switch (number % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
    }
}

function _ltCloneResultsSpec(spec) {
    if (typeof window.structuredClone === 'function') return window.structuredClone(spec);
    return JSON.parse(JSON.stringify(spec));
}

function _ltGetSelectedColourEncoding() {
    const toggle1 = document.getElementById('leagueTablesUnexpectedToggle1');
    const toggle2 = document.getElementById('leagueTablesUnexpectedToggle2');
    const toggle = toggle1 || toggle2;
    return toggle?.checked ? LT_RESULTS_COLOUR_UNEXPECTED : LT_RESULTS_COLOUR_RESULT;
}

function _ltDetectSelectionBinding(spec) {
    const specText = JSON.stringify(spec || {});
    const match = specText.match(/(param_\d+)\['([^']+)'\]/);
    if (!match) return null;
    return { paramName: match[1], field: match[2] };
}

function _ltApplyColourEncoding(spec, colourEncoding) {
    const nextSpec = _ltCloneResultsSpec(spec);
    if (!Array.isArray(nextSpec?.layer)) return nextSpec;

    const rectLayer = nextSpec.layer.find(layer => {
        const markType = typeof layer?.mark === 'string' ? layer.mark : layer?.mark?.type;
        return markType === 'rect';
    });

    if (!rectLayer?.encoding) return nextSpec;

    const selectionBinding = _ltDetectSelectionBinding(nextSpec);
    const selectionTest = selectionBinding
        ? `datum.home_team == ${selectionBinding.paramName}['${selectionBinding.field}'] || datum.away_team == ${selectionBinding.paramName}['${selectionBinding.field}'] || !isValid(${selectionBinding.paramName}['${selectionBinding.field}'])`
        : 'true';

    if (colourEncoding !== LT_RESULTS_COLOUR_RESULT) return nextSpec;

    rectLayer.encoding.color = {
        field: 'result_simple',
        type: 'nominal',
        title: null,
        legend: {
            labelLimit: 220,
            offset: 16,
            orient: 'bottom',
            symbolStrokeColor: 'black',
            symbolStrokeWidth: 1,
            values: ['Home Win', 'Draw', 'Away Win'],
        },
        scale: {
            domain: ['Home Win', 'Draw', 'Away Win', 'To be played', 'N/A'],
            range: ['#146f14', '#d4a017', '#991515', 'white', 'black'],
        },
    };

    rectLayer.encoding.opacity = {
        condition: [
            {
                test: `(${selectionTest}) && isValid(datum.home_score) && isValid(datum.away_score) && datum.home_score != datum.away_score && abs(datum.home_score - datum.away_score) <= 7`,
                value: 0.55,
            },
            { test: selectionTest, value: 1.0 },
        ],
        value: 0.1,
    };

    nextSpec.layer.forEach(layer => {
        const markType = typeof layer?.mark === 'string' ? layer.mark : layer?.mark?.type;
        const textField = layer?.encoding?.text?.field;
        const isScoreLabel = markType === 'text' && (textField === 'away_score_text' || textField === 'home_score_text');
        if (!isScoreLabel || !layer?.encoding) return;
        layer.encoding.color = { value: 'white' };
    });

    return nextSpec;
}

async function _ltLoadResultsIndex() {
    if (_ltResultsIndexData) return _ltResultsIndexData;
    try {
        const response = await fetch('data/charts/league_results_index.json');
        if (!response.ok) {
            console.warn(`Unable to load league results index (${response.status}).`);
            _ltResultsIndexData = {};
            return _ltResultsIndexData;
        }
        _ltResultsIndexData = await response.json();
    } catch (err) {
        console.error('Error loading league results index:', err);
        _ltResultsIndexData = {};
    }
    return _ltResultsIndexData;
}

function _ltGetResultsSpecPath(season, squad) {
    const normalizedSeason = toLeagueSeasonFormat(season);
    const seasonEntry = _ltResultsIndexData?.[normalizedSeason];
    const squadEntry = seasonEntry?.[String(squad)];
    if (squadEntry?.file) return `data/charts/${squadEntry.file}`;
    return `data/charts/league_results_${squad}s_${normalizedSeason}.json`;
}

function _ltScaleResultsEmbedToFit(container) {
    if (!container) return false;
    const embedHost = container.querySelector('.chart-embed-host');
    if (!embedHost) return false;

    const boundary = container.closest('.league-results-chart-card') || container;
    const availableWidth = Math.floor(boundary.clientWidth || container.clientWidth || 0);

    embedHost.style.transform = 'none';
    embedHost.style.transformOrigin = 'top left';
    embedHost.style.width = '';
    embedHost.style.height = '';
    container.style.width = '';
    container.style.height = '';

    const measureIntrinsicSize = () => {
        const svg = embedHost.querySelector('svg');
        let svgWidth = 0, svgHeight = 0;
        if (svg) {
            const vb = svg.viewBox?.baseVal;
            svgWidth = Number(vb?.width) || Number(svg.getAttribute('width')) || svg.width?.baseVal?.value || 0;
            svgHeight = Number(vb?.height) || Number(svg.getAttribute('height')) || svg.height?.baseVal?.value || 0;
        }
        const canvas = embedHost.querySelector('canvas');
        let canvasWidth = 0, canvasHeight = 0;
        if (canvas) {
            canvasWidth = Number(canvas.width) || Number(canvas.getAttribute('width')) || 0;
            canvasHeight = Number(canvas.height) || Number(canvas.getAttribute('height')) || 0;
        }
        const hostRect = embedHost.getBoundingClientRect();
        const scrollWidth = Math.ceil(embedHost.scrollWidth || 0);
        const scrollHeight = Math.ceil(embedHost.scrollHeight || 0);
        const width = Math.ceil(Math.max(svgWidth, canvasWidth, scrollWidth, hostRect.width || 0));
        const height = Math.ceil(Math.max(svgHeight, canvasHeight, scrollHeight, hostRect.height || 0));
        return { width, height };
    };

    const intrinsicSize = measureIntrinsicSize();
    if (!availableWidth || !intrinsicSize.width) return false;

    const scale = Math.min(1, availableWidth / intrinsicSize.width);
    const scaledWidth = Math.ceil(intrinsicSize.width * scale);
    const scaledHeight = Math.ceil(intrinsicSize.height * scale);

    embedHost.style.width = `${intrinsicSize.width}px`;
    embedHost.style.height = `${intrinsicSize.height}px`;
    embedHost.style.transform = `scale(${scale})`;
    container.style.maxWidth = '100%';
    container.style.width = `${Math.min(availableWidth, scaledWidth)}px`;
    container.style.height = `${scaledHeight}px`;

    window.requestAnimationFrame(() => {
        const refreshed = measureIntrinsicSize();
        const nextScale = Math.min(1, availableWidth / Math.max(1, refreshed.width));
        const nextScaledWidth = Math.ceil(refreshed.width * nextScale);
        const nextScaledHeight = Math.ceil(refreshed.height * nextScale);
        embedHost.style.width = `${refreshed.width}px`;
        embedHost.style.height = `${refreshed.height}px`;
        embedHost.style.transform = `scale(${nextScale})`;
        container.style.width = `${Math.min(availableWidth, nextScaledWidth)}px`;
        container.style.height = `${nextScaledHeight}px`;
    });

    boundary.style.overflowX = 'hidden';
    boundary.style.overflowY = 'visible';
    return true;
}

function _ltApplyScalingAll() {
    _ltScaleResultsEmbedToFit(document.getElementById('leagueResultsChart1'));
    _ltScaleResultsEmbedToFit(document.getElementById('leagueResultsChart2'));
}

function _ltBindScaleResize() {
    if (_ltResultsScaleResizeBound) return;
    _ltResultsScaleResizeBound = true;
    window.addEventListener('resize', () => window.requestAnimationFrame(_ltApplyScalingAll));
}

async function _ltRenderResultsChartsForSeason(season) {
    const colourEncoding = _ltGetSelectedColourEncoding();
    const tasks = [1, 2].map(async squad => {
        const containerId = `leagueResultsChart${squad}`;
        const chartHost = document.getElementById(containerId);
        if (!chartHost) return;
        const specPath = _ltGetResultsSpecPath(season, squad);
        try {
            const baseSpec = await loadChartSpec(specPath);
            await embedChartSpec(containerId, baseSpec, {
                containerId,
                actions: false,
                specCustomizer: (spec) => _ltApplyColourEncoding(spec, colourEncoding),
                emptyMessage: `No ${squad === 1 ? '1st' : '2nd'} XV league results available for this season.`,
            });
            _ltScaleResultsEmbedToFit(chartHost);
            window.requestAnimationFrame(() => _ltScaleResultsEmbedToFit(chartHost));
        } catch (error) {
            console.error(`Failed to load league results chart spec: ${specPath}`, error);
            renderStaticSpecChart(containerId, null, `Unable to load ${squad === 1 ? '1st' : '2nd'} XV league results chart.`);
        }
    });
    await Promise.all(tasks);
    _ltBindScaleResize();
}

function _ltInitResultsTooltips() {
    const tooltipText = 'By default, results are shown in green for a home win and red for an away win. Unexpected results (or "upsets") are those where a lower-ranked team beats a higher ranked team.';
    ['1', '2'].forEach(squadNum => {
        const btn = document.getElementById(`leagueTablesColourInfoBtn${squadNum}`);
        if (btn) {
            btn.setAttribute('data-bs-toggle', 'tooltip');
            btn.setAttribute('data-bs-placement', 'top');
            btn.setAttribute('data-bs-html', 'true');
            btn.title = tooltipText;
            try { if (window.bootstrap?.Tooltip) new window.bootstrap.Tooltip(btn); }
            catch (e) { console.warn('Could not initialize tooltip:', e); }
        }
    });
}

function _ltInitResultColourControls() {
    _ltInitResultsTooltips();
    const toggle1 = document.getElementById('leagueTablesUnexpectedToggle1');
    const toggle2 = document.getElementById('leagueTablesUnexpectedToggle2');

    const syncToggles = (sourceToggle) => {
        if (!toggle1 || !toggle2 || !sourceToggle) return;
        if (sourceToggle === toggle1) toggle2.checked = toggle1.checked;
        else if (sourceToggle === toggle2) toggle1.checked = toggle2.checked;
    };

    const handleToggleChange = (event) => {
        syncToggles(event?.currentTarget || null);
        _ltRenderResultsChartsForSeason(_ltGetCurrentSeason());
    };

    if (toggle1) toggle1.addEventListener('change', handleToggleChange);
    if (toggle2) toggle2.addEventListener('change', handleToggleChange);
}

function _ltRenderActiveFilterChips(season) {
    const standingsTarget = document.getElementById('leagueTablesStandingsActiveFilters');
    if (!standingsTarget) return;

    const shortSeason = _ltFormatSeasonShort(season);
    const MAIN_OFFCANVAS = 'squadStatsFiltersOffcanvas';
    const seasonChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${MAIN_OFFCANVAS}" aria-controls="${MAIN_OFFCANVAS}"><strong>Season</strong> <span class="d-none d-md-inline">${season}</span><span class="d-inline d-md-none">${shortSeason}</span></button>`;

    standingsTarget.innerHTML = seasonChip;
}

function _ltSyncSquadSegmentUI(value) {
    const segment = document.getElementById('leagueTablesSquadSegment');
    if (!segment) return;
    if (window.sharedUi?.syncSegmentButtons) {
        window.sharedUi.syncSegmentButtons(segment, value);
        return;
    }
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function _ltInitSquadControls() {
    // Squad filter removed — both squads are always shown.
}

function _ltGetSquadTableRow(squadRows = [], squadNumber) {
    return squadRows.find(row => {
        if (!row?.team) return false;
        const teamName = String(row.team).toLowerCase();
        if (!teamName.includes('east grinstead')) return false;
        return squadNumber === 1 ? !teamName.toLowerCase().includes('ii') : true;
    }) || null;
}

async function renderLeagueTables() {
    const season = _ltGetCurrentSeason();
    const standingsContainer = document.getElementById('leagueTablesStandingsContainer');
    const resultsContainer = document.getElementById('leagueTablesResultsContainer');
    if (!standingsContainer || !resultsContainer) return;

    _ltRenderActiveFilterChips(season);

    if (!_ltData || !_ltData[season]) {
        standingsContainer.innerHTML = '<p>No league table data available for this season.</p>';
        resultsContainer.innerHTML = '<p>No league results chart data available for this season.</p>';
        return;
    }

    const seasonData = _ltData[season];
    let standingsHtml = '';
    let resultsHtml = '';

    if (seasonData['1']) {
        const squad1 = seasonData['1'];
        standingsHtml += `
            <div class="col-lg-6 mb-4 league-results-column" data-league-results-squad="1">
                <h3 class="league-team-title league-section-title league-team-title-1st">1st XV</h3>
                <p class="league-division-title league-division-title-1st">${squad1.division}</p>
                <div style="background: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow-x: auto;">
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr style="background: #e5e4e7;">
                                <th style="text-align: center;">#</th>
                                <th>Team</th>
                                <th style="text-align: center;">P</th>
                                <th style="text-align: center;">W</th>
                                <th style="text-align: center;">D</th>
                                <th style="text-align: center;">L</th>
                                <th style="text-align: center;">PF</th>
                                <th style="text-align: center;">PA</th>
                                <th style="text-align: center;">PD</th>
                                <th style="text-align: center;">BP</th>
                                <th style="text-align: center;">Pts</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${squad1.tables.map(row => {
                                const isEGRFC = row.team.toLowerCase().includes('east grinstead') && !row.team.toLowerCase().includes('ii');
                                const rowClass = isEGRFC ? 'league-highlight-row league-highlight-row-1st' : '';
                                const bonusPoints = row.bonusPoints ?? ((row.triesBefore || 0) + (row.triesLost || 0));
                                return `<tr class="${rowClass}">
                                    <td style="text-align: center;">${row.position}</td>
                                    <td>${row.team}</td>
                                    <td style="text-align: center;">${row.played}</td>
                                    <td style="text-align: center;">${row.won}</td>
                                    <td style="text-align: center;">${row.drawn}</td>
                                    <td style="text-align: center;">${row.lost}</td>
                                    <td style="text-align: center;">${row.pointsFor}</td>
                                    <td style="text-align: center;">${row.pointsAgainst}</td>
                                    <td style="text-align: center;">${row.pointsDifference}</td>
                                    <td style="text-align: center;">${bonusPoints}</td>
                                    <td style="text-align: center;">${row.points}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>`;

        resultsHtml += `
            <div class="col-12 mb-4 league-results-column" data-league-results-squad="1">
                <h3 class="league-team-title league-section-title league-team-title-1st">1st XV</h3>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <p class="league-division-title league-division-title-1st">${squad1.division}</p>
                    <div class="chart-section-head chart-section-head--league-results-toggle">
                        <div class="squad-filter-control player-stats-section-filter" style="flex-direction: row; align-items: center; gap: 0.5rem;" role="group" aria-label="Results View">
                            <div class="form-check form-switch player-stats-motm-switch" style="margin-left: auto;">
                                <input class="form-check-input" type="checkbox" role="switch" id="leagueTablesUnexpectedToggle1" aria-label="Highlight unexpected results">
                                <label class="form-check-label" for="leagueTablesUnexpectedToggle1">Highlight upsets</label>
                            </div>
                            <button type="button" class="btn btn-link btn-sm p-0" id="leagueTablesColourInfoBtn1" title="Colour scheme explanation"><i class="bi bi-info-circle"></i></button>
                        </div>
                    </div>
                </div>
                <div class="league-results-chart-card">
                    <div id="leagueResultsChart1" class="chart-host chart-host--overflow-visible chart-host--intrinsic">Loading 1st XV league results chart...</div>
                </div>
            </div>`;
    }

    if (seasonData['2']) {
        const squad2 = seasonData['2'];
        standingsHtml += `
            <div class="col-lg-6 mb-4 league-results-column" data-league-results-squad="2">
                <h3 class="league-team-title league-section-title league-team-title-2nd">2nd XV</h3>
                <p class="league-division-title league-division-title-2nd">${squad2.division}</p>
                <div style="background: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow-x: auto;">
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr style="background: #e5e4e7;">
                                <th style="text-align: center;">#</th>
                                <th>Team</th>
                                <th style="text-align: center;">P</th>
                                <th style="text-align: center;">W</th>
                                <th style="text-align: center;">D</th>
                                <th style="text-align: center;">L</th>
                                <th style="text-align: center;">PF</th>
                                <th style="text-align: center;">PA</th>
                                <th style="text-align: center;">PD</th>
                                <th style="text-align: center;">BP</th>
                                <th style="text-align: center;">Pts</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${squad2.tables.map(row => {
                                const isEGRFC = row.team.toLowerCase().includes('east grinstead');
                                const rowClass = isEGRFC ? 'league-highlight-row league-highlight-row-2nd' : '';
                                const bonusPoints = row.bonusPoints ?? ((row.triesBefore || 0) + (row.triesLost || 0));
                                return `<tr class="${rowClass}">
                                    <td style="text-align: center;">${row.position}</td>
                                    <td>${row.team}</td>
                                    <td style="text-align: center;">${row.played}</td>
                                    <td style="text-align: center;">${row.won}</td>
                                    <td style="text-align: center;">${row.drawn}</td>
                                    <td style="text-align: center;">${row.lost}</td>
                                    <td style="text-align: center;">${row.pointsFor}</td>
                                    <td style="text-align: center;">${row.pointsAgainst}</td>
                                    <td style="text-align: center;">${row.pointsDifference}</td>
                                    <td style="text-align: center;">${bonusPoints}</td>
                                    <td style="text-align: center;">${row.points}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>`;

        resultsHtml += `
            <div class="col-12 mb-4 league-results-column" data-league-results-squad="2">
                <h3 class="league-team-title league-section-title league-team-title-2nd">2nd XV</h3>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <p class="league-division-title league-division-title-2nd">${squad2.division}</p>
                    <div class="chart-section-head chart-section-head--league-results-toggle">
                        <div class="squad-filter-control player-stats-section-filter" style="flex-direction: row; align-items: center; gap: 0.5rem;" role="group" aria-label="Results View">
                            <div class="form-check form-switch player-stats-motm-switch" style="margin-left: auto;">
                                <input class="form-check-input" type="checkbox" role="switch" id="leagueTablesUnexpectedToggle2" aria-label="Highlight unexpected results">
                                <label class="form-check-label" for="leagueTablesUnexpectedToggle2">Highlight upsets</label>
                            </div>
                            <button type="button" class="btn btn-link btn-sm p-0" id="leagueTablesColourInfoBtn2" title="Colour scheme explanation"><i class="bi bi-info-circle"></i></button>
                        </div>
                    </div>
                </div>
                <div class="league-results-chart-card">
                    <div id="leagueResultsChart2" class="chart-host chart-host--overflow-visible chart-host--intrinsic">Loading 2nd XV league results chart...</div>
                </div>
            </div>`;
    }

    if (!standingsHtml) standingsHtml = '<div class="col-12"><p>No league table data available for the selected squad in this season.</p></div>';
    if (!resultsHtml) resultsHtml = '<div class="col-12"><p>No league results chart data available for the selected squad in this season.</p></div>';

    standingsContainer.innerHTML = standingsHtml;
    resultsContainer.innerHTML = resultsHtml;

    await _ltRenderResultsChartsForSeason(season);
    _ltInitResultColourControls();
}

async function initLeagueTablesEmbed() {
    const standingsContainer = document.getElementById('leagueTablesStandingsContainer');
    if (!standingsContainer) return; // Not on squad-stats page

    try {
        const response = await fetch('data/league_tables.json');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        _ltData = await response.json();
    } catch (err) {
        console.error('Error loading league tables data:', err);
        return;
    }

    await _ltLoadResultsIndex();
    _ltInitSquadControls();
    await renderLeagueTables();
}

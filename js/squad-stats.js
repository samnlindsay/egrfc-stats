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

function renderSquadPositionCompositionChart(selectedSeason, minimumAppearances, positionCountMode) {
    const container = document.getElementById('squadPositionCompositionChart');
    if (!container) return;

    if (!squadPositionCompositionTemplateSpec) {
        container.innerHTML = '<div class="text-center text-muted py-4">Squad position composition chart template not available. Run <code>python update.py</code> to generate charts.</div>';
        return;
    }

    const mode = getSquadStatsGameTypeMode();
    const threshold = Math.max(0, Number(minimumAppearances) || 0);

    const rowFilter = row => (
        normalizeSeasonLabel(row?.season) === selectedSeason
        && row?.gameTypeMode === mode
        && Number(row?.minimumAppearances) === threshold
        && (row?.countMode || 'appearance_position') === positionCountMode
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
    return gameTypeSelect?.value || 'All games';
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

function applySquadStatsControlState({ season, gameType, minimumAppearances, positionCountMode }) {
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const positionCountModeSelect = document.getElementById('squadStatsPositionCountModeSelect');

    syncingSquadStatsControls = true;
    try {
        setSelectValue(seasonSelect, season);
        setSelectValue(gameTypeSelect, gameType);
        setSelectValue(positionCountModeSelect, positionCountMode);
        setMinAppsValue(minAppsInput, minimumAppearances);
        syncSeasonStepperFromSelect();
        syncGameTypeSegmentFromSelect();
        syncPositionCountModeSegmentFromSelect();
        updateMinAppsDisplay();
    } finally {
        syncingSquadStatsControls = false;
    }
}

function syncSeasonStepperFromSelect() {
    const select = document.getElementById('squadStatsSeasonSelect');
    const label = document.getElementById('squadStatsSeasonLabel');
    const prevBtn = document.getElementById('squadStatsSeasonPrev');
    const nextBtn = document.getElementById('squadStatsSeasonNext');
    if (!select || !label) return;
    label.textContent = select.value || '';
    if (prevBtn) prevBtn.disabled = select.selectedIndex <= 0;
    if (nextBtn) nextBtn.disabled = select.selectedIndex >= select.options.length - 1;
}

function syncGameTypeSegmentFromSelect() {
    if (suppressGameTypeSegmentSync) return;
    const select = document.getElementById('squadStatsGameTypeSelect');
    const segment = document.getElementById('squadStatsGameTypeSegment');
    if (!select || !segment) return;
    const value = select.value || 'All games';
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

function syncLeagueContextUnitSegmentFromSelect() {
    const select = document.getElementById('leagueContextUnitSelect');
    const segment = document.getElementById('leagueContextUnitSegment');
    if (!select || !segment) return;
    const value = select.value || 'Total';
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function renderSquadStatsActiveFilterChips(targetId, selectedSeason, gameTypeMode, minimumAppearances, positionCountMode) {
    const host = document.getElementById(targetId);
    if (!host) return;
    
    const chips = [
        `<span class="squad-stats-filter-chip"><strong>Season</strong> ${selectedSeason}</span>`,
        `<span class="squad-stats-filter-chip"><strong>Game Type</strong> ${gameTypeMode}</span>`,
        `<span class="squad-stats-filter-chip"><strong>Min Appearances</strong> ${minimumAppearances}</span>`
    ];
    
    host.innerHTML = chips.join('');
}

function renderSquadStatsHeroStats() {
    const selectedSeason = getSquadStatsSelectedSeason() || getCurrentSeasonLabel();
    const mode = getSquadStatsGameTypeMode();
    const minimumAppearances = getSquadStatsMinimumAppearances();
    const modeData = buildSquadStatsDataFromThresholds(squadStatsWithThresholdsEnrichedData || [], mode);
    const seasonKey = modeData[selectedSeason] ? selectedSeason : getCurrentSeasonLabel();
    const seasonData = modeData[seasonKey] || createSquadSeasonBucket();

    const value1st = getSquadMetricValue('Total', seasonData['1st'], minimumAppearances);
    const value2nd = getSquadMetricValue('Total', seasonData['2nd'], minimumAppearances);
    const valueTotal = getSquadMetricValue('Total', seasonData['Total'], minimumAppearances);

    const value1stEl = document.getElementById('squadStatsHeroValue1st');
    const value2ndEl = document.getElementById('squadStatsHeroValue2nd');
    const valueTotalEl = document.getElementById('squadStatsHeroValueTotal');
    const metaEl = document.getElementById('squadStatsHeroMeta');

    if (value1stEl) value1stEl.textContent = String(value1st);
    if (value2ndEl) value2ndEl.textContent = String(value2nd);
    if (valueTotalEl) valueTotalEl.textContent = String(valueTotal);
    if (metaEl) metaEl.textContent = `${seasonKey} • ${mode} • Min Apps ${minimumAppearances}`;
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
    const rail = document.querySelector('.squad-stats-layout .analysis-rail');
    if (!rail) return;

    const buttons = rail.querySelectorAll('.rail-link');
    if (!buttons.length) return;

    // Handle button clicks for smooth scroll
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                updateAnalysisRailActive(targetId);
            }
        });
    });

    // Handle scroll to update active link
    window.addEventListener('scroll', () => {
        updateAnalysisRailActiveOnScroll();
    }, { passive: true });

    // Set initial active section
    updateAnalysisRailActiveOnScroll();
    squadStatsAnalysisRailInitialised = true;
}

function updateAnalysisRailActive(sectionId) {
    const rail = document.querySelector('.squad-stats-layout .analysis-rail');
    if (!rail) return;

    const buttons = rail.querySelectorAll('.rail-link');
    buttons.forEach(button => {
        button.classList.remove('active');
        if (button.getAttribute('data-target') === sectionId) {
            button.classList.add('active');
        }
    });
}

function updateAnalysisRailActiveOnScroll() {
    const rail = document.querySelector('.squad-stats-layout .analysis-rail');
    if (!rail) return;

    const sections = document.querySelectorAll('.analysis-section[id]');
    let currentSection = sections[0]?.id;

    for (const section of sections) {
        const rect = section.getBoundingClientRect();
        // Consider section active if it's in the upper half of viewport
        if (rect.top < window.innerHeight / 2) {
            currentSection = section.id;
        }
    }

    updateAnalysisRailActive(currentSection);
}

function buildSquadSizeTrendRows(selectedSeason, minimumAppearances) {
    const seasons = getSortedSquadStatsSeasons(squadStatsData).slice().reverse();
    const rows = [];
    const toTrendValue = value => (value === 0 ? null : value);
    seasons.forEach(season => {
        const seasonData = squadStatsData?.[season];
        if (!seasonData) return;
        ['1st', '2nd'].forEach(squadKey => {
            const bucket = seasonData[squadKey];
            if (!bucket) return;
            const isSelected = season === selectedSeason;
            rows.push({ season, squad: squadKey, unit: 'Total', players: toTrendValue(getSquadMetricValue('Total', bucket, minimumAppearances)), isSelected });
            rows.push({ season, squad: squadKey, unit: 'Forwards', players: toTrendValue(getSquadMetricValue('Forwards', bucket, minimumAppearances)), isSelected });
            rows.push({ season, squad: squadKey, unit: 'Backs', players: toTrendValue(getSquadMetricValue('Backs', bucket, minimumAppearances)), isSelected });
        });
    });
    return rows;
}

function renderSquadSizeTrendChart(selectedSeason, minimumAppearances) {
    const container = document.getElementById('squadSizeTrendChart');
    if (!container) return;
    if (!squadSizeTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad size trend template not available. Run <code>python update.py</code> to generate charts.</div>'; return; }
    const values = buildSquadSizeTrendRows(selectedSeason, minimumAppearances);
    if (!values.length) { container.innerHTML = '<div class="text-center text-muted py-4">No squad size trend data available for the selected filters.</div>'; return; }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadSizeTrendTemplateSpec));
    spec.data = { values };
    if (spec.datasets) delete spec.datasets;
    renderStaticSpecChart('squadSizeTrendChart', spec, 'No squad size trend data available for the selected filters.', { hideTitle: true });
}

function buildContinuityAverageTrendRows() {
    const mode = getSquadStatsGameTypeMode();
    return (squadContinuityEnrichedData || [])
        .filter(row => row?.gameTypeMode === mode && ['1st', '2nd'].includes(row?.squad) && ['Total', 'Forwards', 'Backs'].includes(row?.unit))
        .map(row => ({
            season: normalizeSeasonLabel(row?.season),
            squad: row?.squad,
            unit: row?.unit,
            retained: Number(row?.retained) || 0
        }));
}

function renderSquadContinuityTrendChart(selectedSeason) {
    const container = document.getElementById('squadContinuityTrendChart');
    if (!container) return;
    if (!squadContinuityTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad returners trend template not available.</div>'; return; }
    const values = buildContinuityAverageTrendRows();
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
    const select = document.getElementById('leagueContextUnitSelect');
    return select?.value || 'Total';
}

async function renderLeagueContextCharts() {
    const selectedSeason = document.getElementById('squadStatsSeasonSelect')?.value || getCurrentSeasonLabel();
    const selectedUnit = getLeagueContextUnit();
    const charts = [
        {
            containerId: 'leagueSquadSizeContextChart',
            path: 'data/charts/league_squad_size_context_1s.json',
            emptyMessage: `No league squad size data available for ${selectedSeason} (${selectedUnit}).`,
            filterSpec: spec => filterLeagueContextCombinedSpec(
                spec,
                row => row?.Season === selectedSeason && row?.Unit === selectedUnit,
                row => row?.Unit === selectedUnit
            )
        },
        {
            containerId: 'leagueContinuityContextChart',
            path: 'data/charts/league_continuity_context_1s.json',
            emptyMessage: `No league returners data available for ${selectedSeason} (${selectedUnit}).`,
            filterSpec: spec => filterLeagueContextCombinedSpec(
                spec,
                row => row?.Season === selectedSeason && row?.Unit === selectedUnit,
                row => row?.Unit === selectedUnit
            )
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

function renderSquadStatsCharts(selectedSeason, minimumAppearances) {
    renderSquadSizeTrendChart(selectedSeason, minimumAppearances);
    renderSquadContinuityTrendChart(selectedSeason);
    renderSquadOverlapChart();
    renderLeagueContextCharts();
}

function renderSquadOverlapChart() {
    const container = document.getElementById('squadOverlapChart');
    if (!container) return;
    if (!squadOverlapTemplateSpec) {
        container.innerHTML = '<div class="text-center text-muted py-4">Squad overlap chart not available. Run <code>python update.py</code> to generate charts.</div>';
        return;
    }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadOverlapTemplateSpec));
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
        const fallbackSeason = getCurrentSeasonLabel();
        renderSquadStatsHeroStats();
        renderSquadStatsActiveFilterChips('squadCompositionActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode);
        renderSquadStatsActiveFilterChips('squadContinuityActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode);
        renderSquadStatsActiveFilterChips('leagueContextActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode);
        renderSquadPositionCompositionChart(fallbackSeason, minimumAppearances, positionCountMode);
        renderSquadStatsCharts(fallbackSeason, minimumAppearances);
        return;
    }
    const selectedSeasonFromControls = getSquadStatsSelectedSeason();
    const selectedSeason = selectedSeasonFromControls || (seasons.includes(getCurrentSeasonLabel()) ? getCurrentSeasonLabel() : seasons[0]);
    const minimumAppearances = getSquadStatsMinimumAppearances();
    const gameTypeMode = getSquadStatsGameTypeMode();
    const positionCountMode = getSquadStatsPositionCountMode();
    applySquadStatsControlState({ season: selectedSeason, gameType: gameTypeMode, minimumAppearances, positionCountMode });
    renderSquadStatsHeroStats();
    renderSquadStatsActiveFilterChips('squadCompositionActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode);
    renderSquadStatsActiveFilterChips('squadContinuityActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode);
    renderSquadStatsActiveFilterChips('leagueContextActiveFilters', selectedSeason, gameTypeMode, minimumAppearances, positionCountMode);
    initialiseSquadStatsAnalysisRail();
    renderSquadPositionCompositionChart(selectedSeason, minimumAppearances, positionCountMode);
    renderSquadStatsCharts(selectedSeason, minimumAppearances);
}

function initialiseSquadStatsControlsOnce() {
    if (squadStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const positionCountModeSelect = document.getElementById('squadStatsPositionCountModeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const leagueContextUnitSelect = document.getElementById('leagueContextUnitSelect');
    
    if (!seasonSelect || !gameTypeSelect || !positionCountModeSelect || !minAppsInput || !leagueContextUnitSelect) return;
    
    populateSquadStatsSeasonDropdownOptions();
    gameTypeSelect.value = 'All games';
    positionCountModeSelect.value = 'appearance_position';
    minAppsInput.value = '0';
    leagueContextUnitSelect.value = 'Total';

    seasonSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        syncSeasonStepperFromSelect();
        applySquadStatsControlState({
            season: this.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || 'All games',
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position'
        });
        renderSquadStatsPage();
    });

    const prevBtn = document.getElementById('squadStatsSeasonPrev');
    const nextBtn = document.getElementById('squadStatsSeasonNext');
    const stepSeason = (direction) => {
        const newIndex = seasonSelect.selectedIndex + direction;
        if (newIndex < 0 || newIndex >= seasonSelect.options.length) return;
        seasonSelect.selectedIndex = newIndex;
        syncSeasonStepperFromSelect();
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || 'All games',
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position'
        });
        renderSquadStatsPage();
    };
    if (prevBtn) prevBtn.addEventListener('click', () => stepSeason(-1));
    if (nextBtn) nextBtn.addEventListener('click', () => stepSeason(1));

    gameTypeSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: this.value || 'All games',
            minimumAppearances: minAppsInput.value,
            positionCountMode: positionCountModeSelect.value || 'appearance_position'
        });
        renderSquadStatsPage();
    });

    positionCountModeSelect.addEventListener('change', function () {
        if (syncingSquadStatsControls) return;
        applySquadStatsControlState({
            season: seasonSelect.value || getCurrentSeasonLabel(),
            gameType: gameTypeSelect.value || 'All games',
            minimumAppearances: minAppsInput.value,
            positionCountMode: this.value || 'appearance_position'
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
            gameType: gameTypeSelect.value || 'All games',
            minimumAppearances: v,
            positionCountMode: positionCountModeSelect.value || 'appearance_position'
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

    leagueContextUnitSelect.addEventListener('change', function () {
        syncLeagueContextUnitSegmentFromSelect();
        renderLeagueContextCharts();
    });

    const leagueContextUnitSegment = document.getElementById('leagueContextUnitSegment');
    if (leagueContextUnitSegment) {
        leagueContextUnitSegment.addEventListener('click', event => {
            const button = event.target.closest('.squad-filter-segment-btn');
            if (!button) return;
            const value = button.dataset.value;
            if (!value) return;
            leagueContextUnitSelect.value = value;
            syncLeagueContextUnitSegmentFromSelect();
            renderLeagueContextCharts();
        });
    }

    syncGameTypeSegmentFromSelect();
    syncPositionCountModeSegmentFromSelect();
    syncLeagueContextUnitSegmentFromSelect();
    updateMinAppsDisplay();

    squadStatsControlsInitialised = true;
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    loadSquadStatsPage();
});

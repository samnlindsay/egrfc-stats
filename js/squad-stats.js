// Squad Stats + Player Stats page logic

let squadStatsWithThresholdsEnrichedData = null;
let squadPositionProfilesEnrichedData = null;
let squadContinuityEnrichedData = null;
let squadStatsData = null;
let squadSizeTrendTemplateSpec = null;
let squadContinuityTrendTemplateSpec = null;
let squadStatsControlsInitialised = false;

async function loadSquadStatsCanonicalData() {
    if (squadStatsWithThresholdsEnrichedData && squadPositionProfilesEnrichedData && squadContinuityEnrichedData) return;

    const [statsResponse, positionsResponse, continuityResponse] = await Promise.all([
        fetch('data/backend/squad_stats_with_thresholds_enriched.json'),
        fetch('data/backend/squad_position_profiles_enriched.json'),
        fetch('data/backend/squad_continuity_enriched.json')
    ]);

    if (!statsResponse.ok) throw new Error(`Failed to fetch squad stats export (${statsResponse.status})`);
    if (!positionsResponse.ok) throw new Error(`Failed to fetch squad position profiles export (${positionsResponse.status})`);
    if (!continuityResponse.ok) throw new Error(`Failed to fetch squad continuity export (${continuityResponse.status})`);

    squadStatsWithThresholdsEnrichedData = await statsResponse.json();
    squadPositionProfilesEnrichedData = await positionsResponse.json();
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
}

function createSquadMetricBucket() {
    return { playersByThreshold: {}, forwardsByThreshold: {}, backsByThreshold: {} };
}

function createSquadSeasonBucket() {
    return { '1st': createSquadMetricBucket(), '2nd': createSquadMetricBucket(), 'Total': createSquadMetricBucket() };
}

function parsePlayerCountsMap(value) {
    if (value instanceof Map) return new Map(value);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        return new Map(Object.entries(value).map(([player, count]) => [player, Number(count) || 0]));
    }
    if (typeof value === 'string' && value.trim()) {
        try {
            const parsed = JSON.parse(value);
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                return new Map(Object.entries(parsed).map(([player, count]) => [player, Number(count) || 0]));
            }
        } catch (error) {
            console.warn('Unable to parse playerCounts payload:', error);
        }
    }
    return new Map();
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
        ['squadPositionCards1st', 'squadPositionCards2nd'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="text-center text-danger py-3">Unable to load position data.</div>';
        });
    }
}

function getEmptySquadPositionCounts() {
    const createPositionCounts = () => {
        const counts = {};
        SQUAD_POSITION_ORDER.forEach(position => { counts[position] = 0; });
        return counts;
    };
    return { '1st': createPositionCounts(), '2nd': createPositionCounts() };
}

function buildSquadPositionCounts(selectedSeason, minimumAppearances) {
    const counts = getEmptySquadPositionCounts();
    if (!squadPositionProfilesEnrichedData || !selectedSeason) return counts;
    const mode = getSquadStatsGameTypeMode();
    const threshold = Math.max(0, Number(minimumAppearances) || 0);
    (squadPositionProfilesEnrichedData || []).forEach(row => {
        const season = normalizeSeasonLabel(row?.season);
        const squad = row?.squad;
        const position = row?.position;
        if (season !== selectedSeason || row?.gameTypeMode !== mode) return;
        if (!['1st', '2nd'].includes(squad)) return;
        if (!SQUAD_POSITION_ORDER.includes(position)) return;
        const playerMap = parsePlayerCountsMap(row?.playerCounts);
        if (threshold <= 0) {
            counts[squad][position] = playerMap.size;
            return;
        }
        let playerCount = 0;
        playerMap.forEach(value => { if (value >= threshold) playerCount += 1; });
        counts[squad][position] = playerCount;
    });
    return counts;
}

function buildPositionCardsMarkup(positionCounts) {
    const renderCard = (position, value, section) => `
        <div class="squad-position-card squad-position-card--${section}">
            <div class="squad-position-card-title squad-position-card-title--${section}">${position}</div>
            <div class="squad-position-card-value squad-position-card-value--${section}">${value}</div>
        </div>
    `;
    const forwardsRow = FORWARD_POSITIONS.map(p => renderCard(p, positionCounts[p] || 0, 'forwards')).join('');
    const backsRow = BACK_POSITIONS.map(p => renderCard(p, positionCounts[p] || 0, 'backs')).join('');
    return `
        <div class="squad-position-cards-grid">
            <div class="squad-position-cards-row">${forwardsRow}</div>
            <div class="squad-position-cards-row">${backsRow}</div>
        </div>
    `;
}

function renderSquadPositionPanels(selectedSeason, minimumAppearances) {
    const counts = buildSquadPositionCounts(selectedSeason, minimumAppearances);
    const cards1st = document.getElementById('squadPositionCards1st');
    const cards2nd = document.getElementById('squadPositionCards2nd');
    const subtitle1st = document.getElementById('squadPositionSubtitle1st');
    const subtitle2nd = document.getElementById('squadPositionSubtitle2nd');
    const subtitleText = minimumAppearances > 1 ? `Players with ${minimumAppearances}+ appearances in position` : 'Players used in each position';
    if (subtitle1st) subtitle1st.textContent = subtitleText;
    if (subtitle2nd) subtitle2nd.textContent = subtitleText;
    if (cards1st) cards1st.innerHTML = buildPositionCardsMarkup(counts['1st']);
    if (cards2nd) cards2nd.innerHTML = buildPositionCardsMarkup(counts['2nd']);
}

function getSquadMetricValue(unit, bucket, minimumAppearances = 0) {
    if (!bucket) return 0;
    const threshold = Math.max(0, Number(minimumAppearances) || 0);
    const getValueAtThreshold = thresholdMap => Number(thresholdMap?.[threshold]) || 0;
    if (unit === 'Forwards') return getValueAtThreshold(bucket.forwardsByThreshold);
    if (unit === 'Backs') return getValueAtThreshold(bucket.backsByThreshold);
    return getValueAtThreshold(bucket.playersByThreshold);
}

function getSquadMetricCardLabel(minimumAppearances) {
    if (minimumAppearances > 1) return `Players with ${minimumAppearances} or more games`;
    return 'Players used';
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

function getSquadStatsSeasonOptions() {
    const seasonSet = new Set();
    const addSeason = season => { const normalized = normalizeSeasonLabel(season); if (normalized) seasonSet.add(normalized); };
    (availableSeasons || []).forEach(addSeason);
    (squadStatsWithThresholdsEnrichedData || []).forEach(row => addSeason(row?.season));
    addSeason(getCurrentSeasonLabel());
    return getSortedSquadStatsSeasons(Object.fromEntries(Array.from(seasonSet).map(s => [s, true])));
}

function populateSquadStatsSeasonDropdownOptions(seasonSelect) {
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
    return finalSeasons;
}

function refreshSquadStatsData() {
    if (!squadStatsWithThresholdsEnrichedData) { squadStatsData = {}; return; }
    const mode = getSquadStatsGameTypeMode();
    squadStatsData = buildSquadStatsDataFromThresholds(squadStatsWithThresholdsEnrichedData, mode);
}

function renderSquadMetricCards(season, minimumAppearances) {
    const seasonData = squadStatsData?.[season] || createSquadSeasonBucket();
    const labelText = getSquadMetricCardLabel(minimumAppearances);
    const value1st = document.getElementById('squadMetricValue1st');
    const value2nd = document.getElementById('squadMetricValue2nd');
    const valueTotal = document.getElementById('squadMetricValueTotal');
    const label1st = document.getElementById('squadMetricLabel1st');
    const label2nd = document.getElementById('squadMetricLabel2nd');
    const labelTotal = document.getElementById('squadMetricLabelTotal');
    if (value1st) value1st.textContent = getSquadMetricValue('Total', seasonData['1st'], minimumAppearances);
    if (value2nd) value2nd.textContent = getSquadMetricValue('Total', seasonData['2nd'], minimumAppearances);
    if (valueTotal) valueTotal.textContent = getSquadMetricValue('Total', seasonData['Total'], minimumAppearances);
    if (label1st) label1st.textContent = labelText;
    if (label2nd) label2nd.textContent = labelText;
    if (labelTotal) labelTotal.textContent = labelText;
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
    vegaEmbed('#squadSizeTrendChart', spec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' })
        .then(() => pinVegaActionsInElement(container))
        .catch(error => { console.error('Error rendering squad size trend chart:', error); container.innerHTML = '<div class="text-center text-danger py-4">Unable to render squad size trend chart.</div>'; });
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
    if (!squadContinuityTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad continuity trend template not available.</div>'; return; }
    const values = buildContinuityAverageTrendRows();
    if (!values.length) { container.innerHTML = '<div class="text-center text-muted py-4">No continuity data available for the selected filters.</div>'; return; }
    container.innerHTML = '';
    const spec = JSON.parse(JSON.stringify(squadContinuityTrendTemplateSpec));
    spec.data = { values };
    if (spec.datasets) delete spec.datasets;
    vegaEmbed('#squadContinuityTrendChart', spec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' })
        .then(() => pinVegaActionsInElement(container))
        .catch(error => { console.error('Error rendering continuity trend chart:', error); container.innerHTML = '<div class="text-center text-danger py-4">Unable to render continuity trend chart.</div>'; });
}

function getLeagueContextUnit() {
    const select = document.getElementById('leagueContextUnitSelect');
    if (select?.value) return select.value;
    const selectAlt = document.getElementById('leagueContextUnitSelectAlt');
    return selectAlt?.value || 'Total';
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
            emptyMessage: `No league squad continuity data available for ${selectedSeason} (${selectedUnit}).`,
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
            const filteredSpec = chart.filterSpec ? chart.filterSpec(spec) : spec;
            renderStaticSpecChart(chart.containerId, filteredSpec, chart.emptyMessage);
        } catch (error) {
            console.warn(`Unable to load ${chart.path}:`, error);
            renderStaticSpecChart(chart.containerId, null, chart.emptyMessage);
        }
    }));
}

function renderSquadStatsCharts(selectedSeason, minimumAppearances) {
    renderSquadSizeTrendChart(selectedSeason, minimumAppearances);
    renderSquadContinuityTrendChart(selectedSeason);
    renderLeagueContextCharts();
}

function renderSquadStatsPage() {
    if (!squadStatsWithThresholdsEnrichedData) return;
    refreshSquadStatsData();
    const seasons = getSortedSquadStatsSeasons(squadStatsData);
    if (seasons.length === 0) {
        const minimumAppearances = getSquadStatsMinimumAppearances();
        const fallbackSeason = getCurrentSeasonLabel();
        renderSquadMetricCards(fallbackSeason, minimumAppearances);
        renderSquadStatsCharts(fallbackSeason, minimumAppearances);
        return;
    }
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const selectedSeason = seasonSelect?.value || (seasons.includes(getCurrentSeasonLabel()) ? getCurrentSeasonLabel() : seasons[0]);
    const minimumAppearances = getSquadStatsMinimumAppearances();
    if (seasonSelect && seasonSelect.value !== selectedSeason) {
        const $seasonSelect = $('#squadStatsSeasonSelect');
        if ($seasonSelect.data('selectpicker')) $seasonSelect.selectpicker('val', selectedSeason);
        else seasonSelect.value = selectedSeason;
    }
    renderSquadMetricCards(selectedSeason, minimumAppearances);
    renderSquadPositionPanels(selectedSeason, minimumAppearances);
    renderSquadStatsCharts(selectedSeason, minimumAppearances);
    initialiseChartPanelToggles();
}

function initialiseSquadStatsControlsOnce() {
    if (squadStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const leagueContextUnitSelect = document.getElementById('leagueContextUnitSelect');
    const leagueContextUnitSelectAlt = document.getElementById('leagueContextUnitSelectAlt');
    if (!seasonSelect || !gameTypeSelect || !minAppsInput || !leagueContextUnitSelect || !leagueContextUnitSelectAlt) return;
    const $seasonSelect = $('#squadStatsSeasonSelect');
    const $gameTypeSelect = $('#squadStatsGameTypeSelect');
    const $leagueContextUnitSelect = $('#leagueContextUnitSelect');
    const $leagueContextUnitSelectAlt = $('#leagueContextUnitSelectAlt');
    $seasonSelect.selectpicker();
    const seasons = populateSquadStatsSeasonDropdownOptions(seasonSelect);
    const currentSeason = getCurrentSeasonLabel();
    seasonSelect.value = seasons.includes(currentSeason) ? currentSeason : seasons[0];
    const selectedSquadSeason = seasonSelect.value;
    $seasonSelect.selectpicker('destroy');
    $seasonSelect.selectpicker();
    $seasonSelect.selectpicker('val', selectedSquadSeason);
    $gameTypeSelect.selectpicker();
    $leagueContextUnitSelect.selectpicker();
    $leagueContextUnitSelectAlt.selectpicker();
    gameTypeSelect.value = 'All games';
    minAppsInput.value = '0';
    leagueContextUnitSelect.value = 'Total';
    leagueContextUnitSelectAlt.value = 'Total';
    $gameTypeSelect.selectpicker('val', 'All games');
    $leagueContextUnitSelect.selectpicker('val', 'Total');
    $leagueContextUnitSelectAlt.selectpicker('val', 'Total');
    $seasonSelect.on('changed.bs.select', renderSquadStatsPage);
    $gameTypeSelect.on('changed.bs.select', renderSquadStatsPage);
    minAppsInput.addEventListener('input', function () {
        let v = parseInt(this.value, 10);
        if (isNaN(v) || v < 0) v = 0;
        this.value = String(Math.floor(v));
        renderSquadStatsPage();
    });
    minAppsInput.addEventListener('change', function () {
        let v = parseInt(this.value, 10);
        if (isNaN(v) || v < 0) v = 0;
        this.value = String(v);
        renderSquadStatsPage();
    });
    $leagueContextUnitSelect.on('changed.bs.select', function () {
        const value = this.value || 'Total';
        if (leagueContextUnitSelectAlt.value !== value) {
            $leagueContextUnitSelectAlt.selectpicker('val', value);
        }
        renderLeagueContextCharts();
    });
    $leagueContextUnitSelectAlt.on('changed.bs.select', function () {
        const value = this.value || 'Total';
        if (leagueContextUnitSelect.value !== value) {
            $leagueContextUnitSelect.selectpicker('val', value);
        }
        renderLeagueContextCharts();
    });
    squadStatsControlsInitialised = true;
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    loadSquadStatsPage();
});

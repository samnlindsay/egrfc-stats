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
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Season</strong> ${selectedSeason}</button>`);
    }
    if (includeGameType) {
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Game Type</strong> ${gameTypeMode}</button>`);
    }
    if (includeMinAppearances) {
        chips.push(`<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#squadStatsFiltersOffcanvas" aria-controls="squadStatsFiltersOffcanvas"><strong>Min Appearances</strong> ${minimumAppearances}</button>`);
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
    const rail = document.querySelector('.squad-stats-layout .analysis-rail');
    if (!rail) return;

    const layout = rail.closest('.squad-stats-layout');
    const placeholder = document.createElement('div');
    placeholder.className = 'analysis-rail-placeholder';
    rail.insertAdjacentElement('afterend', placeholder);

    const links = rail.querySelectorAll('.rail-link[href^="#"]');
    if (!links.length) return;

    const pinState = {
        triggerScrollY: 0,
        hysteresis: 8
    };

    const recalculatePinTrigger = () => {
        const navOffset = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-offset')) || 74;
        const pinTop = navOffset + 7;
        const wasPinned = rail.classList.contains('is-pinned');

        if (wasPinned) {
            rail.classList.remove('is-pinned');
            rail.style.removeProperty('--analysis-rail-fixed-left');
            rail.style.removeProperty('--analysis-rail-fixed-width');
            placeholder.style.display = 'none';
            placeholder.style.height = '0px';
        }

        const naturalTop = rail.getBoundingClientRect().top + window.scrollY;
        pinState.triggerScrollY = Math.max(0, naturalTop - pinTop);

        if (wasPinned) {
            updateSquadStatsAnalysisRailPinnedState(rail, layout, placeholder, pinState);
        }
    };

    links.forEach(link => {
        link.addEventListener('click', (event) => {
            const targetId = link.getAttribute('href')?.replace('#', '');
            const targetSection = targetId ? document.getElementById(targetId) : null;
            if (!targetSection) return;
            event.preventDefault();
            targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (window.location.hash !== `#${targetId}`) {
                window.history.replaceState(null, '', `#${targetId}`);
            }
            window.setTimeout(() => {
                recalculatePinTrigger();
                updateSquadStatsAnalysisRailPinnedState(rail, layout, placeholder, pinState);
                updateAnalysisRailActiveOnScroll();
            }, 120);
        });
    });

    const navOffset = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-offset')) || 74;
    const railHeight = rail.getBoundingClientRect().height || 48;
    const scrollSpy = window.bootstrap?.ScrollSpy
        ? window.bootstrap.ScrollSpy.getOrCreateInstance(document.body, {
            target: '#squadStatsAnalysisRail',
            offset: Math.ceil(navOffset + railHeight + 12)
        })
        : null;

    const syncActiveLink = () => {
        rail.querySelectorAll('.rail-link').forEach(link => {
            if (link.classList.contains('active')) link.setAttribute('aria-current', 'true');
            else link.removeAttribute('aria-current');
        });
    };

    document.body.addEventListener('activate.bs.scrollspy', syncActiveLink);
    syncActiveLink();
    scrollSpy?.refresh();

    const refreshRail = () => {
        updateSquadStatsAnalysisRailPinnedState(rail, layout, placeholder, pinState);
        updateAnalysisRailActiveOnScroll();
    };

    let refreshRaf = null;
    const scheduleRefresh = () => {
        if (refreshRaf !== null) return;
        refreshRaf = window.requestAnimationFrame(() => {
            refreshRaf = null;
            refreshRail();
        });
    };

    let recalcRaf = null;
    const scheduleRecalculate = () => {
        if (recalcRaf !== null) return;
        recalcRaf = window.requestAnimationFrame(() => {
            recalcRaf = null;
            recalculatePinTrigger();
            refreshRail();
        });
    };

    window.addEventListener('scroll', scheduleRefresh, { passive: true });
    window.addEventListener('resize', scheduleRecalculate);
    recalculatePinTrigger();
    refreshRail();
    window.setTimeout(scheduleRecalculate, 250);
    window.setTimeout(scheduleRecalculate, 900);

    // Apply deep-link hash on initial load if present.
    const initialHash = String(window.location.hash || '').replace('#', '');
    if (initialHash) {
        const targetSection = document.getElementById(initialHash);
        if (targetSection) {
            window.setTimeout(() => {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                scrollSpy?.refresh();
                syncActiveLink();
                recalculatePinTrigger();
                refreshRail();
            }, 80);
        }
    }

    squadStatsAnalysisRailInitialised = true;
}

function updateSquadStatsAnalysisRailPinnedState(rail, layout, placeholder, pinState = null) {
    if (!rail || !layout || !placeholder) return;
    const triggerScrollY = Number(pinState?.triggerScrollY ?? 0);
    const hysteresis = Number(pinState?.hysteresis ?? 0);
    const isPinned = rail.classList.contains('is-pinned');
    const scrollY = window.scrollY;
    const shouldPin = isPinned
        ? scrollY >= (triggerScrollY - hysteresis)
        : scrollY >= (triggerScrollY + hysteresis);

    if (!shouldPin) {
        rail.classList.remove('is-pinned');
        rail.style.removeProperty('--analysis-rail-fixed-left');
        rail.style.removeProperty('--analysis-rail-fixed-width');
        placeholder.style.display = 'none';
        placeholder.style.height = '0px';
        return;
    }

    const layoutRect = layout.getBoundingClientRect();
    const viewportPadding = 8;
    const left = Math.max(viewportPadding, layoutRect.left);
    const available = window.innerWidth - (viewportPadding * 2);
    const width = Math.max(220, Math.min(layoutRect.width, available));

    rail.classList.add('is-pinned');
    rail.style.setProperty('--analysis-rail-fixed-left', `${left}px`);
    rail.style.setProperty('--analysis-rail-fixed-width', `${width}px`);
    placeholder.style.display = 'block';
    placeholder.style.height = `${Math.ceil(rail.offsetHeight)}px`;
}

function updateAnalysisRailActive(sectionId) {
    const rail = document.querySelector('.squad-stats-layout .analysis-rail');
    if (!rail) return;

    const buttons = rail.querySelectorAll('.rail-link');
    buttons.forEach(button => {
        const isActive = button.getAttribute('href') === `#${sectionId}`;
        button.classList.toggle('active', isActive);
        if (isActive) button.setAttribute('aria-current', 'true');
        else button.removeAttribute('aria-current');
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

function getUnitsForTrendCharts(selectedUnit) {
    if (selectedUnit === 'Forwards' || selectedUnit === 'Backs') return [selectedUnit];
    return ['Total', 'Forwards', 'Backs'];
}

function buildSquadSizeTrendRows(selectedSeason, minimumAppearances, selectedUnit) {
    const seasons = getSortedSquadStatsSeasons(squadStatsData).slice().reverse();
    const rows = [];
    const toTrendValue = value => (value === 0 ? null : value);
    const unitsToInclude = getUnitsForTrendCharts(selectedUnit);
    const squadPanels = [
        { bucketKey: '1st', squad: '1st' },
        { bucketKey: '2nd', squad: '2nd' },
        { bucketKey: 'Total', squad: 'Total' },
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

function renderSquadSizeTrendChart(selectedSeason, minimumAppearances, selectedUnit) {
    const container = document.getElementById('squadSizeTrendChart');
    if (!container) return;
    if (!squadSizeTrendTemplateSpec) { container.innerHTML = '<div class="text-center text-muted py-4">Squad size trend template not available. Run <code>python update.py</code> to generate charts.</div>'; return; }
    const values = buildSquadSizeTrendRows(selectedSeason, minimumAppearances, selectedUnit);
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

function renderSquadStatsCharts(selectedSeason, minimumAppearances, selectedUnit) {
    renderSquadSizeTrendChart(selectedSeason, minimumAppearances, selectedUnit);
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
            // Backward-compatible fallback for older specs without unit field.
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
        const fallbackSeason = getCurrentSeasonLabel();
        renderSquadStatsHeroStats();
        renderSquadStatsActiveFilterChips('squadCompositionActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsActiveFilterChips('squadContinuityActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsActiveFilterChips('leagueContextActiveFilters', fallbackSeason, gameTypeMode, minimumAppearances, positionCountMode, selectedUnit, {
            includeGameType: false,
            includeMinAppearances: false,
        });
        renderSquadPositionCompositionChart(fallbackSeason, minimumAppearances, positionCountMode, selectedUnit);
        renderSquadStatsCharts(fallbackSeason, minimumAppearances, selectedUnit);
        return;
    }
    const selectedSeasonFromControls = getSquadStatsSelectedSeason();
    const selectedSeason = selectedSeasonFromControls || (seasons.includes(getCurrentSeasonLabel()) ? getCurrentSeasonLabel() : seasons[0]);
    const minimumAppearances = getSquadStatsMinimumAppearances();
    const gameTypeMode = getSquadStatsGameTypeMode();
    const positionCountMode = getSquadStatsPositionCountMode();
    const selectedUnit = getLeagueContextUnit();
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
    renderSquadStatsCharts(selectedSeason, minimumAppearances, selectedUnit);
}

function initialiseSquadStatsControlsOnce() {
    if (squadStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const positionCountModeSelect = document.getElementById('squadStatsPositionCountModeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const squadStatsUnitSelect = document.getElementById('squadStatsUnitSelect');
    
    if (!seasonSelect || !gameTypeSelect || !positionCountModeSelect || !minAppsInput || !squadStatsUnitSelect) return;
    
    populateSquadStatsSeasonDropdownOptions();
    gameTypeSelect.value = DEFAULT_GAME_TYPE_MODE;
    positionCountModeSelect.value = 'appearance_position';
    minAppsInput.value = '0';
    squadStatsUnitSelect.value = 'Total';

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

    syncGameTypeSegmentFromSelect();
    syncPositionCountModeSegmentFromSelect();
    syncUnitSegmentFromSelect();
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
});

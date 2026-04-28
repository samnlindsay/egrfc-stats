// Player Stats page logic

let playerStatsControlsInitialised = false;
let playerStatsDataSeasons = [];
let playerStatsBaseSpecs = null;
let playerStatsAnalysisRailInitialised = false;

const PLAYER_STATS_DEFAULT_GAME_TYPE = 'All';
const PLAYER_STATS_DEFAULT_SCORE_TYPE = 'Total';
const PLAYER_STATS_DEFAULT_MOTM_AGGREGATE = false;
const PLAYER_STATS_ALL_SEASONS_VALUE = '__all_seasons__';
const PLAYER_STATS_STARTER_POSITIONS_VALUE = 'Starters';
const PLAYER_STATS_DEFAULT_COMBINATION = 'front_row';
const PLAYER_STATS_COMBINATION_OPTIONS = [
    { value: 'front_row', label: 'Front Row' },
    { value: 'second_row', label: 'Second Row' },
    { value: 'back_row', label: 'Back Row' },
    { value: 'half_backs', label: 'Half Backs' },
    { value: 'centres', label: 'Centre' },
    { value: 'back_three', label: 'Back Three' },
];
const PLAYER_STATS_FORWARD_POSITIONS = ['Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8'];
const PLAYER_STATS_BACK_POSITIONS = ['Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back'];

const PLAYER_STATS_MIN_THRESHOLDS = {
    appearances: { inputId: 'playerStatsMinAppearancesInput', valueId: 'playerStatsMinAppearancesValue', min: 1, max: 100, defaultValue: 10 },
    points: { inputId: 'playerStatsMinPointsInput', valueId: 'playerStatsMinPointsValue', min: 1, max: 200, defaultValue: 10 },
    captains: { inputId: 'playerStatsMinCaptainsInput', valueId: 'playerStatsMinCaptainsValue', min: 1, max: 50, defaultValue: 1 },
    motm: { inputId: 'playerStatsMinMotmInput', valueId: 'playerStatsMinMotmValue', min: 1, max: 30, defaultValue: 1 },
    combinations: { inputId: 'playerStatsMinCombinationsInput', valueId: 'playerStatsMinCombinationsValue', min: 1, max: 50, defaultValue: 10 },
};

let playerStatsSelectedPositions = new Set();

function sortSeasonLabelsDescending(seasons) {
    return Array.from(new Set((seasons || []).filter(Boolean))).sort((a, b) => {
        const aYear = Number(String(a).split('/')[0]) || 0;
        const bYear = Number(String(b).split('/')[0]) || 0;
        return bYear - aYear;
    });
}

function extractSeasonsFromSpec(spec) {
    if (!spec || typeof spec !== 'object' || !spec.datasets) return [];
    const datasetNames = collectChartDatasetNames(spec);
    const seasons = new Set();
    datasetNames.forEach(name => {
        const rows = spec.datasets?.[name];
        if (!Array.isArray(rows)) return;
        rows.forEach(row => {
            const season = row?.season;
            if (season && season !== 'Total') seasons.add(season);
        });
    });
    return Array.from(seasons);
}

function getPlayerStatsSeasonOptions() {
    return sortSeasonLabelsDescending([...(availableSeasons || []), ...playerStatsDataSeasons]);
}

function getPlayerStatsAllSeasonsLabel() {
    const seasons = getPlayerStatsSeasonOptions();
    const earliestSeason = seasons[seasons.length - 1];
    if (!earliestSeason) return 'All (2017-)';
    const [startYear, endYear] = String(earliestSeason).split('/');
    if (!startYear || !endYear) return 'All (2017-)';
    const centuryPrefix = String(startYear).slice(0, 2);
    const normalizedEndYear = endYear.length === 2 ? `${centuryPrefix}${endYear}` : endYear;
    return `All (${normalizedEndYear}-)`;
}

function getPlayerStatsSelectedSeasonLabel(selectedSeasonValue) {
    if (!selectedSeasonValue || selectedSeasonValue === PLAYER_STATS_ALL_SEASONS_VALUE) {
        return getPlayerStatsAllSeasonsLabel();
    }
    return selectedSeasonValue;
}

function getPlayerStatsSelectedPositions() {
    return Array.from(playerStatsSelectedPositions);
}

function getPlayerStatsPositionChipLabel(selectedPositions) {
    if (!Array.isArray(selectedPositions) || selectedPositions.length === 0) return 'All';
    const hasStarters = selectedPositions.includes(PLAYER_STATS_STARTER_POSITIONS_VALUE);
    const hasBench = selectedPositions.includes('Bench');
    if (hasStarters && hasBench) return 'All';
    const positions = selectedPositions.slice().sort();
    const forwards = PLAYER_STATS_FORWARD_POSITIONS.slice().sort();
    const backs = PLAYER_STATS_BACK_POSITIONS.slice().sort();
    const sameAs = reference => positions.length === reference.length && positions.every((value, index) => value === reference[index]);
    if (sameAs(forwards)) return 'Forwards';
    if (sameAs(backs)) return 'Backs';
    if (positions.length === 1 && positions[0] === 'Bench') return 'Bench';
    if (positions.length === 1) return positions[0];
    return `${positions[0]} +${positions.length - 1}`;
}

function getPlayerStatsSelectedState() {
    const seasonSelect = document.getElementById('playerStatsSeasonSelect');
    const selectedSeasonValue = seasonSelect?.value || PLAYER_STATS_ALL_SEASONS_VALUE;
    return {
        selectedSeasonValue,
        selectedSeasons: selectedSeasonValue === PLAYER_STATS_ALL_SEASONS_VALUE ? [] : [selectedSeasonValue],
        selectedGameType: document.getElementById('playerStatsGameTypeSelect')?.value || PLAYER_STATS_DEFAULT_GAME_TYPE,
        selectedSquad: document.getElementById('playerStatsSquadSelect')?.value || 'All',
        selectedMotmAggregate: document.getElementById('playerStatsMotmAggregateSwitch')?.checked ?? PLAYER_STATS_DEFAULT_MOTM_AGGREGATE,
        selectedPositions: getPlayerStatsSelectedPositions(),
        selectedCombination: document.getElementById('playerStatsCombinationSelect')?.value || PLAYER_STATS_DEFAULT_COMBINATION,
        selectedScoreType: document.getElementById('playerStatsScoreTypeSelect')?.value || PLAYER_STATS_DEFAULT_SCORE_TYPE,
        minAppearances: getPlayerStatsThresholdValue('appearances'),
        minPoints: getPlayerStatsThresholdValue('points'),
        minCaptains: getPlayerStatsThresholdValue('captains'),
        minMotm: getPlayerStatsThresholdValue('motm'),
        minCombinations: getPlayerStatsThresholdValue('combinations'),
    };
}

function getPlayerStatsCombinationLabel(combinationValue) {
    return PLAYER_STATS_COMBINATION_OPTIONS.find(option => option.value === combinationValue)?.label || 'Front Row';
}

function getPlayerStatsPointsThresholdLabel(scoreType) {
    switch (scoreType) {
        case 'Tries':
            return 'Min Tries';
        case 'Kicks':
            return 'Min Kicks';
        default:
            return 'Min Points';
    }
}

function normalizePlayerStatsSeasonFilter(selectedSeasons) {
    const seasons = Array.isArray(selectedSeasons) ? selectedSeasons.filter(Boolean) : [];
    if (seasons.includes(PLAYER_STATS_ALL_SEASONS_VALUE)) return [];
    return seasons;
}

function resolvePlayerStatsPositions(selectedPositions) {
    const positions = Array.isArray(selectedPositions) ? selectedPositions.filter(Boolean) : [];
    if (positions.length === 0) return [];

    const resolved = new Set();
    positions.forEach(position => {
        if (position === PLAYER_STATS_STARTER_POSITIONS_VALUE) {
            PLAYER_STATS_FORWARD_POSITIONS.forEach(value => resolved.add(value));
            PLAYER_STATS_BACK_POSITIONS.forEach(value => resolved.add(value));
            return;
        }
        resolved.add(position);
    });

    return Array.from(resolved);
}

function getPlayerStatsDatasetRows(spec) {
    if (!spec) return [];

    // Support source files that are exported as raw JSON arrays.
    if (Array.isArray(spec)) {
        return spec.filter(row => row && typeof row === 'object');
    }

    if (typeof spec !== 'object') return [];

    // Support inline Vega-Lite values objects.
    if (Array.isArray(spec.data?.values)) {
        return spec.data.values.filter(row => row && typeof row === 'object');
    }

    if (!spec.datasets) return [];
    const rows = [];
    const datasetNames = collectChartDatasetNames(spec);
    datasetNames.forEach(name => {
        const datasetRows = spec.datasets?.[name];
        if (Array.isArray(datasetRows)) rows.push(...datasetRows);
    });
    return rows;
}

function filterPlayerStatsRowsByScope(rows, selectedSeasons, gameTypeMode, selectedSquad) {
    const seasons = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    return (rows || []).filter(row => {
        if (!row || typeof row !== 'object') return false;
        if (seasons.length > 0 && !seasons.includes(row.season)) return false;
        if (allowedGameTypes && row.game_type && !allowedGameTypes.has(row.game_type)) return false;
        if (selectedSquad !== 'All' && row.squad !== selectedSquad) return false;
        return true;
    });
}

function getTopPlayerAggregate(rows, valueField) {
    const totals = new Map();
    rows.forEach(row => {
        const player = row?.player;
        const value = Number(row?.[valueField] ?? 0);
        if (!player || !Number.isFinite(value)) return;
        totals.set(player, (totals.get(player) || 0) + value);
    });
    return Array.from(totals.entries())
        .map(([player, value]) => ({ player, value }))
        .sort((a, b) => b.value - a.value || a.player.localeCompare(b.player))[0] || null;
}

function getTopPlayerScopedAggregate(rows, valueField) {
    const scopedValues = new Map();
    rows.forEach(row => {
        const player = row?.player;
        const season = row?.season;
        const squad = row?.squad;
        const gameType = row?.game_type;
        const value = Number(row?.[valueField] ?? 0);
        if (!player || !Number.isFinite(value)) return;

        const scopeKey = [player, season, squad, gameType].join('||');
        const current = scopedValues.get(scopeKey);
        if (!Number.isFinite(current) || value > current) scopedValues.set(scopeKey, value);
    });

    const totals = new Map();
    scopedValues.forEach((value, scopeKey) => {
        const [player] = scopeKey.split('||');
        totals.set(player, (totals.get(player) || 0) + value);
    });

    return Array.from(totals.entries())
        .map(([player, value]) => ({ player, value }))
        .sort((a, b) => b.value - a.value || a.player.localeCompare(b.player))[0] || null;
}

function getPlayersMeetingThreshold(rows, valueField, minimumValue, predicate = null) {
    const threshold = Number.isFinite(minimumValue) ? Math.max(0, Math.floor(minimumValue)) : 0;
    const totals = new Map();
    (rows || []).forEach(row => {
        if (!row || typeof row !== 'object') return;
        if (typeof predicate === 'function' && !predicate(row)) return;
        const player = row.player;
        const value = Number(row?.[valueField] ?? 0);
        if (!player || !Number.isFinite(value)) return;
        totals.set(player, (totals.get(player) || 0) + value);
    });

    return new Set(
        Array.from(totals.entries())
            .filter(([, total]) => total >= threshold)
            .map(([player]) => player)
    );
}

function getPlayerStatsSquadColors() {
    const rootStyle = getComputedStyle(document.documentElement);
    const primary = (rootStyle.getPropertyValue('--primary-color') || '').trim() || '#202946';
    const accent = (rootStyle.getPropertyValue('--accent-color') || '').trim() || '#7d96e8';
    return [primary, accent];
}

function normalizePlayerStatsThreshold(value, config) {
    const min = Number(config?.min ?? 0);
    const max = Number(config?.max ?? 100);
    const fallback = Number(config?.defaultValue ?? min);
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return fallback;
    return Math.min(max, Math.max(min, Math.floor(numericValue)));
}

function getPlayerStatsThresholdValue(key) {
    const config = PLAYER_STATS_MIN_THRESHOLDS[key];
    if (!config) return 0;
    const input = document.getElementById(config.inputId);
    return normalizePlayerStatsThreshold(input?.value ?? config.defaultValue, config);
}

function syncPlayerStatsSeasonStepperFromSelect() {
    const select = document.getElementById('playerStatsSeasonSelect');
    const label = document.getElementById('playerStatsSeasonLabelOffcanvas');
    const prevBtn = document.getElementById('playerStatsSeasonPrevOffcanvas');
    const nextBtn = document.getElementById('playerStatsSeasonNextOffcanvas');
    if (!select || !label) return;
    label.textContent = select.options[select.selectedIndex]?.text || getPlayerStatsAllSeasonsLabel();
    if (prevBtn) prevBtn.disabled = select.selectedIndex >= select.options.length - 1;
    if (nextBtn) nextBtn.disabled = select.selectedIndex <= 0;
}

function syncPlayerStatsGameTypeSegmentFromSelect() {
    const select = document.getElementById('playerStatsGameTypeSelect');
    const segment = document.getElementById('playerStatsGameTypeSegment');
    if (!select || !segment) return;
    const value = select.value || PLAYER_STATS_DEFAULT_GAME_TYPE;
    if (window.sharedUi?.syncSegmentButtons) {
        window.sharedUi.syncSegmentButtons(segment, value);
        return;
    }
}

function syncPlayerStatsSquadSegmentFromSelect() {
    const select = document.getElementById('playerStatsSquadSelect');
    const segment = document.getElementById('playerStatsSquadSegment');
    if (!select || !segment) return;
    const value = select.value || 'All';
    if (window.sharedUi?.syncSegmentButtons) {
        window.sharedUi.syncSegmentButtons(segment, value);
        return;
    }
}

function syncPlayerStatsScoreTypeSegmentFromSelect() {
    const select = document.getElementById('playerStatsScoreTypeSelect');
    const segment = document.getElementById('playerStatsScoreTypeSegment');
    if (!select || !segment) return;
    const value = select.value || PLAYER_STATS_DEFAULT_SCORE_TYPE;
    if (window.sharedUi?.syncSegmentButtons) {
        window.sharedUi.syncSegmentButtons(segment, value);
        return;
    }
}

function syncPlayerStatsCombinationSegmentFromSelect() {
    const select = document.getElementById('playerStatsCombinationSelect');
    const segment = document.getElementById('playerStatsCombinationSegment');
    if (!select || !segment) return;
    const value = select.value || PLAYER_STATS_DEFAULT_COMBINATION;
    if (window.sharedUi?.syncSegmentButtons) {
        window.sharedUi.syncSegmentButtons(segment, value);
    }
}

function syncPlayerStatsPositionButtons() {
    const grid = document.getElementById('playerStatsPositionGrid');
    if (!grid) return;
    const selectedPositions = getPlayerStatsSelectedPositions();
    const selectedSet = new Set(selectedPositions);
    const hasStarters = selectedSet.has('Starters');
    const hasBench = selectedSet.has('Bench');
    const isForwards = PLAYER_STATS_FORWARD_POSITIONS.every(p => selectedSet.has(p));
    const isBacks = PLAYER_STATS_BACK_POSITIONS.every(p => selectedSet.has(p));

    grid.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        const value = btn.dataset.value;
        let active = false;
        if (value === PLAYER_STATS_STARTER_POSITIONS_VALUE) active = hasStarters;
        else if (value === 'Forwards') active = isForwards;
        else if (value === 'Backs') active = isBacks;
        else if (value === 'Bench') active = hasBench;
        else active = selectedSet.has(value);
        btn.classList.toggle('is-active', active);
    });
}

function updatePlayerStatsMinThresholdDisplays() {
    Object.keys(PLAYER_STATS_MIN_THRESHOLDS).forEach(key => {
        const config = PLAYER_STATS_MIN_THRESHOLDS[key];
        const normalizedValue = getPlayerStatsThresholdValue(key);
        const value = String(normalizedValue);
        const input = document.getElementById(config.inputId);
        if (input && input.value !== value) input.value = value;
        const valueEl = document.getElementById(config.valueId);
        if (valueEl) valueEl.textContent = value;
    });

    const scoreType = document.getElementById('playerStatsScoreTypeSelect')?.value || PLAYER_STATS_DEFAULT_SCORE_TYPE;
    const minPointsLabel = document.getElementById('playerStatsMinPointsLabel');
    if (minPointsLabel) minPointsLabel.textContent = getPlayerStatsPointsThresholdLabel(scoreType);
}

function renderPlayerStatsActiveFilterChips(state) {
    const {
        selectedSeasonValue,
        selectedGameType,
        selectedSquad,
        selectedMotmAggregate,
        selectedPositions,
        selectedCombination,
        selectedScoreType,
        minAppearances,
        minPoints,
        minCaptains,
        minMotm,
        minCombinations,
    } = state;

    const _seasonLabel = getPlayerStatsSelectedSeasonLabel(selectedSeasonValue);
    const _seasonShort = /^\d{4}\//.test(_seasonLabel) ? _seasonLabel.replace(/^20/, '') : _seasonLabel;
    const seasonChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Season</strong> <span class="d-none d-md-inline">${_seasonLabel}</span><span class="d-inline d-md-none">${_seasonShort}</span></button>`;
    const gameTypeChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Game Type</strong> ${selectedGameType || PLAYER_STATS_DEFAULT_GAME_TYPE}</button>`;
    const squadLabel = selectedSquad === 'All' ? 'All' : `${selectedSquad} XV`;
    const squadChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Squad</strong> ${squadLabel}</button>`;
    const positionsChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Position</strong> ${getPlayerStatsPositionChipLabel(selectedPositions)}</button>`;
    const minAppsChip = `<span class="squad-stats-filter-chip"><strong><span class="d-none d-md-inline">Min Appearances</span><span class="d-inline d-md-none">Min Apps</span></strong> ${minAppearances}</span>`;
    const minPointsChip = `<span class="squad-stats-filter-chip"><strong>${getPlayerStatsPointsThresholdLabel(selectedScoreType || PLAYER_STATS_DEFAULT_SCORE_TYPE)}</strong> ${minPoints}</span>`;
    const minCaptainsChip = `<span class="squad-stats-filter-chip"><strong>Min Captain Apps</strong> ${minCaptains}</span>`;
    const minMotmChip = `<span class="squad-stats-filter-chip"><strong>Min MOTM Awards</strong> ${minMotm}</span>`;
    const minCombinationsChip = `<span class="squad-stats-filter-chip"><strong>Min Starts</strong> ${minCombinations}</span>`;
    const scoreTypeChip = `<span class="squad-stats-filter-chip"><strong>Scoring</strong> ${selectedScoreType || PLAYER_STATS_DEFAULT_SCORE_TYPE}</span>`;
    const motmViewChip = selectedMotmAggregate
        ? '<span class="squad-stats-filter-chip"><strong>Aggregate by position</strong></span>'
        : '';

    const appearancesHost = document.getElementById('playerStatsAppearancesActiveFilters');
    if (appearancesHost) {
        appearancesHost.innerHTML = [seasonChip, gameTypeChip, squadChip, positionsChip, minAppsChip].join('');
    }

    const pointsHost = document.getElementById('playerStatsPointsActiveFilters');
    if (pointsHost) {
        pointsHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minPointsChip, scoreTypeChip].join('');
    }

    const captainsHost = document.getElementById('playerStatsCaptainsActiveFilters');
    if (captainsHost) {
        captainsHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minCaptainsChip].join('');
    }

    const motmHost = document.getElementById('playerStatsMotmActiveFilters');
    if (motmHost) {
        motmHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minMotmChip, motmViewChip].filter(Boolean).join('');
    }

    const combinationChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Combination</strong> ${getPlayerStatsCombinationLabel(selectedCombination)}</button>`;
    const startingCombinationsHost = document.getElementById('playerStatsStartingCombinationsActiveFilters');
    if (startingCombinationsHost) {
        startingCombinationsHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minCombinationsChip, combinationChip].join('');
    }

}

function renderPlayerStatsHero(state) {
    const {
        selectedSeasonValue,
        selectedSeasons,
        selectedGameType,
        selectedSquad,
        selectedPositions,
        selectedScoreType
    } = state;

    const meta = document.getElementById('playerStatsHeroMeta');
    if (meta) {
        const squadLabel = selectedSquad === 'All' ? 'All' : `${selectedSquad} XV`;
        meta.textContent = `${getPlayerStatsSelectedSeasonLabel(selectedSeasonValue)} | ${selectedGameType} | ${squadLabel}`;
    }

    const resolvedPositions = resolvePlayerStatsPositions(selectedPositions);

    const appearancesRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.appearancesSpec),
        selectedSeasons,
        selectedGameType,
        selectedSquad
    ).filter(row => {
        if (!Array.isArray(resolvedPositions) || resolvedPositions.length === 0) return true;
        return resolvedPositions.includes(row?.position);
    });
    const appearancesLeader = getTopPlayerAggregate(
        appearancesRows,
        'games'
    );

    const pointsRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.pointsSpec),
        selectedSeasons,
        selectedGameType,
        selectedSquad
    ).filter(row => row?.score_type === 'Total');
    const pointsLeader = getTopPlayerScopedAggregate(pointsRows, 'total_points');

    const triesRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.pointsSpec),
        selectedSeasons,
        selectedGameType,
        selectedSquad
    ).filter(row => row?.score_type === 'Total');
    const triesLeader = getTopPlayerScopedAggregate(triesRows, 'tries');

    const appearancesValue = document.getElementById('playerStatsHeroAppearancesValue');
    const appearancesNote = document.getElementById('playerStatsHeroAppearancesNote');
    if (appearancesValue) appearancesValue.textContent = appearancesLeader ? String(appearancesLeader.value) : '0';
    if (appearancesNote) {
        appearancesNote.textContent = appearancesLeader ? appearancesLeader.player : 'No data for current filters';
    }

    const pointsValue = document.getElementById('playerStatsHeroPointsValue');
    const pointsNote = document.getElementById('playerStatsHeroPointsNote');
    if (pointsValue) pointsValue.textContent = pointsLeader ? String(pointsLeader.value) : '0';
    if (pointsNote) {
        pointsNote.textContent = pointsLeader ? pointsLeader.player : 'No data for current filters';
    }

    const triesValue = document.getElementById('playerStatsHeroTriesValue');
    const triesNote = document.getElementById('playerStatsHeroTriesNote');
    if (triesValue) triesValue.textContent = triesLeader ? String(triesLeader.value) : '0';
    if (triesNote) {
        triesNote.textContent = triesLeader ? triesLeader.player : 'No data for current filters';
    }
}

function handlePlayerStatsControlChange() {
    syncPlayerStatsSeasonStepperFromSelect();
    syncPlayerStatsGameTypeSegmentFromSelect();
    syncPlayerStatsSquadSegmentFromSelect();
    syncPlayerStatsScoreTypeSegmentFromSelect();
    syncPlayerStatsCombinationSegmentFromSelect();
    syncPlayerStatsPositionButtons();
    updatePlayerStatsMinThresholdDisplays();
    renderPlayerStatsPage();
}

function setPlayerStatsPositionSelection(nextPositions) {
    playerStatsSelectedPositions = new Set(nextPositions);
}

function handlePlayerStatsPositionButton(value) {
    const currentPositions = new Set(playerStatsSelectedPositions);

    if (value === PLAYER_STATS_STARTER_POSITIONS_VALUE) {
        // Toggle Starters independently
        if (currentPositions.has('Starters')) {
            currentPositions.delete('Starters');
        } else {
            currentPositions.add('Starters');
        }
        setPlayerStatsPositionSelection(Array.from(currentPositions));
        handlePlayerStatsControlChange();
        return;
    }

    if (value === 'Forwards') {
        const currentForwards = PLAYER_STATS_FORWARD_POSITIONS.filter(p => currentPositions.has(p));
        if (currentForwards.length === PLAYER_STATS_FORWARD_POSITIONS.length) {
            // Remove all forwards
            PLAYER_STATS_FORWARD_POSITIONS.forEach(p => currentPositions.delete(p));
        } else {
            // Add all forwards
            PLAYER_STATS_FORWARD_POSITIONS.forEach(p => currentPositions.add(p));
        }
        setPlayerStatsPositionSelection(Array.from(currentPositions));
        handlePlayerStatsControlChange();
        return;
    }

    if (value === 'Backs') {
        const currentBacks = PLAYER_STATS_BACK_POSITIONS.filter(p => currentPositions.has(p));
        if (currentBacks.length === PLAYER_STATS_BACK_POSITIONS.length) {
            // Remove all backs
            PLAYER_STATS_BACK_POSITIONS.forEach(p => currentPositions.delete(p));
        } else {
            // Add all backs
            PLAYER_STATS_BACK_POSITIONS.forEach(p => currentPositions.add(p));
        }
        setPlayerStatsPositionSelection(Array.from(currentPositions));
        handlePlayerStatsControlChange();
        return;
    }

    if (value === 'Bench') {
        // Toggle Bench independently
        if (currentPositions.has('Bench')) {
            currentPositions.delete('Bench');
        } else {
            currentPositions.add('Bench');
        }
        setPlayerStatsPositionSelection(Array.from(currentPositions));
        handlePlayerStatsControlChange();
        return;
    }

    // Regular position - toggle
    if (currentPositions.has(value)) currentPositions.delete(value);
    else currentPositions.add(value);
    setPlayerStatsPositionSelection(Array.from(currentPositions));
    handlePlayerStatsControlChange();
}

function initialisePlayerStatsControls() {
    if (playerStatsControlsInitialised) return;

    const seasonSelect = document.getElementById('playerStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('playerStatsGameTypeSelect');
    const squadSelect = document.getElementById('playerStatsSquadSelect');
    const scoreTypeSelect = document.getElementById('playerStatsScoreTypeSelect');
    const combinationSelect = document.getElementById('playerStatsCombinationSelect');
    const motmAggregateSwitch = document.getElementById('playerStatsMotmAggregateSwitch');
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    const minPointsInput = document.getElementById('playerStatsMinPointsInput');
    const minCaptainsInput = document.getElementById('playerStatsMinCaptainsInput');
    const minMotmInput = document.getElementById('playerStatsMinMotmInput');
    const minCombinationsInput = document.getElementById('playerStatsMinCombinationsInput');
    const seasonPrevButton = document.getElementById('playerStatsSeasonPrevOffcanvas');
    const seasonNextButton = document.getElementById('playerStatsSeasonNextOffcanvas');
    const gameTypeSegment = document.getElementById('playerStatsGameTypeSegment');
    const squadSegment = document.getElementById('playerStatsSquadSegment');
    const scoreTypeSegment = document.getElementById('playerStatsScoreTypeSegment');
    const combinationSegment = document.getElementById('playerStatsCombinationSegment');
    const positionGrid = document.getElementById('playerStatsPositionGrid');

    if (!seasonSelect || !gameTypeSelect || !squadSelect || !scoreTypeSelect || !combinationSelect || !motmAggregateSwitch) return;

    const seasons = getPlayerStatsSeasonOptions();
    seasonSelect.innerHTML = '';
    const allSeasonsOption = document.createElement('option');
    allSeasonsOption.value = PLAYER_STATS_ALL_SEASONS_VALUE;
    allSeasonsOption.textContent = getPlayerStatsAllSeasonsLabel();
    seasonSelect.appendChild(allSeasonsOption);
    seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = season;
        seasonSelect.appendChild(option);
    });

    seasonSelect.value = PLAYER_STATS_ALL_SEASONS_VALUE;
    gameTypeSelect.value = PLAYER_STATS_DEFAULT_GAME_TYPE;
    squadSelect.value = 'All';
    scoreTypeSelect.value = PLAYER_STATS_DEFAULT_SCORE_TYPE;
    combinationSelect.value = PLAYER_STATS_DEFAULT_COMBINATION;
    motmAggregateSwitch.checked = PLAYER_STATS_DEFAULT_MOTM_AGGREGATE;
    Object.keys(PLAYER_STATS_MIN_THRESHOLDS).forEach(key => {
        const config = PLAYER_STATS_MIN_THRESHOLDS[key];
        const input = document.getElementById(config.inputId);
        if (input) input.value = String(config.defaultValue);
    });
    setPlayerStatsPositionSelection(['Starters', 'Bench']);

    seasonSelect.addEventListener('change', handlePlayerStatsControlChange);
    gameTypeSelect.addEventListener('change', handlePlayerStatsControlChange);
    squadSelect.addEventListener('change', handlePlayerStatsControlChange);
    scoreTypeSelect.addEventListener('change', handlePlayerStatsControlChange);
    combinationSelect.addEventListener('change', handlePlayerStatsControlChange);
    motmAggregateSwitch.addEventListener('change', handlePlayerStatsControlChange);
    [minAppearancesInput, minPointsInput, minCaptainsInput, minMotmInput, minCombinationsInput]
        .filter(Boolean)
        .forEach(input => {
            input.addEventListener('input', handlePlayerStatsControlChange);
            input.addEventListener('change', handlePlayerStatsControlChange);
        });

    if (seasonPrevButton) {
        seasonPrevButton.addEventListener('click', () => {
            if (seasonSelect.selectedIndex < seasonSelect.options.length - 1) {
                seasonSelect.selectedIndex += 1;
                handlePlayerStatsControlChange();
            }
        });
    }

    if (seasonNextButton) {
        seasonNextButton.addEventListener('click', () => {
            if (seasonSelect.selectedIndex > 0) {
                seasonSelect.selectedIndex -= 1;
                handlePlayerStatsControlChange();
            }
        });
    }

    if (window.sharedUi?.bindSegmentToSelect) {
        if (gameTypeSegment) {
            window.sharedUi.bindSegmentToSelect({
                segment: gameTypeSegment,
                select: gameTypeSelect,
                onSync: () => handlePlayerStatsControlChange(),
            });
        }
        if (squadSegment) {
            window.sharedUi.bindSegmentToSelect({
                segment: squadSegment,
                select: squadSelect,
                onSync: () => handlePlayerStatsControlChange(),
            });
        }
        if (scoreTypeSegment) {
            window.sharedUi.bindSegmentToSelect({
                segment: scoreTypeSegment,
                select: scoreTypeSelect,
                onSync: () => handlePlayerStatsControlChange(),
            });
        }
        if (combinationSegment) {
            window.sharedUi.bindSegmentToSelect({
                segment: combinationSegment,
                select: combinationSelect,
                onSync: () => handlePlayerStatsControlChange(),
            });
        }
    }

    if (positionGrid) {
        positionGrid.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const value = btn.dataset.value;
                if (!value) return;
                handlePlayerStatsPositionButton(value);
            });
        });
    }

    syncPlayerStatsSeasonStepperFromSelect();
    syncPlayerStatsGameTypeSegmentFromSelect();
    syncPlayerStatsSquadSegmentFromSelect();
    syncPlayerStatsScoreTypeSegmentFromSelect();
    syncPlayerStatsCombinationSegmentFromSelect();
    syncPlayerStatsPositionButtons();
    updatePlayerStatsMinThresholdDisplays();
    playerStatsControlsInitialised = true;
}

function initialisePlayerStatsAnalysisRail() {
    if (playerStatsAnalysisRailInitialised) return;
    playerStatsAnalysisRailInitialised = initialiseAnalysisRail({
        railId: 'playerStatsAnalysisRail',
    });
}

function filterPlayerStatsCaptainsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, minCaptains) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const squadColors = getPlayerStatsSquadColors();
    if (Array.isArray(clonedSpec?.spec?.layer)) {
        clonedSpec.spec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
        });
    }
    const scopePredicate = row => {
        const seasons = normalizePlayerStatsSeasonFilter(selectedSeasons);
        if (seasons.length === 0) {
            if (row?.season === 'Total') return false;
        } else if (row?.season === 'Total' || !seasons.includes(row?.season)) {
            return false;
        }
        if (allowedGameTypes && !allowedGameTypes.has(row?.game_type)) return false;
        if (selectedSquad !== 'All' && row?.squad !== selectedSquad) return false;
        return true;
    };
    const rows = getPlayerStatsDatasetRows(clonedSpec).filter(scopePredicate);
    const qualifyingPlayers = getPlayersMeetingThreshold(rows, 'games', minCaptains);

    return filterChartSpecDataset(clonedSpec, row => {
        if (!scopePredicate(row)) return false;
        if (!(qualifyingPlayers instanceof Set) || qualifyingPlayers.size === 0) return false;
        return qualifyingPlayers.has(row?.player);
    });
}

function filterPlayerStatsMotmSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, minMotm) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const squadColors = getPlayerStatsSquadColors();

    if (Array.isArray(clonedSpec.layer)) {
        clonedSpec.layer.forEach(layer => {
            const colorEncoding = layer?.encoding?.color;
            if (colorEncoding?.field === 'squad' && colorEncoding?.scale) {
                colorEncoding.scale.range = squadColors;
            }
        });
    }

    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'squadParam': param.value = selectedSquad; break;
            }
        });
    }

    const scopedRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(clonedSpec),
        selectedSeasons,
        gameTypeMode,
        selectedSquad
    );
    const qualifyingPlayers = getPlayersMeetingThreshold(scopedRows, 'motm_awards', minMotm);

    return filterChartSpecDataset(clonedSpec, row => {
        if (!row || typeof row !== 'object' || !('player' in row)) return true;
        return qualifyingPlayers.has(row.player);
    });
}

function filterPlayerStatsMotmUnitsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, minMotm) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];

    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'squadParam': param.value = selectedSquad; break;
            }
        });
    }

    const scopedRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(clonedSpec),
        selectedSeasons,
        gameTypeMode,
        selectedSquad
    );
    const qualifyingPlayers = getPlayersMeetingThreshold(scopedRows, 'motm_awards', minMotm);

    return filterChartSpecDataset(clonedSpec, row => {
        if (!row || typeof row !== 'object' || !('player' in row)) return true;
        return qualifyingPlayers.has(row.player);
    });
}

function filterPlayerStatsAppearancesSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, positions, minimumAppearances) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const squadColors = getPlayerStatsSquadColors();
    if (Array.isArray(clonedSpec?.layer)) {
        clonedSpec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
        });
    }
    const seasonValue = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const positionsValue = resolvePlayerStatsPositions(positions);
    const threshold = Number.isFinite(minimumAppearances) ? Math.max(0, Math.floor(minimumAppearances)) : 10;
    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'squadParam': param.value = selectedSquad; break;
                case 'positionsParam': param.value = positionsValue; break;
                case 'minAppsParam': param.value = threshold; break;
            }
        });
    }
    return clonedSpec;
}

function filterPlayerStatsPointsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, scoreType, minPoints) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const nextScoreType = scoreType || PLAYER_STATS_DEFAULT_SCORE_TYPE;
    const valueAxisTitle = nextScoreType === 'Tries' ? 'Tries' : 'Points';
    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'gameTypeParam': param.value = gameTypeMode || PLAYER_STATS_DEFAULT_GAME_TYPE; break;
                case 'squadParam': param.value = selectedSquad; break;
                case 'scoreTypeParam': param.value = nextScoreType; break;
            }
        });
    }
    if (Array.isArray(clonedSpec.layer)) {
        clonedSpec.layer.forEach(layer => {
            if (layer?.encoding?.x) {
                layer.encoding.x.axis = layer.encoding.x.axis || {};
                layer.encoding.x.axis.title = valueAxisTitle;
            }
        });
    }
    const scopedRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(clonedSpec),
        selectedSeasons,
        gameTypeMode,
        selectedSquad
    ).filter(row => row?.score_type === nextScoreType);
    const qualifyingPlayers = getPlayersMeetingThreshold(scopedRows, 'value', minPoints);

    return filterChartSpecDataset(clonedSpec, row => {
        if (!row || typeof row !== 'object' || !('player' in row)) return true;
        return qualifyingPlayers.has(row.player);
    });
}

function filterPlayerStatsStartingCombinationsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, selectedCombination, minimumAppearances) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = normalizePlayerStatsSeasonFilter(selectedSeasons);
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const threshold = Number.isFinite(minimumAppearances) ? Math.max(0, Math.floor(minimumAppearances)) : 10;

    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'gameTypeParam': param.value = gameTypeMode || PLAYER_STATS_DEFAULT_GAME_TYPE; break;
                case 'squadParam': param.value = selectedSquad; break;
                case 'combinationParam': param.value = selectedCombination || PLAYER_STATS_DEFAULT_COMBINATION; break;
                case 'minAppsParam': param.value = threshold; break;
            }
        });
    }

    const combinationLabel = getPlayerStatsCombinationLabel(selectedCombination);
    clonedSpec.title = {
        text: `${combinationLabel} Starting Combinations`,
        subtitle: `Minimum ${threshold} appearances`,
    };

    const squadColors = getPlayerStatsSquadColors();
    if (clonedSpec?.encoding?.color?.scale) {
        clonedSpec.encoding.color.scale.range = squadColors;
    }

    return clonedSpec;
}

async function renderPlayerStatsPage() {
    const state = getPlayerStatsSelectedState();
    const {
        selectedSeasons,
        selectedGameType,
        selectedSquad,
        selectedMotmAggregate,
        selectedPositions,
        selectedCombination,
        selectedScoreType,
        minAppearances,
        minPoints,
        minCaptains,
        minMotm,
        minCombinations,
    } = state;

    renderPlayerStatsActiveFilterChips(state);

    try {
        if (!playerStatsBaseSpecs) {
            const [captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec] = await Promise.all([
                loadChartSpec('data/charts/player_stats_captains.json'),
                loadChartSpec('data/charts/player_stats_motm.json'),
                loadChartSpec('data/charts/player_stats_motm_units.json'),
                loadChartSpec('data/charts/player_stats_appearances.json'),
                loadChartSpec('data/charts/point_scorers.json'),
                loadChartSpec('data/charts/player_stats_starting_combinations.json')
            ]);
            playerStatsBaseSpecs = { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec };
        }

        const { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec } = playerStatsBaseSpecs;

        const filteredCaptains = filterPlayerStatsCaptainsSpec(captainsSpec, selectedSeasons, selectedGameType, selectedSquad, minCaptains);
        const filteredMotm = filterPlayerStatsMotmSpec(motmSpec, selectedSeasons, selectedGameType, selectedSquad, minMotm);
        const filteredMotmUnits = filterPlayerStatsMotmUnitsSpec(motmUnitsSpec, selectedSeasons, selectedGameType, selectedSquad, minMotm);
        const filteredAppearances = filterPlayerStatsAppearancesSpec(appearancesSpec, selectedSeasons, selectedGameType, selectedSquad, selectedPositions, minAppearances);
        const filteredPoints = filterPlayerStatsPointsSpec(pointsSpec, selectedSeasons, selectedGameType, selectedSquad, selectedScoreType, minPoints);
        const filteredStartingCombinations = filterPlayerStatsStartingCombinationsSpec(
            startingCombinationsSpec,
            selectedSeasons,
            selectedGameType,
            selectedSquad,
            selectedCombination,
            minCombinations
        );
        const motmSpecToRender = selectedMotmAggregate ? filteredMotmUnits : filteredMotm;
        const motmEmptyMessage = selectedMotmAggregate
            ? 'No MOTM unit breakdown available for the selected filters.'
            : 'No MOTM awards available for the selected filters.';
        const motmLayoutContainerId = selectedMotmAggregate ? 'playerStatsMotmUnitsChart' : 'playerStatsMotmChart';

        renderPlayerStatsHero(state);
        renderStaticSpecChart('playerStatsCaptainsChart', filteredCaptains, 'No captains or vice-captains data available for the selected season.');
        renderStaticSpecChart('playerStatsMotmChart', motmSpecToRender, motmEmptyMessage, { layoutContainerId: motmLayoutContainerId });
        renderStaticSpecChart('playerStatsAppearancesChart', filteredAppearances, 'No player appearances available for the selected filters.');
        renderStaticSpecChart('playerStatsStartingCombinationsChart', filteredStartingCombinations, 'No starting combinations available for the selected filters and threshold.');
        renderStaticSpecChart('playerStatsPointsChart', filteredPoints, 'No point scorers available for the selected filters.');
    } catch (error) {
        console.warn('Unable to load Player Stats charts:', error);
        renderStaticSpecChart('playerStatsCaptainsChart', null, 'Unable to load captains chart.');
        renderStaticSpecChart('playerStatsMotmChart', null, 'Unable to load MOTM chart.');
        renderStaticSpecChart('playerStatsAppearancesChart', null, 'Unable to load appearances chart.');
        renderStaticSpecChart('playerStatsStartingCombinationsChart', null, 'Unable to load starting combinations chart.');
        renderStaticSpecChart('playerStatsPointsChart', null, 'Unable to load point scorers chart.');
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    if (!playerStatsBaseSpecs) {
        const [captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec] = await Promise.all([
            loadChartSpec('data/charts/player_stats_captains.json'),
            loadChartSpec('data/charts/player_stats_motm.json'),
            loadChartSpec('data/charts/player_stats_motm_units.json'),
            loadChartSpec('data/charts/player_stats_appearances.json'),
            loadChartSpec('data/charts/point_scorers.json'),
            loadChartSpec('data/charts/player_stats_starting_combinations.json')
        ]);
        playerStatsBaseSpecs = { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec };
    }

    const { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec, startingCombinationsSpec } = playerStatsBaseSpecs;
    playerStatsDataSeasons = sortSeasonLabelsDescending([
        ...extractSeasonsFromSpec(captainsSpec),
        ...extractSeasonsFromSpec(motmSpec),
        ...extractSeasonsFromSpec(motmUnitsSpec),
        ...extractSeasonsFromSpec(appearancesSpec),
        ...extractSeasonsFromSpec(pointsSpec),
        ...extractSeasonsFromSpec(startingCombinationsSpec)
    ]);

    initialisePlayerStatsControls();
    initialisePlayerStatsAnalysisRail();
    renderPlayerStatsPage();
});

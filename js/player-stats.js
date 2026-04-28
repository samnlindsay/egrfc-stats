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
const PLAYER_STATS_FORWARD_POSITIONS = ['Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8'];
const PLAYER_STATS_BACK_POSITIONS = ['Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back'];

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
    if (!earliestSeason) return 'All';
    const [startYear, endYear] = String(earliestSeason).split('/');
    if (!startYear || !endYear) return `All (${earliestSeason})`;
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
        selectedScoreType: document.getElementById('playerStatsScoreTypeSelect')?.value || PLAYER_STATS_DEFAULT_SCORE_TYPE,
        minimumAppearances: getPlayerStatsMinimumAppearances()
    };
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
    if (!spec || typeof spec !== 'object' || !spec.datasets) return [];
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

function getPlayerStatsEligiblePlayersByMinAppearances(selectedSeasons, gameTypeMode, selectedSquad, minimumAppearances) {
    const threshold = Number.isFinite(minimumAppearances) ? Math.max(0, Math.floor(minimumAppearances)) : 10;
    const scopedRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.appearancesSpec),
        selectedSeasons,
        gameTypeMode,
        selectedSquad
    );

    const totals = new Map();
    scopedRows.forEach(row => {
        const player = row?.player;
        const games = Number(row?.games ?? 0);
        if (!player || !Number.isFinite(games)) return;
        totals.set(player, (totals.get(player) || 0) + games);
    });

    return new Set(
        Array.from(totals.entries())
            .filter(([, total]) => Number(total) >= threshold)
            .map(([player]) => player)
    );
}

function getPlayerStatsSquadColors() {
    const rootStyle = getComputedStyle(document.documentElement);
    const primary = (rootStyle.getPropertyValue('--primary-color') || '').trim() || '#202946';
    const accent = (rootStyle.getPropertyValue('--accent-color') || '').trim() || '#7d96e8';
    return [primary, accent];
}

function normalizePlayerStatsMinAppearances(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return 10;
    const clamped = Math.min(100, Math.max(1, Math.floor(numericValue)));
    if (clamped <= 2) return 1;
    return Math.max(5, Math.round(clamped / 5) * 5);
}

function getPlayerStatsMinimumAppearances() {
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    return normalizePlayerStatsMinAppearances(minAppearancesInput?.value ?? 10);
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

function updatePlayerStatsMinAppsDisplay() {
    const normalizedValue = getPlayerStatsMinimumAppearances();
    const value = String(normalizedValue);
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    if (minAppearancesInput && minAppearancesInput.value !== value) {
        minAppearancesInput.value = value;
    }
    const offcanvasValue = document.getElementById('playerStatsMinAppearancesValue');
    if (offcanvasValue) offcanvasValue.textContent = value;
}

function renderPlayerStatsActiveFilterChips(state) {
    const {
        selectedSeasonValue,
        selectedGameType,
        selectedSquad,
        selectedMotmAggregate,
        selectedPositions,
        selectedScoreType,
        minimumAppearances
    } = state;

    const _seasonLabel = getPlayerStatsSelectedSeasonLabel(selectedSeasonValue);
    const _seasonShort = /^\d{4}\//.test(_seasonLabel) ? _seasonLabel.replace(/^20/, '') : _seasonLabel;
    const seasonChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Season</strong> <span class="d-none d-md-inline">${_seasonLabel}</span><span class="d-inline d-md-none">${_seasonShort}</span></button>`;
    const gameTypeChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Game Type</strong> ${selectedGameType || PLAYER_STATS_DEFAULT_GAME_TYPE}</button>`;
    const squadLabel = selectedSquad === 'All' ? 'All' : `${selectedSquad} XV`;
    const squadChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Squad</strong> ${squadLabel}</button>`;
    const positionsChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong>Position</strong> ${getPlayerStatsPositionChipLabel(selectedPositions)}</button>`;
    const minAppsChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#playerStatsFiltersOffcanvas" aria-controls="playerStatsFiltersOffcanvas"><strong><span class="d-none d-md-inline">Min Appearances</span><span class="d-inline d-md-none">Min Apps</span></strong> ${minimumAppearances}</button>`;
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
        pointsHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minAppsChip, scoreTypeChip].join('');
    }

    const captainsHost = document.getElementById('playerStatsCaptainsActiveFilters');
    if (captainsHost) {
        captainsHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minAppsChip].join('');
    }

    const motmHost = document.getElementById('playerStatsMotmActiveFilters');
    if (motmHost) {
        motmHost.innerHTML = [seasonChip, gameTypeChip, squadChip, minAppsChip, motmViewChip].filter(Boolean).join('');
    }
}

function renderPlayerStatsHero(state) {
    const {
        selectedSeasonValue,
        selectedSeasons,
        selectedGameType,
        selectedSquad,
        selectedPositions,
        selectedScoreType,
        minimumAppearances
    } = state;

    const eligiblePlayers = getPlayerStatsEligiblePlayersByMinAppearances(
        selectedSeasons,
        selectedGameType,
        selectedSquad,
        minimumAppearances
    );

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
        appearancesRows.filter(row => eligiblePlayers.has(row?.player)),
        'games'
    );

    const pointsRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.pointsSpec),
        selectedSeasons,
        selectedGameType,
        selectedSquad
    ).filter(row => row?.score_type === 'Total' && eligiblePlayers.has(row?.player));
    const pointsLeader = getTopPlayerScopedAggregate(pointsRows, 'total_points');

    const triesRows = filterPlayerStatsRowsByScope(
        getPlayerStatsDatasetRows(playerStatsBaseSpecs?.pointsSpec),
        selectedSeasons,
        selectedGameType,
        selectedSquad
    ).filter(row => row?.score_type === 'Total' && eligiblePlayers.has(row?.player));
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
    syncPlayerStatsPositionButtons();
    updatePlayerStatsMinAppsDisplay();
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
    const motmAggregateSwitch = document.getElementById('playerStatsMotmAggregateSwitch');
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    const seasonPrevButton = document.getElementById('playerStatsSeasonPrevOffcanvas');
    const seasonNextButton = document.getElementById('playerStatsSeasonNextOffcanvas');
    const gameTypeSegment = document.getElementById('playerStatsGameTypeSegment');
    const squadSegment = document.getElementById('playerStatsSquadSegment');
    const scoreTypeSegment = document.getElementById('playerStatsScoreTypeSegment');
    const positionGrid = document.getElementById('playerStatsPositionGrid');

    if (!seasonSelect || !gameTypeSelect || !squadSelect || !scoreTypeSelect || !motmAggregateSwitch || !minAppearancesInput) return;

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
    motmAggregateSwitch.checked = PLAYER_STATS_DEFAULT_MOTM_AGGREGATE;
    minAppearancesInput.value = '10';
    setPlayerStatsPositionSelection(['Starters', 'Bench']);

    seasonSelect.addEventListener('change', handlePlayerStatsControlChange);
    gameTypeSelect.addEventListener('change', handlePlayerStatsControlChange);
    squadSelect.addEventListener('change', handlePlayerStatsControlChange);
    scoreTypeSelect.addEventListener('change', handlePlayerStatsControlChange);
    motmAggregateSwitch.addEventListener('change', handlePlayerStatsControlChange);
    minAppearancesInput.addEventListener('input', handlePlayerStatsControlChange);
    minAppearancesInput.addEventListener('change', handlePlayerStatsControlChange);

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
    syncPlayerStatsPositionButtons();
    updatePlayerStatsMinAppsDisplay();
    playerStatsControlsInitialised = true;
}

function initialisePlayerStatsAnalysisRail() {
    if (playerStatsAnalysisRailInitialised) return;
    playerStatsAnalysisRailInitialised = initialiseAnalysisRail({
        railId: 'playerStatsAnalysisRail',
    });
}

function filterPlayerStatsCaptainsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, eligiblePlayers) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const squadColors = getPlayerStatsSquadColors();
    if (Array.isArray(clonedSpec?.spec?.layer)) {
        clonedSpec.spec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
        });
    }
    const predicate = row => {
        const seasons = normalizePlayerStatsSeasonFilter(selectedSeasons);
        if (seasons.length === 0) {
            if (row?.season === 'Total') return false;
        } else if (row?.season === 'Total' || !seasons.includes(row?.season)) {
            return false;
        }
        if (allowedGameTypes && !allowedGameTypes.has(row?.game_type)) return false;
        if (selectedSquad !== 'All' && row?.squad !== selectedSquad) return false;
        if (eligiblePlayers instanceof Set && !eligiblePlayers.has(row?.player)) return false;
        return true;
    };
    return filterChartSpecDataset(clonedSpec, predicate);
}

function filterPlayerStatsMotmSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, eligiblePlayers) {
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

    if (eligiblePlayers instanceof Set) {
        return filterChartSpecDataset(clonedSpec, row => {
            if (!row || typeof row !== 'object' || !('player' in row)) return true;
            return eligiblePlayers.has(row.player);
        });
    }

    return clonedSpec;
}

function filterPlayerStatsMotmUnitsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, eligiblePlayers) {
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

    if (eligiblePlayers instanceof Set) {
        return filterChartSpecDataset(clonedSpec, row => {
            if (!row || typeof row !== 'object' || !('player' in row)) return true;
            return eligiblePlayers.has(row.player);
        });
    }

    return clonedSpec;
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

function filterPlayerStatsPointsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, scoreType, eligiblePlayers) {
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
    if (allowedGameTypes || eligiblePlayers instanceof Set) {
        return filterChartSpecDataset(clonedSpec, row => {
            if (!row || typeof row !== 'object' || !('game_type' in row)) return true;
            if (allowedGameTypes && !allowedGameTypes.has(row.game_type)) return false;
            if (eligiblePlayers instanceof Set && !eligiblePlayers.has(row?.player)) return false;
            return true;
        });
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
        selectedScoreType,
        minimumAppearances
    } = state;

    renderPlayerStatsActiveFilterChips(state);

    try {
        if (!playerStatsBaseSpecs) {
            const [captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec] = await Promise.all([
                loadChartSpec('data/charts/player_stats_captains.json'),
                loadChartSpec('data/charts/player_stats_motm.json'),
                loadChartSpec('data/charts/player_stats_motm_units.json'),
                loadChartSpec('data/charts/player_stats_appearances.json'),
                loadChartSpec('data/charts/point_scorers.json')
            ]);
            playerStatsBaseSpecs = { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec };
        }

        const { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec } = playerStatsBaseSpecs;
        const eligiblePlayers = getPlayerStatsEligiblePlayersByMinAppearances(
            selectedSeasons,
            selectedGameType,
            selectedSquad,
            minimumAppearances
        );

        const filteredCaptains = filterPlayerStatsCaptainsSpec(captainsSpec, selectedSeasons, selectedGameType, selectedSquad, eligiblePlayers);
        const filteredMotm = filterPlayerStatsMotmSpec(motmSpec, selectedSeasons, selectedGameType, selectedSquad, eligiblePlayers);
        const filteredMotmUnits = filterPlayerStatsMotmUnitsSpec(motmUnitsSpec, selectedSeasons, selectedGameType, selectedSquad, eligiblePlayers);
        const filteredAppearances = filterPlayerStatsAppearancesSpec(appearancesSpec, selectedSeasons, selectedGameType, selectedSquad, selectedPositions, minimumAppearances);
        const filteredPoints = filterPlayerStatsPointsSpec(pointsSpec, selectedSeasons, selectedGameType, selectedSquad, selectedScoreType, eligiblePlayers);
        const motmSpecToRender = selectedMotmAggregate ? filteredMotmUnits : filteredMotm;
        const motmEmptyMessage = selectedMotmAggregate
            ? 'No MOTM unit breakdown available for the selected filters.'
            : 'No player of the match awards available for the selected filters.';
        const motmLayoutContainerId = selectedMotmAggregate ? 'playerStatsMotmUnitsChart' : 'playerStatsMotmChart';

        renderPlayerStatsHero(state);
        renderStaticSpecChart('playerStatsCaptainsChart', filteredCaptains, 'No captains or vice-captains data available for the selected season.');
        renderStaticSpecChart('playerStatsMotmChart', motmSpecToRender, motmEmptyMessage, { layoutContainerId: motmLayoutContainerId });
        renderStaticSpecChart('playerStatsAppearancesChart', filteredAppearances, 'No player appearances available for the selected filters.');
        renderStaticSpecChart('playerStatsPointsChart', filteredPoints, 'No point scorers available for the selected filters.');
    } catch (error) {
        console.warn('Unable to load Player Stats charts:', error);
        renderStaticSpecChart('playerStatsCaptainsChart', null, 'Unable to load captains chart.');
        renderStaticSpecChart('playerStatsMotmChart', null, 'Unable to load player of the match chart.');
        renderStaticSpecChart('playerStatsAppearancesChart', null, 'Unable to load appearances chart.');
        renderStaticSpecChart('playerStatsPointsChart', null, 'Unable to load point scorers chart.');
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    if (!playerStatsBaseSpecs) {
        const [captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec] = await Promise.all([
            loadChartSpec('data/charts/player_stats_captains.json'),
            loadChartSpec('data/charts/player_stats_motm.json'),
            loadChartSpec('data/charts/player_stats_motm_units.json'),
            loadChartSpec('data/charts/player_stats_appearances.json'),
            loadChartSpec('data/charts/point_scorers.json')
        ]);
        playerStatsBaseSpecs = { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec };
    }

    const { captainsSpec, motmSpec, motmUnitsSpec, appearancesSpec, pointsSpec } = playerStatsBaseSpecs;
    playerStatsDataSeasons = sortSeasonLabelsDescending([
        ...extractSeasonsFromSpec(captainsSpec),
        ...extractSeasonsFromSpec(motmSpec),
        ...extractSeasonsFromSpec(motmUnitsSpec),
        ...extractSeasonsFromSpec(appearancesSpec),
        ...extractSeasonsFromSpec(pointsSpec)
    ]);

    initialisePlayerStatsControls();
    initialisePlayerStatsAnalysisRail();
    renderPlayerStatsPage();
});

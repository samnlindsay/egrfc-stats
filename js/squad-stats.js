// Squad Stats + Player Stats page logic

let playerAppearancesData = null;
let appearanceReconciliationData = null;
let gamesData = null;
let squadStatsData = null;
let squadSizeTrendTemplateSpec = null;
let squadContinuityTrendTemplateSpec = null;
let squadStatsControlsInitialised = false;
let playerStatsControlsInitialised = false;

async function loadSquadStatsCanonicalData() {
    if (playerAppearancesData && appearanceReconciliationData && gamesData) return;

    const [appearancesResponse, reconciliationResponse, gamesResponse] = await Promise.all([
        fetch('data/backend/player_appearances.json'),
        fetch('data/backend/pitchero_appearance_reconciliation.json'),
        fetch('data/backend/games.json')
    ]);

    if (!appearancesResponse.ok) throw new Error(`Failed to fetch canonical player appearances (${appearancesResponse.status})`);
    if (!reconciliationResponse.ok) throw new Error(`Failed to fetch appearance reconciliation (${reconciliationResponse.status})`);
    if (!gamesResponse.ok) throw new Error(`Failed to fetch canonical games (${gamesResponse.status})`);

    playerAppearancesData = await appearancesResponse.json();
    appearanceReconciliationData = await reconciliationResponse.json();
    gamesData = await gamesResponse.json();

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

function buildSquadStatsDataFromCanonical(appearances, appearanceReconciliation, gameTypeMode) {
    const bySeason = {};
    const gameTypeByGameId = new Map((gamesData || []).map(game => [game.game_id, game.game_type]));
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const createMetricBucket = () => ({ players: new Map(), forwards: new Map(), backs: new Map() });
    const createSeasonBucket = () => ({ '1st': createMetricBucket(), '2nd': createMetricBucket(), 'Total': createMetricBucket() });
    const incrementPlayerCount = (countMap, player, amount = 1) => countMap.set(player, (countMap.get(player) || 0) + amount);

    // Position/unit breakdown still comes from raw appearance rows.
    appearances.forEach(row => {
        const season = row.season;
        const squad = row.squad;
        const player = String(row.player || '').trim();
        const unit = row.unit;
        const gameType = gameTypeByGameId.get(row.game_id);
        if (!season || !player || (squad !== '1st' && squad !== '2nd')) return;
        if (allowedGameTypes && !allowedGameTypes.has(gameType)) return;
        if (!bySeason[season]) bySeason[season] = createSeasonBucket();
        const seasonBucket = bySeason[season];

        if (unit === 'Forwards') {
            incrementPlayerCount(seasonBucket[squad].forwards, player);
            incrementPlayerCount(seasonBucket.Total.forwards, player);
        } else if (unit === 'Backs') {
            incrementPlayerCount(seasonBucket[squad].backs, player);
            incrementPlayerCount(seasonBucket.Total.backs, player);
        }
    });

    // Total player-usage counts use the strict final reconciliation rule when no game-type filter is applied.
    if (!allowedGameTypes) {
        (Array.isArray(appearanceReconciliation) ? appearanceReconciliation : []).forEach(row => {
            const season = String(row.season || '').trim();
            const squad = String(row.squad || '').trim();
            const player = String(row.player || '').trim();
            const scrapedAppearances = Number(row.scraped_appearances || 0);
            const pitcheroAppearances = Number(row.pitchero_appearances || 0);
            const effectiveAppearances = pitcheroAppearances > 0 ? pitcheroAppearances : scrapedAppearances;
            if (!season || !player || (squad !== '1st' && squad !== '2nd') || effectiveAppearances <= 0) return;
            if (!bySeason[season]) bySeason[season] = createSeasonBucket();
            const seasonBucket = bySeason[season];
            incrementPlayerCount(seasonBucket[squad].players, player, effectiveAppearances);
            incrementPlayerCount(seasonBucket.Total.players, player, effectiveAppearances);
        });
    } else {
        appearances.forEach(row => {
            const season = row.season;
            const squad = row.squad;
            const player = String(row.player || '').trim();
            const gameType = gameTypeByGameId.get(row.game_id);
            if (!season || !player || (squad !== '1st' && squad !== '2nd')) return;
            if (!allowedGameTypes.has(gameType)) return;
            if (!bySeason[season]) bySeason[season] = createSeasonBucket();
            const seasonBucket = bySeason[season];
            incrementPlayerCount(seasonBucket[squad].players, player);
            incrementPlayerCount(seasonBucket.Total.players, player);
        });
    }

    return bySeason;
}

async function loadSquadStatsPage() {
    try {
        await loadSquadStatsCanonicalData();
        initialiseSquadStatsControlsOnce();
        renderSquadStatsPage();
    } catch (err) {
        console.error('Error loading squad metrics data:', err);
        const tbody = document.getElementById('squadStatsTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger py-3">Unable to load squad metrics data.</td></tr>';
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

function resolveCanonicalPosition(number, position) {
    const shirtNumber = Number(number);
    if (Number.isFinite(shirtNumber)) {
        if (shirtNumber === 1 || shirtNumber === 3) return 'Prop';
        if (shirtNumber === 2) return 'Hooker';
        if (shirtNumber === 4 || shirtNumber === 5) return 'Second Row';
        if (shirtNumber === 6 || shirtNumber === 7) return 'Flanker';
        if (shirtNumber === 8) return 'Number 8';
        if (shirtNumber === 9) return 'Scrum Half';
        if (shirtNumber === 10) return 'Fly Half';
        if (shirtNumber === 12 || shirtNumber === 13) return 'Centre';
        if (shirtNumber === 11 || shirtNumber === 14) return 'Wing';
        if (shirtNumber === 15) return 'Full Back';
    }
    const normalizedPosition = String(position || '').trim().toLowerCase();
    const aliases = {
        prop: 'Prop', hooker: 'Hooker', 'second row': 'Second Row', flanker: 'Flanker',
        'number 8': 'Number 8', 'scrum half': 'Scrum Half', 'fly half': 'Fly Half',
        centre: 'Centre', wing: 'Wing', 'full back': 'Full Back', fullback: 'Full Back'
    };
    return aliases[normalizedPosition] || null;
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
    if (!playerAppearancesData || !selectedSeason) return counts;
    const allowedGameTypes = getAllowedGameTypes(getSquadStatsGameTypeMode());
    const gameTypeByGameId = new Map((gamesData || []).map(game => [game.game_id, game.game_type]));
    const threshold = Math.max(0, Number(minimumAppearances) || 0);
    const makePlayerMapForPositions = () => {
        const byPosition = {};
        SQUAD_POSITION_ORDER.forEach(position => { byPosition[position] = new Map(); });
        return byPosition;
    };
    const bySquadPositionPlayerCounts = { '1st': makePlayerMapForPositions(), '2nd': makePlayerMapForPositions() };
    (playerAppearancesData || []).forEach(row => {
        const season = normalizeSeasonLabel(row.season);
        const squad = row.squad;
        const player = String(row.player || '').trim();
        const gameType = gameTypeByGameId.get(row.game_id);
        if (season !== selectedSeason || !player || (squad !== '1st' && squad !== '2nd')) return;
        if (allowedGameTypes && !allowedGameTypes.has(gameType)) return;
        const canonicalPosition = resolveCanonicalPosition(row.number, row.position);
        if (!canonicalPosition || !SQUAD_POSITION_ORDER.includes(canonicalPosition)) return;
        const playerCountMap = bySquadPositionPlayerCounts[squad][canonicalPosition];
        playerCountMap.set(player, (playerCountMap.get(player) || 0) + 1);
    });
    ['1st', '2nd'].forEach(squad => {
        SQUAD_POSITION_ORDER.forEach(position => {
            const playerMap = bySquadPositionPlayerCounts[squad][position];
            if (!(playerMap instanceof Map)) return;
            if (threshold <= 0) { counts[squad][position] = playerMap.size; return; }
            let playerCount = 0;
            playerMap.forEach(value => { if (value >= threshold) playerCount += 1; });
            counts[squad][position] = playerCount;
        });
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
    const countPlayersAboveThreshold = countMap => {
        if (!(countMap instanceof Map)) return 0;
        if (threshold <= 0) return countMap.size;
        let count = 0;
        countMap.forEach(value => { if (value >= threshold) count += 1; });
        return count;
    };
    if (unit === 'Forwards') return countPlayersAboveThreshold(bucket.forwards);
    if (unit === 'Backs') return countPlayersAboveThreshold(bucket.backs);
    return countPlayersAboveThreshold(bucket.players);
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
    (playerAppearancesData || []).forEach(row => addSeason(row.season));
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
    if (!playerAppearancesData) { squadStatsData = {}; return; }
    const mode = getSquadStatsGameTypeMode();
    squadStatsData = buildSquadStatsDataFromCanonical(playerAppearancesData, appearanceReconciliationData, mode);
}

function renderSquadMetricCards(season, minimumAppearances) {
    const emptyBucket = () => ({ players: new Map(), forwards: new Map(), backs: new Map() });
    const seasonData = squadStatsData?.[season] || { '1st': emptyBucket(), '2nd': emptyBucket(), 'Total': emptyBucket() };
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

function renderSquadStatsTable(minimumAppearances) {
    const tbody = document.getElementById('squadStatsTableBody');
    if (!tbody) return;
    const subtitle = document.getElementById('squadStatsTableSubtitle');
    if (subtitle) {
        if (minimumAppearances > 1) { subtitle.textContent = `Players with ${minimumAppearances} or more appearances`; subtitle.style.display = 'block'; }
        else { subtitle.textContent = ''; subtitle.style.display = 'none'; }
    }
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const selectedSeason = seasonSelect?.value || getCurrentSeasonLabel();
    const seasonSet = new Set();
    const addSeason = season => { const normalized = normalizeSeasonLabel(season); if (normalized) seasonSet.add(normalized); };
    (availableSeasons || []).forEach(addSeason);
    Object.keys(squadStatsData || {}).forEach(addSeason);
    addSeason(selectedSeason);
    addSeason(getCurrentSeasonLabel());
    const seasons = getSortedSquadStatsSeasons(Object.fromEntries(Array.from(seasonSet).map(s => [s, true])));
    if (seasons.length === 0) { tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted py-3">No squad metrics available.</td></tr>'; return; }
    const emptyBucket = () => ({ players: new Map(), forwards: new Map(), backs: new Map() });
    tbody.innerHTML = seasons.map(season => {
        const seasonData = squadStatsData?.[season] || { '1st': emptyBucket(), '2nd': emptyBucket(), 'Total': emptyBucket() };
        const squad1 = seasonData['1st'];
        const squad2 = seasonData['2nd'];
        const total = seasonData['Total'];
        const rowClass = season === selectedSeason ? 'squad-stats-current-season' : '';
        return `
            <tr class="${rowClass}">
                <td>${season}</td>
                <td class="squad-group-cell-1st squad-cell-fwds">${getSquadMetricValue('Forwards', squad1, minimumAppearances)}</td>
                <td class="squad-group-cell-1st squad-cell-backs">${getSquadMetricValue('Backs', squad1, minimumAppearances)}</td>
                <td class="squad-group-cell-1st squad-cell-total">${getSquadMetricValue('Total', squad1, minimumAppearances)}</td>
                <td class="squad-group-cell-2nd squad-cell-fwds">${getSquadMetricValue('Forwards', squad2, minimumAppearances)}</td>
                <td class="squad-group-cell-2nd squad-cell-backs">${getSquadMetricValue('Backs', squad2, minimumAppearances)}</td>
                <td class="squad-group-cell-2nd squad-cell-total">${getSquadMetricValue('Total', squad2, minimumAppearances)}</td>
                <td class="squad-group-cell-total squad-cell-fwds">${getSquadMetricValue('Forwards', total, minimumAppearances)}</td>
                <td class="squad-group-cell-total squad-cell-backs">${getSquadMetricValue('Backs', total, minimumAppearances)}</td>
                <td class="squad-group-cell-total squad-cell-total">${getSquadMetricValue('Total', total, minimumAppearances)}</td>
            </tr>
        `;
    }).join('');
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
    if (!playerAppearancesData) return [];
    const allowedGameTypes = getAllowedGameTypes(getSquadStatsGameTypeMode());
    const gameInfoById = new Map((gamesData || []).map(game => [game.game_id, game]));
    const gamesBySquadSeason = {};
    (playerAppearancesData || []).forEach(row => {
        const season = normalizeSeasonLabel(row.season);
        const squad = row.squad;
        const gameId = row.game_id;
        const gameInfo = gameInfoById.get(gameId);
        const gameType = row.game_type || gameInfo?.game_type;
        if (!season || (squad !== '1st' && squad !== '2nd')) return;
        if (allowedGameTypes && !allowedGameTypes.has(gameType)) return;
        const key = `${squad}::${season}`;
        if (!gamesBySquadSeason[key]) gamesBySquadSeason[key] = { squad, season, games: [] };
        const gameList = gamesBySquadSeason[key].games;
        if (!gameList.find(g => g.gameId === gameId)) {
            gameList.push({ gameId, date: row.date || gameInfo?.date || null, starters: new Set() });
        }
    });
    (playerAppearancesData || []).forEach(row => {
        const season = normalizeSeasonLabel(row.season);
        const squad = row.squad;
        const gameId = row.game_id;
        const unit = row.unit;
        const gameType = row.game_type || gameInfoById.get(gameId)?.game_type;
        if (!season || (squad !== '1st' && squad !== '2nd')) return;
        if (allowedGameTypes && !allowedGameTypes.has(gameType)) return;
        if (row.is_starter !== true) return;
        const player = String(row.player || '').trim();
        const key = `${squad}::${season}`;
        const squadSeasonData = gamesBySquadSeason[key];
        if (squadSeasonData) {
            squadSeasonData.games.forEach(game => {
                if (game.gameId === gameId) {
                    game.starters.add(player);
                    if (!game.byUnit) game.byUnit = {};
                    if (!game.byUnit[unit]) game.byUnit[unit] = new Set();
                    game.byUnit[unit].add(player);
                }
            });
        }
    });
    const rows = [];
    Object.values(gamesBySquadSeason).forEach(squadSeasonData => {
        const games = squadSeasonData.games.sort((a, b) => {
            const dateA = a.date ? new Date(a.date).getTime() : 0;
            const dateB = b.date ? new Date(b.date).getTime() : 0;
            return dateA !== dateB ? dateA - dateB : String(a.gameId).localeCompare(String(b.gameId));
        });
        if (games.length < 2) return;
        const retentionsByUnit = { 'Total': [], 'Forwards': [], 'Backs': [] };
        for (let i = 1; i < games.length; i++) {
            const prevGame = games[i - 1];
            const currGame = games[i];
            const totalRetained = [...currGame.starters].filter(p => prevGame.starters.has(p)).length;
            retentionsByUnit['Total'].push(totalRetained);
            const prevForwards = prevGame.byUnit?.['Forwards'] || new Set();
            const currForwards = currGame.byUnit?.['Forwards'] || new Set();
            retentionsByUnit['Forwards'].push([...currForwards].filter(p => prevForwards.has(p)).length);
            const prevBacks = prevGame.byUnit?.['Backs'] || new Set();
            const currBacks = currGame.byUnit?.['Backs'] || new Set();
            retentionsByUnit['Backs'].push([...currBacks].filter(p => prevBacks.has(p)).length);
        }
        ['Total', 'Forwards', 'Backs'].forEach(unit => {
            if (retentionsByUnit[unit].length > 0) {
                const avgRetention = retentionsByUnit[unit].reduce((a, b) => a + b, 0) / retentionsByUnit[unit].length;
                rows.push({ season: squadSeasonData.season, squad: squadSeasonData.squad, unit, retained: avgRetention });
            }
        });
    });
    return rows;
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
    if (!playerAppearancesData) return;
    refreshSquadStatsData();
    const seasons = getSortedSquadStatsSeasons(squadStatsData);
    if (seasons.length === 0) {
        const minimumAppearances = getSquadStatsMinimumAppearances();
        const fallbackSeason = getCurrentSeasonLabel();
        renderSquadMetricCards(fallbackSeason, minimumAppearances);
        renderSquadStatsTable(minimumAppearances);
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
    renderSquadStatsTable(minimumAppearances);
    renderSquadStatsCharts(selectedSeason, minimumAppearances);
    initialiseChartPanelToggles();
}

function initialiseSquadStatsControlsOnce() {
    if (squadStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('squadStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('squadStatsGameTypeSelect');
    const minAppsInput = document.getElementById('squadStatsMinAppsSelect');
    const leagueContextUnitSelect = document.getElementById('leagueContextUnitSelect');
    if (!seasonSelect || !gameTypeSelect || !minAppsInput || !leagueContextUnitSelect) return;
    const $seasonSelect = $('#squadStatsSeasonSelect');
    const $gameTypeSelect = $('#squadStatsGameTypeSelect');
    const $leagueContextUnitSelect = $('#leagueContextUnitSelect');
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
    gameTypeSelect.value = 'All games';
    minAppsInput.value = '0';
    leagueContextUnitSelect.value = 'Total';
    $gameTypeSelect.selectpicker('val', 'All games');
    $leagueContextUnitSelect.selectpicker('val', 'Total');
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
    $leagueContextUnitSelect.on('changed.bs.select', renderLeagueContextCharts);
    squadStatsControlsInitialised = true;
}

// Player Stats functions
function getPlayerStatsSeasonOptions() {
    const seasons = Array.from(new Set((availableSeasons || []).filter(Boolean))).sort((a, b) => {
        const aYear = Number(String(a).split('/')[0]) || 0;
        const bYear = Number(String(b).split('/')[0]) || 0;
        return bYear - aYear;
    });
    return ['All', ...seasons];
}

function getPlayerStatsSquadColors() {
    const rootStyle = getComputedStyle(document.documentElement);
    const primary = (rootStyle.getPropertyValue('--primary-color') || '').trim() || '#202946';
    const accent = (rootStyle.getPropertyValue('--accent-color') || '').trim() || '#7d96e8';
    return [primary, accent];
}

function getPlayerStatsMinimumAppearances() {
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    const value = Number(minAppearancesInput?.value ?? 5);
    if (!Number.isFinite(value)) return 5;
    return Math.max(0, Math.floor(value));
}

function initialisePlayerStatsControls() {
    if (playerStatsControlsInitialised) return;
    const seasonSelect = document.getElementById('playerStatsSeasonSelect');
    const gameTypeSelect = document.getElementById('playerStatsGameTypeSelect');
    const squadSelect = document.getElementById('playerStatsSquadSelect');
    const positionSelect = document.getElementById('playerStatsPositionSelect');
    const scoreTypeSelect = document.getElementById('playerStatsScoreTypeSelect');
    const minAppearancesInput = document.getElementById('playerStatsMinAppearancesInput');
    if (!seasonSelect || !gameTypeSelect || !squadSelect || !positionSelect || !scoreTypeSelect || !minAppearancesInput) return;
    const seasons = getPlayerStatsSeasonOptions();
    seasonSelect.innerHTML = '';
    seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = season === 'All' ? 'All seasons' : season;
        seasonSelect.appendChild(option);
    });
    const $seasonSelect = $('#playerStatsSeasonSelect');
    const $gameTypeSelect = $('#playerStatsGameTypeSelect');
    const $squadSelect = $('#playerStatsSquadSelect');
    const $positionSelect = $('#playerStatsPositionSelect');
    const $scoreTypeSelect = $('#playerStatsScoreTypeSelect');
    [$seasonSelect, $gameTypeSelect, $squadSelect, $positionSelect, $scoreTypeSelect].forEach($el => {
        if ($el.data('selectpicker')) $el.selectpicker('destroy');
        $el.selectpicker();
    });
    $seasonSelect.selectpicker('val', 'All');
    $gameTypeSelect.selectpicker('val', 'All games');
    $squadSelect.selectpicker('val', 'All');
    $positionSelect.selectpicker('deselectAll');
    $scoreTypeSelect.selectpicker('val', 'Total');
    $seasonSelect.on('changed.bs.select', renderPlayerStatsPage);
    $gameTypeSelect.on('changed.bs.select', renderPlayerStatsPage);
    $squadSelect.on('changed.bs.select', renderPlayerStatsPage);
    $positionSelect.on('changed.bs.select', renderPlayerStatsPage);
    $scoreTypeSelect.on('changed.bs.select', renderPlayerStatsPage);
    minAppearancesInput.addEventListener('input', renderPlayerStatsPage);
    minAppearancesInput.addEventListener('change', renderPlayerStatsPage);
    playerStatsControlsInitialised = true;
}

function filterPlayerStatsCaptainsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const squadColors = getPlayerStatsSquadColors();
    if (Array.isArray(clonedSpec?.spec?.layer)) {
        clonedSpec.spec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
        });
    }
    const predicate = row => {
        const seasons = Array.isArray(selectedSeasons) ? selectedSeasons : [];
        if (seasons.length === 0) { if (row?.season !== 'Total') return false; }
        else if (row?.season === 'Total' || !seasons.includes(row?.season)) return false;
        if (allowedGameTypes && !allowedGameTypes.has(row?.game_type)) return false;
        if (selectedSquad !== 'All' && row?.squad !== selectedSquad) return false;
        return true;
    };
    return filterChartSpecDataset(clonedSpec, predicate);
}

function filterPlayerStatsAppearancesSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, positions, minimumAppearances) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const squadColors = getPlayerStatsSquadColors();
    if (Array.isArray(clonedSpec?.layer)) {
        clonedSpec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
        });
    }
    const seasonValue = Array.isArray(selectedSeasons) ? selectedSeasons : [];
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const positionsValue = Array.isArray(positions) && positions.length > 0 ? positions : [];
    const threshold = Number.isFinite(minimumAppearances) ? Math.max(0, Math.floor(minimumAppearances)) : 5;
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

function filterPlayerStatsPointsSpec(spec, selectedSeasons, selectedSquad, scoreType) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = Array.isArray(selectedSeasons) ? selectedSeasons : [];
    const nextScoreType = scoreType || 'Total';
    const valueAxisTitle = nextScoreType === 'Tries' ? 'Tries' : 'Points';
    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
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
    return clonedSpec;
}

async function renderPlayerStatsPage() {
    const selectedSeasonValue = document.getElementById('playerStatsSeasonSelect')?.value;
    const selectedSeasons = (selectedSeasonValue && selectedSeasonValue !== 'All')
        ? [selectedSeasonValue]
        : [];
    const selectedGameType = document.getElementById('playerStatsGameTypeSelect')?.value || 'All games';
    const selectedSquad = document.getElementById('playerStatsSquadSelect')?.value || 'All';
    const selectedPositions = $('#playerStatsPositionSelect').val() || [];
    const selectedScoreType = document.getElementById('playerStatsScoreTypeSelect')?.value || 'Total';
    const minimumAppearances = getPlayerStatsMinimumAppearances();
    try {
        const [captainsSpec, appearancesSpec, pointsSpec] = await Promise.all([
            loadChartSpec('data/charts/player_stats_captains.json'),
            loadChartSpec('data/charts/player_stats_appearances.json'),
            loadChartSpec('data/charts/point_scorers.json')
        ]);
        const filteredCaptains = filterPlayerStatsCaptainsSpec(captainsSpec, selectedSeasons, selectedGameType, selectedSquad);
        const filteredAppearances = filterPlayerStatsAppearancesSpec(appearancesSpec, selectedSeasons, selectedGameType, selectedSquad, selectedPositions, minimumAppearances);
        const filteredPoints = filterPlayerStatsPointsSpec(pointsSpec, selectedSeasons, selectedSquad, selectedScoreType);
        renderStaticSpecChart('playerStatsCaptainsChart', filteredCaptains, 'No captains or vice-captains data available for the selected season.');
        renderStaticSpecChart('playerStatsAppearancesChart', filteredAppearances, 'No player appearances available for the selected filters.');
        renderStaticSpecChart('playerStatsPointsChart', filteredPoints, 'No point scorers available for the selected filters.');
    } catch (error) {
        console.warn('Unable to load Player Stats charts:', error);
        renderStaticSpecChart('playerStatsCaptainsChart', null, 'Unable to load captains chart.');
        renderStaticSpecChart('playerStatsAppearancesChart', null, 'Unable to load appearances chart.');
        renderStaticSpecChart('playerStatsPointsChart', null, 'Unable to load point scorers chart.');
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    initialisePlayerStatsControls();
    renderPlayerStatsPage();
    loadSquadStatsPage();
});

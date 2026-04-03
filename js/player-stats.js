// Player Stats page logic

let playerStatsControlsInitialised = false;
let playerStatsDataSeasons = [];
let playerStatsBaseSpecs = null;

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
    const seasons = sortSeasonLabelsDescending([...(availableSeasons || []), ...playerStatsDataSeasons]);
    return seasons;
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
        option.textContent = season;
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
    const currentSeason = getCurrentSeasonLabel();
    const defaultSeason = seasons.includes(currentSeason) ? currentSeason : (seasons[0] || null);
    if (defaultSeason) {
        $seasonSelect.selectpicker('val', [defaultSeason]);
    } else {
        $seasonSelect.selectpicker('deselectAll');
    }
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
        if (seasons.length === 0) {
            if (row?.season === 'Total') return false;
        }
        else if (row?.season === 'Total' || !seasons.includes(row?.season)) return false;
        if (allowedGameTypes && !allowedGameTypes.has(row?.game_type)) return false;
        if (selectedSquad !== 'All' && row?.squad !== selectedSquad) return false;
        return true;
    };
    return filterChartSpecDataset(clonedSpec, predicate);
}

function filterPlayerStatsMotmSpec(spec, selectedSeasons, gameTypeMode, selectedSquad) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = Array.isArray(selectedSeasons) ? selectedSeasons : [];
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const squadColors = getPlayerStatsSquadColors();

    if (Array.isArray(clonedSpec.layer)) {
        clonedSpec.layer.forEach(layer => {
            if (layer?.encoding?.color?.scale) layer.encoding.color.scale.range = squadColors;
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

function filterPlayerStatsPointsSpec(spec, selectedSeasons, gameTypeMode, selectedSquad, scoreType) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const seasonValue = Array.isArray(selectedSeasons) ? selectedSeasons : [];
    const allowedGameTypes = getAllowedGameTypes(gameTypeMode);
    const gameTypesValue = allowedGameTypes ? Array.from(allowedGameTypes) : [];
    const nextScoreType = scoreType || 'Total';
    const valueAxisTitle = nextScoreType === 'Tries' ? 'Tries' : 'Points';
    if (Array.isArray(clonedSpec.params)) {
        clonedSpec.params.forEach(param => {
            switch (param.name) {
                case 'seasonParam': param.value = seasonValue; break;
                case 'gameTypesParam': param.value = gameTypesValue; break;
                case 'gameTypeParam': param.value = gameTypeMode || 'All games'; break;
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
    // Fallback filtering for specs that include raw data with game_type but no Vega params.
    if (allowedGameTypes) {
        return filterChartSpecDataset(clonedSpec, row => {
            if (!row || typeof row !== 'object' || !('game_type' in row)) return true;
            return allowedGameTypes.has(row.game_type);
        });
    }
    return clonedSpec;
}

async function renderPlayerStatsPage() {
    const selectedSeasons = $('#playerStatsSeasonSelect').val() || [];
    const selectedGameType = document.getElementById('playerStatsGameTypeSelect')?.value || 'All games';
    const selectedSquad = document.getElementById('playerStatsSquadSelect')?.value || 'All';
    const selectedPositions = $('#playerStatsPositionSelect').val() || [];
    const selectedScoreType = document.getElementById('playerStatsScoreTypeSelect')?.value || 'Total';
    const minimumAppearances = getPlayerStatsMinimumAppearances();
    try {
        if (!playerStatsBaseSpecs) {
            const [captainsSpec, motmSpec, appearancesSpec, pointsSpec] = await Promise.all([
                loadChartSpec('data/charts/player_stats_captains.json'),
                loadChartSpec('data/charts/player_stats_motm.json'),
                loadChartSpec('data/charts/player_stats_appearances.json'),
                loadChartSpec('data/charts/point_scorers.json')
            ]);
            playerStatsBaseSpecs = { captainsSpec, motmSpec, appearancesSpec, pointsSpec };
        }
        const { captainsSpec, motmSpec, appearancesSpec, pointsSpec } = playerStatsBaseSpecs;
        const filteredCaptains = filterPlayerStatsCaptainsSpec(captainsSpec, selectedSeasons, selectedGameType, selectedSquad);
        const filteredMotm = filterPlayerStatsMotmSpec(motmSpec, selectedSeasons, selectedGameType, selectedSquad);
        const filteredAppearances = filterPlayerStatsAppearancesSpec(appearancesSpec, selectedSeasons, selectedGameType, selectedSquad, selectedPositions, minimumAppearances);
        const filteredPoints = filterPlayerStatsPointsSpec(pointsSpec, selectedSeasons, selectedGameType, selectedSquad, selectedScoreType);
        renderStaticSpecChart('playerStatsCaptainsChart', filteredCaptains, 'No captains or vice-captains data available for the selected season.');
        renderStaticSpecChart('playerStatsMotmChart', filteredMotm, 'No player of the match awards available for the selected filters.');
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
        const [captainsSpec, motmSpec, appearancesSpec, pointsSpec] = await Promise.all([
            loadChartSpec('data/charts/player_stats_captains.json'),
            loadChartSpec('data/charts/player_stats_motm.json'),
            loadChartSpec('data/charts/player_stats_appearances.json'),
            loadChartSpec('data/charts/point_scorers.json')
        ]);
        playerStatsBaseSpecs = { captainsSpec, motmSpec, appearancesSpec, pointsSpec };
    }
    const { captainsSpec, motmSpec, appearancesSpec, pointsSpec } = playerStatsBaseSpecs;
    playerStatsDataSeasons = sortSeasonLabelsDescending([
        ...extractSeasonsFromSpec(captainsSpec),
        ...extractSeasonsFromSpec(motmSpec),
        ...extractSeasonsFromSpec(appearancesSpec),
        ...extractSeasonsFromSpec(pointsSpec)
    ]);
    initialisePlayerStatsControls();
    initialiseChartPanelToggles();
    renderPlayerStatsPage();
});

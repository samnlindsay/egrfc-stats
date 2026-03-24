// Team Sheets page logic

let teamSheetsControlsInitialised = false;

function filterTeamSheetSpec(spec, seasons, squad, gameType, positions) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const predicate = row => {
        if (Array.isArray(seasons) && seasons.length > 0 && !seasons.includes(row?.season)) return false;
        if (squad !== 'All' && row?.squad !== squad) return false;
        if (gameType === 'League only' && row?.game_type !== 'League') return false;
        if (gameType === 'League + Cup' && !['League', 'Cup'].includes(row?.game_type)) return false;
        if (positions.length > 0 && !positions.includes(row?.position)) return false;
        return true;
    };
    return filterChartSpecDataset(clonedSpec, predicate);
}

async function renderTeamSheetsPage() {
    const selectedSeasons = $('#teamSheetsSeasonSelect').val() || [];
    const selectedSquad = document.getElementById('teamSheetsSquadSelect')?.value || 'All';
    const selectedGameType = document.getElementById('teamSheetsGameTypeSelect')?.value || 'All games';
    const selectedPositions = $('#teamSheetsPositionSelect').val() || [];
    try {
        const spec = await loadChartSpec('data/charts/team_sheets.json');
        const filteredSpec = filterTeamSheetSpec(spec, selectedSeasons, selectedSquad, selectedGameType, selectedPositions);
        renderStaticSpecChart('teamSheetsChart', filteredSpec, 'No team sheet data available for the selected filters.');
    } catch (error) {
        console.warn('Unable to load team sheets chart:', error);
        renderStaticSpecChart('teamSheetsChart', null, 'Unable to load team sheets chart.');
    }
}

function initialiseTeamSheetsControls() {
    if (teamSheetsControlsInitialised) return;
    const seasonSelect = document.getElementById('teamSheetsSeasonSelect');
    const squadSelect = document.getElementById('teamSheetsSquadSelect');
    const gameTypeSelect = document.getElementById('teamSheetsGameTypeSelect');
    const positionSelect = document.getElementById('teamSheetsPositionSelect');
    if (!seasonSelect || !squadSelect || !gameTypeSelect || !positionSelect) return;
    const seasons = Array.from(new Set((availableSeasons || []).filter(Boolean)));
    const currentSeason = getCurrentSeasonLabel();
    if (seasons.length === 0) seasons.push(currentSeason);
    seasonSelect.innerHTML = '';
    seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = season;
        option.selected = season === currentSeason;
        seasonSelect.appendChild(option);
    });
    const $seasonSelect = $('#teamSheetsSeasonSelect');
    const $squadSelect = $('#teamSheetsSquadSelect');
    const $gameTypeSelect = $('#teamSheetsGameTypeSelect');
    const $positionSelect = $('#teamSheetsPositionSelect');
    [$seasonSelect, $squadSelect, $gameTypeSelect, $positionSelect].forEach($el => {
        if ($el.data('selectpicker')) $el.selectpicker('destroy');
        $el.selectpicker();
    });
    const selectedSeasons = seasons.includes(currentSeason) ? [currentSeason] : [seasons[0]];
    $seasonSelect.selectpicker('val', selectedSeasons);
    $squadSelect.selectpicker('val', 'All');
    $gameTypeSelect.selectpicker('val', 'All games');
    $positionSelect.selectpicker('deselectAll');
    $seasonSelect.on('changed.bs.select', renderTeamSheetsPage);
    $squadSelect.on('changed.bs.select', renderTeamSheetsPage);
    $gameTypeSelect.on('changed.bs.select', renderTeamSheetsPage);
    $positionSelect.on('changed.bs.select', renderTeamSheetsPage);
    teamSheetsControlsInitialised = true;
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();
    initialiseTeamSheetsControls();
    renderTeamSheetsPage();
});

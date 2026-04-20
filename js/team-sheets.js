// Team Sheets page logic

let teamSheetsControlsInitialised = false;
let teamSheetsSpec = null;
const TEAM_SHEETS_ALL_SEASONS_VALUE = '__all_seasons__';

function renderTeamSheetsActiveFilterChips() {
    const host = document.getElementById('teamSheetsActiveFilters');
    if (!host) return;

    const selectedSeasons = $('#teamSheetsSeasonSelect').val() || [];
    const selectedSquad = document.getElementById('teamSheetsSquadSelect')?.value || 'All';
    const selectedGameType = document.getElementById('teamSheetsGameTypeSelect')?.value || 'All games';
    const selectedPositions = $('#teamSheetsPositionSelect').val() || [];

    // Build season label
    let seasonLabel = 'All';
    if (Array.isArray(selectedSeasons) && selectedSeasons.length > 0) {
        if (selectedSeasons.length === 1 && selectedSeasons[0] === TEAM_SHEETS_ALL_SEASONS_VALUE) {
            seasonLabel = getTeamSheetsAllSeasonsLabel();
        } else {
            seasonLabel = selectedSeasons.length === 1 ? selectedSeasons[0] : `${selectedSeasons.length} selected`;
        }
    }

    // Build position label
    let positionLabel = 'All';
    if (Array.isArray(selectedPositions) && selectedPositions.length > 0) {
        const hasStarters = selectedPositions.includes('Starters');
        const hasBench = selectedPositions.includes('Bench');
        if (hasStarters && hasBench) {
            positionLabel = 'All';
        } else if (hasStarters) {
            positionLabel = 'Starting XV';
        } else if (hasBench) {
            positionLabel = 'Bench';
        }
    }

    const squadLabel = selectedSquad === 'All' ? 'All' : `${selectedSquad} XV`;
    const gameTypeLabel = selectedGameType === 'All games' ? 'All games' : selectedGameType;

    const chipButtonAttrs = 'type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#teamSheetsFiltersOffcanvas" aria-controls="teamSheetsFiltersOffcanvas"';
    host.innerHTML = [
        `<button ${chipButtonAttrs}><strong>Season</strong> ${seasonLabel}</button>`,
        `<button ${chipButtonAttrs}><strong>Squad</strong> ${squadLabel}</button>`,
        `<button ${chipButtonAttrs}><strong>Game Type</strong> ${gameTypeLabel}</button>`,
        `<button ${chipButtonAttrs}><strong>Position</strong> ${positionLabel}</button>`
    ].join('');
}



function extractSeasonsFromSpec(spec) {
    if (!spec) return [];
    const datasets = spec.datasets || {};
    const rows = Object.values(datasets).find(v => Array.isArray(v)) || [];
    const seasons = Array.from(new Set(rows.map(r => r?.season).filter(Boolean)));
    return seasons.sort((a, b) => {
        const startA = parseInt(String(a).split('/')[0], 10);
        const startB = parseInt(String(b).split('/')[0], 10);
        return startA - startB;  // Oldest-to-newest for stepper navigation
    });
}

function getTeamSheetsAllSeasonsLabel() {
    const seasons = extractSeasonsFromSpec(teamSheetsSpec);
    if (!seasons || seasons.length === 0) return 'All';
    const earliestSeason = seasons[0];
    if (!earliestSeason) return 'All';
    const [startYear, endYear] = String(earliestSeason).split('/');
    if (!startYear || !endYear) return `All (${earliestSeason})`;
    const centuryPrefix = String(startYear).slice(0, 2);
    const normalizedEndYear = endYear.length === 2 ? `${centuryPrefix}${endYear}` : endYear;
    return `All (${normalizedEndYear}-)`;
}

function filterTeamSheetSpec(spec, seasons, squad, gameType, positions) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const predicate = row => {
        if (Array.isArray(seasons) && seasons.length > 0 && !seasons.includes(row?.season)) return false;
        if (squad !== 'All' && row?.squad !== squad) return false;
        if (gameType === 'League only' && row?.game_type !== 'League') return false;
        if (gameType === 'League + Cup' && !['League', 'Cup'].includes(row?.game_type)) return false;
        
        // Handle position filtering as an additive union.
        // Example: Forwards + Bench => positions 1-8 OR shirt numbers 16+.
        if (Array.isArray(positions) && positions.length > 0) {
            const hasStarters = positions.includes('Starters');
            const hasBench = positions.includes('Bench');
            const selectedPositions = positions.filter(p => !['Starters', 'Bench', 'Forwards', 'Backs'].includes(p));
            const isStarter = Number(row?.shirt_number) <= 15;
            const isBench = Number(row?.shirt_number) > 15;

            const matchesStarters = hasStarters && isStarter;
            const matchesBench = hasBench && isBench;
            const matchesSpecificPosition = selectedPositions.length > 0 && selectedPositions.includes(row?.position);

            if (!(matchesStarters || matchesBench || matchesSpecificPosition)) return false;
        }
        
        return true;
    };
    return filterChartSpecDataset(clonedSpec, predicate);
}

async function renderTeamSheetsPage() {
    let selectedSeasons = $('#teamSheetsSeasonSelect').val() || [];
    const selectedSquad = document.getElementById('teamSheetsSquadSelect')?.value || 'All';
    const selectedGameType = document.getElementById('teamSheetsGameTypeSelect')?.value || 'All games';
    const selectedPositions = $('#teamSheetsPositionSelect').val() || [];

    // Convert all seasons value to empty array (show all)
    if (Array.isArray(selectedSeasons) && selectedSeasons.length === 1 && selectedSeasons[0] === TEAM_SHEETS_ALL_SEASONS_VALUE) {
        selectedSeasons = [];
    }

    renderTeamSheetsActiveFilterChips();

    try {
        const spec = teamSheetsSpec || await loadChartSpec('data/charts/team_sheets.json');
        const filteredSpec = filterTeamSheetSpec(
            spec,
            selectedSeasons,
            selectedSquad,
            selectedGameType,
            selectedPositions
        );
        renderStaticSpecChart('teamSheetsChart', filteredSpec, 'No team sheet data available for the selected filters.');
    } catch (error) {
        console.warn('Unable to load team sheets chart:', error);
        renderStaticSpecChart('teamSheetsChart', null, 'Unable to load team sheets chart.');
    }
}

function syncTeamSheetsPositionButtons() {
    const grid = document.getElementById('teamSheetsPositionGrid');
    if (!grid) return;
    const selectedPositions = $('#teamSheetsPositionSelect').val() || [];
    const selectedSet = new Set(selectedPositions);
    const hasStarters = selectedSet.has('Starters');
    const hasBench = selectedSet.has('Bench');
    const isForwards = ['Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8'].every(p => selectedSet.has(p))
        && selectedPositions.length === 5 + (hasStarters ? 1 : 0) + (hasBench ? 1 : 0);
    const isBacksAll = ['Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back'].every(p => selectedSet.has(p))
        && selectedPositions.length === 5 + (hasStarters ? 1 : 0) + (hasBench ? 1 : 0);

    grid.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        const value = btn.dataset.value;
        let active = false;
        if (value === 'Starters') active = hasStarters;
        else if (value === 'Bench') active = hasBench;
        else if (value === 'Forwards') active = isForwards;
        else if (value === 'Backs') active = isBacksAll;
        else active = selectedSet.has(value);
        btn.classList.toggle('is-active', active);
    });
}

function initialiseTeamSheetsControls(seasons) {
    if (teamSheetsControlsInitialised) return;
    if (!seasons || seasons.length === 0) seasons = availableSeasons || [];

    // Ensure seasons are sorted newest-to-oldest
    seasons = Array.from(new Set(seasons)).sort((a, b) => {
        const startA = parseInt(String(a).split('/')[0], 10);
        const startB = parseInt(String(b).split('/')[0], 10);
        return startB - startA;
    });

    const currentSeason = getCurrentSeasonLabel();
    const seasonSelect = document.getElementById('teamSheetsSeasonSelect');
    const squadSegment = document.getElementById('teamSheetsSquadSegment');
    const gameTypeSegment = document.getElementById('teamSheetsGameTypeSegment');
    const positionGrid = document.getElementById('teamSheetsPositionGrid');

    if (!seasonSelect || !squadSegment || !gameTypeSegment || !positionGrid) return;

    // Populate season select (hidden, for state management)
    // First add the "All seasons" option
    seasonSelect.innerHTML = '';
    const allSeasonsOption = document.createElement('option');
    allSeasonsOption.value = TEAM_SHEETS_ALL_SEASONS_VALUE;
    allSeasonsOption.textContent = getTeamSheetsAllSeasonsLabel();
    seasonSelect.appendChild(allSeasonsOption);
    
    // Then add individual seasons (oldest-to-newest for stepper)
    seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = season;
        seasonSelect.appendChild(option);
    });

    // Set initial season to "All"
    $('#teamSheetsSeasonSelect').val([TEAM_SHEETS_ALL_SEASONS_VALUE]);

    // Season stepper buttons (prev = older, next = newer in chronological order)
    document.getElementById('teamSheetsSeasonPrev').addEventListener('click', () => {
        const currentVal = getCurrentSelectedTeamSheetsSeason();
        const currentIdx = currentVal === TEAM_SHEETS_ALL_SEASONS_VALUE ? -1 : seasons.indexOf(currentVal);
        if (currentIdx > 0) {
            $('#teamSheetsSeasonSelect').val([seasons[currentIdx - 1]]);
            updateTeamSheetsSeasonLabel(seasons);
            renderTeamSheetsPage();
        }
    });

    document.getElementById('teamSheetsSeasonNext').addEventListener('click', () => {
        const currentVal = getCurrentSelectedTeamSheetsSeason();
        const currentIdx = currentVal === TEAM_SHEETS_ALL_SEASONS_VALUE ? -1 : seasons.indexOf(currentVal);
        if (currentIdx < seasons.length - 1) {
            $('#teamSheetsSeasonSelect').val([seasons[currentIdx + 1]]);
            updateTeamSheetsSeasonLabel(seasons);
            renderTeamSheetsPage();
        }
    });

    // Squad segment buttons
    squadSegment.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', () => {
            squadSegment.querySelectorAll('button').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            const value = btn.dataset.value;
            document.getElementById('teamSheetsSquadSelect').value = value;
            renderTeamSheetsPage();
        });
    });

    // Game Type segment buttons
    gameTypeSegment.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', () => {
            gameTypeSegment.querySelectorAll('button').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            const value = btn.dataset.value;
            document.getElementById('teamSheetsGameTypeSelect').value = value;
            renderTeamSheetsPage();
        });
    });

    // Initialize position select with all available positions
    const positionSelect = document.getElementById('teamSheetsPositionSelect');
    if (positionSelect) {
        const positions = ['Starters', 'Bench', 'Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8', 'Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back', 'Forwards', 'Backs'];
        positionSelect.innerHTML = '';
        positions.forEach(pos => {
            const option = document.createElement('option');
            option.value = pos;
            option.textContent = pos;
            positionSelect.appendChild(option);
        });
        // Default: select Starting XV + Bench (interpreted as All)
        $(positionSelect).val(['Starters', 'Bench']);
    }

    // Position picker buttons (including nested in btn-groups)
    const positionButtons = positionGrid.querySelectorAll('button[data-value]');
    positionButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const value = btn.dataset.value;
            const select = document.getElementById('teamSheetsPositionSelect');
            const currentValues = ($(select).val() || []).slice();

            if (value === 'Starters') {
                // Toggle Starters independently
                if (currentValues.includes('Starters')) {
                    $(select).val(currentValues.filter(v => v !== 'Starters'));
                } else {
                    $(select).val([...currentValues, 'Starters']);
                }
            } else if (value === 'Bench') {
                // Toggle Bench independently
                if (currentValues.includes('Bench')) {
                    $(select).val(currentValues.filter(v => v !== 'Bench'));
                } else {
                    $(select).val([...currentValues, 'Bench']);
                }
            } else if (value === 'Forwards') {
                const forwards = ['Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8'];
                const hasAll = forwards.every(p => currentValues.includes(p));
                if (hasAll && currentValues.filter(v => forwards.includes(v)).length === 5) {
                    // Remove all forwards
                    $(select).val(currentValues.filter(v => !forwards.includes(v)));
                } else {
                    // Add all forwards
                    const newValues = currentValues.filter(v => !forwards.includes(v));
                    $(select).val([...new Set([...newValues, ...forwards])]);
                }
            } else if (value === 'Backs') {
                const backs = ['Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back'];
                const hasAll = backs.every(p => currentValues.includes(p));
                if (hasAll && currentValues.filter(v => backs.includes(v)).length === 5) {
                    // Remove all backs
                    $(select).val(currentValues.filter(v => !backs.includes(v)));
                } else {
                    // Add all backs
                    const newValues = currentValues.filter(v => !backs.includes(v));
                    $(select).val([...new Set([...newValues, ...backs])]);
                }
            } else {
                // Regular position - toggle
                const idx = currentValues.indexOf(value);
                if (idx > -1) {
                    currentValues.splice(idx, 1);
                } else {
                    currentValues.push(value);
                }
                $(select).val(currentValues);
            }

            syncTeamSheetsPositionButtons();
            renderTeamSheetsPage();
        });
    });

    // Update season label display
    updateTeamSheetsSeasonLabel(seasons);
    syncTeamSheetsPositionButtons();

    teamSheetsControlsInitialised = true;
}

function getCurrentSelectedTeamSheetsSeason() {
    const val = $('#teamSheetsSeasonSelect').val();
    return Array.isArray(val) && val.length > 0 ? val[0] : '';
}

function updateTeamSheetsSeasonLabel(seasons) {
    const seasonLabel = document.getElementById('teamSheetsSeasonLabel');
    if (seasonLabel) {
        const current = getCurrentSelectedTeamSheetsSeason();
        if (current === TEAM_SHEETS_ALL_SEASONS_VALUE) {
            seasonLabel.textContent = getTeamSheetsAllSeasonsLabel();
        } else {
            seasonLabel.textContent = current || 'Select';
        }
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    try {
        teamSheetsSpec = await loadChartSpec('data/charts/team_sheets.json');
    } catch (e) {
        console.warn('Unable to pre-load team sheets spec:', e);
    }
    const seasons = extractSeasonsFromSpec(teamSheetsSpec);
    initialiseTeamSheetsControls(seasons);
    renderTeamSheetsPage();
});

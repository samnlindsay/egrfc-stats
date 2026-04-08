(function () {
    const state = {
        squad: 'All',
        season: '2025/26',
        gameType: 'All games',
        minApps: 0,
    };

    const dataset = {
        games: [],
        players: [],
        redZone: [],
        setPiece: [],
    };

    function normaliseGameType(value) {
        const text = String(value || '').toLowerCase();
        if (text.includes('league')) return 'League';
        if (text.includes('cup')) return 'Cup';
        if (text.includes('friendly')) return 'Friendly';
        return 'Other';
    }

    async function loadData() {
        const [gamesRes, playersRes, redZoneRes, setPieceRes] = await Promise.all([
            fetch('data/backend/games.json'),
            fetch('data/backend/players.json'),
            fetch('data/backend/v_red_zone.json'),
            fetch('data/backend/set_piece.json'),
        ]);

        dataset.games = gamesRes.ok ? await gamesRes.json() : [];
        dataset.players = playersRes.ok ? await playersRes.json() : [];
        dataset.redZone = redZoneRes.ok ? await redZoneRes.json() : [];
        dataset.setPiece = setPieceRes.ok ? await setPieceRes.json() : [];
    }

    function average(values) {
        if (!values.length) return 0;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    function getFilteredGames() {
        return dataset.games.filter(row => {
            const seasonOk = String(row?.season || '') === state.season;
            const squadOk = state.squad === 'All' || String(row?.squad || '') === state.squad;

            if (!seasonOk || !squadOk) return false;

            const type = normaliseGameType(row?.game_type || '');
            if (state.gameType === 'League only') return type === 'League';
            if (state.gameType === 'League + Cup') return type === 'League' || type === 'Cup';
            return type === 'League' || type === 'Cup' || type === 'Friendly';
        });
    }

    function getFilteredPlayers() {
        return dataset.players.filter(row => {
            const squadOk = state.squad === 'All' || String(row?.squad || '') === state.squad;
            const appsOk = Number(row?.total_appearances || 0) >= state.minApps;
            return squadOk && appsOk;
        });
    }

    function getFilteredSetPiece() {
        return dataset.setPiece.filter(row => {
            const seasonOk = String(row?.season || '') === state.season;
            const squadOk = state.squad === 'All' || String(row?.squad || '') === state.squad;
            return seasonOk && squadOk;
        });
    }

    function getFilteredRedZone() {
        return dataset.redZone.filter(row => {
            const seasonOk = String(row?.season || '') === state.season;
            const squadOk = state.squad === 'All' || String(row?.squad || '') === state.squad;
            return seasonOk && squadOk && String(row?.team || '') === 'EGRFC';
        });
    }

    function render() {
        const games = getFilteredGames();
        const players = getFilteredPlayers();
        const setPiece = getFilteredSetPiece();
        const redZone = getFilteredRedZone();

        const wins = games.filter(g => g?.result === 'W').length;
        const draws = games.filter(g => g?.result === 'D').length;
        const losses = games.filter(g => g?.result === 'L').length;

        const pointsFor = average(games.map(g => Number(g?.score_for || 0)));
        const pointsAgainst = average(games.map(g => Number(g?.score_against || 0)));

        const wsKpiGames = document.getElementById('wsKpiGames');
        const wsKpiWinRate = document.getElementById('wsKpiWinRate');
        const wsKpiPointsFor = document.getElementById('wsKpiPointsFor');
        const wsKpiPointsAgainst = document.getElementById('wsKpiPointsAgainst');
        const wsKpiPlayers = document.getElementById('wsKpiPlayers');

        if (wsKpiGames) wsKpiGames.textContent = String(games.length);
        if (wsKpiWinRate) wsKpiWinRate.textContent = games.length ? ((wins / games.length) * 100).toFixed(1) + '%' : '-';
        if (wsKpiPointsFor) wsKpiPointsFor.textContent = games.length ? pointsFor.toFixed(1) : '-';
        if (wsKpiPointsAgainst) wsKpiPointsAgainst.textContent = games.length ? pointsAgainst.toFixed(1) : '-';
        if (wsKpiPlayers) wsKpiPlayers.textContent = String(players.length);

        const wsRecentMatches = document.getElementById('wsRecentMatches');
        if (wsRecentMatches) {
            const recent = games
                .slice()
                .sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')))
                .slice(0, 8);

            wsRecentMatches.innerHTML = recent.length
                ? recent.map(g => '<li>' + g.date + ' | ' + g.squad + ' XV vs ' + g.opposition + ' | ' + g.score_for + '-' + g.score_against + ' (' + g.result + ')</li>').join('')
                : '<li>No matches for current filters.</li>';
        }

        const total = Math.max(1, games.length);
        const wsOutcomesNote = document.getElementById('wsOutcomesNote');
        const wsWinsBar = document.getElementById('wsWinsBar');
        const wsDrawsBar = document.getElementById('wsDrawsBar');
        const wsLossesBar = document.getElementById('wsLossesBar');
        if (wsOutcomesNote) wsOutcomesNote.textContent = 'W-D-L: ' + wins + '-' + draws + '-' + losses + ' across ' + games.length + ' games.';
        if (wsWinsBar) wsWinsBar.style.width = ((wins / total) * 100).toFixed(1) + '%';
        if (wsDrawsBar) wsDrawsBar.style.width = ((draws / total) * 100).toFixed(1) + '%';
        if (wsLossesBar) wsLossesBar.style.width = ((losses / total) * 100).toFixed(1) + '%';

        const wsPlayersRows = document.getElementById('wsPlayersRows');
        if (wsPlayersRows) {
            const topPlayers = players
                .slice()
                .sort((a, b) => Number(b?.total_appearances || 0) - Number(a?.total_appearances || 0))
                .slice(0, 12);

            wsPlayersRows.innerHTML = topPlayers.length
                ? topPlayers.map(player => {
                    return '<tr><td>' + player.name + '</td><td>' + Number(player.total_appearances || 0) + '</td><td>' + Number(player.career_points || 0) + '</td></tr>';
                }).join('')
                : '<tr><td colspan="3" class="text-muted">No player rows for current filter.</td></tr>';
        }

        const lineoutRates = setPiece.map(r => Number(r?.lineouts_success_rate)).filter(Number.isFinite);
        const scrumRates = setPiece.map(r => Number(r?.scrums_success_rate)).filter(Number.isFinite);

        const wsSetPieceNote = document.getElementById('wsSetPieceNote');
        const wsLineoutChip = document.getElementById('wsLineoutChip');
        const wsScrumChip = document.getElementById('wsScrumChip');
        if (wsSetPieceNote) wsSetPieceNote.textContent = setPiece.length
            ? 'Set piece data from ' + setPiece.length + ' match rows.'
            : 'No set piece rows for this filter.';
        if (wsLineoutChip) wsLineoutChip.textContent = 'Lineout: ' + (lineoutRates.length ? (average(lineoutRates) * 100).toFixed(1) + '%' : '-');
        if (wsScrumChip) wsScrumChip.textContent = 'Scrum: ' + (scrumRates.length ? (average(scrumRates) * 100).toFixed(1) + '%' : '-');

        const pointsPerEntry = redZone.map(r => Number(r?.points_per_entry)).filter(Number.isFinite);
        const triesPerEntry = redZone.map(r => Number(r?.tries_per_entry)).filter(Number.isFinite);
        const wsRedZoneNote = document.getElementById('wsRedZoneNote');
        const wsPointsEntryChip = document.getElementById('wsPointsEntryChip');
        const wsTriesEntryChip = document.getElementById('wsTriesEntryChip');
        if (wsRedZoneNote) wsRedZoneNote.textContent = redZone.length
            ? 'Red zone sample contains ' + redZone.length + ' rows.'
            : 'No red zone data for this filter.';
        if (wsPointsEntryChip) wsPointsEntryChip.textContent = 'Points/Entry: ' + (pointsPerEntry.length ? average(pointsPerEntry).toFixed(2) : '-');
        if (wsTriesEntryChip) wsTriesEntryChip.textContent = 'Tries/Entry: ' + (triesPerEntry.length ? average(triesPerEntry).toFixed(2) : '-');
    }

    function setupControls() {
        document.querySelectorAll('[data-squad]').forEach(btn => {
            btn.addEventListener('click', function () {
                const nextSquad = this.getAttribute('data-squad') || 'All';
                state.squad = nextSquad;
                document.querySelectorAll('[data-squad]').forEach(el => {
                    el.classList.toggle('active', el.getAttribute('data-squad') === nextSquad);
                });
                render();
            });
        });

        const seasonSelect = document.getElementById('workspaceSeasonSelect');
        if (seasonSelect) {
            seasonSelect.addEventListener('change', function () {
                state.season = this.value;
                render();
            });
        }

        const gameTypeSelect = document.getElementById('workspaceGameTypeSelect');
        if (gameTypeSelect) {
            gameTypeSelect.addEventListener('change', function () {
                state.gameType = this.value;
                render();
            });
        }

        const minApps = document.getElementById('workspaceMinApps');
        const minAppsValue = document.getElementById('workspaceMinAppsValue');
        if (minApps) {
            minApps.addEventListener('input', function () {
                const nextValue = Number(this.value) || 0;
                state.minApps = nextValue;
                if (minAppsValue) minAppsValue.textContent = String(nextValue);
                render();
            });
        }

        const workspaceResetBtn = document.getElementById('workspaceResetBtn');
        if (workspaceResetBtn) {
            workspaceResetBtn.addEventListener('click', function () {
                state.squad = 'All';
                state.season = '2025/26';
                state.gameType = 'All games';
                state.minApps = 0;

                document.querySelectorAll('[data-squad]').forEach(el => {
                    el.classList.toggle('active', el.getAttribute('data-squad') === 'All');
                });

                if (seasonSelect) seasonSelect.value = state.season;
                if (gameTypeSelect) gameTypeSelect.value = state.gameType;
                if (minApps) minApps.value = '0';
                if (minAppsValue) minAppsValue.textContent = '0';

                render();
            });
        }
    }

    async function init() {
        setupControls();
        await loadData();
        render();
    }

    document.addEventListener('DOMContentLoaded', function () {
        init().catch(error => {
            console.error('Workspace lab initialisation failed:', error);
        });
    });
})();

(function () {
    const seasons = ['2021/22', '2022/23', '2023/24', '2024/25', '2025/26'];
    const defaultState = {
        squad: 'All',
        gameType: 'All games',
        season: '2025/26',
        minApps: 0,
        league: true,
        cup: true,
        friendly: false,
        showBench: true,
        showReplacements: true,
    };

    const state = { ...defaultState };
    const dataset = {
        games: [],
        players: [],
        redZone: [],
        setPiece: [],
    };

    const seasonCurrentBtn = document.getElementById('seasonCurrentBtn');
    const seasonPrevBtn = document.getElementById('seasonPrevBtn');
    const seasonNextBtn = document.getElementById('seasonNextBtn');
    const activeFilterRibbon = document.getElementById('activeFilterRibbon');
    const minAppsRange = document.getElementById('minAppsRange');
    const minAppsValue = document.getElementById('minAppsValue');

    function parseSeasonStart(seasonLabel) {
        const match = String(seasonLabel || '').match(/^(\d{4})\//);
        return match ? Number(match[1]) : 0;
    }

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

    function getCompetitionTypeSet() {
        const selected = new Set();
        if (state.league) selected.add('League');
        if (state.cup) selected.add('Cup');
        if (state.friendly) selected.add('Friendly');
        return selected;
    }

    function getFilteredGames() {
        const competitionTypes = getCompetitionTypeSet();

        return dataset.games.filter(row => {
            const seasonOk = String(row?.season || '') === state.season;
            const squadOk = state.squad === 'All' || String(row?.squad || '') === state.squad;

            let gameTypeOk = true;
            const gameType = String(row?.game_type || '');
            if (state.gameType === 'League only') {
                gameTypeOk = normaliseGameType(gameType) === 'League';
            } else if (state.gameType === 'League + Cup') {
                const n = normaliseGameType(gameType);
                gameTypeOk = n === 'League' || n === 'Cup';
            }

            const competitionOk = competitionTypes.has(normaliseGameType(gameType));
            const scoredOk = Number.isFinite(Number(row?.score_for)) && Number.isFinite(Number(row?.score_against));
            return seasonOk && squadOk && gameTypeOk && competitionOk && scoredOk;
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

    function getFilteredPlayers(filteredGames) {
        const playerRows = state.squad === 'All'
            ? dataset.players
            : dataset.players.filter(row => String(row?.squad || '') === state.squad);

        return playerRows.filter(row => Number(row?.total_appearances || 0) >= state.minApps);
    }

    function average(values) {
        if (!values.length) return 0;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    function updateLiveCards() {
        const filteredGames = getFilteredGames();
        const filteredPlayers = getFilteredPlayers(filteredGames);
        const filteredRedZone = getFilteredRedZone();
        const filteredSetPiece = getFilteredSetPiece();

        const wins = filteredGames.filter(row => row?.result === 'W').length;
        const draws = filteredGames.filter(row => row?.result === 'D').length;
        const losses = filteredGames.filter(row => row?.result === 'L').length;
        const winRate = filteredGames.length ? (wins / filteredGames.length) * 100 : 0;
        const avgPoints = average(filteredGames.map(row => Number(row?.score_for || 0)));

        const kpiGamesPlayed = document.getElementById('kpiGamesPlayed');
        const kpiWinRate = document.getElementById('kpiWinRate');
        const kpiPlayersUsed = document.getElementById('kpiPlayersUsed');
        const kpiAvgPoints = document.getElementById('kpiAvgPoints');

        if (kpiGamesPlayed) kpiGamesPlayed.textContent = String(filteredGames.length);
        if (kpiWinRate) kpiWinRate.textContent = filteredGames.length ? winRate.toFixed(1) + '%' : '-';
        if (kpiPlayersUsed) kpiPlayersUsed.textContent = String(filteredPlayers.length);
        if (kpiAvgPoints) kpiAvgPoints.textContent = filteredGames.length ? avgPoints.toFixed(1) : '-';

        const playersUsedNote = document.getElementById('squadPlayersUsedNote');
        const positionSpreadNote = document.getElementById('squadPositionSpreadNote');
        const overlapNote = document.getElementById('squadOverlapNote');
        if (playersUsedNote) playersUsedNote.textContent = filteredPlayers.length + ' players meet the active filter criteria.';

        const forwards = filteredPlayers.filter(row => {
            const p = String(row?.position || '').toLowerCase();
            return p.includes('prop') || p.includes('hooker') || p.includes('lock') || p.includes('second row') || p.includes('flanker') || p.includes('number 8');
        }).length;
        const backs = Math.max(0, filteredPlayers.length - forwards);
        if (positionSpreadNote) positionSpreadNote.textContent = 'Forwards: ' + forwards + ' | Backs: ' + backs + '.';

        const dualSquad = dataset.players.filter(row => Number(row?.total_appearances || 0) >= state.minApps && String(row?.squad || '') !== state.squad && state.squad !== 'All').length;
        if (overlapNote) overlapNote.textContent = state.squad === 'All'
            ? 'Split currently shown across both squads in this season context.'
            : dualSquad + ' additional players exist in the opposite squad with matching threshold.';

        const continuityReturnersNote = document.getElementById('continuityReturnersNote');
        const continuityVolatilityNote = document.getElementById('continuityVolatilityNote');
        if (continuityReturnersNote) continuityReturnersNote.textContent = 'W-D-L: ' + wins + '-' + draws + '-' + losses + ' in filtered matches.';
        if (continuityVolatilityNote) continuityVolatilityNote.textContent = 'Average points difference: ' + (filteredGames.length ? average(filteredGames.map(row => Number(row?.score_for || 0) - Number(row?.score_against || 0))).toFixed(1) : '-') + '.';

        const recentMatchesList = document.getElementById('recentMatchesList');
        if (recentMatchesList) {
            const recentMatches = filteredGames
                .slice()
                .sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')))
                .slice(0, 6);

            recentMatchesList.innerHTML = recentMatches.length
                ? recentMatches.map(row => {
                    return '<li>' + row.date + ' | ' + row.squad + ' XV vs ' + row.opposition + ' | '
                        + row.score_for + '-' + row.score_against + ' (' + row.result + ')' + '</li>';
                }).join('')
                : '<li>No matches for this filter.</li>';
        }

        const lineoutSuccessNote = document.getElementById('lineoutSuccessNote');
        const scrumSuccessNote = document.getElementById('scrumSuccessNote');

        const lineoutRates = filteredSetPiece.map(row => Number(row?.lineouts_success_rate)).filter(Number.isFinite);
        const scrumRates = filteredSetPiece.map(row => Number(row?.scrums_success_rate)).filter(Number.isFinite);
        if (lineoutSuccessNote) lineoutSuccessNote.textContent = lineoutRates.length
            ? 'Average lineout success: ' + (average(lineoutRates) * 100).toFixed(1) + '%.'
            : 'No lineout data for active filters.';
        if (scrumSuccessNote) scrumSuccessNote.textContent = scrumRates.length
            ? 'Average scrum success: ' + (average(scrumRates) * 100).toFixed(1) + '%.'
            : 'No scrum data for active filters.';

        const pointsPerEntryNote = document.getElementById('pointsPerEntryNote');
        const triesPerEntryNote = document.getElementById('triesPerEntryNote');
        const pointsPerEntryVals = filteredRedZone.map(row => Number(row?.points_per_entry)).filter(Number.isFinite);
        const triesPerEntryVals = filteredRedZone.map(row => Number(row?.tries_per_entry)).filter(Number.isFinite);
        if (pointsPerEntryNote) pointsPerEntryNote.textContent = pointsPerEntryVals.length
            ? 'Average points per 22m entry: ' + average(pointsPerEntryVals).toFixed(2) + '.'
            : 'No red zone points data for active filters.';
        if (triesPerEntryNote) triesPerEntryNote.textContent = triesPerEntryVals.length
            ? 'Average tries per 22m entry: ' + average(triesPerEntryVals).toFixed(2) + '.'
            : 'No red zone try data for active filters.';

        const topPlayersRows = document.getElementById('topPlayersRows');
        if (topPlayersRows) {
            const topPlayers = filteredPlayers
                .slice()
                .sort((a, b) => Number(b?.total_appearances || 0) - Number(a?.total_appearances || 0))
                .slice(0, 10);

            topPlayersRows.innerHTML = topPlayers.length
                ? topPlayers.map(player => {
                    return '<tr><td>' + player.name + '</td><td>'
                        + Number(player.total_appearances || 0) + '</td><td>'
                        + Number(player.career_points || 0) + '</td></tr>';
                }).join('')
                : '<tr><td colspan="3" class="text-muted">No players for this filter.</td></tr>';
        }
    }

    function renderActiveFilterRibbon() {
        if (!activeFilterRibbon) return;

        const chips = [];
        if (state.squad !== defaultState.squad) chips.push(['Squad', state.squad, 'squad']);
        if (state.gameType !== defaultState.gameType) chips.push(['Game Type', state.gameType, 'gameType']);
        if (state.season !== defaultState.season) chips.push(['Season', state.season, 'season']);
        if (state.minApps !== defaultState.minApps) chips.push(['Min Apps', String(state.minApps), 'minApps']);

        const competitions = [];
        if (state.league) competitions.push('League');
        if (state.cup) competitions.push('Cup');
        if (state.friendly) competitions.push('Friendly');
        if (competitions.length !== 2 || competitions[0] !== 'League' || competitions[1] !== 'Cup') {
            chips.push(['Competition', competitions.join(' + ') || 'None', 'competition']);
        }

        if (state.showBench !== defaultState.showBench) chips.push(['Bench', state.showBench ? 'On' : 'Off', 'showBench']);
        if (state.showReplacements !== defaultState.showReplacements) chips.push(['Replacements', state.showReplacements ? 'On' : 'Off', 'showReplacements']);

        if (chips.length === 0) {
            activeFilterRibbon.innerHTML = '<span class="text-muted small">No active overrides. Showing default analysis view.</span>';
            updateLiveCards();
            return;
        }

        activeFilterRibbon.innerHTML = chips
            .map(([label, value, key]) => {
                return '<span class="active-filter-chip">'
                    + '<strong>' + label + ':</strong> ' + value
                    + '<button type="button" class="chip-clear" data-clear-key="' + key + '" aria-label="Clear ' + label + '">\u00d7</button>'
                    + '</span>';
            })
            .join('');

        updateLiveCards();
    }

    function setSeason(newSeason) {
        if (!seasons.includes(newSeason)) return;
        state.season = newSeason;
        if (seasonCurrentBtn) seasonCurrentBtn.textContent = state.season;
        renderActiveFilterRibbon();
    }

    function cycleSeason(direction) {
        const currentIndex = seasons.indexOf(state.season);
        if (currentIndex < 0) {
            setSeason(defaultState.season);
            return;
        }
        const nextIndex = Math.max(0, Math.min(seasons.length - 1, currentIndex + direction));
        setSeason(seasons[nextIndex]);
    }

    function setSegmentValue(filterKey, value) {
        state[filterKey] = value;

        document.querySelectorAll('.btn-segment[data-filter-key="' + filterKey + '"]').forEach(btn => {
            const active = btn.getAttribute('data-filter-value') === value;
            btn.classList.toggle('active', active);
        });

        renderActiveFilterRibbon();
    }

    function resetState() {
        Object.assign(state, defaultState);
        setSegmentValue('squad', state.squad);
        setSegmentValue('gameType', state.gameType);
        setSeason(state.season);

        if (minAppsRange) minAppsRange.value = String(state.minApps);
        if (minAppsValue) minAppsValue.textContent = String(state.minApps);

        const boolMap = [
            ['compLeague', 'league'],
            ['compCup', 'cup'],
            ['compFriendly', 'friendly'],
            ['showBench', 'showBench'],
            ['showReplacements', 'showReplacements'],
        ];

        boolMap.forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (el) el.checked = !!state[key];
        });

        renderActiveFilterRibbon();
    }

    function clearKey(key) {
        if (key === 'season') {
            setSeason(defaultState.season);
            return;
        }
        if (key === 'minApps') {
            state.minApps = defaultState.minApps;
            if (minAppsRange) minAppsRange.value = String(state.minApps);
            if (minAppsValue) minAppsValue.textContent = String(state.minApps);
            renderActiveFilterRibbon();
            return;
        }
        if (key === 'competition') {
            state.league = true;
            state.cup = true;
            state.friendly = false;
            const compLeague = document.getElementById('compLeague');
            const compCup = document.getElementById('compCup');
            const compFriendly = document.getElementById('compFriendly');
            if (compLeague) compLeague.checked = true;
            if (compCup) compCup.checked = true;
            if (compFriendly) compFriendly.checked = false;
            renderActiveFilterRibbon();
            return;
        }
        if (key === 'showBench' || key === 'showReplacements') {
            state[key] = defaultState[key];
            const checkbox = document.getElementById(key);
            if (checkbox) checkbox.checked = defaultState[key];
            renderActiveFilterRibbon();
            return;
        }

        if (key === 'squad' || key === 'gameType') {
            setSegmentValue(key, defaultState[key]);
        }
    }

    function setupSegmentButtons() {
        document.querySelectorAll('.btn-segment[data-filter-key]').forEach(btn => {
            btn.addEventListener('click', function () {
                const filterKey = this.getAttribute('data-filter-key');
                const value = this.getAttribute('data-filter-value');
                if (!filterKey || value === null) return;
                setSegmentValue(filterKey, value);
            });
        });
    }

    function setupSeasonControls() {
        if (seasonPrevBtn) {
            seasonPrevBtn.addEventListener('click', function () {
                cycleSeason(-1);
            });
        }
        if (seasonNextBtn) {
            seasonNextBtn.addEventListener('click', function () {
                cycleSeason(1);
            });
        }
    }

    function setupAdvancedFilters() {
        if (minAppsRange) {
            minAppsRange.addEventListener('input', function () {
                const nextValue = Number(this.value) || 0;
                state.minApps = nextValue;
                if (minAppsValue) minAppsValue.textContent = String(nextValue);
            });
        }

        const boolMap = [
            ['compLeague', 'league'],
            ['compCup', 'cup'],
            ['compFriendly', 'friendly'],
            ['showBench', 'showBench'],
            ['showReplacements', 'showReplacements'],
        ];

        boolMap.forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', function () {
                state[key] = this.checked;
            });
        });

        const applyAdvancedFilters = document.getElementById('applyAdvancedFilters');
        if (applyAdvancedFilters) {
            applyAdvancedFilters.addEventListener('click', function () {
                renderActiveFilterRibbon();
            });
        }
    }

    function setupRailNavigation() {
        document.querySelectorAll('.rail-link').forEach(button => {
            button.addEventListener('click', function () {
                const targetId = this.getAttribute('data-target');
                const target = targetId ? document.getElementById(targetId) : null;
                if (!target) return;

                document.querySelectorAll('.rail-link').forEach(link => link.classList.remove('active'));
                this.classList.add('active');

                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    function setupFocusCards() {
        const modalEl = document.getElementById('cardFocusModal');
        const focusTitle = document.getElementById('cardFocusModalLabel');
        const focusCopy = document.getElementById('focusModalCopy');
        const focusModal = modalEl ? new bootstrap.Modal(modalEl) : null;

        document.querySelectorAll('.focus-card-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const card = this.closest('.insight-card');
                if (!card || !focusModal || !focusTitle || !focusCopy) return;
                const title = card.getAttribute('data-card-title') || 'Focused Insight';
                focusTitle.textContent = title;
                focusCopy.textContent = 'Focused view for ' + title + '. Use this mode on mobile when compact cards feel too dense.';
                focusModal.show();
            });
        });

        const expandAllCardsBtn = document.getElementById('expandAllCardsBtn');
        if (expandAllCardsBtn) {
            expandAllCardsBtn.addEventListener('click', function () {
                const firstCard = document.querySelector('.insight-card');
                if (!firstCard || !focusModal || !focusTitle || !focusCopy) return;
                const title = firstCard.getAttribute('data-card-title') || 'Focused Insight';
                focusTitle.textContent = title;
                focusCopy.textContent = 'In a real implementation, this action could open a carousel of expanded cards in sequence.';
                focusModal.show();
            });
        }
    }

    function setupRibbonActions() {
        if (!activeFilterRibbon) return;
        activeFilterRibbon.addEventListener('click', function (event) {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            if (!target.matches('[data-clear-key]')) return;
            const key = target.getAttribute('data-clear-key');
            if (!key) return;
            clearKey(key);
        });
    }

    function setupResetButton() {
        const resetBtn = document.getElementById('resetLabFiltersBtn');
        if (!resetBtn) return;
        resetBtn.addEventListener('click', function () {
            resetState();
        });
    }

    async function init() {
        setupSegmentButtons();
        setupSeasonControls();
        setupAdvancedFilters();
        setupRailNavigation();
        setupFocusCards();
        setupRibbonActions();
        setupResetButton();

        seasons.sort((a, b) => parseSeasonStart(a) - parseSeasonStart(b));
        await loadData();
        resetState();
    }

    document.addEventListener('DOMContentLoaded', function () {
        init().catch(error => {
            console.error('UX lab initialisation failed:', error);
        });
    });
})();

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
    const VEGA_EMBED_ACTIONS = false;
    const chartSpecCache = {};

    const seasonCurrentBtn = document.getElementById('seasonCurrentBtn');
    const seasonPrevBtn = document.getElementById('seasonPrevBtn');
    const seasonNextBtn = document.getElementById('seasonNextBtn');
    const activeFilterRibbon = document.getElementById('activeFilterRibbon');

    const minAppsRange = document.getElementById('minAppsRange');
    const minAppsValue = document.getElementById('minAppsValue');
    const compLeague = document.getElementById('compLeague');
    const compCup = document.getElementById('compCup');
    const compFriendly = document.getElementById('compFriendly');
    const showBench = document.getElementById('showBench');
    const showReplacements = document.getElementById('showReplacements');

    const mobileSquadSelect = document.getElementById('mobileSquadSelect');
    const mobileGameTypeSelect = document.getElementById('mobileGameTypeSelect');
    const mobileSeasonSelect = document.getElementById('mobileSeasonSelect');
    const mobileMinAppsRange = document.getElementById('mobileMinAppsRange');
    const mobileMinAppsValue = document.getElementById('mobileMinAppsValue');
    const mobileCompLeague = document.getElementById('mobileCompLeague');
    const mobileCompCup = document.getElementById('mobileCompCup');
    const mobileCompFriendly = document.getElementById('mobileCompFriendly');
    const mobileShowBench = document.getElementById('mobileShowBench');
    const mobileShowReplacements = document.getElementById('mobileShowReplacements');

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

    function getCompetitionLabel() {
        const labels = [];
        if (state.league) labels.push('League');
        if (state.cup) labels.push('Cup');
        if (state.friendly) labels.push('Friendly');
        return labels.join(' + ') || 'None';
    }

    function getScopedStateValue(key) {
        const map = {
            squad: state.squad,
            season: state.season,
            gameType: state.gameType,
            minApps: String(state.minApps),
            competition: getCompetitionLabel(),
            showBench: state.showBench ? 'Bench On' : 'Bench Off',
            showReplacements: state.showReplacements ? 'Repl On' : 'Repl Off',
        };
        return map[key] || '-';
    }

    function getScopedLabel(key) {
        const map = {
            squad: 'Squad',
            season: 'Season',
            gameType: 'Game',
            minApps: 'Min Apps',
            competition: 'Comp',
            showBench: 'Bench',
            showReplacements: 'Repl',
        };
        return map[key] || key;
    }

    function renderScopedChips() {
        const containers = document.querySelectorAll('[data-filter-scope]');
        containers.forEach(container => {
            const scope = String(container.getAttribute('data-filter-scope') || '')
                .split(',')
                .map(item => item.trim())
                .filter(Boolean);

            if (!scope.length) {
                container.innerHTML = '';
                return;
            }

            container.innerHTML = scope.map(key => {
                return '<span class="scoped-filter-chip"><strong>' + getScopedLabel(key) + ':</strong> ' + getScopedStateValue(key) + '</span>';
            }).join('');
        });
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

    function getFilteredPlayers() {
        const playerRows = state.squad === 'All'
            ? dataset.players
            : dataset.players.filter(row => String(row?.squad || '') === state.squad);

        return playerRows.filter(row => Number(row?.total_appearances || 0) >= state.minApps);
    }

    function average(values) {
        if (!values.length) return 0;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    function renderNoDataChart(containerId, message) {
        const host = document.getElementById(containerId);
        if (!host) return;
        host.innerHTML = '<div class="small text-muted p-2">' + message + '</div>';
    }

    function cloneSpec(spec) {
        return JSON.parse(JSON.stringify(spec));
    }

    async function fetchChartSpec(path) {
        if (chartSpecCache[path]) return chartSpecCache[path];
        const response = await fetch(path);
        if (!response.ok) throw new Error('Failed to load chart spec: ' + path);
        const spec = await response.json();
        chartSpecCache[path] = spec;
        return spec;
    }

    async function embedChartFromFile(containerId, path) {
        const host = document.getElementById(containerId);
        if (!host || typeof vegaEmbed !== 'function') return;

        try {
            const sourceSpec = await fetchChartSpec(path);
            const authoredSpec = cloneSpec(sourceSpec);
            await vegaEmbed('#' + containerId, authoredSpec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' });
        } catch (error) {
            console.error('Failed to render chart', containerId, error);
            renderNoDataChart(containerId, 'Chart unavailable for current filters.');
        }
    }

    function renderPrototypeCharts() {
        const chartMap = [
            ['chartPlayersUsed', 'data/charts/squad_size_trend.json'],
            ['chartPositionSpread', 'data/charts/league_squad_size_context_1s.json'],
            ['chartOverlapDistribution', 'data/charts/squad_overlap.json'],
            ['chartAverageReturners', 'data/charts/squad_continuity_average.json'],
            ['chartSelectionVolatility', 'data/charts/league_continuity_context_1s.json'],
            ['chartLineoutSuccess', 'data/charts/set_piece_success_lineout.json'],
            ['chartScrumSuccess', 'data/charts/set_piece_success_scrum.json'],
            ['chartPointsPerEntry', 'data/charts/red_zone_points.json'],
            ['chartTryConversion', 'data/charts/red_zone_points.json'],
            ['chartPlayerAppearances', 'data/charts/player_stats_appearances.json'],
        ];

        chartMap.forEach(([containerId, path]) => {
            embedChartFromFile(containerId, path);
        });

    }

    function updateLiveCards() {
        const filteredGames = getFilteredGames();
        const filteredPlayers = getFilteredPlayers();
        const filteredRedZone = getFilteredRedZone();
        const filteredSetPiece = getFilteredSetPiece();
        const filteredSetPieceTeam = filteredSetPiece.filter(row => String(row?.team || '') === 'EGRFC');

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
        if (continuityReturnersNote) continuityReturnersNote.textContent = 'Average returners context: W-D-L is ' + wins + '-' + draws + '-' + losses + ' in filtered matches.';
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
        const lineoutRates = filteredSetPieceTeam.map(row => Number(row?.lineouts_success_rate)).filter(Number.isFinite);
        const scrumRates = filteredSetPieceTeam.map(row => Number(row?.scrums_success_rate)).filter(Number.isFinite);
        if (lineoutSuccessNote) lineoutSuccessNote.textContent = lineoutRates.length
            ? 'Average lineout success: ' + (average(lineoutRates) * 100).toFixed(1) + '%. '
            : 'No lineout data for active filters.';
        if (scrumSuccessNote) scrumSuccessNote.textContent = scrumRates.length
            ? 'Average scrum success: ' + (average(scrumRates) * 100).toFixed(1) + '%. '
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
                    return '<tr><td data-label="Player">' + player.name + '</td><td data-label="Apps">'
                        + Number(player.total_appearances || 0) + '</td><td data-label="Points">'
                        + Number(player.career_points || 0) + '</td></tr>';
                }).join('')
                : '<tr><td colspan="3" class="text-muted">No players for this filter.</td></tr>';
        }

        renderPrototypeCharts();
    }

    function renderActiveFilterRibbon() {
        if (!activeFilterRibbon) return;

        const chips = [];
        if (state.squad !== defaultState.squad) chips.push(['Squad', state.squad, 'squad']);
        if (state.gameType !== defaultState.gameType) chips.push(['Game Type', state.gameType, 'gameType']);
        if (state.season !== defaultState.season) chips.push(['Season', state.season, 'season']);
        if (state.minApps !== defaultState.minApps) chips.push(['Min Apps', String(state.minApps), 'minApps']);

        const competitions = getCompetitionLabel();
        if (competitions !== 'League + Cup') {
            chips.push(['Competition', competitions, 'competition']);
        }

        if (state.showBench !== defaultState.showBench) chips.push(['Bench', state.showBench ? 'On' : 'Off', 'showBench']);
        if (state.showReplacements !== defaultState.showReplacements) chips.push(['Replacements', state.showReplacements ? 'On' : 'Off', 'showReplacements']);

        if (chips.length === 0) {
            activeFilterRibbon.innerHTML = '<span class="text-muted small">No active overrides. Showing default analysis view.</span>';
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
    }

    function setSeason(newSeason) {
        if (!seasons.includes(newSeason)) return;
        state.season = newSeason;
        if (seasonCurrentBtn) seasonCurrentBtn.textContent = state.season;
    }

    function cycleSeason(direction) {
        const currentIndex = seasons.indexOf(state.season);
        if (currentIndex < 0) {
            setSeason(defaultState.season);
            return;
        }
        const nextIndex = Math.max(0, Math.min(seasons.length - 1, currentIndex + direction));
        setSeason(seasons[nextIndex]);
        renderAll();
    }

    function setSegmentValue(filterKey, value) {
        state[filterKey] = value;

        document.querySelectorAll('.btn-segment[data-filter-key="' + filterKey + '"]').forEach(btn => {
            const active = btn.getAttribute('data-filter-value') === value;
            btn.classList.toggle('active', active);
        });
    }

    function syncDesktopAdvancedControls() {
        if (minAppsRange) minAppsRange.value = String(state.minApps);
        if (minAppsValue) minAppsValue.textContent = String(state.minApps);
        if (compLeague) compLeague.checked = !!state.league;
        if (compCup) compCup.checked = !!state.cup;
        if (compFriendly) compFriendly.checked = !!state.friendly;
        if (showBench) showBench.checked = !!state.showBench;
        if (showReplacements) showReplacements.checked = !!state.showReplacements;
    }

    function syncMobileControls() {
        if (mobileSquadSelect) mobileSquadSelect.value = state.squad;
        if (mobileGameTypeSelect) mobileGameTypeSelect.value = state.gameType;
        if (mobileSeasonSelect) mobileSeasonSelect.value = state.season;
        if (mobileMinAppsRange) mobileMinAppsRange.value = String(state.minApps);
        if (mobileMinAppsValue) mobileMinAppsValue.textContent = String(state.minApps);
        if (mobileCompLeague) mobileCompLeague.checked = !!state.league;
        if (mobileCompCup) mobileCompCup.checked = !!state.cup;
        if (mobileCompFriendly) mobileCompFriendly.checked = !!state.friendly;
        if (mobileShowBench) mobileShowBench.checked = !!state.showBench;
        if (mobileShowReplacements) mobileShowReplacements.checked = !!state.showReplacements;
    }

    function syncPrimaryDesktopControls() {
        setSegmentValue('squad', state.squad);
        setSegmentValue('gameType', state.gameType);
        if (seasonCurrentBtn) seasonCurrentBtn.textContent = state.season;
    }

    function renderAll() {
        syncPrimaryDesktopControls();
        syncDesktopAdvancedControls();
        syncMobileControls();
        renderActiveFilterRibbon();
        renderScopedChips();
        updateLiveCards();
    }

    function resetState() {
        Object.assign(state, defaultState);
        renderAll();
    }

    function clearKey(key) {
        if (key === 'season') {
            setSeason(defaultState.season);
        } else if (key === 'minApps') {
            state.minApps = defaultState.minApps;
        } else if (key === 'competition') {
            state.league = true;
            state.cup = true;
            state.friendly = false;
        } else if (key === 'showBench' || key === 'showReplacements') {
            state[key] = defaultState[key];
        } else if (key === 'squad' || key === 'gameType') {
            state[key] = defaultState[key];
        }

        renderAll();
    }

    function setupSegmentButtons() {
        document.querySelectorAll('.btn-segment[data-filter-key]').forEach(btn => {
            btn.addEventListener('click', function () {
                const filterKey = this.getAttribute('data-filter-key');
                const value = this.getAttribute('data-filter-value');
                if (!filterKey || value === null) return;
                setSegmentValue(filterKey, value);
                renderAll();
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

    function setupDesktopAdvancedFilters() {
        if (minAppsRange) {
            minAppsRange.addEventListener('input', function () {
                state.minApps = Number(this.value) || 0;
                if (minAppsValue) minAppsValue.textContent = String(state.minApps);
            });
        }

        const desktopBoolMap = [
            [compLeague, 'league'],
            [compCup, 'cup'],
            [compFriendly, 'friendly'],
            [showBench, 'showBench'],
            [showReplacements, 'showReplacements'],
        ];

        desktopBoolMap.forEach(([el, key]) => {
            if (!el) return;
            el.addEventListener('change', function () {
                state[key] = this.checked;
            });
        });

        const applyAdvancedFilters = document.getElementById('applyAdvancedFilters');
        if (applyAdvancedFilters) {
            applyAdvancedFilters.addEventListener('click', function () {
                renderAll();
            });
        }
    }

    function setupMobileFilters() {
        if (mobileMinAppsRange) {
            mobileMinAppsRange.addEventListener('input', function () {
                const next = Number(this.value) || 0;
                if (mobileMinAppsValue) mobileMinAppsValue.textContent = String(next);
            });
        }

        const applyMobileFilters = document.getElementById('applyMobileFilters');
        if (applyMobileFilters) {
            applyMobileFilters.addEventListener('click', function () {
                if (mobileSquadSelect) state.squad = mobileSquadSelect.value;
                if (mobileGameTypeSelect) state.gameType = mobileGameTypeSelect.value;
                if (mobileSeasonSelect) state.season = mobileSeasonSelect.value;
                if (mobileMinAppsRange) state.minApps = Number(mobileMinAppsRange.value) || 0;
                if (mobileCompLeague) state.league = mobileCompLeague.checked;
                if (mobileCompCup) state.cup = mobileCompCup.checked;
                if (mobileCompFriendly) state.friendly = mobileCompFriendly.checked;
                if (mobileShowBench) state.showBench = mobileShowBench.checked;
                if (mobileShowReplacements) state.showReplacements = mobileShowReplacements.checked;
                renderAll();
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
                const title = card.getAttribute('data-card-title') || 'Inspect Mode (Beta)';
                focusTitle.textContent = 'Inspect: ' + title;
                focusCopy.textContent = 'This beta view is retained for testing. Keep or remove based on real mobile use cases.';
                focusModal.show();
            });
        });

        const expandAllCardsBtn = document.getElementById('expandAllCardsBtn');
        if (expandAllCardsBtn) {
            expandAllCardsBtn.addEventListener('click', function () {
                const firstCard = document.querySelector('.insight-card');
                if (!firstCard || !focusModal || !focusTitle || !focusCopy) return;
                const title = firstCard.getAttribute('data-card-title') || 'Inspect Mode (Beta)';
                focusTitle.textContent = 'Inspect: ' + title;
                focusCopy.textContent = 'Inspect mode can become a carousel or zoomed card if testing proves clear value.';
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
        setupDesktopAdvancedFilters();
        setupMobileFilters();
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

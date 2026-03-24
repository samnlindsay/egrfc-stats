/**
 * Season Summary Module
 * Handles loading and displaying season summary statistics
 */

const SeasonSummary = (() => {
    let summaryData = null;
    let currentSeason = null;
    let currentGameType = 'All games';

    const init = () => {
        console.log('🔧 Initializing Season Summary module...');
        loadSeasonSummaryData();
    };

    const loadSeasonSummaryData = () => {
        fetch('data/season_summary.json')
            .then(res => res.json())
            .then(data => {
                summaryData = data;
                console.log('📊 Season summary data loaded:', data);
                initializeFilters();
                renderSeasonSummary();
            })
            .catch(error => console.error('❌ Failed to load season summary data:', error));
    };

    const initializeFilters = () => {
        if (!summaryData || !summaryData.games_results) return;

        // Get unique seasons
        const seasons = [...new Set(summaryData.games_results.map(r => r.season))].sort().reverse();
        
        // Populate season selector
        const seasonSelect = document.getElementById('seasonSummarySeasonSelect');
        if (seasonSelect) {
            seasonSelect.innerHTML = '';
            seasons.forEach(season => {
                const option = document.createElement('option');
                option.value = season;
                option.textContent = season.replace('/', '-');
                seasonSelect.appendChild(option);
            });
            // Rebuild selectpicker after replacing options to avoid duplicate render state
            if ($.fn.selectpicker) {
                const $seasonSelect = $(seasonSelect);
                const selectedSeason = seasons[0];
                $seasonSelect.selectpicker('destroy');
                $seasonSelect.selectpicker();
                $seasonSelect.selectpicker('val', selectedSeason);
            }
            currentSeason = seasons[0];
        }

        // Bind filter change events
        const gameTypeSelect = document.getElementById('seasonSummaryGameTypeSelect');
        if (seasonSelect) {
            seasonSelect.addEventListener('change', (e) => {
                currentSeason = e.target.value;
                renderSeasonSummary();
            });
        }
        if (gameTypeSelect) {
            gameTypeSelect.addEventListener('change', (e) => {
                currentGameType = e.target.value;
                renderSeasonSummary();
            });
        }
    };

    const renderSeasonSummary = () => {
        if (!summaryData || !currentSeason) return;

        updateResultsTitles();

        // Filter data for current selection
        const resultsForSeason = summaryData.games_results.filter(r => r.season === currentSeason);
        const scorersForSeason = summaryData.top_point_scorers.filter(s => s.season === currentSeason);
        const tryScorersSeason = summaryData.top_try_scorers.filter(s => s.season === currentSeason);
        const appearancesForSeason = summaryData.most_appearances.filter(a => a.season === currentSeason);
        const setpieceForSeason = summaryData.set_piece_stats.filter(s => s.season === currentSeason);

        // Render for each squad
        renderSquadSummary('1st', resultsForSeason, scorersForSeason, tryScorersSeason, appearancesForSeason, setpieceForSeason);
        renderSquadSummary('2nd', resultsForSeason, scorersForSeason, tryScorersSeason, appearancesForSeason, setpieceForSeason);
    };

    const updateResultsTitles = () => {
        const titleText = `${currentSeason} Results`;
        const title1st = document.getElementById('seasonSummaryResultsTitle1st');
        const title2nd = document.getElementById('seasonSummaryResultsTitle2nd');

        if (title1st) {
            title1st.textContent = titleText;
        }
        if (title2nd) {
            title2nd.textContent = titleText;
        }
    };

    const getAllowedGameTypes = () => {
        if (currentGameType === 'League + Cup') {
            return new Set(['League', 'Cup']);
        }
        if (currentGameType === 'League only') {
            return new Set(['League']);
        }
        return null;
    };

    const renderSquadSummary = (squad, results, scorers, tryscorers, appearances, setpiece) => {
        // Get results for this squad and game type
        const resultData = getResultData(results, squad);
        
        if (!resultData) {
            // No data for this squad, show dashes
            displaySquadData(squad, null, null, null, null, null);
            return;
        }

        // Get top scorers for this squad
        const topPointScorer = getTopScorer(scorers, squad);
        const topTryScorer = getTopScorer(tryscorers, squad, 'tries');
        const mostAppearances = getTopAppearances(appearances, squad);
        const setpieceData = setpiece.find(s => s.squad === squad);

        displaySquadData(squad, resultData, topPointScorer, topTryScorer, mostAppearances, setpieceData);
    };

    const getResultData = (results, squad) => {
        const squadResults = results.filter(r => r.squad === squad);
        const allowedGameTypes = getAllowedGameTypes();
        const filteredResults = allowedGameTypes
            ? squadResults.filter(r => allowedGameTypes.has(r.game_type))
            : squadResults;

        if (filteredResults.length === 0) return null;

        return {
            games_played: filteredResults.reduce((sum, r) => sum + r.games_played, 0),
            games_won: filteredResults.reduce((sum, r) => sum + (r.games_won || 0), 0),
            games_lost: filteredResults.reduce((sum, r) => sum + (r.games_lost || 0), 0),
            games_drawn: filteredResults.reduce((sum, r) => sum + (r.games_drawn || 0), 0),
            avg_pf_home: calculateWeightedAvg(filteredResults, 'avg_pf_home', 'home_games'),
            avg_pa_home: calculateWeightedAvg(filteredResults, 'avg_pa_home', 'home_games'),
            avg_pf_away: calculateWeightedAvg(filteredResults, 'avg_pf_away', 'away_games'),
            avg_pa_away: calculateWeightedAvg(filteredResults, 'avg_pa_away', 'away_games'),
            avg_pf_overall: calculateWeightedAvg(filteredResults, 'avg_pf_overall', 'games_played'),
            avg_pa_overall: calculateWeightedAvg(filteredResults, 'avg_pa_overall', 'games_played')
        };
    };

    const calculateWeightedAvg = (results, metric, weight) => {
        if (results.length === 0) return null;
        
        let totalWeighted = 0;
        let totalWeight = 0;
        
        results.forEach(r => {
            if (r[metric] !== null && r[metric] !== undefined && r[weight] !== null && r[weight] !== undefined) {
                totalWeighted += r[metric] * r[weight];
                totalWeight += r[weight];
            }
        });
        
        if (totalWeight === 0) return null;
        return Math.round((totalWeighted / totalWeight) * 100) / 100;
    };

    const getTopScorer = (scorers, squad, field = 'points') => {
        const scorersForSquad = scorers.filter(s => s.squad === squad);
        if (scorersForSquad.length === 0) return null;

        const maxValue = scorersForSquad.reduce((maxSoFar, scorer) => {
            const value = Number(scorer[field]);
            return Number.isFinite(value) && value > maxSoFar ? value : maxSoFar;
        }, -Infinity);

        if (!Number.isFinite(maxValue)) return null;

        const tiedPlayers = [...new Set(
            scorersForSquad
                .filter(scorer => Number(scorer[field]) === maxValue)
                .map(scorer => scorer.player)
                .filter(Boolean)
        )].sort((a, b) => a.localeCompare(b));

        return {
            value: maxValue,
            players: tiedPlayers,
        };
    };

    const getTopAppearances = (appearances, squad) => {
        const allowedGameTypes = getAllowedGameTypes();
        const appsForSquad = appearances.filter(a => {
            if (a.squad !== squad) {
                return false;
            }
            if (!allowedGameTypes) {
                return true;
            }
            return allowedGameTypes.has(a.game_type);
        });

        if (appsForSquad.length === 0) return null;

        const appearanceTotalsByPlayer = appsForSquad.reduce((acc, row) => {
            const player = row.player;
            const value = Number(row.appearances) || 0;
            if (!player) {
                return acc;
            }
            acc[player] = (acc[player] || 0) + value;
            return acc;
        }, {});

        const playerEntries = Object.entries(appearanceTotalsByPlayer);
        if (playerEntries.length === 0) return null;

        const maxAppearances = Math.max(...playerEntries.map(([, total]) => total));
        const tiedPlayers = playerEntries
            .filter(([, total]) => total === maxAppearances)
            .map(([player]) => player)
            .sort((a, b) => a.localeCompare(b));

        return {
            appearances: maxAppearances,
            players: tiedPlayers,
        };
    };

    const displaySquadData = (squad, resultData, topPointScorer, topTryScorer, mostAppearances, setpieceData) => {
        const squadKey = squad === '1st' ? '1st' : '2nd';
        const prefix = `season-summary-${squadKey.toLowerCase()}`;

        // Games results
        const wonElement = document.getElementById(`${prefix}-won`);
        const lostElement = document.getElementById(`${prefix}-lost`);
        const drawnElement = document.getElementById(`${prefix}-drawn`);
        const playedElement = document.getElementById(`${prefix}-played`);

        if (resultData && resultData.games_played) {
            const w = Math.round(resultData.games_won || 0);
            const d = Math.round(resultData.games_drawn || 0);
            const l = Math.round(resultData.games_lost || 0);
            const p = Math.round(resultData.games_played || 0);
            if (wonElement) wonElement.textContent = w;
            if (lostElement) lostElement.textContent = l;
            if (drawnElement) drawnElement.textContent = d;
            if (playedElement) playedElement.textContent = p;
        } else {
            if (wonElement) wonElement.textContent = '-';
            if (lostElement) lostElement.textContent = '-';
            if (drawnElement) drawnElement.textContent = '-';
            if (playedElement) playedElement.textContent = '-';
        }

        // Top scorers and appearances
        displayTopScorer(`${prefix}-top-point-value`, `${prefix}-top-point-player`, topPointScorer, 'points');
        displayTopScorer(`${prefix}-top-try-value`, `${prefix}-top-try-player`, topTryScorer, 'tries');
        displayTopAppearances(`${prefix}-most-appearances-value`, `${prefix}-most-appearances-player`, mostAppearances);

        // Set piece stats
        displayValue(`${prefix}-lineout-sr`, setpieceData?.avg_lineout_success_rate, 'percentage');
        displayValue(`${prefix}-scrum-sr`, setpieceData?.avg_scrum_success_rate, 'percentage');
        displayValue(`${prefix}-points-22m`, setpieceData?.avg_points_per_22m_entry, 'decimal');
        displayValue(`${prefix}-tries-22m`, setpieceData?.avg_tries_per_22m_entry, 'decimal');
    };

    const displayValue = (elementId, value, format = 'number') => {
        const element = document.getElementById(elementId);
        if (!element) return;

        if (value === null || value === undefined || isNaN(value)) {
            element.textContent = '-';
            return;
        }

        let formatted;
        switch (format) {
            case 'percentage':
                formatted = Math.round(value * 10000) / 100 + '%';
                break;
            case 'decimal':
                formatted = Math.round(value * 100) / 100;
                break;
            default:
                formatted = Math.round(value * 100) / 100;
        }
        element.textContent = formatted;
    };

    const displayTopScorer = (valueElementId, playerElementId, scorer, metric = 'points') => {
        const valueElement = document.getElementById(valueElementId);
        const playerElement = document.getElementById(playerElementId);
        if (!valueElement || !playerElement) return;

        if (!scorer) {
            valueElement.textContent = '-';
            playerElement.textContent = '-';
            return;
        }

        valueElement.textContent = scorer.value !== null && scorer.value !== undefined
            ? Math.round(scorer.value)
            : '-';
        playerElement.textContent = scorer.players && scorer.players.length > 0
            ? scorer.players.join(' / ')
            : '-';
    };

    const displayTopAppearances = (valueElementId, playerElementId, appearance) => {
        const valueElement = document.getElementById(valueElementId);
        const playerElement = document.getElementById(playerElementId);
        if (!valueElement || !playerElement) return;

        if (!appearance) {
            valueElement.textContent = '-';
            playerElement.textContent = '-';
            return;
        }

        valueElement.textContent = appearance.appearances !== null && appearance.appearances !== undefined
            ? Math.round(appearance.appearances)
            : '-';
        playerElement.textContent = appearance.players && appearance.players.length > 0
            ? appearance.players.join(' / ')
            : '-';
    };

    return {
        init
    };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    SeasonSummary.init();
});

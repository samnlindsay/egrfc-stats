/**
 * Season Summary Module
 * Handles loading and displaying season summary statistics
 */

const SeasonSummary = (() => {
    let summaryData = null;
    let currentSeason = null;
    let currentGameType = 'All games';

    const init = () => {
        loadSeasonSummaryData();
    };

    const loadSeasonSummaryData = () => {
        fetch('data/backend/season_summary_enriched.json')
            .then(res => res.json())
            .then(data => {
                summaryData = Array.isArray(data) ? data : [];
                initializeFilters();
                renderSeasonSummary();
            })
            .catch(error => console.error('Failed to load season summary data:', error));
    };

    const initializeFilters = () => {
        if (!Array.isArray(summaryData) || summaryData.length === 0) return;

        const seasons = [...new Set(summaryData.map(row => row?.season).filter(Boolean))].sort().reverse();
        const seasonSelect = document.getElementById('seasonSummarySeasonSelect');
        if (seasonSelect) {
            seasonSelect.innerHTML = '';
            seasons.forEach(season => {
                const option = document.createElement('option');
                option.value = season;
                option.textContent = season.replace('/', '-');
                seasonSelect.appendChild(option);
            });
            if ($.fn.selectpicker) {
                const $seasonSelect = $(seasonSelect);
                const selectedSeason = seasons[0];
                $seasonSelect.selectpicker('destroy');
                $seasonSelect.selectpicker();
                $seasonSelect.selectpicker('val', selectedSeason);
            }
            currentSeason = seasons[0];
        }

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

    const parsePlayers = (value) => {
        if (Array.isArray(value)) return value.filter(Boolean);
        if (typeof value === 'string' && value.trim()) {
            try {
                const parsed = JSON.parse(value);
                return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
            } catch (error) {
                console.warn('Unable to parse season summary players payload:', error);
            }
        }
        return [];
    };

    const renderSeasonSummary = () => {
        if (!Array.isArray(summaryData) || !currentSeason) return;
        updateResultsTitles();
        renderSquadSummary('1st');
        renderSquadSummary('2nd');
    };

    const updateResultsTitles = () => {
        const titleText = `${currentSeason} Results`;
        const title1st = document.getElementById('seasonSummaryResultsTitle1st');
        const title2nd = document.getElementById('seasonSummaryResultsTitle2nd');
        if (title1st) title1st.textContent = titleText;
        if (title2nd) title2nd.textContent = titleText;
    };

    const renderSquadSummary = (squad) => {
        const row = (summaryData || []).find(entry => entry?.season === currentSeason && entry?.gameTypeMode === currentGameType && entry?.squad === squad);
        displaySquadData(squad, row || null);
    };

    const displaySquadData = (squad, row) => {
        const squadKey = squad === '1st' ? '1st' : '2nd';
        const prefix = `season-summary-${squadKey.toLowerCase()}`;

        const wonElement = document.getElementById(`${prefix}-won`);
        const lostElement = document.getElementById(`${prefix}-lost`);
        const drawnElement = document.getElementById(`${prefix}-drawn`);
        const playedElement = document.getElementById(`${prefix}-played`);

        if (row && row.gamesPlayed) {
            if (wonElement) wonElement.textContent = Math.round(row.gamesWon || 0);
            if (lostElement) lostElement.textContent = Math.round(row.gamesLost || 0);
            if (drawnElement) drawnElement.textContent = Math.round(row.gamesDrawn || 0);
            if (playedElement) playedElement.textContent = Math.round(row.gamesPlayed || 0);
        } else {
            if (wonElement) wonElement.textContent = '-';
            if (lostElement) lostElement.textContent = '-';
            if (drawnElement) drawnElement.textContent = '-';
            if (playedElement) playedElement.textContent = '-';
        }

        displayTopMetric(`${prefix}-top-point-value`, `${prefix}-top-point-player`, row?.topPointScorerValue, parsePlayers(row?.topPointScorerPlayers));
        displayTopMetric(`${prefix}-top-try-value`, `${prefix}-top-try-player`, row?.topTryScorerValue, parsePlayers(row?.topTryScorerPlayers));
        displayTopMetric(`${prefix}-most-appearances-value`, `${prefix}-most-appearances-player`, row?.topAppearanceValue, parsePlayers(row?.topAppearancePlayers));

        displayValue(`${prefix}-lineout-sr`, row?.avgLineoutSuccessRate, 'percentage');
        displayValue(`${prefix}-scrum-sr`, row?.avgScrumSuccessRate, 'percentage');
        displayValue(`${prefix}-points-22m`, row?.avgPointsPer22mEntry, 'decimal');
        displayValue(`${prefix}-tries-22m`, row?.avgTriesPer22mEntry, 'decimal');
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

    const displayTopMetric = (valueElementId, playerElementId, value, players) => {
        const valueElement = document.getElementById(valueElementId);
        const playerElement = document.getElementById(playerElementId);
        if (!valueElement || !playerElement) return;

        if (value === null || value === undefined || Number.isNaN(Number(value))) {
            valueElement.textContent = '-';
            playerElement.textContent = '-';
            return;
        }

        valueElement.textContent = Math.round(Number(value));
        playerElement.textContent = Array.isArray(players) && players.length > 0 ? players.join(' / ') : '-';
    };

    return {
        init
    };
})();

document.addEventListener('DOMContentLoaded', () => {
    SeasonSummary.init();
});

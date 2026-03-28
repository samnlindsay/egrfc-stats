// League Tables page logic

let leagueTablesData = null;
let leagueResultsIndexData = null;

async function loadLeagueResultsIndex() {
    if (leagueResultsIndexData) {
        return leagueResultsIndexData;
    }

    try {
        const response = await fetch('data/charts/league_results_index.json');
        if (!response.ok) {
            console.warn(`Unable to load league results index (${response.status}).`);
            leagueResultsIndexData = {};
            return leagueResultsIndexData;
        }
        leagueResultsIndexData = await response.json();
    } catch (err) {
        console.error('Error loading league results index:', err);
        leagueResultsIndexData = {};
    }

    return leagueResultsIndexData;
}

function createLeagueResultsSpecPanel(panelId, chartContainerId, title, colorModifier, season, squad) {
    return `
        <div class="chart-panel chart-panel--inline">
            <button type="button" class="chart-panel-toggle ${colorModifier}"
                data-target="${panelId}" data-accordion-group="league-results-panels" aria-expanded="false" aria-controls="${panelId}">
                <span class="chart-panel-toggle-text">
                    <span class="chart-panel-toggle-title">${title}</span>
                    <span class="chart-panel-toggle-hint">League match results</span>
                </span>
                <span class="chart-panel-toggle-icon" aria-hidden="true"></span>
            </button>
            <div id="${panelId}" class="chart-panel-content" hidden>
                <div class="chart-panel-card" data-league-season="${season}" data-league-squad="${squad}" data-chart-container-id="${chartContainerId}">
                    <div id="${chartContainerId}"></div>
                </div>
            </div>
        </div>
    `;
}

function getLeagueResultsSpecPath(season, squad) {
    const normalizedSeason = toLeagueSeasonFormat(season);
    const seasonEntry = leagueResultsIndexData?.[normalizedSeason];
    const squadEntry = seasonEntry?.[String(squad)];
    if (squadEntry?.file) {
        return `data/charts/${squadEntry.file}`;
    }

    return `data/charts/league_results_${squad}s_${normalizedSeason}.json`;
}

async function renderLeagueResultsChartsForSeason(season) {
    const tasks = [1, 2].map(async squad => {
        const containerId = `leagueResultsChart${squad}`;
        const chartHost = document.getElementById(containerId);
        if (!chartHost) {
            return;
        }

        const specPath = getLeagueResultsSpecPath(season, squad);
        try {
            const spec = await loadChartSpec(specPath);
            renderStaticSpecChart(containerId, spec, `No ${squad === 1 ? '1st' : '2nd'} XV league results available for this season.`);
        } catch (error) {
            console.error(`Failed to load league results chart spec: ${specPath}`, error);
            renderStaticSpecChart(containerId, null, `Unable to load ${squad === 1 ? '1st' : '2nd'} XV league results chart.`);
        }
    });

    await Promise.all(tasks);
}

function syncLeagueResultsPanelWidthState() {
    const columns = Array.from(document.querySelectorAll('.league-results-column'));
    if (!columns.length) return;

    columns.forEach(column => column.classList.remove('league-results-column--expanded'));

    const expandedToggle = document.querySelector('.chart-panel-toggle[data-accordion-group="league-results-panels"][aria-expanded="true"]');
    if (!expandedToggle) return;

    const expandedColumn = expandedToggle.closest('.league-results-column');
    if (expandedColumn) expandedColumn.classList.add('league-results-column--expanded');
}

function initialiseLeagueResultsPanelLayout() {
    document.querySelectorAll('.chart-panel-toggle[data-accordion-group="league-results-panels"]').forEach(toggle => {
        if (toggle.__leagueResultsLayoutBound) return;
        toggle.__leagueResultsLayoutBound = true;
        toggle.addEventListener('click', () => {
            window.requestAnimationFrame(syncLeagueResultsPanelWidthState);
        });
    });
    syncLeagueResultsPanelWidthState();
}

async function loadLeagueTablePage() {
    if (!leagueTablesData) {
        try {
            const response = await fetch('data/league_tables.json');
            leagueTablesData = await response.json();
        } catch (err) {
            console.error('Error loading league tables data:', err);
            return;
        }
    }
    await loadLeagueResultsIndex();
    await renderLeagueTables();
}

async function renderLeagueTables() {
    const season = document.getElementById('leagueTableSeasonSelect').value;
    const container = document.getElementById('leagueTablesContainer');
    if (!leagueTablesData || !leagueTablesData[season]) {
        container.innerHTML = '<p>No data available for this season.</p>';
        return;
    }

    const seasonData = leagueTablesData[season];
    let html = '';

    if (seasonData['1']) {
        const squad1 = seasonData['1'];
        html += `
            <div class="col-lg-6 mb-4 league-results-column" data-league-results-squad="1">
                <h3 class="league-team-title league-section-title league-team-title-1st">1st XV</h3>
                <p class="league-division-title league-division-title-1st">${squad1.division}</p>
                <div style="background: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow-x: auto;">
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr style="background: #e5e4e7;">
                                <th style="text-align: center;">#</th>
                                <th>Team</th>
                                <th style="text-align: center;">P</th>
                                <th style="text-align: center;">W</th>
                                <th style="text-align: center;">D</th>
                                <th style="text-align: center;">L</th>
                                <th style="text-align: center;">PF</th>
                                <th style="text-align: center;">PA</th>
                                <th style="text-align: center;">PD</th>
                                <th style="text-align: center;">BP</th>
                                <th style="text-align: center;">Pts</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${squad1.tables.map(row => {
                                const isEGRFC = row.team.toLowerCase().includes('east grinstead') && !row.team.toLowerCase().includes('ii');
                                const rowClass = isEGRFC ? 'league-highlight-row league-highlight-row-1st' : '';
                                const bonusPoints = row.bonusPoints ?? ((row.triesBefore || 0) + (row.triesLost || 0));
                                return `
                                    <tr class="${rowClass}">
                                        <td style="text-align: center;">${row.position}</td>
                                        <td>${row.team}</td>
                                        <td style="text-align: center;">${row.played}</td>
                                        <td style="text-align: center;">${row.won}</td>
                                        <td style="text-align: center;">${row.drawn}</td>
                                        <td style="text-align: center;">${row.lost}</td>
                                        <td style="text-align: center;">${row.pointsFor}</td>
                                        <td style="text-align: center;">${row.pointsAgainst}</td>
                                        <td style="text-align: center;">${row.pointsDifference}</td>
                                        <td style="text-align: center;">${bonusPoints}</td>
                                        <td style="text-align: center;">${row.points}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
                <div style="margin-top: 0.5rem;">
                    ${createLeagueResultsSpecPanel(
                        'league-results-panel-1',
                        'leagueResultsChart1',
                        '1st XV Results',
                        'chart-panel-toggle--primary',
                        season,
                        1
                    )}
                </div>
            </div>
        `;
    }

    if (seasonData['2']) {
        const squad2 = seasonData['2'];
        html += `
            <div class="col-12 d-lg-none">
                <hr class="league-squad-divider">
            </div>
            <div class="col-lg-6 mb-4 league-results-column" data-league-results-squad="2">
                <h3 class="league-team-title league-section-title league-team-title-2nd">2nd XV</h3>
                <p class="league-division-title league-division-title-2nd">${squad2.division}</p>
                <div style="background: white; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow-x: auto;">
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr style="background: #e5e4e7;">
                                <th style="text-align: center;">#</th>
                                <th>Team</th>
                                <th style="text-align: center;">P</th>
                                <th style="text-align: center;">W</th>
                                <th style="text-align: center;">D</th>
                                <th style="text-align: center;">L</th>
                                <th style="text-align: center;">PF</th>
                                <th style="text-align: center;">PA</th>
                                <th style="text-align: center;">PD</th>
                                <th style="text-align: center;">BP</th>
                                <th style="text-align: center;">Pts</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${squad2.tables.map(row => {
                                const isEGRFC = row.team.toLowerCase().includes('east grinstead');
                                const rowClass = isEGRFC ? 'league-highlight-row league-highlight-row-2nd' : '';
                                const bonusPoints = row.bonusPoints ?? ((row.triesBefore || 0) + (row.triesLost || 0));
                                return `
                                    <tr class="${rowClass}">
                                        <td style="text-align: center;">${row.position}</td>
                                        <td>${row.team}</td>
                                        <td style="text-align: center;">${row.played}</td>
                                        <td style="text-align: center;">${row.won}</td>
                                        <td style="text-align: center;">${row.drawn}</td>
                                        <td style="text-align: center;">${row.lost}</td>
                                        <td style="text-align: center;">${row.pointsFor}</td>
                                        <td style="text-align: center;">${row.pointsAgainst}</td>
                                        <td style="text-align: center;">${row.pointsDifference}</td>
                                        <td style="text-align: center;">${bonusPoints}</td>
                                        <td style="text-align: center;">${row.points}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
                <div style="margin-top: 0.5rem;">
                    ${createLeagueResultsSpecPanel(
                        'league-results-panel-2',
                        'leagueResultsChart2',
                        '2nd XV Results',
                        'chart-panel-toggle--accent',
                        season,
                        2
                    )}
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
    initialiseChartPanelToggles();
    initialiseLeagueResultsPanelLayout();
    await renderLeagueResultsChartsForSeason(season);
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();

    const seasonSelect = document.getElementById('leagueTableSeasonSelect');
    if (seasonSelect) {
        const $seasonSelect = $('#leagueTableSeasonSelect');

        seasonSelect.innerHTML = '';
        availableSeasons.forEach(season => {
            const option = document.createElement('option');
            option.value = season;
            option.textContent = season;
            seasonSelect.appendChild(option);
        });

        const currentSeason = getCurrentSeasonLabel();
        if (availableSeasons.includes(currentSeason)) {
            seasonSelect.value = currentSeason;
        } else if (availableSeasons.length > 0) {
            seasonSelect.value = availableSeasons[0];
        }

        const selectedLeagueSeason = seasonSelect.value;
        rebuildBootstrapSelect(seasonSelect);
        $seasonSelect.selectpicker('val', selectedLeagueSeason);

        $seasonSelect.on('change', async () => {
            await renderLeagueTables();
        });
    }

    await loadLeagueTablePage();
});

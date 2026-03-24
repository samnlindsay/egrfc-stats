// League Tables page logic

let leagueTablesData = null;

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
    renderLeagueTables();
}

function renderLeagueTables() {
    const season = document.getElementById('leagueTableSeasonSelect').value;
    const container = document.getElementById('leagueTablesContainer');
    if (!leagueTablesData || !leagueTablesData[season]) {
        container.innerHTML = '<p>No data available for this season.</p>';
        return;
    }

    const seasonData = leagueTablesData[season];
    const leagueSeason = toLeagueSeasonFormat(season);
    let html = '';

    if (seasonData['1']) {
        const squad1 = seasonData['1'];
        html += `
            <div class="col-lg-6 mb-4">
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
                    ${createLeagueResultsPanel(
                        'league-results-panel-1',
                        `Charts/league/results.html?season=${encodeURIComponent(leagueSeason)}&squad=1`,
                        '1st XV Results',
                        'chart-panel-toggle--primary'
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
            <div class="col-lg-6 mb-4">
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
                    ${createLeagueResultsPanel(
                        'league-results-panel-2',
                        `Charts/league/results.html?season=${encodeURIComponent(leagueSeason)}&squad=2`,
                        '2nd XV Results',
                        'chart-panel-toggle--accent'
                    )}
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
    initialiseChartPanelToggles();
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();

    const seasonSelect = document.getElementById('leagueTableSeasonSelect');
    if (seasonSelect) {
        const $seasonSelect = $('#leagueTableSeasonSelect');
        $seasonSelect.selectpicker();

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
        $seasonSelect.selectpicker('destroy');
        $seasonSelect.selectpicker();
        $seasonSelect.selectpicker('val', selectedLeagueSeason);

        $seasonSelect.on('change', renderLeagueTables);
    }

    loadLeagueTablePage();
});

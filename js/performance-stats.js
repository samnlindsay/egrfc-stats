(function () {
    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }

        try {
            const response = await fetch(path);
            if (!response.ok) {
                throw new Error(`Failed to fetch chart (${response.status}): ${path}`);
            }
            const spec = await response.json();
            container.innerHTML = '';
            await vegaEmbed(container, spec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' });
            pinVegaActionsInElement(container);
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
        }
    }

    function buildRedZoneSpec(setPieceRows) {
        const rows = setPieceRows
            .map((row) => ({
                season: row.season,
                squad: row.squad,
                metric: 'Points per 22m entry',
                value: Number(row.avg_points_per_22m_entry),
            }))
            .concat(
                setPieceRows.map((row) => ({
                    season: row.season,
                    squad: row.squad,
                    metric: 'Tries per 22m entry',
                    value: Number(row.avg_tries_per_22m_entry),
                }))
            )
            .filter((row) => Number.isFinite(row.value));

        const orderedSeasons = Array.from(new Set(rows.map((row) => String(row.season)))).sort((a, b) => {
            const ay = parseInt(String(a).slice(0, 4), 10);
            const by = parseInt(String(b).slice(0, 4), 10);
            return ay - by;
        });

        return {
            $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
            title: {
                text: '1st XV Red Zone Efficiency',
                subtitle: 'How effectively 22m entries convert into points and tries.',
            },
            width: 520,
            height: 280,
            data: { values: rows },
            mark: { type: 'line', point: true, strokeWidth: 2.2 },
            encoding: {
                x: {
                    field: 'season',
                    type: 'ordinal',
                    sort: orderedSeasons,
                    title: 'Season',
                },
                y: {
                    field: 'value',
                    type: 'quantitative',
                    title: 'Per 22m Entry',
                },
                color: {
                    field: 'metric',
                    type: 'nominal',
                    title: null,
                    scale: {
                        domain: ['Points per 22m entry', 'Tries per 22m entry'],
                        range: ['#202946', '#981515'],
                    },
                },
                strokeDash: {
                    field: 'squad',
                    type: 'nominal',
                    title: null,
                    legend: null,
                },
                tooltip: [
                    { field: 'season', type: 'nominal', title: 'Season' },
                    { field: 'metric', type: 'nominal', title: 'Metric' },
                    { field: 'value', type: 'quantitative', title: 'Value', format: '.2f' },
                ],
            },
            config: {
                axis: {
                    labelFontSize: 12,
                    titleFontSize: 13,
                },
                legend: {
                    labelFontSize: 12,
                    titleFontSize: 12,
                },
                view: {
                    stroke: null,
                },
            },
        };
    }

    async function renderRedZoneChart() {
        const container = document.getElementById('redZone1stChart');
        if (!container) {
            return;
        }

        try {
            const response = await fetch('data/backend/season_summary_enriched.json');
            if (!response.ok) {
                throw new Error(`Failed to fetch season summary (${response.status})`);
            }

            const summary = await response.json();
            const rows = (Array.isArray(summary) ? summary : [])
                .filter((row) => row && row.squad === '1st' && row.gameTypeMode === 'All games')
                .map((row) => ({
                    season: row.season,
                    squad: row.squad,
                    avg_points_per_22m_entry: row.avgPointsPer22mEntry,
                    avg_tries_per_22m_entry: row.avgTriesPer22mEntry,
                }));
            if (rows.length === 0) {
                container.innerHTML = '<div class="text-center text-muted py-4">No red-zone data available.</div>';
                return;
            }

            const spec = buildRedZoneSpec(rows);
            container.innerHTML = '';
            await vegaEmbed(container, spec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' });
            pinVegaActionsInElement(container);
        } catch (error) {
            console.error('Unable to render red zone performance chart:', error);
            container.innerHTML = '<div class="text-center text-muted py-4">Red-zone chart unavailable.</div>';
        }
    }

    document.addEventListener('DOMContentLoaded', async function () {
        await Promise.all([
            renderChartSpec('setPiece1stScrumChart', 'data/charts/set_piece_success_1st_scrum.json', '1st XV scrum chart unavailable.'),
            renderChartSpec('setPiece1stLineoutChart', 'data/charts/set_piece_success_1st_lineout.json', '1st XV lineout chart unavailable.'),
            renderChartSpec('setPiece2ndScrumChart', 'data/charts/set_piece_success_2nd_scrum.json', '2nd XV scrum chart unavailable.'),
            renderChartSpec('setPiece2ndLineoutChart', 'data/charts/set_piece_success_2nd_lineout.json', '2nd XV lineout chart unavailable.'),
            renderRedZoneChart(),
                renderChartSpec('lineoutZoneChart', 'data/charts/lineout_success_by_zone.json', '1st XV lineout zone chart unavailable.'),
            renderChartSpec('lineoutBreakdown1stChart', 'data/charts/lineout_breakdown_1st.json', '1st XV lineout breakdown unavailable.'),
            renderChartSpec('lineoutBreakdown2ndChart', 'data/charts/lineout_breakdown_2nd.json', '2nd XV lineout breakdown unavailable.'),
            ]);
        initialiseChartPanelToggles();
    });
})();

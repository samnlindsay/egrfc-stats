(function () {
    const LINEOUT_H2H_SPEC_PATH = 'data/charts/lineout_h2h.json';

    const PANEL_SPECS = [
        { containerId: 'lineoutPerfBreakdownNumbersChart', path: 'data/charts/lineout_breakdown_numbers.json', emptyMessage: 'Numbers breakdown unavailable.' },
        { containerId: 'lineoutPerfBreakdownAreaChart', path: 'data/charts/lineout_breakdown_area.json', emptyMessage: 'Zone breakdown unavailable.' },
        { containerId: 'lineoutPerfBreakdownCallTypeChart', path: 'data/charts/lineout_breakdown_call_type.json', emptyMessage: 'Call type breakdown unavailable.' },
        { containerId: 'lineoutPerfBreakdownDummyChart', path: 'data/charts/lineout_breakdown_dummy.json', emptyMessage: 'Dummy breakdown unavailable.' },
        { containerId: 'lineoutPerfBreakdownThrowerChart', path: 'data/charts/lineout_breakdown_thrower.json', emptyMessage: 'Thrower breakdown unavailable.' },
        { containerId: 'lineoutPerfBreakdownJumperChart', path: 'data/charts/lineout_breakdown_jumper.json', emptyMessage: 'Jumper breakdown unavailable.' },
        { containerId: 'lineoutPerfTrendNumbersChart', path: 'data/charts/lineout_trend_numbers.json', emptyMessage: 'Numbers trend unavailable.' },
        { containerId: 'lineoutPerfTrendAreaChart', path: 'data/charts/lineout_trend_area.json', emptyMessage: 'Zone trend unavailable.' },
        { containerId: 'lineoutPerfTrendCallTypeChart', path: 'data/charts/lineout_trend_call_type.json', emptyMessage: 'Call type trend unavailable.' },
        { containerId: 'lineoutPerfTrendDummyChart', path: 'data/charts/lineout_trend_dummy.json', emptyMessage: 'Dummy trend unavailable.' },
        { containerId: 'lineoutPerfTrendThrowerChart', path: 'data/charts/lineout_trend_thrower.json', emptyMessage: 'Thrower trend unavailable.' },
        { containerId: 'lineoutPerfTrendJumperChart', path: 'data/charts/lineout_trend_jumper.json', emptyMessage: 'Jumper trend unavailable.' },
    ];

    const ANALYSIS_SIGNAL_IDS = {
        loSquad: 'lineoutFilterSquad',
        loSeason: 'lineoutFilterSeason',
        loGameType: 'lineoutFilterGameType',
        loThrower: 'lineoutFilterThrower',
        loJumper: 'lineoutFilterJumper',
        loArea: 'lineoutFilterArea',
        loNumbers: 'lineoutFilterNumbers',
    };

    const H2H_SIGNAL_IDS = {
        h2hSquadFilter: 'lineoutFilterSquad',
        h2hSeasonFilter: 'lineoutFilterSeason',
        h2hGameTypeFilter: 'lineoutFilterGameType',
        h2hOppositionFilter: 'h2hFilterOpposition',
        h2hTeamHighlight: 'h2hFilterTeamHighlight',
        h2hOutcomeHighlight: 'h2hFilterOutcomeHighlight',
    };

    const views = new Map();
    let lineoutH2HBaseSpec = null;
    let lineoutH2HLayoutKey = null;

    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        try {
            const spec = await loadChartSpec(path);
            container.innerHTML = '';
            const result = await vegaEmbed(container, spec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' });
            pinVegaActionsInElement(container);
            return result.view;
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            return null;
        }
    }

    function cloneSpec(spec) {
        return JSON.parse(JSON.stringify(spec));
    }

    function getLineoutH2HLayoutKey() {
        const teamValue = document.getElementById('h2hFilterTeamHighlight')?.value || 'All';
        const outcomeValue = document.getElementById('h2hFilterOutcomeHighlight')?.value || 'All';
        return (teamValue === 'All' && outcomeValue === 'All') ? 'offset-on' : 'offset-off';
    }

    function applyLineoutH2HLayout(spec, layoutKey) {
        const step = layoutKey === 'offset-on' ? 8 : 15;
        const barSize = layoutKey === 'offset-on' ? 8 : 12;

        const flowBarLayer = spec?.hconcat?.[0]?.layer?.[1];
        if (flowBarLayer) {
            flowBarLayer.height = { step };
            flowBarLayer.encoding = flowBarLayer.encoding || {};
            flowBarLayer.encoding.size = { value: barSize };
        }

        const successLayers = spec?.hconcat?.[1]?.layer || [];
        successLayers.forEach((layer) => {
            layer.height = { step };
        });

        const aggregateFlowLayer = spec?.vconcat?.[1]?.hconcat?.[0]?.layer?.[1];
        if (aggregateFlowLayer) {
            aggregateFlowLayer.height = { step };
        }
        const aggregateSuccessLayers = spec?.vconcat?.[1]?.hconcat?.[1]?.layer || [];
        aggregateSuccessLayers.forEach((layer) => {
            layer.height = { step };
        });

        return spec;
    }

    async function ensureLineoutH2HViewLayout() {
        const container = document.getElementById('lineoutH2HChart');
        if (!container) return null;

        if (!lineoutH2HBaseSpec) {
            lineoutH2HBaseSpec = await loadChartSpec(LINEOUT_H2H_SPEC_PATH);
        }

        const layoutKey = getLineoutH2HLayoutKey();
        if (layoutKey === lineoutH2HLayoutKey && views.get('lineoutH2HChart')) {
            return views.get('lineoutH2HChart');
        }

        const layoutSpec = applyLineoutH2HLayout(cloneSpec(lineoutH2HBaseSpec), layoutKey);
        container.innerHTML = '';
        const result = await vegaEmbed(container, layoutSpec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' });
        pinVegaActionsInElement(container);
        lineoutH2HLayoutKey = layoutKey;
        views.set('lineoutH2HChart', result.view);
        return result.view;
    }

    function populateSelect(id, values, allLabel) {
        const select = document.getElementById(id);
        if (!select) return;
        const currentValue = select.value;
        select.innerHTML = '';
        const allOption = document.createElement('option');
        allOption.value = 'All';
        allOption.textContent = allLabel;
        select.appendChild(allOption);
        values.forEach((value) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
        select.value = Array.from(select.options).some((option) => option.value === currentValue) ? currentValue : 'All';
        rebuildBootstrapSelect(select);
    }

    function seasonSort(a, b) {
        const ay = parseInt(String(a).slice(0, 4), 10);
        const by = parseInt(String(b).slice(0, 4), 10);
        return ay - by;
    }

    function setSignalFromControl(view, signalName, controlId, fallback = 'All') {
        if (!view) return;
        const element = document.getElementById(controlId);
        view.signal(signalName, element ? element.value : fallback);
    }

    function enforceH2HFilterExclusivity(changedControlId) {
        const teamSelect = document.getElementById('h2hFilterTeamHighlight');
        const outcomeSelect = document.getElementById('h2hFilterOutcomeHighlight');
        if (!teamSelect || !outcomeSelect) return;

        if (changedControlId === 'h2hFilterTeamHighlight' && teamSelect.value !== 'All') {
            outcomeSelect.value = 'All';
        }

        if (changedControlId === 'h2hFilterOutcomeHighlight' && outcomeSelect.value !== 'All') {
            teamSelect.value = 'All';
        }
    }

    function collapseLineoutAnalysisPair(pair) {
        if (!pair) return;

        pair.querySelectorAll('.chart-panel-toggle').forEach((toggle) => {
            const targetId = toggle.getAttribute('data-target');
            const panel = targetId ? document.getElementById(targetId) : null;
            toggle.setAttribute('aria-expanded', 'false');
            if (panel) {
                panel.hidden = true;
            }
        });
    }

    function collapseSiblingPanelsInPair(currentToggle, pair) {
        if (!pair) return;

        pair.querySelectorAll('.chart-panel-toggle').forEach((otherToggle) => {
            if (otherToggle === currentToggle) return;
            const otherTargetId = otherToggle.getAttribute('data-target');
            const otherPanel = otherTargetId ? document.getElementById(otherTargetId) : null;
            otherToggle.setAttribute('aria-expanded', 'false');
            if (otherPanel) {
                otherPanel.hidden = true;
            }
        });
    }

    function initialiseLineoutAnalysisAccordion() {
        document.querySelectorAll('.lineout-analysis-pair .chart-panel-toggle').forEach((toggle) => {
            if (toggle.__lineoutAnalysisAccordionBound) return;
            toggle.__lineoutAnalysisAccordionBound = true;

            toggle.addEventListener('click', () => {
                const currentPair = toggle.closest('.lineout-analysis-pair');
                if (!currentPair) return;

                window.requestAnimationFrame(() => {
                    if (toggle.getAttribute('aria-expanded') === 'true') {
                        collapseSiblingPanelsInPair(toggle, currentPair);

                        document.querySelectorAll('.lineout-analysis-pair').forEach((otherPair) => {
                            if (otherPair === currentPair) return;
                            collapseLineoutAnalysisPair(otherPair);
                        });
                    }
                });
            });
        });

    }

    async function applyFiltersToViews() {
        const pending = [];

        PANEL_SPECS.forEach(({ containerId }) => {
            const view = views.get(containerId);
            if (!view) return;
            Object.entries(ANALYSIS_SIGNAL_IDS).forEach(([signalName, controlId]) => {
                setSignalFromControl(view, signalName, controlId);
            });
            view.signal('loOpposition', 'All');
            view.signal('loCall', 'All');
            pending.push(view.runAsync());
        });

        const h2hView = await ensureLineoutH2HViewLayout();
        if (h2hView) {
            Object.entries(H2H_SIGNAL_IDS).forEach(([signalName, controlId]) => {
                setSignalFromControl(h2hView, signalName, controlId);
            });
            pending.push(h2hView.runAsync());
        }

        await Promise.all(pending);
    }

    async function loadFilterOptions() {
        const [lineoutsRes, setPieceRes, gamesRes] = await Promise.all([
            fetch('data/backend/lineouts.json'),
            fetch('data/backend/set_piece.json'),
            fetch('data/backend/games.json'),
        ]);

        if (!lineoutsRes.ok || !setPieceRes.ok || !gamesRes.ok) {
            throw new Error('Failed to fetch backend datasets for lineout filters.');
        }

        const [lineoutsRaw, setPieceRaw, gamesRaw] = await Promise.all([lineoutsRes.json(), setPieceRes.json(), gamesRes.json()]);
        const gamesById = new Map((Array.isArray(gamesRaw) ? gamesRaw : []).map((game) => [game.game_id, game]));

        const lineoutRows = (Array.isArray(lineoutsRaw) ? lineoutsRaw : []).map((row) => {
            const game = gamesById.get(row.game_id) || {};
            return {
                season: String(row.season || game.season || ''),
                game_type: String(game.game_type || 'Unknown'),
                thrower: String(row.thrower || 'Unknown'),
                jumper: String(row.jumper || 'Unknown'),
                area: String(row.area || 'Unknown'),
                numbers: String(row.numbers || 'Unknown'),
                call_type: String(row.call_type || 'Unknown'),
            };
        });

        const setPieceRows = (Array.isArray(setPieceRaw) ? setPieceRaw : []).map((row) => {
            const game = gamesById.get(row.game_id) || {};
            return { opposition: String(row.opposition || game.opposition || 'Unknown') };
        });

        populateSelect('lineoutFilterSeason', Array.from(new Set(lineoutRows.map((row) => row.season))).filter(Boolean).sort(seasonSort).reverse(), 'All Seasons');
        populateSelect('lineoutFilterThrower', Array.from(new Set(lineoutRows.map((row) => row.thrower))).sort(), 'All Throwers');
        populateSelect('lineoutFilterJumper', Array.from(new Set(lineoutRows.map((row) => row.jumper))).sort(), 'All Jumpers');
        populateSelect('lineoutFilterArea', Array.from(new Set(lineoutRows.map((row) => row.area))).sort(), 'All Zones');
        populateSelect('lineoutFilterNumbers', Array.from(new Set(lineoutRows.map((row) => row.numbers))).sort(), 'All Numbers');
        populateSelect('h2hFilterOpposition', Array.from(new Set(setPieceRows.map((row) => row.opposition))).sort(), 'All Opponents');
    }

    async function loadInteractiveCharts() {
        const interactiveCharts = [
            ...PANEL_SPECS,
        ];

        await Promise.all(interactiveCharts.map(async ({ containerId, path, emptyMessage }) => {
            const view = await renderChartSpec(containerId, path, emptyMessage);
            if (view) views.set(containerId, view);
        }));

        try {
            await ensureLineoutH2HViewLayout();
        } catch (error) {
            const container = document.getElementById('lineoutH2HChart');
            if (container) {
                console.error(`Unable to render chart from ${LINEOUT_H2H_SPEC_PATH}:`, error);
                container.innerHTML = '<div class="text-center text-muted py-4">Lineouts head-to-head chart unavailable.</div>';
            }
        }
    }

    async function setupLineoutPage() {
        const controlIds = [
            'lineoutFilterSquad', 'lineoutFilterSeason', 'lineoutFilterGameType',
            'lineoutFilterThrower', 'lineoutFilterJumper', 'lineoutFilterArea',
            'lineoutFilterNumbers',
            'h2hFilterOpposition', 'h2hFilterTeamHighlight', 'h2hFilterOutcomeHighlight',
        ];

        await loadFilterOptions();
        controlIds.forEach((id) => {
            rebuildBootstrapSelect(document.getElementById(id));
        });
        await loadInteractiveCharts();
        await applyFiltersToViews();

        controlIds.forEach((id) => {
            const element = document.getElementById(id);
            if (!element) return;
            element.addEventListener('change', () => {
                enforceH2HFilterExclusivity(id);
                applyFiltersToViews().catch((error) => {
                    console.error('Unable to apply lineout page filters:', error);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        await Promise.all([
            renderChartSpec('setPiece1stLineoutChart', 'data/charts/set_piece_success_1st_lineout.json', '1st XV lineout chart unavailable.'),
            renderChartSpec('setPiece2ndLineoutChart', 'data/charts/set_piece_success_2nd_lineout.json', '2nd XV lineout chart unavailable.'),
            setupLineoutPage(),
        ]);
        initialiseChartPanelToggles();
        initialiseLineoutAnalysisAccordion();
    });
})();

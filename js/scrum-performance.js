(function () {
    const SCRUM_H2H_SPEC_PATH = 'data/charts/scrum_h2h.json';

    function getControlElement(preferredId, fallbackId = null) {
        return document.getElementById(preferredId) || (fallbackId ? document.getElementById(fallbackId) : null);
    }

    function getControlValue(preferredId, fallbackId = null, fallbackValue = 'All') {
        const el = getControlElement(preferredId, fallbackId);
        return el ? el.value : fallbackValue;
    }

    const H2H_SIGNAL_IDS = {
        h2hSquadFilter: 'scrumFilterSquad',
        h2hSeasonFilter: 'scrumFilterSeason',
        h2hGameTypeFilter: 'scrumFilterGameType',
        h2hOppositionFilter: 'scrumFilterOpposition',
        h2hTeamHighlight: 'scrumFilterTeamHighlight',
        h2hOutcomeHighlight: 'scrumFilterOutcomeHighlight',
    };

    let scrumH2HView = null;
    let scrumH2HBaseSpec = null;
    let scrumH2HLayoutKey = null;
    let scrumSuccessView = null;

    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        try {
            const spec = await loadChartSpec(path);
            return await embedChartSpec(container, spec, { containerId, emptyMessage });
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            return null;
        }
    }

    async function renderSplitSetPiecePanelsFromSingleSpec(path, panelConfigs) {
        let baseSpec = null;
        try {
            baseSpec = await loadChartSpec(path);
        } catch (error) {
            console.error(`Unable to load shared chart spec from ${path}:`, error);
            panelConfigs.forEach(({ containerId, emptyMessage }) => {
                const container = document.getElementById(containerId);
                if (container) {
                    container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
                }
            });
            return;
        }

        await Promise.all(panelConfigs.map(async ({ containerId, squad, emptyMessage }) => {
            const container = document.getElementById(containerId);
            if (!container) return;

            try {
                const spec = cloneSpec(baseSpec);
                const view = await embedChartSpec(container, spec, { containerId, emptyMessage });
                if (view) {
                    view.signal('spSquadParam', squad);
                    await view.runAsync();
                }
            } catch (error) {
                console.error(`Unable to render split set-piece panel for ${containerId}:`, error);
                container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            }
        }));
    }

    function cloneSpec(spec) {
        return JSON.parse(JSON.stringify(spec));
    }

    function getScrumH2HLayoutKey() {
        const teamValue = document.getElementById('scrumFilterTeamHighlight')?.value || 'All';
        const outcomeValue = document.getElementById('scrumFilterOutcomeHighlight')?.value || 'All';
        return (teamValue === 'All' && outcomeValue === 'All') ? 'offset-on' : 'offset-off';
    }

    function applyScrumH2HLayout(spec, layoutKey) {
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

    async function ensureScrumH2HViewLayout() {
        const container = document.getElementById('scrumH2HChart');
        if (!container) return null;

        if (!scrumH2HBaseSpec) {
            scrumH2HBaseSpec = await loadChartSpec(SCRUM_H2H_SPEC_PATH);
        }

        const layoutKey = getScrumH2HLayoutKey();
        if (layoutKey === scrumH2HLayoutKey && scrumH2HView) {
            return scrumH2HView;
        }

        const layoutSpec = applyScrumH2HLayout(cloneSpec(scrumH2HBaseSpec), layoutKey);
        scrumH2HLayoutKey = layoutKey;
        scrumH2HView = await embedChartSpec(container, layoutSpec, {
            containerId: 'scrumH2HChart',
            emptyMessage: 'Scrums head-to-head chart unavailable.'
        });
        return scrumH2HView;
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

    function toOppositionClubName(opposition) {
        const text = String(opposition || 'Unknown').trim();
        const club = text.replace(/\s+(?:I{1,6}|[1-6](?:st|nd|rd|th)?|A|B)(?:\s+XV)?$/i, '').trim();
        return club || 'Unknown';
    }

    async function loadScrumFilterOptions() {
        const [setPieceRes, gamesRes] = await Promise.all([
            fetch('data/backend/set_piece.json'),
            fetch('data/backend/games.json'),
        ]);

        if (!setPieceRes.ok || !gamesRes.ok) {
            throw new Error('Failed to fetch backend datasets for scrum filters.');
        }

        const [setPieceRaw, gamesRaw] = await Promise.all([setPieceRes.json(), gamesRes.json()]);
        const gamesById = new Map((Array.isArray(gamesRaw) ? gamesRaw : []).map((game) => [game.game_id, game]));
        const rows = (Array.isArray(setPieceRaw) ? setPieceRaw : []).map((row) => {
            const game = gamesById.get(row.game_id) || {};
            return {
                season: String(row.season || game.season || ''),
                opposition_club: toOppositionClubName(row.opposition || game.opposition || 'Unknown'),
            };
        });

        if (document.getElementById('scrumFilterSeason')) {
            populateSelect('scrumFilterSeason', Array.from(new Set(rows.map((row) => row.season))).filter(Boolean).sort(seasonSort).reverse(), 'All Seasons');
        }
        populateSelect('scrumFilterOpposition', Array.from(new Set(rows.map((row) => row.opposition_club))).sort(), 'All Opponents');
    }

    async function applyScrumFilters() {
        scrumH2HView = await ensureScrumH2HViewLayout();

        if (scrumH2HView) {
            Object.entries(H2H_SIGNAL_IDS).forEach(([signalName, controlId]) => {
                if (controlId === 'scrumFilterSquad') {
                    scrumH2HView.signal(signalName, getControlValue('scrumFilterSquad', 'lineoutFilterSquad'));
                    return;
                }
                if (controlId === 'scrumFilterSeason') {
                    scrumH2HView.signal(signalName, getControlValue('scrumFilterSeason', 'lineoutFilterSeason'));
                    return;
                }
                if (controlId === 'scrumFilterGameType') {
                    scrumH2HView.signal(signalName, getControlValue('scrumFilterGameType', 'lineoutFilterGameType'));
                    return;
                }
                scrumH2HView.signal(signalName, getControlValue(controlId));
            });
        }

        if (scrumSuccessView) {
            scrumSuccessView.signal('spSquadParam', getControlValue('scrumFilterSquad', 'lineoutFilterSquad'));
            await scrumSuccessView.runAsync();
        }

        if (scrumH2HView) {
            await scrumH2HView.runAsync();
        }
    }

    function enforceH2HFilterExclusivity(changedControlId) {
        const teamSelect = document.getElementById('scrumFilterTeamHighlight');
        const outcomeSelect = document.getElementById('scrumFilterOutcomeHighlight');
        if (!teamSelect || !outcomeSelect) return;

        if (changedControlId === 'scrumFilterTeamHighlight' && teamSelect.value !== 'All') {
            outcomeSelect.value = 'All';
        }

        if (changedControlId === 'scrumFilterOutcomeHighlight' && outcomeSelect.value !== 'All') {
            teamSelect.value = 'All';
        }
    }

    async function setupScrumFilters() {
        const controls = [
            'scrumFilterSquad', 'scrumFilterSeason', 'scrumFilterGameType',
            'scrumFilterOpposition', 'scrumFilterTeamHighlight', 'scrumFilterOutcomeHighlight',
            'lineoutFilterSquad', 'lineoutFilterSeason', 'lineoutFilterGameType',
        ];

        await loadScrumFilterOptions();
        controls.forEach((id) => {
            rebuildBootstrapSelect(getControlElement(id));
        });
        try {
            scrumH2HView = await ensureScrumH2HViewLayout();
        } catch (error) {
            scrumH2HView = await renderChartSpec('scrumH2HChart', SCRUM_H2H_SPEC_PATH, 'Scrums head-to-head chart unavailable.');
        }
        await applyScrumFilters();

        controls.forEach((id) => {
            const element = getControlElement(id);
            if (!element) return;
            element.addEventListener('change', () => {
                enforceH2HFilterExclusivity(id);
                applyScrumFilters().catch((error) => {
                    console.error('Unable to apply scrum page filters:', error);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        scrumSuccessView = await renderChartSpec('setPieceScrumChart', 'data/charts/set_piece_success_scrum.json', 'Scrum success chart unavailable.');

        await renderSplitSetPiecePanelsFromSingleSpec('data/charts/set_piece_success_scrum.json', [
            { containerId: 'setPiece1stScrumChart', squad: '1st', emptyMessage: '1st XV scrum chart unavailable.' },
            { containerId: 'setPiece2ndScrumChart', squad: '2nd', emptyMessage: '2nd XV scrum chart unavailable.' },
        ]);

        const hasScrumFilters = Boolean(
            getControlElement('scrumFilterSquad') ||
            getControlElement('scrumFilterSeason') ||
            getControlElement('scrumFilterGameType') ||
            getControlElement('lineoutFilterSquad') ||
            getControlElement('lineoutFilterSeason') ||
            getControlElement('lineoutFilterGameType')
        );
        const hasScrumDeepDiveChart = Boolean(document.getElementById('scrumH2HChart'));

        if (hasScrumFilters || hasScrumDeepDiveChart) {
            await setupScrumFilters();
        }

        initialiseChartPanelToggles();
    });
})();

(function () {
    const SPEC_PATH = 'data/charts/red_zone_points.json';
    const CHART_CONTAINER_ID = 'rzPointsChart';

    function getControlElement(preferredId, fallbackId = null) {
        return document.getElementById(preferredId) || (fallbackId ? document.getElementById(fallbackId) : null);
    }

    function getControlValue(preferredId, fallbackId = null, fallbackValue = 'All') {
        const el = getControlElement(preferredId, fallbackId);
        return el ? el.value : fallbackValue;
    }

    const SIGNAL_IDS = {
        rzSquad: 'rzFilterSquad',
        rzSeason: 'rzFilterSeason',
        rzGameType: 'rzFilterGameType',
    };

    const views = new Map();

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

    async function renderChartSpec(containerId, path, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        try {
            const spec = await loadChartSpec(path);
            if (spec && spec.title) {
                if (typeof spec.title === 'string') {
                    spec.title = 'Red Zone Success';
                } else if (typeof spec.title === 'object') {
                    spec.title.text = 'Red Zone Success';
                }
            }
            return await embedChartSpec(container, spec, { containerId, emptyMessage });
        } catch (error) {
            console.error(`Unable to render chart from ${path}:`, error);
            container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
            return null;
        }
    }

    async function loadFilterOptions() {
        const response = await fetch('data/backend/v_red_zone.json');
        if (!response.ok) {
            throw new Error(`Unable to load red-zone backend rows (HTTP ${response.status})`);
        }
        const rows = await response.json();
        const seasons = [...new Set((Array.isArray(rows) ? rows : []).map((row) => String(row.season || '')).filter(Boolean))]
            .sort((a, b) => {
                const ay = parseInt(a.slice(0, 4), 10);
                const by = parseInt(b.slice(0, 4), 10);
                return by - ay;
            });

        if (document.getElementById('rzFilterSeason')) {
            populateSelect('rzFilterSeason', seasons, 'All Seasons');
        }
        rebuildBootstrapSelect(getControlElement('rzFilterSquad', 'lineoutFilterSquad'));
        rebuildBootstrapSelect(getControlElement('rzFilterGameType', 'lineoutFilterGameType'));
    }

    async function applyFilters() {
        const pending = [];
        views.forEach((view) => {
            if (!view) return;
            Object.entries(SIGNAL_IDS).forEach(([signalName, controlId]) => {
                if (controlId === 'rzFilterSquad') {
                    view.signal(signalName, getControlValue('rzFilterSquad', 'lineoutFilterSquad'));
                    return;
                }
                if (controlId === 'rzFilterSeason') {
                    view.signal(signalName, getControlValue('rzFilterSeason', 'lineoutFilterSeason'));
                    return;
                }
                if (controlId === 'rzFilterGameType') {
                    view.signal(signalName, getControlValue('rzFilterGameType', 'lineoutFilterGameType'));
                    return;
                }
                view.signal(signalName, getControlValue(controlId));
            });
            pending.push(view.runAsync());
        });
        await Promise.all(pending);
    }

    async function init() {
        await loadFilterOptions();

        const view = await renderChartSpec(CHART_CONTAINER_ID, SPEC_PATH, 'Red zone chart unavailable.');
        if (view) {
            views.set(CHART_CONTAINER_ID, view);
        }

        await applyFilters();
        

        ['rzFilterSquad', 'rzFilterSeason', 'rzFilterGameType', 'lineoutFilterSquad', 'lineoutFilterSeason', 'lineoutFilterGameType'].forEach((id) => {
            getControlElement(id)?.addEventListener('change', () => {
                applyFilters().catch((error) => {
                    console.error('Unable to apply red-zone filters:', error);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        init().catch((error) => {
            console.error('Red zone page initialisation failed:', error);
            const el = document.getElementById(CHART_CONTAINER_ID);
            if (el) {
                el.innerHTML = '<div class="text-center text-muted py-4">Red zone data unavailable.</div>';
            }
            
        });
    });
})();

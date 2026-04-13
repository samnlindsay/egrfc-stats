// Shared constants, utilities and chart helpers used across all pages.

const VEGA_EMBED_ACTIONS = { export: true, source: false, compiled: false, editor: false };
const FORWARD_POSITIONS = ['Prop', 'Hooker', 'Second Row', 'Flanker', 'Number 8'];
const BACK_POSITIONS = ['Scrum Half', 'Fly Half', 'Centre', 'Wing', 'Full Back'];
const SQUAD_POSITION_ORDER = [...FORWARD_POSITIONS, ...BACK_POSITIONS];
let availableSeasons = ['2025/26', '2024/25', '2023/24', '2022/23', '2021/22', '2019/20', '2018/19', '2017/18', '2016/17'];
const chartSpecCache = new Map();
const chartSpecRequestVersion = String(Date.now());

function getCurrentSeasonLabel() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const startYear = month >= 7 ? year : year - 1;
    const endSuffix = String((startYear + 1) % 100).padStart(2, '0');
    return `${startYear}/${endSuffix}`;
}

async function loadAvailableSeasons() {
    try {
        const response = await fetch('data/league_tables.json');
        if (!response.ok) {
            console.warn(`Failed to fetch league_tables.json (${response.status}), using default seasons`);
            return;
        }
        const data = await response.json();
        if (data.seasons && Array.isArray(data.seasons) && data.seasons.length > 0) {
            availableSeasons = data.seasons;
        }
    } catch (err) {
        console.error('Failed to load seasons from league_tables.json:', err.message);
    }
}

function normalizeSeasonLabel(value) {
    if (!value) return null;
    const season = String(value).trim().replace('-', '/');
    const match = season.match(/^(\d{4})\/(\d{2}|\d{4})$/);
    if (!match) return null;
    const startYear = match[1];
    const endPart = match[2];
    const endSuffix = endPart.length === 4 ? endPart.slice(-2) : endPart;
    return `${startYear}/${endSuffix}`;
}

function getSortedSquadStatsSeasons(dataBySeason) {
    const seasons = Object.keys(dataBySeason || {});
    if (seasons.length === 0) return [];
    return seasons.sort((a, b) => {
        const startA = parseInt(String(a).split('/')[0], 10);
        const startB = parseInt(String(b).split('/')[0], 10);
        if (!Number.isFinite(startA) || !Number.isFinite(startB)) return String(b).localeCompare(String(a));
        return startB - startA;
    });
}

function getAllowedGameTypes(mode) {
    if (mode === 'League + Cup') return new Set(['League', 'Cup']);
    if (mode === 'League only') return new Set(['League']);
    return null;
}

function createGameLink(gameId) {
    if (!gameId) return null;
    return `match-info.html?game=${encodeURIComponent(String(gameId || '').trim())}`;
}

function createPlayerLink(playerName) {
    if (!playerName) return null;
    return `player-profile.html?player=${encodeURIComponent(String(playerName || '').trim())}`;
}

function pinVegaActionsInElement(rootElement) {
    if (!rootElement) return;
    const run = () => {
        rootElement.querySelectorAll('.vega-embed').forEach(embed => {
            embed.style.display = 'block';
            embed.style.position = 'relative';
            const details = embed.querySelector('details[title="Click to view actions"], details');
            if (!details) return;
            details.style.position = 'absolute';
            details.style.top = '8px';
            details.style.right = '8px';
            details.style.left = 'auto';
            details.style.margin = '0';
            details.style.float = 'none';
            details.style.zIndex = '10';
            const actions = details.querySelector('.vega-actions');
            if (actions) {
                actions.style.position = 'absolute';
                actions.style.top = '100%';
                actions.style.right = '0';
                actions.style.left = 'auto';
                actions.style.zIndex = '11';
            }
        });
    };
    run();
    [50, 150, 400, 900].forEach(delay => window.setTimeout(run, delay));
}

async function loadChartSpec(path) {
    if (chartSpecCache.has(path)) return chartSpecCache.get(path);
    const separator = path.includes('?') ? '&' : '?';
    const requestPath = `${path}${separator}v=${encodeURIComponent(chartSpecRequestVersion)}`;
    const response = await fetch(requestPath, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Failed to fetch ${path} (${response.status})`);
    const spec = await response.json();
    chartSpecCache.set(path, spec);
    return spec;
}

function filterChartSpecDataset(spec, predicate) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const filteredRows = [];
    
    if (clonedSpec.datasets) {
        Object.keys(clonedSpec.datasets).forEach(key => {
            const rows = clonedSpec.datasets[key];
            if (Array.isArray(rows)) {
                const filtered = rows.filter(predicate);
                clonedSpec.datasets[key] = filtered;
                filteredRows.push(...filtered);
            }
        });
    }
    if (clonedSpec.data && Array.isArray(clonedSpec.data.values)) {
        const filtered = clonedSpec.data.values.filter(predicate);
        clonedSpec.data.values = filtered;
        filteredRows.push(...filtered);
    }
    
    // Filter color scale to only include values present in filtered data
    if (filteredRows.length > 0 && clonedSpec.encoding && clonedSpec.encoding.color && clonedSpec.encoding.color.scale) {
        const colorScale = clonedSpec.encoding.color.scale;
        if (colorScale.domain && colorScale.range && colorScale.domain.length === colorScale.range.length) {
            const colorField = clonedSpec.encoding.color.field ? clonedSpec.encoding.color.field.split(':')[0] : null;
            if (colorField) {
                const uniqueColorValues = new Set();
                filteredRows.forEach(row => {
                    const value = row[colorField];
                    if (value !== undefined && value !== null) {
                        uniqueColorValues.add(String(value));
                    }
                });
                
                if (uniqueColorValues.size > 0 && uniqueColorValues.size < colorScale.domain.length) {
                    const valuesToIndices = new Map();
                    colorScale.domain.forEach((val, idx) => {
                        valuesToIndices.set(String(val), idx);
                    });
                    
                    const filteredDomain = [];
                    const filteredRange = [];
                    colorScale.domain.forEach((val, idx) => {
                        if (uniqueColorValues.has(String(val))) {
                            filteredDomain.push(val);
                            filteredRange.push(colorScale.range[idx]);
                        }
                    });
                    
                    colorScale.domain = filteredDomain;
                    colorScale.range = filteredRange;
                }
            }
        }
    }
    
    return clonedSpec;
}

function collectChartDatasetNames(spec, datasetNames = new Set()) {
    if (!spec || typeof spec !== 'object') return datasetNames;
    if (spec.data && typeof spec.data.name === 'string') datasetNames.add(spec.data.name);
    ['layer', 'hconcat', 'vconcat', 'concat'].forEach(key => {
        const childSpecs = spec[key];
        if (Array.isArray(childSpecs)) childSpecs.forEach(child => collectChartDatasetNames(child, datasetNames));
    });
    if (spec.spec) collectChartDatasetNames(spec.spec, datasetNames);
    return datasetNames;
}

function filterNamedDatasetsInSpec(spec, datasetNames, predicate) {
    if (!spec || typeof spec !== 'object') return spec;
    if (spec.datasets) {
        datasetNames.forEach(name => {
            const rows = spec.datasets[name];
            if (Array.isArray(rows)) spec.datasets[name] = rows.filter(predicate);
        });
    }
    return spec;
}

function filterLeagueContextCombinedSpec(spec, comparisonPredicate, trendPredicate) {
    const clonedSpec = JSON.parse(JSON.stringify(spec));
    const combinedCharts = Array.isArray(clonedSpec.hconcat) ? clonedSpec.hconcat : null;
    if (!combinedCharts || combinedCharts.length < 2) {
        return filterChartSpecDataset(clonedSpec, comparisonPredicate);
    }
    const comparisonDatasetNames = collectChartDatasetNames(combinedCharts[0]);
    const trendDatasetNames = collectChartDatasetNames(combinedCharts[1]);
    filterNamedDatasetsInSpec(clonedSpec, comparisonDatasetNames, comparisonPredicate);
    filterNamedDatasetsInSpec(clonedSpec, trendDatasetNames, trendPredicate);
    return clonedSpec;
}

function chartSpecHasRows(spec) {
    if (!spec) return false;
    if (spec.datasets) return Object.values(spec.datasets).some(rows => Array.isArray(rows) && rows.length > 0);
    if (spec.data && Array.isArray(spec.data.values)) return spec.data.values.length > 0;
    return true;
}

function prepareChartSpecForEmbed(spec, options = {}) {
    const processedSpec = JSON.parse(JSON.stringify(spec));
    if (options.hideTitle !== false) delete processedSpec.title;
    return processedSpec;
}

function renderStaticSpecChart(containerId, spec, emptyMessage, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!spec || !chartSpecHasRows(spec)) {
        container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
        return;
    }
    container.innerHTML = '';
    const embedHost = document.createElement('div');
    embedHost.className = 'chart-embed-host';
    if (containerId === 'teamSheetsChart') embedHost.classList.add('chart-embed-host--team-sheets');
    container.appendChild(embedHost);
    const chartSpec = prepareChartSpecForEmbed(spec, options);
    vegaEmbed(embedHost, chartSpec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' })
        .then(() => pinVegaActionsInElement(container))
        .catch(error => {
            console.error(`Error rendering ${containerId}:`, error);
            container.innerHTML = '<div class="text-center text-danger py-4">Unable to render chart.</div>';
        });
}

function rebuildBootstrapSelect(select, options = {}) {
    if (!select || !window.jQuery || !window.jQuery.fn || !window.jQuery.fn.selectpicker) {
        return false;
    }

    const $select = window.jQuery(select);
    const currentValue = select.multiple
        ? Array.from(select.selectedOptions || []).map(option => option.value)
        : select.value;

    if ($select.data('selectpicker')) {
        $select.selectpicker('destroy');
    }

    $select.selectpicker(options);

    if (select.multiple) {
        $select.selectpicker('val', Array.isArray(currentValue) ? currentValue : []);
    } else if (currentValue !== undefined && currentValue !== null && currentValue !== '') {
        $select.selectpicker('val', currentValue);
    }

    return true;
}

function toLeagueSeasonFormat(season) {
    if (!season || !season.includes('/')) return season;
    const [startYear, endShort] = String(season).split('/');
    return `${startYear}-20${endShort}`;
}

function updateLeagueResultsIframeHeight(iframe) {
    if (!iframe) return;
    try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!doc) return;
        const primaryContent =
            doc.querySelector('#vis') ||
            doc.querySelector('.vega-embed') ||
            doc.querySelector('main') ||
            doc.body;
        const svg = doc.querySelector('#vis svg, .vega-embed svg, svg');
        if (doc.body) { doc.body.style.overflowX = 'hidden'; doc.body.style.margin = '0'; doc.body.style.padding = '0'; }
        if (doc.documentElement) { doc.documentElement.style.overflowX = 'hidden'; doc.documentElement.style.margin = '0'; doc.documentElement.style.padding = '0'; }
        if (primaryContent) { primaryContent.style.transformOrigin = 'top left'; primaryContent.style.transform = 'none'; primaryContent.style.width = 'auto'; }
        if (svg) { svg.style.display = 'block'; svg.style.width = '100%'; svg.style.height = 'auto'; svg.style.maxWidth = '100%'; svg.style.margin = '0'; }
        const contentWidth = Math.max(
            svg?.getBoundingClientRect ? svg.getBoundingClientRect().width : 0,
            primaryContent?.scrollWidth || 0, primaryContent?.offsetWidth || 0,
            primaryContent?.getBoundingClientRect ? primaryContent.getBoundingClientRect().width : 0
        );
        const availableWidth = Math.max(
            iframe.clientWidth || 0,
            iframe.getBoundingClientRect ? iframe.getBoundingClientRect().width : 0
        );
        const scale = contentWidth > 0 && availableWidth > 0 ? Math.min(1, availableWidth / contentWidth) : 1;
        let svgDrawHeight = 0;
        if (svg?.getBoundingClientRect) svgDrawHeight = Math.ceil(svg.getBoundingClientRect().height || 0);
        if (svg && typeof svg.getBBox === 'function') {
            try {
                const bbox = svg.getBBox();
                if (bbox && bbox.height > 0) svgDrawHeight = Math.max(svgDrawHeight, Math.ceil((bbox.y || 0) + bbox.height));
            } catch (e) {}
        }
        const intrinsicContentHeight = Math.max(
            svgDrawHeight,
            primaryContent?.getBoundingClientRect ? Math.ceil(primaryContent.getBoundingClientRect().height || 0) : 0,
            primaryContent?.scrollHeight || 0, primaryContent?.offsetHeight || 0
        );
        const fallbackDocumentHeight = Math.max(doc.body?.scrollHeight || 0, doc.documentElement?.scrollHeight || 0);
        const bindings = doc.querySelector('.vega-bindings');
        const svgRect = svg?.getBoundingClientRect ? svg.getBoundingClientRect() : null;
        const bindingsRect = bindings?.getBoundingClientRect ? bindings.getBoundingClientRect() : null;
        const visualTop = Math.min(
            Number.isFinite(svgRect?.top) ? svgRect.top : Number.POSITIVE_INFINITY,
            Number.isFinite(bindingsRect?.top) ? bindingsRect.top : Number.POSITIVE_INFINITY
        );
        const visualBottom = Math.max(
            Number.isFinite(svgRect?.bottom) ? svgRect.bottom : 0,
            Number.isFinite(bindingsRect?.bottom) ? bindingsRect.bottom : 0
        );
        const visualContentHeight = Number.isFinite(visualTop) && visualBottom > visualTop ? Math.ceil(visualBottom - visualTop) : 0;
        let contentHeight = 0;
        if (visualContentHeight > 0) contentHeight = visualContentHeight;
        else if (svgDrawHeight > 0) contentHeight = svgDrawHeight;
        else if (intrinsicContentHeight > 0) contentHeight = intrinsicContentHeight;
        else contentHeight = fallbackDocumentHeight;
        const visibleHeight = contentHeight * scale;
        const nextHeight = Math.ceil(visibleHeight + 2);
        if (nextHeight > 0) { iframe.style.height = `${nextHeight}px`; iframe.style.minHeight = '0'; }
        const wrapper = iframe.closest('.chart-panel-card');
        if (wrapper) wrapper.style.minHeight = '0';
    } catch (e) {}
}

function createLeagueResultsPanel(panelId, src, title, colorModifier) {
    return `
        <div class="chart-panel">
            <button type="button" class="chart-panel-toggle ${colorModifier}"
                data-target="${panelId}" aria-expanded="false" aria-controls="${panelId}">
                <span class="chart-panel-toggle-text">
                    <span class="chart-panel-toggle-title">${title}</span>
                    <span class="chart-panel-toggle-hint">League match results</span>
                </span>
                <span class="chart-panel-toggle-icon" aria-hidden="true"></span>
            </button>
            <div id="${panelId}" class="chart-panel-content" hidden>
                <div class="chart-panel-card">
                    <iframe src="${src}" class="league-results-frame" title="${title} chart" loading="lazy"></iframe>
                </div>
            </div>
        </div>
    `;
}

function initialiseChartPanelToggles() {
    document.querySelectorAll('.chart-panel-toggle').forEach(toggle => {
        if (toggle.__chartPanelInitialised) return;
        toggle.__chartPanelInitialised = true;
        toggle.addEventListener('click', function () {
            const targetId = this.getAttribute('data-target');
            const panel = targetId ? document.getElementById(targetId) : null;
            if (!panel) return;
            const accordionGroup = this.getAttribute('data-accordion-group');
            const isExpanded = this.getAttribute('aria-expanded') !== 'false';
            this.setAttribute('aria-expanded', String(!isExpanded));
            panel.hidden = isExpanded;
            if (accordionGroup && isExpanded === false) {
                document.querySelectorAll(`.chart-panel-toggle[data-accordion-group="${accordionGroup}"]`).forEach(otherToggle => {
                    if (otherToggle === this) return;
                    const otherTargetId = otherToggle.getAttribute('data-target');
                    const otherPanel = otherTargetId ? document.getElementById(otherTargetId) : null;
                    otherToggle.setAttribute('aria-expanded', 'false');
                    if (otherPanel) otherPanel.hidden = true;
                });
            }
            if (!isExpanded) {
                const iframe = panel.querySelector('.league-results-frame');
                if (iframe) window.setTimeout(() => updateLeagueResultsIframeHeight(iframe), 50);
            }
        });
    });

    document.querySelectorAll('.league-results-frame').forEach(iframe => {
        iframe.addEventListener('load', () => {
            updateLeagueResultsIframeHeight(iframe);
            [150, 500, 1000, 1800].forEach(delay => window.setTimeout(() => updateLeagueResultsIframeHeight(iframe), delay));
        });
    });

    if (!window.__chartPanelResizeBound) {
        window.addEventListener('resize', () => {
            document.querySelectorAll('.league-results-frame').forEach(iframe => updateLeagueResultsIframeHeight(iframe));
        });
        window.__chartPanelResizeBound = true;
    }
}

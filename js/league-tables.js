// League Tables page logic

let leagueTablesData = null;
let leagueResultsIndexData = null;
let leagueTablesAnalysisRailInitialised = false;
let leagueResultsScaleResizeBound = false;

const LEAGUE_FILTERS_OFFCANVAS_ID = 'leagueTablesFiltersOffcanvas';
const LEAGUE_RESULTS_COLOUR_UNEXPECTED = 'unexpected';
const LEAGUE_RESULTS_COLOUR_RESULT = 'result';

function cloneLeagueResultsSpec(spec) {
    if (typeof window.structuredClone === 'function') {
        return window.structuredClone(spec);
    }
    return JSON.parse(JSON.stringify(spec));
}

function getLeagueResultsSelectedColourEncoding() {
    const toggle1 = document.getElementById('leagueTablesUnexpectedToggle1');
    const toggle2 = document.getElementById('leagueTablesUnexpectedToggle2');
    const toggle = toggle1 || toggle2;
    return toggle?.checked ? LEAGUE_RESULTS_COLOUR_UNEXPECTED : LEAGUE_RESULTS_COLOUR_RESULT;
}

function detectLeagueResultsSelectionBinding(spec) {
    const specText = JSON.stringify(spec || {});
    const match = specText.match(/(param_\d+)\['([^']+)'\]/);
    if (!match) return null;
    return { paramName: match[1], field: match[2] };
}

function applyLeagueResultsColourEncoding(spec, colourEncoding) {
    const nextSpec = cloneLeagueResultsSpec(spec);
    if (!Array.isArray(nextSpec?.layer)) return nextSpec;

    const rectLayer = nextSpec.layer.find(layer => {
        const markType = typeof layer?.mark === 'string' ? layer.mark : layer?.mark?.type;
        return markType === 'rect';
    });

    if (!rectLayer?.encoding) return nextSpec;

    const selectionBinding = detectLeagueResultsSelectionBinding(nextSpec);
    const selectionTest = selectionBinding
        ? `datum.home_team == ${selectionBinding.paramName}['${selectionBinding.field}'] || datum.away_team == ${selectionBinding.paramName}['${selectionBinding.field}'] || !isValid(${selectionBinding.paramName}['${selectionBinding.field}'])`
        : 'true';
    if (colourEncoding !== LEAGUE_RESULTS_COLOUR_RESULT) {
        return nextSpec;
    }

    rectLayer.encoding.color = {
        field: 'result_simple',
        type: 'nominal',
        title: null,
        legend: {
            labelLimit: 220,
            offset: 16,
            orient: 'bottom',
            symbolStrokeColor: 'black',
            symbolStrokeWidth: 1,
            values: ['Home Win', 'Draw', 'Away Win']
        },
        scale: {
            domain: ['Home Win', 'Draw', 'Away Win', 'To be played', 'N/A'],
            range: ['#146f14', '#d4a017', '#991515', 'white', 'black']
        }
    };

    rectLayer.encoding.opacity = {
        condition: [
            {
                test: `(${selectionTest}) && isValid(datum.home_score) && isValid(datum.away_score) && datum.home_score != datum.away_score && abs(datum.home_score - datum.away_score) <= 7`,
                value: 0.55
            },
            {
                test: selectionTest,
                value: 1.0
            }
        ],
        value: 0.1
    };


    nextSpec.layer.forEach(layer => {
        const markType = typeof layer?.mark === 'string' ? layer.mark : layer?.mark?.type;
        const textField = layer?.encoding?.text?.field;
        const isScoreLabel = markType === 'text' && (textField === 'away_score_text' || textField === 'home_score_text');
        if (!isScoreLabel || !layer?.encoding) return;

        layer.encoding.color = { value: 'white' };
    });

    return nextSpec;
}

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
    const colourEncoding = getLeagueResultsSelectedColourEncoding();
    const tasks = [1, 2].map(async squad => {
        const containerId = `leagueResultsChart${squad}`;
        const chartHost = document.getElementById(containerId);
        if (!chartHost) {
            return;
        }

        const specPath = getLeagueResultsSpecPath(season, squad);
        try {
            const baseSpec = await loadChartSpec(specPath);
            await embedChartSpec(containerId, baseSpec, {
                containerId,
                actions: false,
                specCustomizer: (spec) => applyLeagueResultsColourEncoding(spec, colourEncoding),
                emptyMessage: `No ${squad === 1 ? '1st' : '2nd'} XV league results available for this season.`
            });
            scaleLeagueResultsEmbedToFit(chartHost);
            window.requestAnimationFrame(() => scaleLeagueResultsEmbedToFit(chartHost));
        } catch (error) {
            console.error(`Failed to load league results chart spec: ${specPath}`, error);
            renderStaticSpecChart(containerId, null, `Unable to load ${squad === 1 ? '1st' : '2nd'} XV league results chart.`);
        }
    });

    await Promise.all(tasks);
    bindLeagueResultsScaleResize();
}

function scaleLeagueResultsEmbedToFit(container) {
    if (!container) return false;

    const embedHost = container.querySelector('.chart-embed-host');
    if (!embedHost) return false;

    const boundary = container.closest('.league-results-chart-card') || container;
    const availableWidth = Math.floor(boundary.clientWidth || container.clientWidth || 0);

    // Reset prior inline sizing so we can measure intrinsic unscaled bounds.
    embedHost.style.transform = 'none';
    embedHost.style.transformOrigin = 'top left';
    embedHost.style.width = '';
    embedHost.style.height = '';
    container.style.width = '';
    container.style.height = '';

    const measureIntrinsicSize = () => {
        const svg = embedHost.querySelector('svg');
        let svgWidth = 0;
        let svgHeight = 0;
        if (svg) {
            const vb = svg.viewBox?.baseVal;
            svgWidth = Number(vb?.width) || Number(svg.getAttribute('width')) || svg.width?.baseVal?.value || 0;
            svgHeight = Number(vb?.height) || Number(svg.getAttribute('height')) || svg.height?.baseVal?.value || 0;
        }

        const canvas = embedHost.querySelector('canvas');
        let canvasWidth = 0;
        let canvasHeight = 0;
        if (canvas) {
            canvasWidth = Number(canvas.width) || Number(canvas.getAttribute('width')) || 0;
            canvasHeight = Number(canvas.height) || Number(canvas.getAttribute('height')) || 0;
        }

        const hostRect = embedHost.getBoundingClientRect();
        const scrollWidth = Math.ceil(embedHost.scrollWidth || 0);
        const scrollHeight = Math.ceil(embedHost.scrollHeight || 0);

        const width = Math.ceil(Math.max(svgWidth, canvasWidth, scrollWidth, hostRect.width || 0));
        const height = Math.ceil(Math.max(svgHeight, canvasHeight, scrollHeight, hostRect.height || 0));
        return { width, height };
    };

    const intrinsicSize = measureIntrinsicSize();
    const intrinsicWidth = intrinsicSize.width;
    const intrinsicHeight = intrinsicSize.height;

    if (!availableWidth || !intrinsicWidth) {
        return false;
    }

    const scale = Math.min(1, availableWidth / intrinsicWidth);
    const scaledWidth = Math.ceil(intrinsicWidth * scale);
    const scaledHeight = Math.ceil(intrinsicHeight * scale);

    // Fix the unscaled host box first, then transform it.
    embedHost.style.width = `${intrinsicWidth}px`;
    embedHost.style.height = `${intrinsicHeight}px`;
    embedHost.style.transform = `scale(${scale})`;

    container.style.maxWidth = '100%';

    // Keep container tightly wrapped to transformed bounds.
    container.style.width = `${Math.min(availableWidth, scaledWidth)}px`;
    container.style.height = `${scaledHeight}px`;

    // Re-apply once on next frame in case font/layout settles late.
    window.requestAnimationFrame(() => {
        const refreshed = measureIntrinsicSize();
        const nextScale = Math.min(1, availableWidth / Math.max(1, refreshed.width));
        const nextScaledWidth = Math.ceil(refreshed.width * nextScale);
        const nextScaledHeight = Math.ceil(refreshed.height * nextScale);

        embedHost.style.width = `${refreshed.width}px`;
        embedHost.style.height = `${refreshed.height}px`;
        embedHost.style.transform = `scale(${nextScale})`;

        container.style.width = `${Math.min(availableWidth, nextScaledWidth)}px`;
        container.style.height = `${nextScaledHeight}px`;
    });

    boundary.style.overflowX = 'hidden';
    boundary.style.overflowY = 'visible';
    return true;
}

function applyLeagueResultsScalingAll() {
    scaleLeagueResultsEmbedToFit(document.getElementById('leagueResultsChart1'));
    scaleLeagueResultsEmbedToFit(document.getElementById('leagueResultsChart2'));
}

function bindLeagueResultsScaleResize() {
    if (leagueResultsScaleResizeBound) return;
    leagueResultsScaleResizeBound = true;
    window.addEventListener('resize', () => {
        window.requestAnimationFrame(applyLeagueResultsScalingAll);
    });
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

function formatSeasonShort(season) {
    if (!season || !season.includes('/')) return season || 'Unknown';
    const parts = season.split('/');
    if (parts.length !== 2) return season;
    return `${parts[0].slice(-2)}/${parts[1].slice(-2)}`;
}

function getSquadTableRow(squadRows = [], squadNumber) {
    return squadRows.find(row => {
        if (!row?.team) return false;
        const teamName = String(row.team).toLowerCase();
        if (!teamName.includes('east grinstead')) return false;
        return squadNumber === 1 ? !teamName.includes('ii') : true;
    }) || null;
}

function getSelectedSquadFilter() {
    const squadSelect = document.getElementById('leagueTablesSquadSelect');
    return squadSelect?.value || 'All';
}

function shouldIncludeSquad(squadLabel, selectedFilter) {
    if (selectedFilter === 'All') return true;
    return selectedFilter === squadLabel;
}

function getOrdinalSuffix(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 'th';
    const mod100 = number % 100;
    if (mod100 >= 11 && mod100 <= 13) return 'th';
    switch (number % 10) {
    case 1:
        return 'st';
    case 2:
        return 'nd';
    case 3:
        return 'rd';
    default:
        return 'th';
    }
}

function formatLeaguePositionValue(squadData, squadNumber) {
    const row = getSquadTableRow(squadData?.tables, squadNumber);
    if (!row || !row.position) return '—';

    const position = Number(row.position);
    if (!Number.isFinite(position)) return String(row.position);

    const suffix = getOrdinalSuffix(position);
    const teamCount = Array.isArray(squadData?.tables) ? squadData.tables.length : null;
    const teamCountMarkup = teamCount ? `<span class="league-hero-position-total">out of ${teamCount}</span>` : '';

    return `<span class="league-hero-position-rank">${position}<sup>${suffix}</sup></span>${teamCountMarkup}`;
}

function getSquadFilterLabel(value) {
    if (value === '1st') return '1st XV';
    if (value === '2nd') return '2nd XV';
    return 'Both squads';
}

function updateLeagueTablesHero(season, seasonData) {
    const metaEl = document.getElementById('leagueTablesHeroMeta');
    const firstValueEl = document.getElementById('leagueTablesHero1stValue');
    const firstNoteEl = document.getElementById('leagueTablesHero1stNote');
    const secondValueEl = document.getElementById('leagueTablesHero2ndValue');
    const secondNoteEl = document.getElementById('leagueTablesHero2ndNote');

    if (!metaEl || !firstValueEl || !firstNoteEl || !secondValueEl || !secondNoteEl) {
        return;
    }

    const squad1 = seasonData?.['1'];
    const squad2 = seasonData?.['2'];

    metaEl.textContent = season || 'No season selected';

    firstValueEl.innerHTML = formatLeaguePositionValue(squad1, 1);
    firstNoteEl.textContent = squad1?.division || 'No 1st XV league data';

    secondValueEl.innerHTML = formatLeaguePositionValue(squad2, 2);
    secondNoteEl.textContent = squad2?.division || 'No 2nd XV league data';
}

function renderLeagueTableActiveFilters(season, squadFilter) {
    const standingsTarget = document.getElementById('leagueTablesStandingsActiveFilters');
    const resultsTarget = document.getElementById('leagueTablesResultsActiveFilters');
    if (!standingsTarget && !resultsTarget) return;

    const shortSeason = formatSeasonShort(season);
    const seasonChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${LEAGUE_FILTERS_OFFCANVAS_ID}" aria-controls="${LEAGUE_FILTERS_OFFCANVAS_ID}"><strong>Season</strong> <span class="d-none d-md-inline">${season}</span><span class="d-inline d-md-none">${shortSeason}</span></button>`;
    const squadChip = `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${LEAGUE_FILTERS_OFFCANVAS_ID}" aria-controls="${LEAGUE_FILTERS_OFFCANVAS_ID}"><strong>Squad</strong> ${getSquadFilterLabel(squadFilter)}</button>`;

    if (standingsTarget) standingsTarget.innerHTML = `${seasonChip}${squadChip}`;
    if (resultsTarget) resultsTarget.innerHTML = `${seasonChip}${squadChip}`;
}

function updateLeagueTablesSeasonStepperState() {
    const seasonSelect = document.getElementById('leagueTableSeasonSelect');
    const label = document.getElementById('leagueTablesSeasonLabelOffcanvas');
    const prevBtn = document.getElementById('leagueTablesSeasonPrevOffcanvas');
    const nextBtn = document.getElementById('leagueTablesSeasonNextOffcanvas');
    if (!seasonSelect || !label || !prevBtn || !nextBtn) return;

    const seasons = Array.from(seasonSelect.options).map(option => option.value);
    const selected = seasonSelect.value;
    const index = seasons.indexOf(selected);

    label.textContent = selected || getCurrentSeasonLabel();
    prevBtn.disabled = index <= 0;
    nextBtn.disabled = index < 0 || index >= seasons.length - 1;
}

function shiftLeagueTableSeason(offset) {
    const seasonSelect = document.getElementById('leagueTableSeasonSelect');
    if (!seasonSelect) return;

    const seasons = Array.from(seasonSelect.options).map(option => option.value);
    const currentIndex = seasons.indexOf(seasonSelect.value);
    if (currentIndex < 0) return;

    const nextIndex = currentIndex + offset;
    if (nextIndex < 0 || nextIndex >= seasons.length) return;

    seasonSelect.value = seasons[nextIndex];
    seasonSelect.dispatchEvent(new Event('change', { bubbles: true }));
}

function initialiseLeagueTableSeasonControls() {
    const prevBtn = document.getElementById('leagueTablesSeasonPrevOffcanvas');
    const nextBtn = document.getElementById('leagueTablesSeasonNextOffcanvas');
    if (prevBtn && !prevBtn.__leagueTablesBound) {
        prevBtn.__leagueTablesBound = true;
        prevBtn.addEventListener('click', () => shiftLeagueTableSeason(-1));
    }
    if (nextBtn && !nextBtn.__leagueTablesBound) {
        nextBtn.__leagueTablesBound = true;
        nextBtn.addEventListener('click', () => shiftLeagueTableSeason(1));
    }
    updateLeagueTablesSeasonStepperState();
}

function syncLeagueTablesSquadSegmentUI(value) {
    const segment = document.getElementById('leagueTablesSquadSegment');
    if (!segment) return;
    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.value === value);
    });
}

function setLeagueTablesSquadFilter(value, { rerender = true } = {}) {
    const squadSelect = document.getElementById('leagueTablesSquadSelect');
    if (!squadSelect) return;
    if (![...squadSelect.options].some(option => option.value === value)) return;

    squadSelect.value = value;
    syncLeagueTablesSquadSegmentUI(value);
    if (rerender) {
        renderLeagueTables();
    }
}

function initialiseLeagueTablesSquadControls() {
    const squadSelect = document.getElementById('leagueTablesSquadSelect');
    const segment = document.getElementById('leagueTablesSquadSegment');
    if (!squadSelect || !segment) return;

    segment.querySelectorAll('.squad-filter-segment-btn').forEach(btn => {
        if (btn.__leagueTablesBound) return;
        btn.__leagueTablesBound = true;
        btn.addEventListener('click', () => setLeagueTablesSquadFilter(btn.dataset.value));
    });

    squadSelect.addEventListener('change', () => {
        syncLeagueTablesSquadSegmentUI(squadSelect.value);
        renderLeagueTables();
    });

    syncLeagueTablesSquadSegmentUI(squadSelect.value || 'All');
}

function initialiseLeagueTableResultsTooltips() {
    const tooltipText = 'By default, results are shown in green for a home win and red for an away win. Unexpected results (or "upsets") are those where a lower-ranked team beats a higher ranked team.';
    
    ['1', '2'].forEach(squadNum => {
        const btn = document.getElementById(`leagueTablesColourInfoBtn${squadNum}`);
        if (btn) {
            btn.setAttribute('data-bs-toggle', 'tooltip');
            btn.setAttribute('data-bs-placement', 'top');
            btn.setAttribute('data-bs-html', 'true');
            btn.title = tooltipText;
            
            // Initialize Bootstrap tooltip if available
            try {
                if (window.bootstrap?.Tooltip) {
                    new window.bootstrap.Tooltip(btn);
                }
            } catch (e) {
                console.warn('Could not initialize tooltip:', e);
            }
        }
    });
}

function initialiseLeagueTablesResultColourControls() {
    initialiseLeagueTableResultsTooltips();
    
    const toggle1 = document.getElementById('leagueTablesUnexpectedToggle1');
    const toggle2 = document.getElementById('leagueTablesUnexpectedToggle2');

    const syncToggles = (sourceToggle) => {
        if (!toggle1 || !toggle2 || !sourceToggle) return;
        if (sourceToggle === toggle1) {
            toggle2.checked = toggle1.checked;
        } else if (sourceToggle === toggle2) {
            toggle1.checked = toggle2.checked;
        }
    };

    const handleToggleChange = (event) => {
        syncToggles(event?.currentTarget || null);
        const season = document.getElementById('leagueTableSeasonSelect').value;
        renderLeagueResultsChartsForSeason(season);
    };

    if (toggle1) {
        toggle1.addEventListener('change', handleToggleChange);
    }
    if (toggle2) {
        toggle2.addEventListener('change', handleToggleChange);
    }
}

function updateLeagueTablesAnalysisRailActive(sectionId) {
    const rail = document.getElementById('leagueTablesAnalysisRail');
    if (!rail) return;
    rail.querySelectorAll('.rail-link').forEach(link => {
        const isMatch = link.getAttribute('href') === `#${sectionId}`;
        link.classList.toggle('active', isMatch);
        link.setAttribute('aria-current', isMatch ? 'true' : 'false');
    });
}

function updateLeagueTablesAnalysisRailOnScroll() {
    const sections = document.querySelectorAll('.analysis-section[id]');
    if (!sections.length) return;

    let currentSection = sections[0]?.id;
    for (const section of sections) {
        const rect = section.getBoundingClientRect();
        if (rect.top < window.innerHeight / 2) {
            currentSection = section.id;
        }
    }

    if (currentSection) updateLeagueTablesAnalysisRailActive(currentSection);
}

function updateLeagueTablesAnalysisRailPinnedState(rail, layout, placeholder, pinState = null) {
    if (!rail || !layout || !placeholder) return;
    const triggerScrollY = Number(pinState?.triggerScrollY ?? 0);
    const hysteresis = Number(pinState?.hysteresis ?? 0);
    const isPinned = rail.classList.contains('is-pinned');
    const scrollY = window.scrollY;
    const shouldPin = isPinned
        ? scrollY >= (triggerScrollY - hysteresis)
        : scrollY >= (triggerScrollY + hysteresis);

    if (!shouldPin) {
        rail.classList.remove('is-pinned');
        rail.style.removeProperty('--analysis-rail-fixed-left');
        rail.style.removeProperty('--analysis-rail-fixed-width');
        placeholder.style.display = 'none';
        placeholder.style.height = '0px';
        return;
    }

    const layoutRect = layout.getBoundingClientRect();
    const viewportPadding = 8;
    const left = Math.max(viewportPadding, layoutRect.left);
    const available = window.innerWidth - (viewportPadding * 2);
    const width = Math.max(220, Math.min(layoutRect.width, available));

    rail.classList.add('is-pinned');
    rail.style.setProperty('--analysis-rail-fixed-left', `${left}px`);
    rail.style.setProperty('--analysis-rail-fixed-width', `${width}px`);
    placeholder.style.display = 'block';
    placeholder.style.height = `${Math.ceil(rail.offsetHeight)}px`;
}

function initialiseLeagueTablesAnalysisRail() {
    if (leagueTablesAnalysisRailInitialised) return;

    const rail = document.querySelector('.league-tables-layout .analysis-rail');
    if (!rail) return;

    const layout = rail.closest('.league-tables-layout');
    if (!layout) return;
    const placeholder = document.createElement('div');
    placeholder.className = 'analysis-rail-placeholder';
    rail.insertAdjacentElement('afterend', placeholder);

    const links = rail.querySelectorAll('.rail-link[href^="#"]');
    if (!links.length) return;

    const pinState = {
        triggerScrollY: 0,
        hysteresis: 8
    };

    const recalculatePinTrigger = () => {
        const navOffset = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-offset')) || 74;
        const pinTop = navOffset + 7;
        const wasPinned = rail.classList.contains('is-pinned');

        if (wasPinned) {
            rail.classList.remove('is-pinned');
            rail.style.removeProperty('--analysis-rail-fixed-left');
            rail.style.removeProperty('--analysis-rail-fixed-width');
            placeholder.style.display = 'none';
            placeholder.style.height = '0px';
        }

        const naturalTop = rail.getBoundingClientRect().top + window.scrollY;
        pinState.triggerScrollY = Math.max(0, naturalTop - pinTop);

        if (wasPinned) {
            updateLeagueTablesAnalysisRailPinnedState(rail, layout, placeholder, pinState);
        }
    };

    links.forEach(link => {
        link.addEventListener('click', (event) => {
            const targetId = link.getAttribute('href')?.replace('#', '');
            const targetSection = targetId ? document.getElementById(targetId) : null;
            if (!targetSection) return;
            event.preventDefault();
            targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (window.location.hash !== `#${targetId}`) {
                window.history.replaceState(null, '', `#${targetId}`);
            }
            window.setTimeout(() => {
                recalculatePinTrigger();
                updateLeagueTablesAnalysisRailPinnedState(rail, layout, placeholder, pinState);
                updateLeagueTablesAnalysisRailOnScroll();
            }, 120);
        });
    });

    const navOffset = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-offset')) || 74;
    const railHeight = rail.getBoundingClientRect().height || 48;
    const scrollSpy = window.bootstrap?.ScrollSpy
        ? window.bootstrap.ScrollSpy.getOrCreateInstance(document.body, {
            target: '#leagueTablesAnalysisRail',
            offset: Math.ceil(navOffset + railHeight + 12)
        })
        : null;

    const syncActiveLink = () => {
        rail.querySelectorAll('.rail-link').forEach(link => {
            if (link.classList.contains('active')) link.setAttribute('aria-current', 'true');
            else link.removeAttribute('aria-current');
        });
    };

    document.body.addEventListener('activate.bs.scrollspy', syncActiveLink);
    syncActiveLink();
    scrollSpy?.refresh();

    const refreshRail = () => {
        updateLeagueTablesAnalysisRailPinnedState(rail, layout, placeholder, pinState);
        updateLeagueTablesAnalysisRailOnScroll();
    };

    let refreshRaf = null;
    const scheduleRefresh = () => {
        if (refreshRaf !== null) return;
        refreshRaf = window.requestAnimationFrame(() => {
            refreshRaf = null;
            refreshRail();
        });
    };

    let recalcRaf = null;
    const scheduleRecalculate = () => {
        if (recalcRaf !== null) return;
        recalcRaf = window.requestAnimationFrame(() => {
            recalcRaf = null;
            recalculatePinTrigger();
            scrollSpy?.refresh();
            syncActiveLink();
            refreshRail();
        });
    };

    window.addEventListener('scroll', scheduleRefresh, { passive: true });
    window.addEventListener('resize', scheduleRecalculate);
    window.addEventListener('hashchange', scheduleRecalculate);

    recalculatePinTrigger();
    refreshRail();
    window.setTimeout(scheduleRecalculate, 250);
    window.setTimeout(scheduleRecalculate, 900);

    const initialHash = String(window.location.hash || '').replace('#', '');
    if (initialHash) {
        const targetSection = document.getElementById(initialHash);
        if (targetSection) {
            window.setTimeout(() => {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                scrollSpy?.refresh();
                syncActiveLink();
                recalculatePinTrigger();
                refreshRail();
            }, 80);
        }
    }

    leagueTablesAnalysisRailInitialised = true;
}

async function renderLeagueTables() {
    const season = document.getElementById('leagueTableSeasonSelect').value;
    const squadFilter = getSelectedSquadFilter();
    const standingsContainer = document.getElementById('leagueTablesStandingsContainer');
    const resultsContainer = document.getElementById('leagueTablesResultsContainer');
    if (!standingsContainer || !resultsContainer) return;

    updateLeagueTablesSeasonStepperState();
    renderLeagueTableActiveFilters(season, squadFilter);

    if (!leagueTablesData || !leagueTablesData[season]) {
        standingsContainer.innerHTML = '<p>No league table data available for this season.</p>';
        resultsContainer.innerHTML = '<p>No league results chart data available for this season.</p>';
        updateLeagueTablesHero(season, null);
        return;
    }

    const seasonData = leagueTablesData[season];
    updateLeagueTablesHero(season, seasonData);

    let standingsHtml = '';
    let resultsHtml = '';

    if (seasonData['1'] && shouldIncludeSquad('1st', squadFilter)) {
        const squad1 = seasonData['1'];
        standingsHtml += `
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
            </div>
        `;

        resultsHtml += `
            <div class="col-12 mb-4 league-results-column" data-league-results-squad="1">
                <h3 class="league-team-title league-section-title league-team-title-1st">1st XV</h3>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <p class="league-division-title league-division-title-1st">${squad1.division}</p>
                    <div class="chart-section-head chart-section-head--league-results-toggle">
                        <div class="squad-filter-control player-stats-section-filter" style="flex-direction: row; align-items: center; gap: 0.5rem;" role="group" aria-label="Results View">
                            <div class="form-check form-switch player-stats-motm-switch" style="margin-left: auto;">
                                <input class="form-check-input" type="checkbox" role="switch" id="leagueTablesUnexpectedToggle1" aria-label="Highlight unexpected results">
                                <label class="form-check-label" for="leagueTablesUnexpectedToggle1">Highlight upsets</label>
                            </div>
                            <button type="button" class="btn btn-link btn-sm p-0" id="leagueTablesColourInfoBtn1" title="Colour scheme explanation"><i class="bi bi-info-circle"></i></button>
                        </div>
                    </div>
                </div>
                <div class="league-results-chart-card">
                    <div id="leagueResultsChart1" class="chart-host chart-host--overflow-visible chart-host--intrinsic">Loading 1st XV league results chart...</div>
                </div>
            </div>
        `;
    }

    if (seasonData['2'] && shouldIncludeSquad('2nd', squadFilter)) {
        const squad2 = seasonData['2'];
        standingsHtml += `
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
            </div>
        `;

        resultsHtml += `
            <div class="col-12 mb-4 league-results-column" data-league-results-squad="2">
                <h3 class="league-team-title league-section-title league-team-title-2nd">2nd XV</h3>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <p class="league-division-title league-division-title-2nd">${squad2.division}</p>
                    <div class="chart-section-head chart-section-head--league-results-toggle">
                        <div class="squad-filter-control player-stats-section-filter" style="flex-direction: row; align-items: center; gap: 0.5rem;" role="group" aria-label="Results View">
                            <div class="form-check form-switch player-stats-motm-switch" style="margin-left: auto;">
                                <input class="form-check-input" type="checkbox" role="switch" id="leagueTablesUnexpectedToggle2" aria-label="Highlight unexpected results">
                                <label class="form-check-label" for="leagueTablesUnexpectedToggle2">Highlight upsets</label>
                            </div>
                            <button type="button" class="btn btn-link btn-sm p-0" id="leagueTablesColourInfoBtn2" title="Colour scheme explanation"><i class="bi bi-info-circle"></i></button>
                        </div>
                    </div>
                </div>
                <div class="league-results-chart-card">
                    <div id="leagueResultsChart2" class="chart-host chart-host--overflow-visible chart-host--intrinsic">Loading 2nd XV league results chart...</div>
                </div>
            </div>
        `;
    }

    if (!standingsHtml) {
        standingsHtml = '<div class="col-12"><p>No league table data available for the selected squad in this season.</p></div>';
    }
    if (!resultsHtml) {
        resultsHtml = '<div class="col-12"><p>No league results chart data available for the selected squad in this season.</p></div>';
    }

    standingsContainer.innerHTML = standingsHtml;
    resultsContainer.innerHTML = resultsHtml;

    await renderLeagueResultsChartsForSeason(season);
    
    initialiseLeagueTablesResultColourControls();
}

document.addEventListener('DOMContentLoaded', async function () {
    await loadAvailableSeasons();

    const seasonSelect = document.getElementById('leagueTableSeasonSelect');
    if (seasonSelect) {
        const parseSeasonStartYear = (seasonLabel) => {
            const match = String(seasonLabel || '').match(/^(\d{4})\//);
            return match ? Number(match[1]) : Number.NEGATIVE_INFINITY;
        };

        const sortedSeasons = [...availableSeasons].sort((a, b) => {
            return parseSeasonStartYear(a) - parseSeasonStartYear(b);
        });

        seasonSelect.innerHTML = '';
        sortedSeasons.forEach(season => {
            const option = document.createElement('option');
            option.value = season;
            option.textContent = season;
            seasonSelect.appendChild(option);
        });

        const currentSeason = getCurrentSeasonLabel();
        if (sortedSeasons.includes(currentSeason)) {
            seasonSelect.value = currentSeason;
        } else if (sortedSeasons.length > 0) {
            seasonSelect.value = sortedSeasons[0];
        }

        seasonSelect.addEventListener('change', async () => {
            await renderLeagueTables();
        });

        initialiseLeagueTableSeasonControls();
    }

    initialiseLeagueTablesSquadControls();

    initialiseLeagueTablesAnalysisRail();
    await loadLeagueTablePage();
});

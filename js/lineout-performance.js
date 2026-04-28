(function () {
    const FILTERS_OFFCANVAS_ID = 'lineoutFiltersOffcanvas';
    const LINEOUT_H2H_SPEC_PATH = 'data/charts/lineout_h2h.json';
    const LINEOUT_BREAKDOWN_SOURCE_PATH = 'data/charts/lineout_breakdown_source.json';
    const BREAKDOWN_MIN_ATTEMPTS = 10;

    const PANEL_SPECS = [
        {
            field: 'numbers',
            fieldLabel: 'Numbers',
            linkField: 'numbers',
            isDualAxis: true,
            containerId: 'lineoutPerfBreakdownNumbersChart',
            tableHeadId: 'lineoutPerfBreakdownNumbersTableHead',
            tableBodyId: 'lineoutPerfBreakdownNumbersTableBody',
            path: 'data/charts/lineout_breakdown_numbers.json',
            trendBarContainerId: 'lineoutTrendNumbersBarChart',
            trendLineContainerId: 'lineoutTrendNumbersLineChart',
            trendPath: 'data/charts/lineout_trend_numbers.json',
            emptyMessage: 'Numbers breakdown unavailable.',
            emptyTableMessage: 'No numbers breakdown rows match the current filters.',
            sort: ['4', '5', '6', '7'],
        },
        {
            field: 'area',
            fieldLabel: 'Zone',
            linkField: 'area',
            isDualAxis: true,
            containerId: 'lineoutPerfBreakdownAreaChart',
            tableHeadId: 'lineoutPerfBreakdownAreaTableHead',
            tableBodyId: 'lineoutPerfBreakdownAreaTableBody',
            path: 'data/charts/lineout_breakdown_area.json',
            trendBarContainerId: 'lineoutTrendAreaBarChart',
            trendLineContainerId: 'lineoutTrendAreaLineChart',
            trendPath: 'data/charts/lineout_trend_area.json',
            emptyMessage: 'Zone breakdown unavailable.',
            emptyTableMessage: 'No zone breakdown rows match the current filters.',
            sort: ['Front', 'Middle', 'Back'],
        },
        {
            field: 'jumper',
            fieldLabel: 'Jumper',
            linkField: 'jumper_tier',
            isDualAxis: true,
            singleLegendSection: true,
            containerId: 'lineoutPerfBreakdownJumperChart',
            tableHeadId: 'lineoutPerfBreakdownJumperTableHead',
            tableBodyId: 'lineoutPerfBreakdownJumperTableBody',
            path: 'data/charts/lineout_breakdown_jumper.json',
            trendBarContainerId: 'lineoutTrendJumperBarChart',
            trendLineContainerId: 'lineoutTrendJumperLineChart',
            trendPath: 'data/charts/lineout_trend_jumper.json',
            emptyMessage: 'Jumper breakdown unavailable.',
            emptyTableMessage: 'No jumper breakdown rows match the current filters.',
            sort: '-y',
            fullNameField: 'jumper_name',
        },
        {
            field: 'thrower',
            fieldLabel: 'Thrower',
            linkField: 'thrower_tier',
            isDualAxis: true,
            singleLegendSection: true,
            containerId: 'lineoutPerfBreakdownThrowerChart',
            tableHeadId: 'lineoutPerfBreakdownThrowerTableHead',
            tableBodyId: 'lineoutPerfBreakdownThrowerTableBody',
            path: 'data/charts/lineout_breakdown_thrower.json',
            trendBarContainerId: 'lineoutTrendThrowerBarChart',
            trendLineContainerId: 'lineoutTrendThrowerLineChart',
            trendPath: 'data/charts/lineout_trend_thrower.json',
            emptyMessage: 'Thrower breakdown unavailable.',
            emptyTableMessage: 'No thrower breakdown rows match the current filters.',
            sort: '-y',
            fullNameField: 'thrower_name',
        },
        {
            field: 'play',
            fieldLabel: 'Play',
            linkField: 'play',
            isDualAxis: true,
            containerId: 'lineoutPerfBreakdownPlayChart',
            tableHeadId: 'lineoutPerfBreakdownPlayTableHead',
            tableBodyId: 'lineoutPerfBreakdownPlayTableBody',
            path: 'data/charts/lineout_breakdown_play.json',
            trendBarContainerId: 'lineoutTrendPlayBarChart',
            trendLineContainerId: 'lineoutTrendPlayLineChart',
            trendPath: 'data/charts/lineout_trend_play.json',
            emptyMessage: 'Play breakdown unavailable.',
            emptyTableMessage: 'No play breakdown rows match the current filters.',
            sort: ['Hot', 'Cold', 'Lost'],
            attemptsOnly: true,
        },
        {
            field: 'season',
            fieldLabel: 'Season',
            linkField: 'season',
            isDualAxis: false,
            containerId: 'lineoutPerfBreakdownSeasonChart',
            tableHeadId: 'lineoutPerfBreakdownSeasonTableHead',
            tableBodyId: 'lineoutPerfBreakdownSeasonTableBody',
            path: 'data/charts/lineout_breakdown_season.json',
            trendBarContainerId: null,
            trendLineContainerId: null,
            trendPath: null,
            emptyMessage: 'Season breakdown unavailable.',
            emptyTableMessage: 'No season breakdown rows match the current filters.',
            sort: 'season_asc',
        },
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
    const sectionViewGroups = new Map();
    const sectionLegendDefs = new Map();
    const SECTION_HIGHLIGHT_SIGNAL = '__sectionHighlightKey';
    let lineoutH2HBaseSpec = null;
    let lineoutH2HLayoutKey = null;
    let lineoutBreakdownSourceRows = [];
    let lineoutSeasonStepper = null;
    let lineoutAnalysisRailInitialised = false;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, '&#96;');
    }

    async function fetchJson(path) {
        const separator = path.includes('?') ? '&' : '?';
        const requestPath = `${path}${separator}v=${encodeURIComponent(String(Date.now()))}`;
        const response = await fetch(requestPath, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Failed to fetch ${path} (${response.status})`);
        }
        return response.json();
    }

    function cloneJson(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function splitTrendSpec(baseSpec) {
        const spec = baseSpec && typeof baseSpec === 'object' ? baseSpec : null;
        if (!spec || !Array.isArray(spec.hconcat) || spec.hconcat.length < 2) {
            return { barSpec: spec, lineSpec: null };
        }

        const [barChild, lineChild] = spec.hconcat;
        const base = cloneJson(spec);
        delete base.hconcat;

        const barSpec = { ...cloneJson(base), ...cloneJson(barChild) };
        const lineSpec = { ...cloneJson(base), ...cloneJson(lineChild) };
        return { barSpec, lineSpec };
    }

    function applyAxisOrientation(spec, orient = 'left') {
        if (!spec || typeof spec !== 'object') return;

        if (spec.encoding && spec.encoding.y && spec.encoding.y.axis !== null) {
            spec.encoding.y.axis = {
                ...(spec.encoding.y.axis || {}),
                orient,
            };
        }

        ['layer', 'hconcat', 'vconcat', 'concat'].forEach((key) => {
            const childSpecs = spec[key];
            if (Array.isArray(childSpecs)) {
                childSpecs.forEach((child) => applyAxisOrientation(child, orient));
            }
        });

        if (spec.spec) {
            applyAxisOrientation(spec.spec, orient);
        }
    }

    function disableLegendsDeep(spec) {
        if (!spec || typeof spec !== 'object') return;

        const legendChannels = ['color', 'fill', 'stroke', 'shape', 'size', 'opacity'];
        if (spec.encoding && typeof spec.encoding === 'object') {
            legendChannels.forEach((channel) => {
                const enc = spec.encoding[channel];
                if (enc && typeof enc === 'object') {
                    enc.legend = null;
                }
            });
        }

        ['layer', 'hconcat', 'vconcat', 'concat'].forEach((key) => {
            const childSpecs = spec[key];
            if (Array.isArray(childSpecs)) {
                childSpecs.forEach((child) => disableLegendsDeep(child));
            }
        });

        if (spec.spec) {
            disableLegendsDeep(spec.spec);
        }
    }

    function getDatumLinkValue(item, linkField, panelField) {
        const datum = item && item.datum ? item.datum : null;
        if (!datum) return null;

        const nested = datum && typeof datum === 'object' && datum.datum && typeof datum.datum === 'object'
            ? datum.datum
            : null;

        const directCandidates = [
            linkField,
            panelField,
            `${panelField}_tier`,
            `${panelField}_name`,
            `${panelField}_tier_name`,
        ].filter(Boolean);

        const readFrom = (row) => {
            if (!row || typeof row !== 'object') return null;
            for (const key of directCandidates) {
                if (Object.prototype.hasOwnProperty.call(row, key) && row[key] != null) {
                    return String(row[key]);
                }
            }
            return null;
        };

        return readFrom(datum) || readFrom(nested);
    }

    function addSectionHighlightParam(spec, linkField) {
        if (!spec || typeof spec !== 'object' || !linkField) return;

        if (!Array.isArray(spec.params)) {
            spec.params = [];
        }

        if (!spec.params.some((param) => param && param.name === SECTION_HIGHLIGHT_SIGNAL)) {
            spec.params.push({ name: SECTION_HIGHLIGHT_SIGNAL, value: null });
        }

        if (spec.encoding && typeof spec.encoding === 'object') {
            const existingOpacity = spec.encoding.opacity;
            const existingConditions = [];
            let existingFallback = 1;

            if (existingOpacity && typeof existingOpacity === 'object') {
                if (Array.isArray(existingOpacity.condition)) {
                    existingConditions.push(...existingOpacity.condition);
                } else if (existingOpacity.condition && typeof existingOpacity.condition === 'object') {
                    existingConditions.push(existingOpacity.condition);
                }

                if (typeof existingOpacity.value !== 'undefined') {
                    existingFallback = existingOpacity.value;
                }
            } else if (typeof existingOpacity !== 'undefined') {
                existingFallback = existingOpacity;
            }

            spec.encoding.opacity = {
                condition: [
                    {
                        test: `isValid(${SECTION_HIGHLIGHT_SIGNAL}) && datum["${linkField}"] === ${SECTION_HIGHLIGHT_SIGNAL}`,
                        value: 1,
                    },
                    {
                        test: `isValid(${SECTION_HIGHLIGHT_SIGNAL})`,
                        value: 0.2,
                    },
                    ...existingConditions,
                ],
                value: existingFallback,
            };
        }

        ['layer', 'hconcat', 'vconcat', 'concat'].forEach((key) => {
            const childSpecs = spec[key];
            if (Array.isArray(childSpecs)) {
                childSpecs.forEach((child) => addSectionHighlightParam(child, linkField));
            }
        });

        if (spec.spec) {
            addSectionHighlightParam(spec.spec, linkField);
        }
    }

    function registerSectionViews(spec, viewIds) {
        const ids = viewIds.filter(Boolean);
        if (!ids.length) return;
        sectionViewGroups.set(spec.field, {
            linkField: spec.linkField,
            viewIds: ids,
        });
    }

    function wireSectionInteractivity(spec) {
        const group = sectionViewGroups.get(spec.field);
        if (!group || !group.linkField || !group.viewIds.length) return;

        const linkField = group.linkField;
        const groupViews = group.viewIds.map((id) => views.get(id)).filter(Boolean);
        if (!groupViews.length) return;

        const applyHighlight = (value) => {
            groupViews.forEach((chartView) => {
                try {
                    chartView.signal(SECTION_HIGHLIGHT_SIGNAL, value == null ? null : String(value));
                    chartView.runAsync();
                } catch (error) {
                    console.warn('Unable to update section highlight signal:', error);
                }
            });
        };

        groupViews.forEach((chartView) => {
            if (chartView.__lineoutSectionLinkBound) return;
            chartView.__lineoutSectionLinkBound = true;

            chartView.addEventListener('click', (_event, item) => {
                applyHighlight(getDatumLinkValue(item, linkField, spec.field));
            });

            chartView.addEventListener('dblclick', () => {
                applyHighlight(null);
            });
        });
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
        if (select.classList.contains('selectpicker')) {
            rebuildBootstrapSelect(select);
        }
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

    function getControlValue(id, fallback = 'All') {
        const element = document.getElementById(id);
        return element ? element.value : fallback;
    }

    function seasonDisplayLabel(value) {
        const text = String(value || 'All');
        return text === 'All' ? 'All (2017-)' : text;
    }

    function syncLineoutSeasonStepperFromSelect() {
        if (lineoutSeasonStepper && typeof lineoutSeasonStepper.sync === 'function') {
            lineoutSeasonStepper.sync();
            return;
        }

        const label = document.getElementById('lineoutSeasonLabel');
        if (!label) return;
        label.textContent = seasonDisplayLabel(getControlValue('lineoutFilterSeason', 'All'));
    }

    function renderLineoutActiveFilters() {
        const hosts = Array.from(document.querySelectorAll('[data-lineout-active-filters]'));
        if (!hosts.length) return;

        const gameTypeValue = getControlValue('lineoutFilterGameType', 'All');
        const gameTypeLabel = gameTypeValue === 'League + Cup' ? 'League+Cup' : gameTypeValue;

        const chips = [
            { label: 'Squad', value: `${getControlValue('lineoutFilterSquad', '1st')} XV` },
            { label: 'Season', value: seasonDisplayLabel(getControlValue('lineoutFilterSeason', 'All')) },
            { label: 'Game Type', value: gameTypeLabel },
            { label: 'Numbers', value: getControlValue('lineoutFilterNumbers', 'All') },
            { label: 'Zone', value: getControlValue('lineoutFilterArea', 'All') },
            { label: 'Thrower', value: getControlValue('lineoutFilterThrower', 'All') },
            { label: 'Jumper', value: getControlValue('lineoutFilterJumper', 'All') },
        ].filter((chip) => String(chip.value || '').trim());

        if (window.sharedUi && typeof window.sharedUi.renderOffcanvasFilterChips === 'function') {
            hosts.forEach((host) => {
                window.sharedUi.renderOffcanvasFilterChips({
                    host,
                    offcanvasId: FILTERS_OFFCANVAS_ID,
                    chips,
                    chipClass: 'squad-stats-filter-chip squad-stats-filter-chip-btn',
                });
            });
            return;
        }

        const chipsHtml = chips
            .map((chip) => `<button type="button" class="squad-stats-filter-chip squad-stats-filter-chip-btn" data-bs-toggle="offcanvas" data-bs-target="#${escapeHtml(FILTERS_OFFCANVAS_ID)}" aria-controls="${escapeHtml(FILTERS_OFFCANVAS_ID)}"><strong>${escapeHtml(chip.label)}</strong> ${escapeHtml(chip.value)}</button>`)
            .join('');
        hosts.forEach((host) => {
            host.innerHTML = chipsHtml;
        });
    }

    function rowMatchesAnalysisFilters(row, options = {}) {
        const { includeSeason = true } = options;

        const squad = getControlValue('lineoutFilterSquad');
        if (squad !== 'All' && String(row?.squad || '') !== squad) return false;

        if (includeSeason) {
            const season = getControlValue('lineoutFilterSeason');
            if (season !== 'All' && String(row?.season || '') !== season) return false;
        }

        const gameType = getControlValue('lineoutFilterGameType');
        const allowedGameTypes = getAllowedGameTypes(gameType);
        if (allowedGameTypes && !allowedGameTypes.has(String(row?.game_type || 'Unknown'))) return false;
        if (!allowedGameTypes && gameType !== 'All' && String(row?.game_type || 'Unknown') !== gameType) return false;

        const thrower = getControlValue('lineoutFilterThrower');
        if (thrower !== 'All' && String(row?.thrower || '') !== thrower) return false;

        const jumper = getControlValue('lineoutFilterJumper');
        if (jumper !== 'All' && String(row?.jumper || '') !== jumper) return false;

        const area = getControlValue('lineoutFilterArea');
        if (area !== 'All' && String(row?.area || '') !== area) return false;

        const numbers = getControlValue('lineoutFilterNumbers');
        if (numbers !== 'All' && String(row?.numbers || '') !== numbers) return false;

        return true;
    }

    function sortBreakdownRows(rows, spec) {
        const sortedRows = [...rows];
        if (Array.isArray(spec.sort)) {
            const order = new Map(spec.sort.map((value, index) => [String(value), index]));
            sortedRows.sort((a, b) => {
                const orderA = order.has(a.value) ? order.get(a.value) : Number.MAX_SAFE_INTEGER;
                const orderB = order.has(b.value) ? order.get(b.value) : Number.MAX_SAFE_INTEGER;
                if (orderA !== orderB) return orderA - orderB;
                if (b.attempts !== a.attempts) return b.attempts - a.attempts;
                return a.value.localeCompare(b.value);
            });
            return sortedRows;
        }

        if (spec.sort === 'season_asc') {
            sortedRows.sort((a, b) => seasonSort(a.value, b.value));
            return sortedRows;
        }

        sortedRows.sort((a, b) => {
            if (b.attempts !== a.attempts) return b.attempts - a.attempts;
            return a.value.localeCompare(b.value);
        });
        return sortedRows;
    }

    function aggregateLineoutBreakdownRows(spec) {
        const grouped = new Map();

        lineoutBreakdownSourceRows.filter((row) => rowMatchesAnalysisFilters(row, { includeSeason: false })).forEach((row) => {
            const value = String(row?.[spec.field] || 'Unknown');
            const fullNameValue = spec.fullNameField ? String(row?.[spec.fullNameField] || value) : null;
            const key = spec.fullNameField ? `${value}||${fullNameValue}` : value;
            if (!grouped.has(key)) {
                grouped.set(key, {
                    value,
                    fullNameValue,
                    attempts: 0,
                    won: 0,
                    bySeason: {},
                });
            }

            const entry = grouped.get(key);
            const season = String(row?.season || 'Unknown');
            entry.attempts += 1;
            entry.won += Number(row?.won || 0);
            if (!entry.bySeason[season]) {
                entry.bySeason[season] = { attempts: 0, won: 0 };
            }
            entry.bySeason[season].attempts += 1;
            entry.bySeason[season].won += Number(row?.won || 0);
        });

        return sortBreakdownRows(
            Array.from(grouped.values())
                .map((row) => ({
                    ...row,
                    successRate: row.attempts > 0 ? row.won / row.attempts : 0,
                }))
                .filter((row) => row.attempts >= BREAKDOWN_MIN_ATTEMPTS),
            spec,
        );
    }

    function formatPercentage(value) {
        return `${Math.round(Number(value || 0) * 100)}%`;
    }

    function formatWonAttempts(won, attempts) {
        return `${won}/${attempts}`;
    }

    const BREAKDOWN_BADGE_COLORS = {
        numbers: { '4': { bg: 'var(--accent-color)', fg: 'var(--primary-color)' }, '5': { bg: 'var(--primary-color)', fg: '#fff' }, '6': { bg: '#994C4C', fg: '#fff' }, '7': { bg: 'var(--red-color)', fg: '#fff' } },
        area: { 'Front': { bg: 'var(--red-color)', fg: '#fff' }, 'Middle': { bg: 'var(--amber-color)', fg: 'var(--primary-color)' }, 'Back': { bg: 'var(--green-color)', fg: '#fff' } },
        play: { 'Hot': { bg: '#fff', fg: '#000', border: true }, 'Cold': { bg: 'blue', fg: '#fff' }, 'Lost': { bg: 'var(--red-color)', fg: '#fff' } },
    };

    function renderBreakdownValueCell(spec, row) {
        const badgeColors = BREAKDOWN_BADGE_COLORS[spec.field];
        // If field is "numbers", append "-man" to value in badge, but not in tooltip or table sorting
        const valueForBadge = spec.field === 'numbers' ? `${row.value}-man` : row.value;

        if (badgeColors) {
            const colors = badgeColors[row.value];
            if (colors) {
                const style = `background:${colors.bg};color:${colors.fg};` + (colors.border ? 'border:1px solid #dee2e6;' : '');
                return `<span class="badge rounded-pill" style="${style}">${escapeHtml(valueForBadge)}</span>`;
            }
            return `<span class="badge rounded-pill bg-secondary">${escapeHtml(row.value)}</span>`;
        }

        if (spec.fullNameField) {
            return escapeHtml(row.fullNameValue || row.value);
        }

        return escapeHtml(row.value);
    }

    function renderBreakdownTable(spec) {
        const tableHead = document.getElementById(spec.tableHeadId);
        const tableBody = document.getElementById(spec.tableBodyId);
        if (!tableHead || !tableBody) return;
        tableHead.classList.add('table-dark');

        const rows = aggregateLineoutBreakdownRows(spec);
        const selectedSeason = getControlValue('lineoutFilterSeason', 'All');
        const highlightTotal = selectedSeason === 'All';
        const seasonColumns = spec.field === 'season'
            ? []
            : Array.from(
                new Set(
                    rows.flatMap((row) => Object.keys(row.bySeason || {})),
                ),
            ).sort(seasonSort);

        if (spec.attemptsOnly) {
            // Play table: show attempts only (no won/attempts ratio or success rate).
            const seasonHeaderCells = seasonColumns
                .map((season) => `<th class="text-center ${selectedSeason === season ? 'lineout-breakdown-col-highlight' : ''}">${escapeHtml(season)}</th>`)
                .join('');

            tableHead.innerHTML = `
                <tr>
                    <th>${escapeHtml(spec.fieldLabel)}</th>
                    <th class="text-center ${highlightTotal ? 'lineout-breakdown-col-highlight' : ''}">Total</th>
                    ${seasonHeaderCells}
                </tr>
            `;

            if (!rows.length) {
                const columnCount = 2 + seasonColumns.length;
                tableBody.innerHTML = `<tr><td colspan="${columnCount}" class="text-center">${escapeHtml(spec.emptyTableMessage)}</td></tr>`;
                return;
            }

            tableBody.innerHTML = rows.map((row) => `
                <tr>
                    <td>${renderBreakdownValueCell(spec, row)}</td>
                    <td class="text-end border-end fw-bold ${highlightTotal ? 'lineout-breakdown-col-highlight' : ''}">${row.attempts}</td>
                    ${seasonColumns.map((season) => {
                        const stats = row.bySeason?.[season] || null;
                        const highlightClass = selectedSeason === season ? 'lineout-breakdown-col-highlight' : '';
                        if (!stats || !stats.attempts) {
                            return `<td class="text-end text-muted border-end ${highlightClass}">-</td>`;
                        }
                        return `<td class="text-end border-end ${highlightClass}">${stats.attempts}</td>`;
                    }).join('')}
                </tr>
            `).join('');
            return;
        }

        const seasonHeaderCells = seasonColumns
            .map((season) => `<th class="text-center ${selectedSeason === season ? 'lineout-breakdown-col-highlight' : ''}" colspan="2">${escapeHtml(season)}</th>`)
            .join('');

        tableHead.innerHTML = `
            <tr>
                <th>${escapeHtml(spec.fieldLabel)}</th>
                <th class="text-center ${highlightTotal ? 'lineout-breakdown-col-highlight' : ''}" colspan="2">Total Success</th>
                ${seasonHeaderCells}
            </tr>
        `;

        if (!rows.length) {
            const columnCount = 3 + (seasonColumns.length * 2);
            tableBody.innerHTML = `<tr><td colspan="${columnCount}" class="text-center">${escapeHtml(spec.emptyTableMessage)}</td></tr>`;
            return;
        }

        tableBody.innerHTML = rows.map((row) => `
            <tr>
                <td>${renderBreakdownValueCell(spec, row)}</td>
                <td class="text-end ${highlightTotal ? 'lineout-breakdown-col-highlight' : ''}">${row.won}/${row.attempts}</td>
                <td class="border-end text-end fw-bold ${highlightTotal ? 'lineout-breakdown-col-highlight' : ''}" title="${escapeAttribute(formatPercentage(row.successRate))}">${escapeHtml(formatPercentage(row.successRate))}</td>
                ${seasonColumns.map((season) => {
                    const stats = row.bySeason?.[season] || null;
                    const highlightClass = selectedSeason === season ? 'lineout-breakdown-col-highlight' : '';
                    if (!stats || !stats.attempts) {
                        return `<td class="text-end text-muted ${highlightClass}">-</td><td class="text-end text-muted ${highlightClass}">-</td>`;
                    }
                    const seasonSuccess = stats.won / stats.attempts;
                    return `<td class="text-end ${highlightClass}">${stats.won}/${stats.attempts}</td><td class="border-end text-end fw-bold ${highlightClass}" title="${escapeAttribute(formatPercentage(seasonSuccess))}">${escapeHtml(formatPercentage(seasonSuccess))}</td>`;
                }).join('')}
            </tr>
        `).join('');
    }

    function renderBreakdownTables() {
        PANEL_SPECS.forEach(renderBreakdownTable);
    }

    async function applyFiltersToViews() {
        const pending = [];

        PANEL_SPECS.forEach(({ containerId, trendBarContainerId, trendLineContainerId }) => {
            [containerId, trendBarContainerId, trendLineContainerId].forEach((id) => {
                if (!id) return;
                const view = views.get(id);
                if (!view) return;
                Object.entries(ANALYSIS_SIGNAL_IDS).forEach(([signalName, controlId]) => {
                    setSignalFromControl(view, signalName, controlId);
                });
                pending.push(view.runAsync());
            });
        });

        const successView = views.get('setPieceLineoutChart');
        if (successView) {
            setSignalFromControl(successView, 'spSquadParam', 'lineoutFilterSquad');
            pending.push(successView.runAsync());
        }

        await Promise.all(pending);
        renderBreakdownTables();
        renderLineoutActiveFilters();
        refreshConsolidatedLegends();
    }

    async function loadFilterOptions() {
        const lineoutSource = await fetchJson(LINEOUT_BREAKDOWN_SOURCE_PATH);
        lineoutBreakdownSourceRows = Array.isArray(lineoutSource) ? lineoutSource : [];

        populateSelect(
            'lineoutFilterSeason',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.season || '')).filter(Boolean))).sort(seasonSort).reverse(),
            'All (2017-)',
        );
        populateSelect(
            'lineoutFilterThrower',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.thrower || 'Unknown')))).sort(),
            'All Throwers',
        );
        populateSelect(
            'lineoutFilterJumper',
            Array.from(new Set(lineoutBreakdownSourceRows.map((row) => String(row?.jumper || 'Unknown')))).sort(),
            'All Jumpers',
        );
        populateSelect(
            'lineoutFilterArea',
            ['Front', 'Middle', 'Back'].filter((value) => lineoutBreakdownSourceRows.some((row) => String(row?.area || '') === value)),
            'All Zones',
        );
        populateSelect(
            'lineoutFilterNumbers',
            ['4', '5', '6', '7'].filter((value) => lineoutBreakdownSourceRows.some((row) => String(row?.numbers || '') === value)),
            'All Numbers',
        );

        const h2hOppositionSelect = document.getElementById('h2hFilterOpposition');
        if (h2hOppositionSelect) {
            const [setPieceRaw, gamesRaw] = await Promise.all([
                fetchJson('data/backend/set_piece.json'),
                fetchJson('data/backend/games.json'),
            ]);
            const gamesById = new Map((Array.isArray(gamesRaw) ? gamesRaw : []).map((game) => [game.game_id, game]));
            const setPieceRows = (Array.isArray(setPieceRaw) ? setPieceRaw : []).map((row) => {
                const game = gamesById.get(row.game_id) || {};
                return { opposition_club: toOppositionClubName(row.opposition || game.opposition || 'Unknown') };
            });
            populateSelect('h2hFilterOpposition', Array.from(new Set(setPieceRows.map((row) => row.opposition_club))).sort(), 'All Opponents');
        }
    }

    function getLegendContainerId(field) {
        if (field === 'jumper') return 'lineoutJumperLegend';
        if (field === 'thrower') return 'lineoutThrowerLegend';
        return null;
    }

    function findColorEncoding(spec) {
        if (!spec || typeof spec !== 'object') return null;

        if (spec.encoding && spec.encoding.color && typeof spec.encoding.color === 'object') {
            return spec.encoding.color;
        }

        const childKeys = ['layer', 'hconcat', 'vconcat', 'concat'];
        for (const key of childKeys) {
            const children = spec[key];
            if (!Array.isArray(children)) continue;
            for (const child of children) {
                const found = findColorEncoding(child);
                if (found) return found;
            }
        }

        if (spec.spec) {
            return findColorEncoding(spec.spec);
        }

        return null;
    }

    function extractLegendDefinitionFromSpec(spec) {
        const colorEncoding = findColorEncoding(spec);
        if (!colorEncoding) return null;

        const scale = colorEncoding.scale && typeof colorEncoding.scale === 'object'
            ? colorEncoding.scale
            : {};
        const domain = Array.isArray(scale.domain) ? scale.domain : [];
        const range = Array.isArray(scale.range) ? scale.range : [];
        if (!domain.length) return null;

        return {
            title: String(colorEncoding.title || ''),
            items: domain.map((value, index) => ({
                label: String(value),
                color: typeof range[index] === 'string' ? range[index] : '#7d96e8',
            })),
        };
    }

    function refreshConsolidatedLegends() {
        ['jumper', 'thrower'].forEach((field) => {
            const containerId = getLegendContainerId(field);
            const legendDef = sectionLegendDefs.get(field);
            if (!containerId || !legendDef) return;
            renderConsolidatedLegend(containerId, legendDef);
        });
    }

    function renderConsolidatedLegend(containerId, legendDef) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const items = legendDef && Array.isArray(legendDef.items) ? legendDef.items : [];
        if (!items.length) {
            container.innerHTML = '';
            return;
        }

        const title = legendDef && legendDef.title ? legendDef.title : 'Legend';
        const legendHtml = `
            <div class="lineout-section-legend-box" role="group" aria-label="${escapeAttribute(title)} legend">
                <p class="lineout-section-legend-title">${escapeHtml(title)}</p>
                <div class="lineout-section-legend-row">
                    ${items.map((item) => `
                        <span class="lineout-section-legend-item">
                            <span class="lineout-section-legend-symbol" style="background:${escapeAttribute(item.color)};"></span>
                            <span class="lineout-section-legend-text">${escapeHtml(item.label)}</span>
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
        container.innerHTML = legendHtml;
    }

    async function loadInteractiveCharts() {
        await Promise.all(PANEL_SPECS.map(async (panelSpec) => {
            const {
                field,
                isDualAxis,
                singleLegendSection,
                linkField,
                containerId,
                path,
                emptyMessage,
                trendContainerId,
                trendPath,
                trendBarContainerId,
                trendLineContainerId,
            } = panelSpec;

            const viewIds = [];
            const breakdownContainer = document.getElementById(containerId);
            const breakdownSpec = await fetchJson(path);
            let legendSourceSpec = breakdownSpec;
            addSectionHighlightParam(breakdownSpec, linkField);
            if (singleLegendSection) {
                disableLegendsDeep(breakdownSpec);
            }
            if (!isDualAxis) {
                applyAxisOrientation(breakdownSpec, 'left');
            }

            if (breakdownContainer) {
                const breakdownView = await embedChartSpec(breakdownContainer, breakdownSpec, {
                    containerId,
                    emptyMessage,
                });
                if (breakdownView) {
                    views.set(containerId, breakdownView);
                    viewIds.push(containerId);
                }
            }

            if (trendPath && (trendBarContainerId || trendContainerId)) {
                const trendSpec = await fetchJson(trendPath);
                const { barSpec, lineSpec } = splitTrendSpec(trendSpec);
                const trendBarId = trendBarContainerId || trendContainerId;
                const trendBarContainer = document.getElementById(trendBarId);

                if (barSpec) {
                    addSectionHighlightParam(barSpec, linkField);
                    applyAxisOrientation(barSpec, 'left');
                    legendSourceSpec = barSpec;
                    if (singleLegendSection) {
                        disableLegendsDeep(barSpec);
                    }
                }

                if (trendBarContainer && barSpec) {
                    const barView = await embedChartSpec(trendBarContainer, barSpec, {
                        containerId: trendBarId,
                        emptyMessage: `${emptyMessage.replace('breakdown', 'trend')} (bar panel unavailable).`,
                    });
                    if (barView) {
                        views.set(trendBarId, barView);
                        viewIds.push(trendBarId);
                    }
                }

                if (trendLineContainerId) {
                    const trendLineContainer = document.getElementById(trendLineContainerId);
                    if (trendLineContainer) {
                        if (lineSpec) {
                            addSectionHighlightParam(lineSpec, linkField);
                            applyAxisOrientation(lineSpec, 'left');
                            if (singleLegendSection) {
                                disableLegendsDeep(lineSpec);
                            }

                            const lineView = await embedChartSpec(trendLineContainer, lineSpec, {
                                containerId: trendLineContainerId,
                                emptyMessage: `${emptyMessage.replace('breakdown', 'trend')} (line panel unavailable).`,
                            });
                            if (lineView) {
                                views.set(trendLineContainerId, lineView);
                                viewIds.push(trendLineContainerId);
                            }
                        } else {
                            trendLineContainer.innerHTML = '<div class="text-center text-muted py-4">Line trend unavailable.</div>';
                        }
                    }
                }
            }

            registerSectionViews(panelSpec, viewIds);
            if (field !== 'season') {
                wireSectionInteractivity(panelSpec);
            }

            // Render a single section legend from chart tier domains (top names + Other)
            if (singleLegendSection) {
                const legendDef = extractLegendDefinitionFromSpec(legendSourceSpec);
                if (legendDef) {
                    sectionLegendDefs.set(field, legendDef);
                    const legendContainerId = getLegendContainerId(field);
                    if (legendContainerId) {
                        renderConsolidatedLegend(legendContainerId, legendDef);
                    }
                }
            }
        }));
    }

    function initialiseLineoutAnalysisRail() {
        if (lineoutAnalysisRailInitialised || typeof initialiseAnalysisRail !== 'function') {
            return;
        }
        lineoutAnalysisRailInitialised = initialiseAnalysisRail({
            railId: 'lineoutDeepDiveAnalysisRail',
        });
    }

    async function setupLineoutPage() {
        const controlIds = [
            'lineoutFilterSquad', 'lineoutFilterSeason', 'lineoutFilterGameType',
            'lineoutFilterThrower', 'lineoutFilterJumper', 'lineoutFilterArea',
            'lineoutFilterNumbers',
            'h2hFilterOpposition', 'h2hFilterTeamHighlight', 'h2hFilterOutcomeHighlight',
        ];

        await loadFilterOptions();

        if (window.sharedUi && typeof window.sharedUi.bindSegmentToSelect === 'function') {
            window.sharedUi.bindSegmentToSelect({
                segment: 'lineoutSquadSegment',
                select: 'lineoutFilterSquad',
            });

            window.sharedUi.bindSegmentToSelect({
                segment: 'lineoutGameTypeSegment',
                select: 'lineoutFilterGameType',
            });
        }

        if (window.sharedUi && typeof window.sharedUi.attachSeasonStepper === 'function') {
            lineoutSeasonStepper = window.sharedUi.attachSeasonStepper({
                select: 'lineoutFilterSeason',
                label: 'lineoutSeasonLabel',
                prevButton: 'lineoutSeasonPrev',
                nextButton: 'lineoutSeasonNext',
                formatLabel: (value) => seasonDisplayLabel(value),
            });
        }
        syncLineoutSeasonStepperFromSelect();

        document.querySelectorAll('#lineoutFiltersOffcanvas .selectpicker').forEach((select) => {
            rebuildBootstrapSelect(select);
        });

        await loadInteractiveCharts();
        await applyFiltersToViews();

        controlIds.forEach((id) => {
            const element = document.getElementById(id);
            if (!element) return;
            element.addEventListener('change', () => {
                enforceH2HFilterExclusivity(id);
                if (id === 'lineoutFilterSeason') {
                    syncLineoutSeasonStepperFromSelect();
                }
                applyFiltersToViews().catch((error) => {
                    console.error('Unable to apply lineout page filters:', error);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        const lineoutSuccessView = await renderChartSpecFromPath('setPieceLineoutChart', 'data/charts/set_piece_success_lineout.json', 'Lineout success chart unavailable.');
        if (lineoutSuccessView) views.set('setPieceLineoutChart', lineoutSuccessView);

        await renderSplitSetPiecePanelsFromSingleSpec('data/charts/set_piece_success_lineout.json', [
            { containerId: 'setPiece1stLineoutChart', squad: '1st', emptyMessage: '1st XV lineout chart unavailable.' },
            { containerId: 'setPiece2ndLineoutChart', squad: '2nd', emptyMessage: '2nd XV lineout chart unavailable.' },
        ]);

        const hasLineoutFilters = Boolean(document.getElementById('lineoutFilterSquad') || document.getElementById('lineoutFilterSeason') || document.getElementById('lineoutFilterGameType'));
        const hasLineoutDeepDiveCharts = Boolean(document.getElementById('lineoutH2HChart') || document.getElementById('lineoutPerfBreakdownNumbersChart'));

        if (hasLineoutFilters || hasLineoutDeepDiveCharts) {
            await setupLineoutPage();
        }

        initialiseLineoutAnalysisRail();
        
    });
})();
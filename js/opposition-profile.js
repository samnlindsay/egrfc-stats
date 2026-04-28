(function () {
    const TEAM_SHEETS_SPEC_PATH = 'data/charts/opposition_profile_team_sheets.json';
    const RESULTS_SPEC_PATH = 'data/charts/opposition_results.json';
    const LINEOUT_H2H_SPEC_PATH = 'data/charts/lineout_h2h.json';
    const SCRUM_H2H_SPEC_PATH = 'data/charts/scrum_h2h.json';

    let gamesRows = [];
    let teamSheetsSpec = null;
    let resultsSpec = null;
    let lineoutH2HSpec = null;
    let scrumH2HSpec = null;

    let lineoutH2HView = null;
    let scrumH2HView = null;
    let currentOppositionClub = null;
    let clubLogosManifest = {};
    let oppositionProfileAnalysisRailInitialised = false;
    let oppositionFinderRows = [];
    let oppositionHistoryRows = [];
    const oppositionFinderPagination = {
        page: 1,
        pageSize: 10,
    };
    const oppositionHistoryPagination = {
        page: 1,
        pageSize: 10,
    };
    const oppositionFinderSort = {
        key: 'stats.played',
        direction: 'desc',
    };
    const oppositionHistorySort = {
        key: 'date',
        direction: 'desc',
    };
    let currentSetPieceType = 'lineout';

    function normaliseLogoKey(name) {
        return String(name || '')
            .toLowerCase()
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/&/g, ' and ')
            .replace(/\b(?:rugby football club|football club|rugby club|rfc|fc|club)\b/g, ' ')
            .replace(/\b(?:1st|2nd|3rd|4th|5th|ii|iii|iv|v|vi|vii|viii|ix|x)\b/g, ' ')
            .replace(/\b(?:xv|xvii?)\b/g, ' ')
            .replace(/\band\b/g, ' ')
            .replace(/[^a-z0-9]+/g, '');
    }

    function baseClubName(name) {
        const text = String(name || 'Unknown').trim();
        return text.replace(/\s+(?:I{1,6}|[1-6](?:st|nd|rd|th)?|A|B)(?:\s+XV)?$/i, '').trim();
    }

    function getClubLogoSrc(name) {
        const clubName = String(name || '').trim();
        if (!clubName) return '';

        const keys = [
            normaliseLogoKey(clubName),
            normaliseLogoKey(baseClubName(clubName)),
        ].filter(Boolean);

        for (const key of keys) {
            if (key in clubLogosManifest) {
                return `img/logos/${clubLogosManifest[key]}`;
            }
        }

        return '';
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function toOppositionClubName(opposition) {
        const text = String(opposition || 'Unknown').trim();
        const club = text.replace(/\s+(?:I{1,6}|[1-6](?:st|nd|rd|th)?|A|B)(?:\s+XV)?$/i, '').trim();
        return club || 'Unknown';
    }

    function normaliseResult(row) {
        const result = String(row?.result || '').trim().toUpperCase();
        if (result === 'W' || result === 'D' || result === 'L') return result;
        return '-';
    }

    function resultBadgeHtml(result) {
        const value = String(result || '-').trim().toUpperCase();
        const cssClass = value === 'W'
            ? 'result-badge--win'
            : value === 'L'
                ? 'result-badge--loss'
                : value === 'D'
                    ? 'result-badge--draw'
                    : '';
        if (!cssClass) return value;
        return `<span class="result-badge ${cssClass}">${value}</span>`;
    }

    function formatDisplayDate(value) {
        const raw = String(value || '').trim();
        if (!raw) return '-';
        const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        const date = match
            ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
            : new Date(raw);
        if (Number.isNaN(date.getTime())) return raw;
        return date.toLocaleDateString('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
        });
    }

    function ordinalSuffix(day) {
        const n = Number(day);
        if (!Number.isFinite(n)) return '';
        const mod100 = n % 100;
        if (mod100 >= 11 && mod100 <= 13) return 'th';
        const mod10 = n % 10;
        if (mod10 === 1) return 'st';
        if (mod10 === 2) return 'nd';
        if (mod10 === 3) return 'rd';
        return 'th';
    }

    function formatDisplayDateLongOrdinal(value) {
        const raw = String(value || '').trim();
        if (!raw) return '-';
        const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        const date = match
            ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
            : new Date(raw);
        if (Number.isNaN(date.getTime())) return raw;
        const day = date.getDate();
        const month = date.toLocaleDateString('en-GB', { month: 'long' });
        const year = date.getFullYear();
        return `${day}${ordinalSuffix(day)} ${month} ${year}`;
    }

    function eastGrinsteadTeamLabel(squad) {
        if (squad === '1st') return 'East Grinstead 1st XV';
        if (squad === '2nd') return 'East Grinstead 2nd XV';
        return 'East Grinstead XV';
    }

    function buildLastMatchSummary(filteredGames) {
        if (!Array.isArray(filteredGames) || !filteredGames.length) return '-';
        const latest = filteredGames.slice().sort(dateSortDesc)[0];
        if (!latest) return '-';

        const dateLabel = formatDisplayDateLongOrdinal(latest?.date);
        const teamLabel = eastGrinsteadTeamLabel(String(latest?.squad || '').trim());
        const opposition = String(latest?.opposition || currentOppositionClub || 'Unknown').trim();

        const pf = Number(latest?.score_for);
        const pa = Number(latest?.score_against);
        const hasScore = Number.isFinite(pf) && Number.isFinite(pa);
        const scoreLabel = hasScore ? `${pf} - ${pa}` : '-';

        const competition = String(
            latest?.league || latest?.competition || latest?.competition_name || latest?.game_type || ''
        ).trim();

        const result = normaliseResult(latest);
        const resultClass = result === 'W'
            ? 'result-badge--win'
            : result === 'L'
                ? 'result-badge--loss'
                : result === 'D'
                    ? 'result-badge--draw'
                    : '';

        const dateHtml = `<span style="font-weight: 700; color: var(--primary-color);">${escapeHtml(dateLabel)}</span>`;
        const teamHtml = `<span style="font-weight: 700; color: #1f2a4a;">${escapeHtml(teamLabel)}</span>`;
        const scoreHtml = resultClass
            ? `<span class="result-badge ${resultClass}" style="font-weight: 800;">${escapeHtml(scoreLabel)}</span>`
            : `<span style="font-weight: 800; color: #111111;">${escapeHtml(scoreLabel)}</span>`;
        const oppositionHtml = `<span style="font-weight: 700; color: #1f2a4a;">${escapeHtml(opposition)}</span>`;
        const competitionHtml = competition
            ? `<span style="color: #5d6780;">${escapeHtml(competition)}</span>`
            : '';
        const separatorHtml = '<span style="display: inline-block; margin: 0 0.5rem; color: #8a92a7;">|</span>';
        const fullResultHtml = `${teamHtml} ${scoreHtml} ${oppositionHtml}`;

        return competition
          ? `${dateHtml}${separatorHtml}${competitionHtml}<br>${fullResultHtml}`
          : `${dateHtml}${separatorHtml}${scoreHtml}<br>${fullResultHtml}`;
    }

    function squadPillHtml(squad) {
        if (squad === '1st') return '<span class="squad-pill squad-pill--1st">1st XV</span>';
        if (squad === '2nd') return '<span class="squad-pill squad-pill--2nd">2nd XV</span>';
        return '<span class="squad-pill squad-pill--unknown">Unknown</span>';
    }

    function updateOppositionUrl(oppositionClub) {
        const url = new URL(window.location.href);
        if (oppositionClub) {
            url.searchParams.set('opposition', oppositionClub);
        } else {
            url.searchParams.delete('opposition');
        }
        window.history.replaceState({}, '', url.toString());
    }

    function syncOppositionSelectUI(oppositionClub) {
        const select = document.getElementById('oppositionSelect');
        if (!select) return;
        select.value = oppositionClub || '';
        rebuildBootstrapSelect(select);
    }

    function parseIsoDate(value) {
        const raw = String(value || '').trim();
        const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
        const d = new Date(raw);
        return Number.isNaN(d.getTime()) ? null : d;
    }

    function hasRecordedResult(row) {
        const resultText = String(row?.result || '').trim();
        return resultText !== '' && resultText !== '-';
    }

    function findSquadHeroFixtures(squad) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const squadGames = gamesRows
            .filter((row) => String(row?.squad || '').trim() === squad)
            .map((row) => ({ row, date: parseIsoDate(row?.date) }))
            .filter((item) => item.date instanceof Date)
            .sort((a, b) => a.date - b.date);

        if (!squadGames.length) return { next: null, last: null };

        const upcoming = squadGames.filter(
            (item) => item.date > today && !hasRecordedResult(item.row)
        );
        const next = upcoming[0]?.row || null;

        const completed = squadGames
            .filter((item) => item.date <= today || hasRecordedResult(item.row))
            .sort((a, b) => b.date - a.date);
        const last = completed[0]?.row || null;

        return { next, last };
    }

    function heroFixtureNote(row, fallbackText = '') {
        if (!row) return fallbackText || '-';
        const dateText = formatDisplayDate(row?.date);
        const venue = String(row?.home_away || '').toUpperCase() === 'A' ? 'Away' : 'Home';
        return `${dateText} | ${venue}`;
    }

    function renderHeroMetricCard(container, row, fallbackRow = null) {
        if (!container) return;
        const clickRow = row || fallbackRow;

        if (!clickRow) {
            container.innerHTML = '<span class="opposition-hero-action-card is-empty">No fixture</span>';
            return;
        }

        const club = toOppositionClubName(clickRow?.opposition);
        const note = row
            ? heroFixtureNote(row)
            : `${heroFixtureNote(fallbackRow)} | latest available`;

        container.innerHTML = `<button type="button" class="opposition-hero-action-card" data-opposition-hero-select="${escapeHtml(club)}"><span class="opposition-hero-action-value">${escapeHtml(club)}</span><span class="opposition-hero-action-note">${escapeHtml(note)}</span></button>`;
    }

    function renderOppositionHeroQuickLinks() {
        const first = findSquadHeroFixtures('1st');
        const second = findSquadHeroFixtures('2nd');

        const firstNextHost = document.getElementById('oppositionHero1stNext');
        const firstLastHost = document.getElementById('oppositionHero1stLast');
        const secondNextHost = document.getElementById('oppositionHero2ndNext');
        const secondLastHost = document.getElementById('oppositionHero2ndLast');

        renderHeroMetricCard(firstNextHost, first.next, first.last);
        renderHeroMetricCard(firstLastHost, first.last, null);
        renderHeroMetricCard(secondNextHost, second.next, second.last);
        renderHeroMetricCard(secondLastHost, second.last, null);
    }

    function bindOppositionHeroQuickLinks() {
        const metrics = document.querySelector('.ux-hero-metrics');
        if (!metrics || metrics.__oppositionHeroLinksBound) return;
        metrics.__oppositionHeroLinksBound = true;
        metrics.addEventListener('click', (event) => {
            const trigger = event.target.closest('[data-opposition-hero-select]');
            if (!trigger) return;
            const club = String(trigger.getAttribute('data-opposition-hero-select') || '').trim();
            if (!club) return;
            syncOppositionSelectUI(club);
            renderOppositionProfile(club).catch((error) => {
                console.error('Failed to render opposition profile:', error);
                showError('Unable to render opposition profile.');
            });
            const profileSection = document.getElementById('opposition-profile');
            if (profileSection) profileSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    function renderOppositionActiveFilters(_oppositionClub) {
        // No per-section filter chips on this page — selection is inline via the dropdown.
    }

    function setChartPlaceholder(containerId, message) {
        const container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return;
        container.innerHTML = `<p class="chart-section-hint mb-0">${escapeHtml(message)}</p>`;
        container.classList.add('chart-host--showing-placeholder');
    }

    function clearChartPlaceholder(container) {
        container.innerHTML = '';
        container.classList.remove('chart-host--showing-placeholder');
    }

    function toggleOverviewState(hasSelection) {
        const contentWrap = document.getElementById('oppositionProfileContentWrap');
        if (contentWrap) contentWrap.classList.toggle('d-none', !hasSelection);

        const detailLinks = document.querySelectorAll('.opposition-profile-rail-detail');
        detailLinks.forEach((link) => link.classList.toggle('d-none', !hasSelection));

        // Nudge the shared rail refresh path after visibility changes.
        window.dispatchEvent(new Event('resize'));
    }

    function venueLabel(homeAway) {
        return String(homeAway || '').toUpperCase() === 'H' ? 'Home' : 'Away';
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = String(value ?? '-');
    }

    function setHtml(id, value) {
        const element = document.getElementById(id);
        if (element) element.innerHTML = String(value ?? '-');
    }

    function renderOppositionHero(oppositionClub) {
        const nameElement = document.getElementById('oppositionProfileHeroName');
        if (nameElement) {
            nameElement.textContent = String(oppositionClub || 'Unknown');
        }

        const logoWrap = document.getElementById('oppositionProfileHeroLogoWrap');
        if (!logoWrap) return;

        const logoSrc = getClubLogoSrc(oppositionClub);
        if (!logoSrc) {
            logoWrap.classList.add('match-info-team-logo-wrap--empty');
            logoWrap.innerHTML = '';
            return;
        }

        logoWrap.classList.remove('match-info-team-logo-wrap--empty');
        logoWrap.innerHTML = `<img class="match-info-team-logo" src="${escapeHtml(logoSrc)}" alt="${escapeHtml(oppositionClub)} club logo" loading="lazy">`;
    }

    function getOppositionStats(filteredGames) {
        return filteredGames.reduce((acc, row) => {
            const result = normaliseResult(row);
            if (result === 'W' || result === 'D' || result === 'L') {
                acc.played += 1;
                if (result === 'W') acc.won += 1;
                if (result === 'D') acc.drawn += 1;
                if (result === 'L') acc.lost += 1;
            }
            return acc;
        }, { won: 0, drawn: 0, lost: 0, played: 0 });
    }

    function oppositionSort(a, b) {
        return String(a).localeCompare(String(b), undefined, { sensitivity: 'base' });
    }

    function getNestedValue(row, path) {
        return String(path || '').split('.').reduce((value, key) => value?.[key], row);
    }

    function compareOppositionFinderValues(a, b, key) {
        const valueA = getNestedValue(a, key);
        const valueB = getNestedValue(b, key);

        if (typeof valueA === 'number' || typeof valueB === 'number') {
            const numberA = Number(valueA ?? 0);
            const numberB = Number(valueB ?? 0);
            if (numberA !== numberB) return numberA - numberB;
            return oppositionSort(a.club, b.club);
        }

        return oppositionSort(String(valueA ?? ''), String(valueB ?? ''));
    }

    function sortOppositionFinderRows(rows) {
        const directionFactor = oppositionFinderSort.direction === 'asc' ? 1 : -1;
        const key = oppositionFinderSort.key;
        return rows.slice().sort((a, b) => compareOppositionFinderValues(a, b, key) * directionFactor);
    }

    function updateOppositionFinderSortHeaderUI() {
        document.querySelectorAll('[data-opposition-sort]').forEach((button) => {
            const key = String(button.getAttribute('data-opposition-sort') || '');
            const label = String(button.getAttribute('data-opposition-sort-label') || key);
            const isActive = key === oppositionFinderSort.key;
            const direction = isActive ? oppositionFinderSort.direction : 'none';
            const indicator = button.querySelector('.database-sort-indicator');
            if (indicator) {
                indicator.textContent = isActive ? (direction === 'asc' ? '▲' : '▼') : '';
            }
            button.setAttribute('aria-label', `${label}${isActive ? ` sorted ${direction === 'asc' ? 'ascending' : 'descending'}` : ''}`);
            const th = button.closest('th');
            if (th) th.setAttribute('aria-sort', isActive ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
        });
    }

    function setOppositionFinderSort(key) {
        if (!key) return;
        if (oppositionFinderSort.key === key) {
            oppositionFinderSort.direction = oppositionFinderSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            oppositionFinderSort.key = key;
            oppositionFinderSort.direction = key === 'club' ? 'asc' : 'desc';
        }
        oppositionFinderPagination.page = 1;
    }

    function dateSortDesc(a, b) {
        return String(b?.date || '').localeCompare(String(a?.date || ''));
    }

    function compareOppositionHistoryValues(a, b, key) {
        const getCompetition = (row) => String(
            row?.league || row?.competition || row?.competition_name || row?.game_type || ''
        ).trim();
        const getCaptain = (row) => String(row?.captain || '').trim();
        const getVenue = (row) => venueLabel(row?.home_away);
        const getResult = (row) => {
            const result = normaliseResult(row);
            const order = { W: 3, D: 2, L: 1, '-': 0 };
            return order[result] ?? -1;
        };

        if (key === 'date') {
            return String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        if (key === 'squad') {
            const squadOrder = { '1st': 1, '2nd': 2 };
            const diff = (squadOrder[a?.squad] ?? 99) - (squadOrder[b?.squad] ?? 99);
            return diff || String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        if (key === 'competition') {
            const diff = oppositionSort(getCompetition(a), getCompetition(b));
            return diff || String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        if (key === 'venue') {
            const diff = oppositionSort(getVenue(a), getVenue(b));
            return diff || String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        if (key === 'result') {
            const diff = getResult(a) - getResult(b);
            return diff || String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        if (key === 'captain') {
            const diff = oppositionSort(getCaptain(a), getCaptain(b));
            return diff || String(a?.date || '').localeCompare(String(b?.date || ''));
        }
        return 0;
    }

    function sortOppositionHistoryRows(rows) {
        const directionFactor = oppositionHistorySort.direction === 'asc' ? 1 : -1;
        const key = oppositionHistorySort.key;
        return rows.slice().sort((a, b) => compareOppositionHistoryValues(a, b, key) * directionFactor);
    }

    function updateOppositionHistorySortHeaderUI() {
        document.querySelectorAll('[data-opposition-history-sort]').forEach((button) => {
            const key = String(button.getAttribute('data-opposition-history-sort') || '');
            const label = String(button.getAttribute('data-opposition-history-sort-label') || key);
            const isActive = key === oppositionHistorySort.key;
            const direction = isActive ? oppositionHistorySort.direction : 'none';
            const indicator = button.querySelector('.database-sort-indicator');
            if (indicator) {
                indicator.textContent = isActive ? (direction === 'asc' ? '▲' : '▼') : '';
            }
            button.setAttribute('aria-label', `${label}${isActive ? ` sorted ${direction === 'asc' ? 'ascending' : 'descending'}` : ''}`);
            const th = button.closest('th');
            if (th) th.setAttribute('aria-sort', isActive ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
        });
    }

    function setOppositionHistorySort(key) {
        if (!key) return;
        if (oppositionHistorySort.key === key) {
            oppositionHistorySort.direction = oppositionHistorySort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            oppositionHistorySort.key = key;
            oppositionHistorySort.direction = key === 'date' ? 'desc' : 'asc';
        }
        oppositionHistoryPagination.page = 1;
    }

    function getOppositionHistoryPagedRows() {
        const pageSize = oppositionHistoryPagination.pageSize;
        const total = oppositionHistoryRows.length;
        const pageCount = Math.max(1, Math.ceil(total / pageSize));
        const page = Math.min(pageCount, Math.max(1, oppositionHistoryPagination.page));
        oppositionHistoryPagination.page = page;
        const start = (page - 1) * pageSize;
        return {
            total,
            page,
            pageCount,
            start,
            rows: oppositionHistoryRows.slice(start, start + pageSize),
        };
    }

    function renderOppositionHistoryPaginationSummary(paged) {
        const summary = document.getElementById('oppositionHistoryPaginationSummary');
        if (!summary) return;
        if (!paged.total) {
            summary.textContent = '0 matches';
            return;
        }
        const from = paged.start + 1;
        const to = paged.start + paged.rows.length;
        summary.textContent = `${from}-${to} of ${paged.total} matches`;
    }

    function syncOppositionHistoryPaginationButtons(paged) {
        const prevBtn = document.getElementById('oppositionHistoryPrev');
        const nextBtn = document.getElementById('oppositionHistoryNext');
        if (prevBtn) prevBtn.disabled = paged.page <= 1;
        if (nextBtn) nextBtn.disabled = paged.page >= paged.pageCount;
    }

    function clubCountsFromGames(rows) {
        const byClub = new Map();
        (Array.isArray(rows) ? rows : []).forEach((row) => {
            const club = toOppositionClubName(row?.opposition);
            if (!byClub.has(club)) {
                byClub.set(club, []);
            }
            byClub.get(club).push(row);
        });
        return byClub;
    }

    function getOppositionFinderRows(rowsByClub) {
        const rows = Array.from(rowsByClub.entries())
            .map(([club, rows]) => {
                const stats = getOppositionStats(rows);
                const stats1st = rows.reduce((acc, row) => {
                    if (row?.squad === '1st') {
                        const result = normaliseResult(row);
                        if (result === 'W' || result === 'D' || result === 'L') {
                            acc.played += 1;
                            if (result === 'W') acc.won += 1;
                            if (result === 'D') acc.drawn += 1;
                            if (result === 'L') acc.lost += 1;
                        }
                    }
                    return acc;
                }, { won: 0, drawn: 0, lost: 0, played: 0 });
                const stats2nd = rows.reduce((acc, row) => {
                    if (row?.squad === '2nd') {
                        const result = normaliseResult(row);
                        if (result === 'W' || result === 'D' || result === 'L') {
                            acc.played += 1;
                            if (result === 'W') acc.won += 1;
                            if (result === 'D') acc.drawn += 1;
                            if (result === 'L') acc.lost += 1;
                        }
                    }
                    return acc;
                }, { won: 0, drawn: 0, lost: 0, played: 0 });

                const winPct = stats.played > 0 ? (stats.won / stats.played) * 100 : null;

                return {
                    club,
                    stats: {
                        ...stats,
                        win_pct: winPct,
                    },
                    stats1st,
                    stats2nd,
                    logo: getClubLogoSrc(club),
                };
            });

        return sortOppositionFinderRows(rows);
    }

    function getOppositionFinderPagedRows() {
        const pageSize = oppositionFinderPagination.pageSize;
        const total = oppositionFinderRows.length;
        const pageCount = Math.max(1, Math.ceil(total / pageSize));
        const page = Math.min(pageCount, Math.max(1, oppositionFinderPagination.page));
        oppositionFinderPagination.page = page;
        const start = (page - 1) * pageSize;
        return {
            total,
            page,
            pageCount,
            start,
            rows: oppositionFinderRows.slice(start, start + pageSize),
        };
    }

    function renderOppositionFinderPaginationSummary(paged) {
        const summary = document.getElementById('oppositionTopPaginationSummary');
        if (!summary) return;
        if (!paged.total) {
            summary.textContent = '0 clubs';
            return;
        }
        const from = paged.start + 1;
        const to = paged.start + paged.rows.length;
        summary.textContent = `${from}-${to} of ${paged.total} clubs`;
    }

    function syncOppositionFinderPaginationButtons(paged) {
        const prevBtn = document.getElementById('oppositionTopPrev');
        const nextBtn = document.getElementById('oppositionTopNext');
        if (prevBtn) prevBtn.disabled = paged.page <= 1;
        if (nextBtn) nextBtn.disabled = paged.page >= paged.pageCount;
    }

    function renderTopOppositionsTable(rowsByClub) {
        const body = document.getElementById('oppositionTopTableBody');
        if (!body) return;

        oppositionFinderRows = getOppositionFinderRows(rowsByClub);
        updateOppositionFinderSortHeaderUI();
        const paged = getOppositionFinderPagedRows();
        const topRows = paged.rows;

        if (topRows.length === 0) {
            body.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No opposition data found.</td></tr>';
            renderOppositionFinderPaginationSummary(paged);
            syncOppositionFinderPaginationButtons(paged);
            return;
        }

        body.innerHTML = topRows.map((row, idx) => {
            const logoHtml = row.logo
                ? `<img src="${escapeHtml(row.logo)}" alt="${escapeHtml(row.club)} logo" class="opposition-table-logo" loading="lazy">`
                : '';
            const winPct = Number.isFinite(row?.stats?.win_pct) ? `${row.stats.win_pct.toFixed(0)}%` : '-';
            const displayRank = paged.start + idx + 1;
            return `
                <tr class="opposition-selectable-row" data-opposition-select="${escapeHtml(row.club)}" tabindex="0" aria-label="Open ${escapeHtml(row.club)} opposition profile">
                    <td class="opposition-table-rank">${displayRank}</td>
                    <td class="opposition-table-opposition">
                        <div class="opposition-table-opposition-content">
                            ${logoHtml}
                            <a class="fw-bold" href="opposition-profile.html?opposition=${encodeURIComponent(String(row.club || '').trim())}">${escapeHtml(row.club)}</a>
                        </div>
                    </td>
                    <td class="opposition-table-games-1st text-end">${row.stats1st.played}</td>
                    <td class="opposition-table-games-2nd text-end">${row.stats2nd.played}</td>
                    <td class="opposition-table-games-total text-end">${row.stats.played}</td>
                    <td class="opposition-table-result opposition-table-result--win text-end">${row.stats.won}</td>
                    <td class="opposition-table-result opposition-table-result--draw text-end">${row.stats.drawn}</td>
                    <td class="opposition-table-result opposition-table-result--loss text-end">${row.stats.lost}</td>
                    <td class="opposition-table-win-pct text-end">${winPct}</td>
                    <td class="opposition-table-action match-table-open-cell">
                        <button type="button" class="btn btn-outline-primary btn-sm rounded-circle p-0 d-inline-flex align-items-center justify-content-center match-open-btn opposition-select-row-btn" data-opposition-select="${escapeHtml(row.club)}" aria-label="Open ${escapeHtml(row.club)} opposition profile">
                            <i class="bi bi-search" aria-hidden="true"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        renderOppositionFinderPaginationSummary(paged);
        syncOppositionFinderPaginationButtons(paged);
    }

    function populateOppositionSelect(rowsByClub) {
        const select = document.getElementById('oppositionSelect');
        if (!select) return;

        const clubs = Array.from(rowsByClub.keys()).sort(oppositionSort);
        const previousValue = String(select.value || currentOppositionClub || '').trim();
        select.innerHTML = '<option value="" selected>All</option>' + clubs.map((club) => `<option value="${club}">${club}</option>`).join('');
        if (previousValue && clubs.includes(previousValue)) {
            select.value = previousValue;
        }

        rebuildBootstrapSelect(select);
    }

    function showError(message) {
        const element = document.getElementById('oppositionProfileError');
        if (!element) return;
        element.textContent = message;
        element.classList.remove('d-none');
    }

    function clearError() {
        const element = document.getElementById('oppositionProfileError');
        if (!element) return;
        element.textContent = '';
        element.classList.add('d-none');
    }

    function renderSummary(filteredGames) {
        const stats = getOppositionStats(filteredGames);
        const oppositionClub = filteredGames.length ? toOppositionClubName(filteredGames[0]?.opposition) : currentOppositionClub;
        renderOppositionHero(oppositionClub);
        setText('opposition-summary-won', stats.won);
        setText('opposition-summary-drawn', stats.drawn);
        setText('opposition-summary-lost', stats.lost);
        setText('opposition-summary-played', stats.played);
        
        // Calculate home/away record
        const homeAwayRecord = filteredGames.reduce((acc, row) => {
            const result = normaliseResult(row);
            const venueCode = String(row?.home_away || '').toUpperCase();
            const isHome = venueCode === 'H';
            const isAway = venueCode === 'A';
            
            if (isHome) {
                if (result === 'W') acc.homeWins++;
                if (result === 'L') acc.homeLosses++;
            }
            if (isAway) {
                if (result === 'W') acc.awayWins++;
                if (result === 'L') acc.awayLosses++;
            }
            return acc;
        }, { homeWins: 0, homeLosses: 0, awayWins: 0, awayLosses: 0 });
        
        const homeHtml = `<span class="result-badge result-badge--win">${homeAwayRecord.homeWins}W</span> <span class="result-badge result-badge--loss">${homeAwayRecord.homeLosses}L</span>`;
        const awayHtml = `<span class="result-badge result-badge--win">${homeAwayRecord.awayWins}W</span> <span class="result-badge result-badge--loss">${homeAwayRecord.awayLosses}L</span>`;
        
        setHtml('opposition-summary-home-breakdown', homeHtml);
        setHtml('opposition-summary-away-breakdown', awayHtml);
        
        setHtml('opposition-summary-last-match', buildLastMatchSummary(filteredGames));
    }

    function renderResultsTable(filteredGames) {
        const body = document.getElementById('oppositionResultsTableBody');
        if (!body) return;

        if (!currentOppositionClub) {
            oppositionHistoryRows = [];
            updateOppositionHistorySortHeaderUI();
            renderOppositionHistoryPaginationSummary({ total: 0, start: 0, rows: [] });
            syncOppositionHistoryPaginationButtons({ page: 1, pageCount: 1 });
            body.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Select an opposition club to load previous matches.</td></tr>';
            return;
        }

        if (!filteredGames.length) {
            oppositionHistoryRows = [];
            updateOppositionHistorySortHeaderUI();
            renderOppositionHistoryPaginationSummary({ total: 0, start: 0, rows: [] });
            syncOppositionHistoryPaginationButtons({ page: 1, pageCount: 1 });
            body.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No matches found for this opposition.</td></tr>';
            return;
        }

        oppositionHistoryRows = sortOppositionHistoryRows(filteredGames);
        updateOppositionHistorySortHeaderUI();
        const paged = getOppositionHistoryPagedRows();
        renderOppositionHistoryPaginationSummary(paged);
        syncOppositionHistoryPaginationButtons(paged);

        body.innerHTML = paged.rows
            .map((row) => {
                const result = normaliseResult(row);
                const resultClass =
                  result === "W"
                    ? "result-badge--win"
                    : result === "L"
                      ? "result-badge--loss"
                      : result === "D"
                        ? "result-badge--draw"
                        : "";
                                const hasScoreFor = row?.score_for !== null && row?.score_for !== undefined && row?.score_for !== '';
                                const hasScoreAgainst = row?.score_against !== null && row?.score_against !== undefined && row?.score_against !== '';
                                const score = hasScoreFor && hasScoreAgainst ? `${row.score_for} - ${row.score_against}` : '-';
                const competition = String(
                    row?.league || row?.competition || row?.competition_name || row?.game_type || ''
                ).trim();
                const gameLink = createGameLink(row?.game_id);
                const rowClass = row?.squad === '1st'
                    ? 'opposition-results-row opposition-results-row--1st'
                    : row?.squad === '2nd'
                        ? 'opposition-results-row opposition-results-row--2nd'
                        : 'opposition-results-row';

                const captain = String(row?.captain || '').trim();
                const captainLink = captain ? createPlayerLink(captain) : null;
                const captainHtml = captainLink 
                    ? `<a class="table-player-link" href="${captainLink}">${escapeHtml(captain)}</a>`
                    : '-';
                const openHtml = gameLink
                    ? `<a class="btn btn-outline-primary btn-sm rounded-circle p-0 d-inline-flex align-items-center justify-content-center match-open-btn" href="${gameLink}" aria-label="View match detail"><i class="bi bi-search" aria-hidden="true"></i></a>`
                    : '-';
                return `
                    <tr class="${rowClass}">
                        <td>${formatDisplayDate(row?.date)}</td>
                        <td>${squadPillHtml(row?.squad)}</td>
                        <td>${competition}</td>
                        <td>${venueLabel(row?.home_away)}</td>
                        <td>${resultClass && score !== '-' ? `<span class="result-badge ${resultClass}">${escapeHtml(score)}</span>` : escapeHtml(score)}</td>
                        <td>${captainHtml}</td>
                        <td class="match-table-open-cell">${openHtml}</td>
                    </tr>
                `;
            })
            .join('');
    }

    function filterTeamSheetsSpecByClub(spec, oppositionClub) {
        if (!spec || !oppositionClub) return null;
        const clonedSpec = JSON.parse(JSON.stringify(spec));
        return filterChartSpecDataset(clonedSpec, (row) => {
            const rowClub = toOppositionClubName(row?.opposition);
            return rowClub === oppositionClub;
        });
    }

    function filterResultsSpecByClub(spec, oppositionClub) {
        if (!spec || !oppositionClub) return null;
        const clonedSpec = JSON.parse(JSON.stringify(spec));
        return filterChartSpecDataset(clonedSpec, (row) => {
            const rowClub = toOppositionClubName(row?.opposition);
            return rowClub === oppositionClub;
        });
    }

    function layoutH2HSpec(baseSpec) {
        const cloned = JSON.parse(JSON.stringify(baseSpec));

        function compactLeafSpecs(node) {
            if (!node || typeof node !== 'object') return;

            if (Array.isArray(node.vconcat)) {
                node.vconcat.forEach(compactLeafSpecs);
            }

            if (Array.isArray(node.hconcat)) {
                node.hconcat.forEach(compactLeafSpecs);
            }

            if (Array.isArray(node.layer)) {
                node.layer.forEach(compactLeafSpecs);
            }

            if (node.mark) {
                const hasRowEncoding = Boolean(node.encoding && (node.encoding.y || node.encoding.yOffset));
                if (hasRowEncoding) {
                    node.height = { step: 14 };
                }
                if (hasRowEncoding && node.mark.type === 'bar') {
                    node.encoding = node.encoding || {};
                    node.encoding.size = { value: 12 };
                }
            }
        }

        compactLeafSpecs(cloned);

        return cloned;
    }

    function filterH2HSpecByClub(spec, oppositionClub) {
        if (!spec || !oppositionClub || oppositionClub === 'All') {
            return layoutH2HSpec(spec);
        }

        return layoutH2HSpec(
            filterChartSpecDataset(spec, (row) => {
                if (!row || !Object.prototype.hasOwnProperty.call(row, 'opposition_club')) {
                    return true;
                }
                return toOppositionClubName(row.opposition_club) === oppositionClub;
            })
        );
    }

    function h2hSpecHasGameRows(spec) {
        if (!spec) return false;

        if (spec.datasets) {
            const datasetRows = Object.values(spec.datasets);
            for (const rows of datasetRows) {
                if (!Array.isArray(rows)) continue;
                if (rows.some((row) => row && Object.prototype.hasOwnProperty.call(row, 'game_id'))) {
                    return true;
                }
            }
        }

        if (spec.data && Array.isArray(spec.data.values)) {
            return spec.data.values.some((row) => row && Object.prototype.hasOwnProperty.call(row, 'game_id'));
        }

        return false;
    }

    async function renderH2HCharts(oppositionClub = 'All') {
        const chartContainer = document.getElementById('oppositionSetPieceChart');
        const chartsWrap = document.getElementById('oppositionSetPieceCharts');
        const intro = document.getElementById('oppositionSetPieceIntro');
        const noData = document.getElementById('oppositionSetPieceNoData');

        if (!chartContainer) return;

        const showSetPieceState = (hasData) => {
            if (chartsWrap) chartsWrap.classList.toggle('d-none', !hasData);
            if (intro) intro.classList.toggle('d-none', !hasData);
            if (noData) noData.classList.toggle('d-none', hasData);
        };

        if (!oppositionClub || oppositionClub === 'All') {
            chartContainer.innerHTML = '';
            lineoutH2HView = null;
            scrumH2HView = null;
            showSetPieceState(false);
            return;
        }

        const filteredLineoutSpec = filterH2HSpecByClub(lineoutH2HSpec, oppositionClub);
        const filteredScrumSpec = filterH2HSpecByClub(scrumH2HSpec, oppositionClub);

        // Check if filtered specs include real game rows.
        const lineoutHasData = h2hSpecHasGameRows(filteredLineoutSpec);
        const scrumHasData = h2hSpecHasGameRows(filteredScrumSpec);
        const hasSetPieceData = lineoutHasData && scrumHasData;

        chartContainer.innerHTML = '';
        lineoutH2HView = null;
        scrumH2HView = null;

        if (!hasSetPieceData) {
            showSetPieceState(false);
            return;
        }

        showSetPieceState(true);
        
        // Render the currently selected chart type
        const selectedSpec = currentSetPieceType === 'lineout' ? filteredLineoutSpec : filteredScrumSpec;
        const chartTitle = currentSetPieceType === 'lineout' ? 'lineout' : 'scrum';
        
        await embedChartSpec(chartContainer, selectedSpec, {
            containerId: 'oppositionSetPieceChart',
            emptyMessage: `${chartTitle} chart unavailable.`,
            responsiveScaleMin: 0.5,
            responsiveScaleMinXs: 0.42
        })
            .then(view => {
                if (currentSetPieceType === 'lineout') {
                    lineoutH2HView = view;
                } else {
                    scrumH2HView = view;
                }
            })
            .catch(error => {
                console.error(`Error rendering ${chartTitle} h2h chart:`, error);
                showSetPieceState(false);
            });
    }

    async function applyH2HFilters(oppositionClub) {
        await renderH2HCharts(oppositionClub || 'All');
    }

    async function renderOppositionProfile(oppositionClub) {
        if (!oppositionClub) {
            currentOppositionClub = null;
            oppositionHistoryPagination.page = 1;
            updateOppositionUrl('');
            renderOppositionActiveFilters('');
            toggleOverviewState(false);
            renderResultsTable([]);
            renderStaticSpecChart('oppositionResultsChart', null, 'Select an opposition club to load the results chart.', {
                responsiveScaleMin: 0.5,
                responsiveScaleMinXs: 0.42,
            });
            renderStaticSpecChart('oppositionTeamSheetsChart', null, 'Select an opposition club to load team sheet data.');
            await renderH2HCharts('All');
            return;
        }

        currentOppositionClub = oppositionClub;
    oppositionHistoryPagination.page = 1;
        updateOppositionUrl(oppositionClub);
        renderOppositionActiveFilters(oppositionClub);

        const filteredGames = gamesRows.filter((row) => toOppositionClubName(row?.opposition) === oppositionClub);
        renderSummary(filteredGames);
        renderResultsTable(filteredGames);
        toggleOverviewState(true);

        const filteredResultsSpec = filterResultsSpecByClub(resultsSpec, oppositionClub);
        renderStaticSpecChart('oppositionResultsChart', filteredResultsSpec, 'No results chart data for this opposition.', {
            responsiveScaleMin: 0.5,
            responsiveScaleMinXs: 0.42,
        });

        const filteredTeamSheetsSpec = filterTeamSheetsSpecByClub(teamSheetsSpec, oppositionClub);
        renderStaticSpecChart('oppositionTeamSheetsChart', filteredTeamSheetsSpec, 'No team sheet data for this opposition.');

        await applyH2HFilters(oppositionClub);
    }

    function bindControls(rowsByClub) {
        const oppositionSelect = document.getElementById('oppositionSelect');
        const prevBtn = document.getElementById('oppositionTopPrev');
        const nextBtn = document.getElementById('oppositionTopNext');
        const historyPrevBtn = document.getElementById('oppositionHistoryPrev');
        const historyNextBtn = document.getElementById('oppositionHistoryNext');
        const finderTable = document.getElementById('oppositionTopTableWrap');
        const historyTable = document.getElementById('oppositionHistoryTableWrap');
        if (oppositionSelect) {
            oppositionSelect.addEventListener('change', () => {
                renderOppositionProfile(oppositionSelect.value).catch((error) => {
                    console.error('Failed to render opposition profile:', error);
                    showError('Unable to render opposition profile.');
                });
            });
        }

        if (prevBtn && !prevBtn.__oppositionPaginationBound) {
            prevBtn.__oppositionPaginationBound = true;
            prevBtn.addEventListener('click', () => {
                oppositionFinderPagination.page = Math.max(1, oppositionFinderPagination.page - 1);
                renderTopOppositionsTable(rowsByClub);
            });
        }

        if (nextBtn && !nextBtn.__oppositionPaginationBound) {
            nextBtn.__oppositionPaginationBound = true;
            nextBtn.addEventListener('click', () => {
                oppositionFinderPagination.page += 1;
                renderTopOppositionsTable(rowsByClub);
            });
        }

        if (historyPrevBtn && !historyPrevBtn.__oppositionHistoryPaginationBound) {
            historyPrevBtn.__oppositionHistoryPaginationBound = true;
            historyPrevBtn.addEventListener('click', () => {
                oppositionHistoryPagination.page = Math.max(1, oppositionHistoryPagination.page - 1);
                renderResultsTable(oppositionHistoryRows);
            });
        }

        if (historyNextBtn && !historyNextBtn.__oppositionHistoryPaginationBound) {
            historyNextBtn.__oppositionHistoryPaginationBound = true;
            historyNextBtn.addEventListener('click', () => {
                oppositionHistoryPagination.page += 1;
                renderResultsTable(oppositionHistoryRows);
            });
        }

        if (finderTable && !finderTable.__oppositionSortBound) {
            finderTable.__oppositionSortBound = true;
            finderTable.addEventListener('click', (event) => {
                const sortButton = event.target.closest('[data-opposition-sort]');
                if (!sortButton) return;
                const sortKey = String(sortButton.getAttribute('data-opposition-sort') || '');
                setOppositionFinderSort(sortKey);
                renderTopOppositionsTable(rowsByClub);
            });
        }

        if (historyTable && !historyTable.__oppositionHistorySortBound) {
            historyTable.__oppositionHistorySortBound = true;
            historyTable.addEventListener('click', (event) => {
                const sortButton = event.target.closest('[data-opposition-history-sort]');
                if (!sortButton) return;
                const key = sortButton.getAttribute('data-opposition-history-sort');
                setOppositionHistorySort(key);
                renderResultsTable(oppositionHistoryRows);
            });
        }

        const setpieceTypeSegment = document.getElementById('setpieceTypeSegment');
        const setpieceTypeSelect = document.getElementById('setpieceTypeSelect');
        if (setpieceTypeSegment && setpieceTypeSelect && window.sharedUi?.bindSegmentToSelect) {
            window.sharedUi.bindSegmentToSelect({
                segment: setpieceTypeSegment,
                select: setpieceTypeSelect,
                onSync: (value) => {
                    currentSetPieceType = String(value || 'lineout');
                    renderH2HCharts(currentOppositionClub || 'All');
                },
            });
        }


        const topTableBody = document.getElementById('oppositionTopTableBody');
        if (topTableBody && !topTableBody.__oppositionPickerBound) {
            topTableBody.__oppositionPickerBound = true;
            topTableBody.addEventListener('click', (event) => {
                const trigger = event.target.closest('[data-opposition-select]');
                if (!trigger) return;
                const oppositionClub = String(trigger.getAttribute('data-opposition-select') || '').trim();
                if (!oppositionClub) return;
                syncOppositionSelectUI(oppositionClub);
                renderOppositionProfile(oppositionClub).catch((error) => {
                    console.error('Failed to render opposition profile:', error);
                    showError('Unable to render opposition profile.');
                });
                const profileSection = document.getElementById('opposition-profile');
                if (profileSection) {
                    profileSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });

            topTableBody.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                const row = event.target.closest('tr[data-opposition-select]');
                if (!row) return;
                if (event.target.closest('button, a, input, select, textarea')) return;
                event.preventDefault();
                const oppositionClub = String(row.getAttribute('data-opposition-select') || '').trim();
                if (!oppositionClub) return;
                syncOppositionSelectUI(oppositionClub);
                renderOppositionProfile(oppositionClub).catch((error) => {
                    console.error('Failed to render opposition profile:', error);
                    showError('Unable to render opposition profile.');
                });
                const profileSection = document.getElementById('opposition-profile');
                if (profileSection) {
                    profileSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        }

        const url = new URL(window.location.href);
        const oppositionParam = String(url.searchParams.get('opposition') || '').trim();
        const clubs = new Set(Array.from(rowsByClub.keys()));
        if (oppositionParam && clubs.has(oppositionParam)) {
            syncOppositionSelectUI(oppositionParam);
            renderOppositionProfile(oppositionParam).catch((error) => {
                console.error('Failed to render opposition profile:', error);
                showError('Unable to render opposition profile.');
            });
        } else {
            renderOppositionActiveFilters('');
        }
    }

    function initialiseOppositionProfileAnalysisRail() {
        if (oppositionProfileAnalysisRailInitialised) return;
        oppositionProfileAnalysisRailInitialised = initialiseAnalysisRail({
            railId: 'oppositionProfileAnalysisRail',
            sectionSelector: '.analysis-section[id], .opposition-profile-subsection[id]',
            initialHashDelay: 60,
        });
    }

    async function initOppositionPage() {
        clearError();
        toggleOverviewState(false);

        // Load logos manifest
        try {
            const logosResponse = await fetch('data/logos.json');
            if (logosResponse.ok) {
                clubLogosManifest = await logosResponse.json();
            }
        } catch (_error) {
            console.warn('Could not load logos manifest', _error);
        }

        const gamesResponse = await fetch('data/backend/games.json');
        if (!gamesResponse.ok) {
            throw new Error(`Failed to load games data (${gamesResponse.status})`);
        }

        gamesRows = await gamesResponse.json();
        if (!Array.isArray(gamesRows)) {
            gamesRows = [];
        }

        const [loadedTeamSheetsSpec, loadedResultsSpec, loadedLineoutH2HSpec, loadedScrumH2HSpec] = await Promise.all([
            loadChartSpec(TEAM_SHEETS_SPEC_PATH),
            loadChartSpec(RESULTS_SPEC_PATH),
            loadChartSpec(LINEOUT_H2H_SPEC_PATH),
            loadChartSpec(SCRUM_H2H_SPEC_PATH),
        ]);

        teamSheetsSpec = loadedTeamSheetsSpec;
        resultsSpec = loadedResultsSpec;
        lineoutH2HSpec = loadedLineoutH2HSpec;
        scrumH2HSpec = loadedScrumH2HSpec;

        const rowsByClub = clubCountsFromGames(gamesRows);
        renderTopOppositionsTable(rowsByClub);
        populateOppositionSelect(rowsByClub);
        bindControls(rowsByClub);
        renderOppositionHeroQuickLinks();
        bindOppositionHeroQuickLinks();
        initialiseOppositionProfileAnalysisRail();

        await renderOppositionProfile('');
    }

    document.addEventListener('DOMContentLoaded', async () => {
        try {
            await initOppositionPage();
        } catch (error) {
            console.error('Failed to initialise opposition profile page:', error);
            showError('Unable to load opposition profile data.');
        }
    });
})();

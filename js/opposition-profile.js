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
        const pf = Number(row?.score_for);
        const pa = Number(row?.score_against);
        if (Number.isFinite(pf) && Number.isFinite(pa)) {
            if (pf > pa) return 'W';
            if (pf < pa) return 'L';
            return 'D';
        }
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
            acc.played += 1;
            if (result === 'W') acc.won += 1;
            if (result === 'D') acc.drawn += 1;
            if (result === 'L') acc.lost += 1;
            return acc;
        }, { won: 0, drawn: 0, lost: 0, played: 0 });
    }

    function oppositionSort(a, b) {
        return String(a).localeCompare(String(b), undefined, { sensitivity: 'base' });
    }

    function dateSortDesc(a, b) {
        return String(b?.date || '').localeCompare(String(a?.date || ''));
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

    function renderTopOppositionsTable(rowsByClub) {
        const body = document.getElementById('oppositionTopTableBody');
        if (!body) return;

        const topRows = Array.from(rowsByClub.entries())
            .map(([club, rows]) => {
                const stats = getOppositionStats(rows);
                const stats1st = rows.reduce((acc, row) => {
                    acc.played += row?.squad === '1st' ? 1 : 0;
                    if (row?.squad === '1st') {
                        const result = normaliseResult(row);
                        if (result === 'W') acc.won += 1;
                        if (result === 'D') acc.drawn += 1;
                        if (result === 'L') acc.lost += 1;
                    }
                    return acc;
                }, { won: 0, drawn: 0, lost: 0, played: 0 });
                const stats2nd = rows.reduce((acc, row) => {
                    acc.played += row?.squad === '2nd' ? 1 : 0;
                    if (row?.squad === '2nd') {
                        const result = normaliseResult(row);
                        if (result === 'W') acc.won += 1;
                        if (result === 'D') acc.drawn += 1;
                        if (result === 'L') acc.lost += 1;
                    }
                    return acc;
                }, { won: 0, drawn: 0, lost: 0, played: 0 });
                return { club, stats, stats1st, stats2nd, logo: getClubLogoSrc(club) };
            })
            .sort((a, b) => {
                if (b.stats.played !== a.stats.played) return b.stats.played - a.stats.played;
                return oppositionSort(a.club, b.club);
            })
            .slice(0, 10);

        if (topRows.length === 0) {
            body.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No opposition data found.</td></tr>';
            return;
        }

        body.innerHTML = topRows.map((row, idx) => {
            const logoHtml = row.logo
                ? `<img src="${escapeHtml(row.logo)}" alt="${escapeHtml(row.club)} logo" class="opposition-table-logo" loading="lazy">`
                : '';
            return `
                <tr>
                    <td class="opposition-table-rank">${idx + 1}</td>
                    <td class="opposition-table-opposition">
                        <div class="opposition-table-opposition-content">
                            ${logoHtml}
                            <strong>${escapeHtml(row.club)}</strong>
                        </div>
                    </td>
                    <td class="opposition-table-games-1st text-end">${row.stats1st.played}</td>
                    <td class="opposition-table-games-2nd text-end">${row.stats2nd.played}</td>
                    <td class="opposition-table-games-total text-end">${row.stats.played}</td>
                    <td class="opposition-table-result opposition-table-result--win text-end">${row.stats.won}</td>
                    <td class="opposition-table-result opposition-table-result--draw text-end">${row.stats.drawn}</td>
                    <td class="opposition-table-result opposition-table-result--loss text-end">${row.stats.lost}</td>
                    <td class="opposition-table-action">
                        <a href="opposition-profile.html?opposition=${encodeURIComponent(row.club)}" class="match-data-link" title="Open ${escapeHtml(row.club)} opposition profile">
                            <i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>
                            <span>Opposition Profile</span>
                        </a>
                    </td>
                </tr>
            `;
        }).join('');

        // Re-bind click handlers for the new links if needed (though links already work via href)
        // The close button in each row should navigate when clicked
    }

    function populateOppositionSelect(rowsByClub) {
        const select = document.getElementById('oppositionSelect');
        if (!select) return;

        const clubs = Array.from(rowsByClub.keys()).sort(oppositionSort);
        select.innerHTML = '<option value="" disabled selected hidden>Select opposition...</option>' + clubs.map((club) => `<option value="${club}">${club}</option>`).join('');

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

    function showContent(show) {
        const placeholder = document.getElementById('oppositionProfilePlaceholder');
        const content = document.getElementById('oppositionProfileContent');
        if (placeholder) placeholder.classList.toggle('d-none', show);
        if (content) content.classList.toggle('d-none', !show);
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

        if (!filteredGames.length) {
            body.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No matches found for this opposition.</td></tr>';
            return;
        }

        body.innerHTML = filteredGames
            .slice()
            .sort(dateSortDesc)
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
                const score = String(row?.score_for) && String(row?.score_against) ? `${row.score_for} - ${row.score_against}` : '';
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
                    ? `<a class="match-team-sheet-player-link" style="font-size: 1rem; font-weight:normal" href="${captainLink}">${escapeHtml(captain)}</a>`
                    : '-';
                return `
                    <tr class="${rowClass}">
                        <td>${formatDisplayDate(row?.date)}</td>
                        <td>${String(row?.season || '-')}</td>
                        <td>${squadPillHtml(row?.squad)}</td>
                        <td>${competition}</td>
                        <td>${venueLabel(row?.home_away)}</td>
                        <td>${resultClass ? `<span class="result-badge ${resultClass}">${escapeHtml(score)}</span>` : escapeHtml(score)}</td>
                        <td>${captainHtml}</td>
                        <td>${gameLink ? `<a class="match-data-link" href="${gameLink}"><i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>Match Info</a>` : '-'}</td>
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
        const lineoutContainer = document.getElementById('oppositionLineoutH2HChart');
        const scrumContainer = document.getElementById('oppositionScrumH2HChart');
        const lineoutPanel = document.querySelector('[data-target="opposition-lineout-h2h-panel"]')?.closest('.chart-panel');
        const scrumPanel = document.querySelector('[data-target="opposition-scrum-h2h-panel"]')?.closest('.chart-panel');

        if (!lineoutContainer || !scrumContainer) return;

        const filteredLineoutSpec = filterH2HSpecByClub(lineoutH2HSpec, oppositionClub);
        const filteredScrumSpec = filterH2HSpecByClub(scrumH2HSpec, oppositionClub);

        // Check if filtered specs include real game rows.
        const lineoutHasData = h2hSpecHasGameRows(filteredLineoutSpec);
        const scrumHasData = h2hSpecHasGameRows(filteredScrumSpec);

        // Show/hide panels based on data availability
        if (lineoutPanel) lineoutPanel.style.display = lineoutHasData ? 'block' : 'none';
        if (scrumPanel) scrumPanel.style.display = scrumHasData ? 'block' : 'none';

        lineoutContainer.innerHTML = '';
        scrumContainer.innerHTML = '';
        lineoutH2HView = null;
        scrumH2HView = null;

        if (lineoutHasData) {
            await vegaEmbed(lineoutContainer, filteredLineoutSpec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' })
                .then(result => {
                    lineoutH2HView = result.view;
                    pinVegaActionsInElement(lineoutContainer);
                })
                .catch(error => {
                    console.error('Error rendering lineout h2h chart:', error);
                });
        }

        if (scrumHasData) {
            await vegaEmbed(scrumContainer, filteredScrumSpec, { actions: VEGA_EMBED_ACTIONS, renderer: 'svg' })
                .then(result => {
                    scrumH2HView = result.view;
                    pinVegaActionsInElement(scrumContainer);
                })
                .catch(error => {
                    console.error('Error rendering scrum h2h chart:', error);
                });
        }
    }

    async function applyH2HFilters(oppositionClub) {
        await renderH2HCharts(oppositionClub || 'All');
    }

    async function renderOppositionProfile(oppositionClub) {
        if (!oppositionClub) {
            currentOppositionClub = null;
            showContent(false);
            return;
        }

        currentOppositionClub = oppositionClub;

        const filteredGames = gamesRows.filter((row) => toOppositionClubName(row?.opposition) === oppositionClub);
        renderSummary(filteredGames);
        renderResultsTable(filteredGames);

        const filteredResultsSpec = filterResultsSpecByClub(resultsSpec, oppositionClub);
        renderStaticSpecChart('oppositionResultsChart', filteredResultsSpec, 'No results chart data for this opposition.');

        const filteredTeamSheetsSpec = filterTeamSheetsSpecByClub(teamSheetsSpec, oppositionClub);
        renderStaticSpecChart('oppositionTeamSheetsChart', filteredTeamSheetsSpec, 'No team sheet data for this opposition.');

        await applyH2HFilters(oppositionClub);

        showContent(true);
    }

    function bindControls(rowsByClub) {
        const oppositionSelect = document.getElementById('oppositionSelect');
        if (oppositionSelect) {
            oppositionSelect.addEventListener('change', () => {
                renderOppositionProfile(oppositionSelect.value).catch((error) => {
                    console.error('Failed to render opposition profile:', error);
                    showError('Unable to render opposition profile.');
                });
            });
        }

        const url = new URL(window.location.href);
        const oppositionParam = String(url.searchParams.get('opposition') || '').trim();
        const clubs = new Set(Array.from(rowsByClub.keys()));
        if (oppositionParam && clubs.has(oppositionParam)) {
            if (oppositionSelect) {
                oppositionSelect.value = oppositionParam;
                rebuildBootstrapSelect(oppositionSelect);
            }
            renderOppositionProfile(oppositionParam).catch((error) => {
                console.error('Failed to render opposition profile:', error);
                showError('Unable to render opposition profile.');
            });
        }
    }

    async function initOppositionPage() {
        clearError();
        showContent(false);

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

        await renderH2HCharts('All');

        const rowsByClub = clubCountsFromGames(gamesRows);
        renderTopOppositionsTable(rowsByClub);
        populateOppositionSelect(rowsByClub);
        bindControls(rowsByClub);

        initialiseChartPanelToggles();
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

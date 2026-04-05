let allMatches = [];
let filteredMatches = [];
let pagination = { page: 1, pageSize: 10 };
let isInitialisingControls = false;
let appearancesByGameId = new Map();
let profilesByName = new Map();
let isCompactTeamSheetMode = false;
let clubLogosManifest = {}; // Will be populated by loadLogosManifest()

// Load the logos manifest on page load
async function loadLogosManifest() {
    try {
        const response = await fetch('data/logos.json');
        if (response.ok) {
            clubLogosManifest = await response.json();
        }
    } catch (_error) {
        console.warn('Could not load logos manifest', _error);
    }
}

function isSelectPickerEnabled() {
    return !!(window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function canonicalizeName(value) {
    return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function choosePreferredProfile(existing, candidate) {
    if (!existing) return candidate;
    if (!candidate) return existing;

    const existingPhoto = String(existing?.photo_url || '').trim();
    const candidatePhoto = String(candidate?.photo_url || '').trim();
    if (!existingPhoto && candidatePhoto) return candidate;
    if (existingPhoto && !candidatePhoto) return existing;

    const existingApps = Number(existing?.totalAppearances || 0);
    const candidateApps = Number(candidate?.totalAppearances || 0);
    if (candidateApps > existingApps) return candidate;
    return existing;
}

function formatDisplayDate(value) {
    const raw = String(value || '').trim();
    if (!raw) return '-';
    const isoDateMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    const parsed = isoDateMatch
        ? new Date(Number(isoDateMatch[1]), Number(isoDateMatch[2]) - 1, Number(isoDateMatch[3]))
        : new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;

    const day = parsed.getDate();
    const month = parsed.toLocaleDateString('en-GB', { month: 'long' });
    const year = parsed.getFullYear();
    return `${ordinalSuffix(day)} ${month} ${year}`;
}

function normaliseResult(row) {
    const result = String(row?.result || '').toUpperCase();
    const pf = Number(row?.score_for);
    const pa = Number(row?.score_against);
    const prefix = result || '-';
    if (Number.isFinite(pf) && Number.isFinite(pa)) return `${prefix} ${pf}-${pa}`;
    return prefix;
}

function resultBadgeHtml(score) {
    const text = String(score || '-').trim();
    const first = text.charAt(0).toUpperCase();
    const cls = first === 'W' ? 'result-badge--win' : first === 'L' ? 'result-badge--loss' : first === 'D' ? 'result-badge--draw' : '';
    if (!cls) return escapeHtml(text);
    return `<span class="result-badge ${cls}">${escapeHtml(text)}</span>`;
}

function formatSquadLabel(value) {
    const squad = String(value || '').trim();
    if (squad === '1st') return '1st XV';
    if (squad === '2nd') return '2nd XV';
    return squad || 'Unknown';
}

function fixtureLabel(row) {
    const dateLabel = formatDisplayDate(row?.date);
    return `${dateLabel} - ${formatSquadLabel(row?.squad)} v ${String(row?.opposition || 'Unknown')}`;
}

function eastGrinsteadTeamName(row) {
    const squadLabel = formatSquadLabel(row?.squad);
    return squadLabel ? `East Grinstead ${squadLabel}` : 'East Grinstead';
}

function buildMatchHeroData(row) {
    const isHome = String(row?.home_away || '').trim().toUpperCase() !== 'A';
    const egTeam = eastGrinsteadTeamName(row);
    const opposition = String(row?.opposition || 'Unknown').trim() || 'Unknown';
    const scoreFor = Number(row?.score_for);
    const scoreAgainst = Number(row?.score_against);
    const squad = String(row?.squad || '').trim();

    const resultClass = String(row?.result || '').toUpperCase() === 'W'
        ? 'match-info-hero--win'
        : String(row?.result || '').toUpperCase() === 'L'
            ? 'match-info-hero--loss'
            : String(row?.result || '').toUpperCase() === 'D'
                ? 'match-info-hero--draw'
                : '';

    const squadClass = squad === '1st' ? 'match-info-hero--1st' : squad === '2nd' ? 'match-info-hero--2nd' : '';
    const egSideClass = isHome ? 'match-info-hero--eg-home' : 'match-info-hero--eg-away';

    return {
        homeTeam: isHome ? egTeam : opposition,
        awayTeam: isHome ? opposition : egTeam,
        homeLogoSrc: getClubLogoSrc(isHome ? egTeam : opposition),
        awayLogoSrc: getClubLogoSrc(isHome ? opposition : egTeam),
        homeScore: Number.isFinite(isHome ? scoreFor : scoreAgainst) ? String(isHome ? scoreFor : scoreAgainst) : '-',
        awayScore: Number.isFinite(isHome ? scoreAgainst : scoreFor) ? String(isHome ? scoreAgainst : scoreFor) : '-',
        date: formatDisplayDate(row?.date),
        competition: String(row?.competition || row?.game_type || '-'),
        resultClass: `${squadClass} ${resultClass} ${egSideClass}`.trim(),
    };
}

function pickFirstScorerValue(row, keys) {
    if (!row || !Array.isArray(keys)) return undefined;
    for (const key of keys) {
        if (!(key in row)) continue;
        const value = row[key];
        if (value === null || value === undefined) continue;
        if (typeof value === 'string' && !value.trim()) continue;
        if (Array.isArray(value) && value.length === 0) continue;
        if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) continue;
        return value;
    }
    return undefined;
}

function parseScorerToken(rawToken) {
    const token = String(rawToken || '').replace(/^[-*\u2022\s]+/, '').trim();
    if (!token || !/[A-Za-z]/.test(token)) return null;

    let match = token.match(/^(.+?)\s*\((\d+)\)\s*$/);
    if (match) {
        return {
            name: match[1].trim(),
            count: Math.max(1, Number.parseInt(match[2], 10) || 1),
        };
    }

    match = token.match(/^(.+?)\s*[xX]\s*(\d+)\s*$/);
    if (match) {
        return {
            name: match[1].trim(),
            count: Math.max(1, Number.parseInt(match[2], 10) || 1),
        };
    }

    match = token.match(/^(.+?)\s*[:\-]\s*(\d+)\s*$/);
    if (match) {
        return {
            name: match[1].trim(),
            count: Math.max(1, Number.parseInt(match[2], 10) || 1),
        };
    }

    return { name: token, count: 1 };
}

function scorerEntriesFromUnknown(raw) {
    if (raw === null || raw === undefined) return [];

    if (Array.isArray(raw)) {
        return raw.flatMap(item => scorerEntriesFromUnknown(item));
    }

    if (typeof raw === 'object') {
        const namedFields = ['player', 'name', 'scorer'];
        const countFields = ['count', 'tries', 'conversions', 'penalties', 'value'];
        const hasNamedField = namedFields.some(field => field in raw);
        if (hasNamedField) {
            const playerName = String(
                raw.player || raw.name || raw.scorer || ''
            ).trim();
            if (!playerName || !/[A-Za-z]/.test(playerName)) return [];
            const countValue = countFields
                .map(field => Number(raw[field]))
                .find(Number.isFinite);
            return [{ name: playerName, count: Math.max(1, countValue || 1) }];
        }

        return Object.entries(raw).flatMap(([name, value]) => {
            const cleanName = String(name || '').trim();
            if (!cleanName || !/[A-Za-z]/.test(cleanName)) return [];

            if (Number.isFinite(Number(value))) {
                return [{ name: cleanName, count: Math.max(1, Number(value) || 1) }];
            }

            if (value && typeof value === 'object') {
                const nestedCount = Number(value.count ?? value.value ?? value.total);
                if (Number.isFinite(nestedCount)) {
                    return [{ name: cleanName, count: Math.max(1, nestedCount || 1) }];
                }
            }

            const parsed = parseScorerToken(`${cleanName} ${String(value || '').trim()}`);
            return parsed ? [parsed] : [];
        });
    }

    if (typeof raw === 'string') {
        const text = raw.trim();
        if (!text) return [];

        if ((text.startsWith('[') && text.endsWith(']')) || (text.startsWith('{') && text.endsWith('}'))) {
            try {
                const parsed = JSON.parse(text);
                return scorerEntriesFromUnknown(parsed);
            } catch (_error) {
                // Fall through to token parsing when the value is not valid JSON.
            }
        }

        return text
            .split(/\r?\n|,|;|\|/)
            .map(token => parseScorerToken(token))
            .filter(Boolean);
    }

    return [];
}

function resolveScorerNameToCanonical(scorerName) {
    const nameKey = canonicalizeName(scorerName);
    const profile = profilesByName.get(nameKey);
    if (profile && profile.name) {
        return profile.name;
    }
    return scorerName;
}

function collapseScorerEntries(entries) {
    const byPlayer = new Map();
    entries.forEach(entry => {
        const rawName = String(entry?.name || '').trim();
        if (!rawName) return;
        const key = canonicalizeName(rawName);
        if (!key) return;
        const canonicalName = resolveScorerNameToCanonical(rawName);
        const existing = byPlayer.get(key) || { name: canonicalName, count: 0 };
        existing.count += Math.max(1, Number(entry?.count) || 1);
        byPlayer.set(key, existing);
    });

    return [...byPlayer.values()]
        .sort((a, b) => {
            if (b.count !== a.count) return b.count - a.count;
            return a.name.localeCompare(b.name);
        });
}

function scorerCategoryHtml(title, entries) {
    if (!entries.length) return '';
    const rows = entries
        .map(entry => {
            const playerName = String(entry?.name || '').trim();
            const link = profileLinkHref(playerName);
            const safeName = escapeHtml(playerName);
            const count = entry.count > 1 ? ` (${entry.count})` : '';
            return `<li class="match-info-scorers-item"><a class="match-team-sheet-player-link" href="${escapeAttribute(link)}">${safeName}</a>${count}</li>`;
        })
        .join('');

    return `
        <div class="match-info-scorers-group">
            <h4 class="match-info-scorers-group-title">${escapeHtml(title)}</h4>
            <ul class="match-info-scorers-list">${rows}</ul>
        </div>
    `;
}

function scorerEntryInlineHtml(entry) {
    const name = String(entry?.name || '').trim();
    const safeName = escapeHtml(name);
    const link = profileLinkHref(name);
    const count = Math.max(1, Number(entry?.count) || 1);
    const countHtml = count > 1
        ? `<span class="match-info-score-multiplier" aria-label="scored ${count} times">${count}</span>`
        : '<span class="match-info-score-multiplier match-info-score-multiplier--empty" aria-hidden="true"></span>';
    return `<span class="match-info-scorer-line"><a class="match-team-sheet-player-link" href="${escapeAttribute(link)}" style="border-bottom: none;"><span class="match-info-scorer-name">${safeName}</span></a>${countHtml}</span>`;
}

function scorerEntriesInlineHtml(entries, multiline = false) {
    if (!Array.isArray(entries) || !entries.length) return '-';
    const tokens = entries.map(entry => scorerEntryInlineHtml(entry));
    return multiline
    ? `<span class="match-info-scorer-lines">${tokens.join('')}</span>`
        : tokens.join(', ');
}

function scorerCategoriesForRow(row) {
    const categorySources = [
        {
            title: 'Tries',
            keys: ['try_scorers', 'tries_scorers', 'tries_by_player', 'triesScorers', 'tryScorers', 'tries'],
        },
        {
            title: 'Conversions',
            keys: ['conversion_scorers', 'conversions_scorers', 'conversions_by_player', 'conversionScorers', 'conversionsScorers', 'conversions', 'converters'],
        },
        {
            title: 'Penalties',
            keys: ['penalty_scorers', 'penalties_scorers', 'penalties_by_player', 'penaltyScorers', 'penaltiesScorers', 'penalties', 'penalty_kickers'],
        },
    ];

    return categorySources.map(category => {
        const raw = pickFirstScorerValue(row, category.keys);
        const entries = collapseScorerEntries(scorerEntriesFromUnknown(raw));
        return {
            title: category.title,
            entries,
            total: entries.reduce((sum, entry) => sum + (Number(entry?.count) || 0), 0),
        };
    });
}

function renderScorerMetaRow(row) {
    const categories = scorerCategoriesForRow(row);
    const hasAnyScorers = categories.some(category => category.entries.length > 0);
    if (!hasAnyScorers) return '';

    const itemBlocks = categories.map(category => `
        <div class="match-info-meta-item">
            <span class="match-info-meta-label">${escapeHtml(category.title)}</span>
            <span class="match-info-meta-value match-info-meta-value--scorers">${scorerEntriesInlineHtml(category.entries, true)}</span>
        </div>
    `);

    const itemsHtml = itemBlocks
        .map((itemHtml, index) => index < itemBlocks.length - 1
            ? `${itemHtml}<div class="match-info-meta-divider" aria-hidden="true"></div>`
            : itemHtml)
        .join('');

    return `<div class="match-info-meta-row match-info-meta-row--scoring">${itemsHtml}</div>`;
}

function renderLeadershipMetaRow(row) {
    const captain = String(row?.captain || '').trim();
    const motm = String(row?.motm || '').trim();

    if (!captain && !motm) return '';

    const items = [];

    if (captain) {
        const captainLink = profileLinkHref(captain);
        items.push(`
            <div class="match-info-meta-item">
                <span class="match-info-meta-label">Captain</span>
                <span class="match-info-meta-value"><a class="match-team-sheet-player-link" href="${escapeAttribute(captainLink)}">${escapeHtml(captain)}</a></span>
            </div>
        `);
    }

    if (motm) {
        const motmLink = profileLinkHref(motm);
        items.push(`
            <div class="match-info-meta-item">
                <span class="match-info-meta-label">Man of the Match</span>
                <span class="match-info-meta-value"><a class="match-team-sheet-player-link" href="${escapeAttribute(motmLink)}">${escapeHtml(motm)}</a></span>
            </div>
        `);
    }

    const itemsHtml = items
        .map((itemHtml, index) => index < items.length - 1
            ? `${itemHtml}<div class="match-info-meta-divider" aria-hidden="true"></div>`
            : itemHtml)
        .join('');

    const rowClass = items.length > 1 ? 'match-info-meta-row match-info-meta-row--paired' : 'match-info-meta-row';
    return `<div class="${rowClass}">${itemsHtml}</div>`;
}

function renderScorersSection(row) {
    const categoryHtml = scorerCategoriesForRow(row)
        .map(category => scorerCategoryHtml(category.title, category.entries))
        .filter(Boolean);

    if (!categoryHtml.length) return '';

    return `
        <section class="match-info-scorers" aria-label="Scorers">
            <h3 class="match-info-scorers-title">Scorers (Pitchero)</h3>
            <div class="match-info-scorers-grid">
                ${categoryHtml.join('')}
            </div>
        </section>
    `;
}

function pitcheroLinkButtonHtml(row) {
    const url = String(row?.pitchero_match_url || '').trim();
    if (!url) return '';
    return `<a class="match-info-external-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"><i class="bi bi-box-arrow-up-right" aria-hidden="true"></i><span>Open Pitchero Match Centre</span></a>`;
}

function profileLinkHref(playerName) {
    return `player-profile.html?player=${encodeURIComponent(String(playerName || '').trim())}`;
}

function formatPositionLabel(position) {
    return String(position || '')
        .trim()
    .toUpperCase()
    .replace(/\s+/g, ' ');
}

function captainBadgeHtml(isCaptain, isViceCaptain) {
    const badges = [];
    if (isCaptain) {
        badges.push('<span class="match-team-sheet-badge match-team-sheet-badge--captain"><span class="match-team-sheet-badge-label-full">Captain</span><span class="match-team-sheet-badge-label-short">C</span></span>');
    }
    if (isViceCaptain) {
        badges.push('<span class="match-team-sheet-badge match-team-sheet-badge--vice"><span class="match-team-sheet-badge-label-full">Vice Captain</span><span class="match-team-sheet-badge-label-short">VC</span></span>');
    }
    return badges.join('');
}

function ordinalSuffix(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n) || n <= 0) return String(value || '');
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
    const mod10 = n % 10;
    if (mod10 === 1) return `${n}st`;
    if (mod10 === 2) return `${n}nd`;
    if (mod10 === 3) return `${n}rd`;
    return `${n}th`;
}

function milestoneBadgeHtml(row) {
    const markers = [];
    const clubCount = Number(row?.club_appearance_number || 0);
    const firstXVCount = Number(row?.first_xv_appearance_number || 0);

    const markerMeta = {
        1: { levelClass: 'match-team-sheet-milestone--debut', iconText: '1' },
        25: { levelClass: 'match-team-sheet-milestone--25', iconText: '25' },
        50: { levelClass: 'match-team-sheet-milestone--50', iconText: '50' },
        100: { levelClass: 'match-team-sheet-milestone--100', iconText: '100' },
    };

    const pushMarker = (count, scopeClass, scopeLabel) => {
        const meta = markerMeta[count];
        if (!meta) return;
        const milestoneLabel = count === 1 ? 'debut' : `${ordinalSuffix(count)} appearance`;
        const title = `${scopeLabel} ${milestoneLabel}`;
        const markerInner = `<span class="match-team-sheet-milestone-text">${meta.iconText}</span>`;
        markers.push(
            `<span class="match-team-sheet-milestone ${scopeClass} ${meta.levelClass}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"><span class="match-team-sheet-milestone-core">${markerInner}</span></span>`
        );
    };

    if ([1, 25, 50, 100].includes(clubCount)) {
        pushMarker(clubCount, 'match-team-sheet-milestone--scope-club', 'Club');
    }

    if ([1, 25, 50, 100].includes(firstXVCount)) {
        pushMarker(firstXVCount, 'match-team-sheet-milestone--scope-first-xv', '1st XV');
    }

    return markers.join('');
}

function hasAnyMilestone(rows) {
    return rows.some(row => [1, 25, 50, 100].includes(Number(row?.club_appearance_number || 0))
        || [1, 25, 50, 100].includes(Number(row?.first_xv_appearance_number || 0)));
}

function milestoneLegendHtml(showLegend) {
    if (!showLegend) return '';

    const icon = (scopeClass, levelClass, text, title) => {
        const inner = `<span class="match-team-sheet-milestone-text">${text}</span>`;
        return `<span class="match-team-sheet-milestone ${scopeClass} ${levelClass}" aria-hidden="true" title="${escapeHtml(title)}"><span class="match-team-sheet-milestone-core">${inner}</span></span>`;
    };

    const pairedIcon = (levelClass, text, label) => `
        <span class="match-team-sheet-legend-pair" aria-hidden="true">
            <span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--club">${icon('match-team-sheet-milestone--scope-club', levelClass, text, `Club ${label}`)}</span>
            <span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--first-xv">${icon('match-team-sheet-milestone--scope-first-xv', levelClass, text, `1st XV ${label}`)}</span>
        </span>
    `;

    return `
        <div class="match-team-sheet-legend" aria-label="Appearance milestone key">
            <h4 class="match-team-sheet-legend-title">Milestone Appearances</h4>
            <div class="match-team-sheet-legend-row">
                <span class="match-team-sheet-legend-scopes">Club<br><strong>1st XV</strong></span>
                <span class="match-team-sheet-legend-item">${pairedIcon('match-team-sheet-milestone--debut', '1', 'debut')}<span class="match-team-sheet-legend-text">Debut</span></span>
                <span class="match-team-sheet-legend-item">${pairedIcon('match-team-sheet-milestone--25', '25', '25th appearance')}<span class="match-team-sheet-legend-text">25th</span></span>
                <span class="match-team-sheet-legend-item">${pairedIcon('match-team-sheet-milestone--50', '50', '50th appearance')}<span class="match-team-sheet-legend-text">50th</span></span>
                <span class="match-team-sheet-legend-item">${pairedIcon('match-team-sheet-milestone--100', '100', '100th appearance')}<span class="match-team-sheet-legend-text">100th</span></span>
            </div>
        </div>
    `;
}

function playerIdentityHtml(playerName, profile, isCaptain, isViceCaptain, row) {
    const safeName = escapeHtml(playerName || 'Unknown');
    const photoUrl = String(profile?.photo_url || '').trim();
    const hasProfile = !!profile;

    const avatar = photoUrl
        ? `<img class="match-team-sheet-avatar" src="${escapeHtml(photoUrl)}" alt="${safeName}" loading="lazy">`
        : '<span class="match-team-sheet-avatar-placeholder" aria-hidden="true"><i class="bi bi-person-fill"></i></span>';

    const nameMarkup = hasProfile
        ? `<a class="match-team-sheet-player-link" href="${profileLinkHref(playerName)}">${safeName}</a>`
        : `<span class="match-team-sheet-player-name">${safeName}</span>`;

    return `
        <span class="match-team-sheet-player-wrap">
            ${avatar}
            <span class="match-team-sheet-player-text">
                ${nameMarkup}
                ${captainBadgeHtml(isCaptain, isViceCaptain)}
                ${milestoneBadgeHtml(row)}
            </span>
        </span>
    `;
}

function positionLabelHtml(position) {
    const raw = String(position || '').trim().toUpperCase();
    if (!raw) return '';
    return `<span class="match-team-sheet-position-label" aria-label="${escapeHtml(raw)}"><span class="match-team-sheet-position-label-text">${formatPositionLabel(raw)}</span></span>`;
}

function teamSheetModeToggleLabel() {
    return isCompactTeamSheetMode ? 'Bold mode' : 'Compact mode';
}

function buildTeamSheetRows(rows, startNumber, endNumberInclusive) {
    const byNumber = new Map(rows.map(row => [Number(row?.number), row]));
    const htmlRows = [];

    for (let number = startNumber; number <= endNumberInclusive; number += 1) {
        const row = byNumber.get(number);
        const playerName = String(row?.player || '').trim();
        const profile = profilesByName.get(canonicalizeName(playerName));

        htmlRows.push(`
            <li class="match-team-sheet-item${row ? '' : ' match-team-sheet-item--empty'}">
                <span class="match-team-sheet-number-wrap">
                    <span class="match-team-sheet-number">${number}</span>
                    ${positionLabelHtml(row?.position)}
                </span>
                <span class="match-team-sheet-content">
                    ${row
                        ? `${playerIdentityHtml(playerName, profile, !!row?.is_captain, !!row?.is_vice_captain, row)}`
                        : '<span class="match-team-sheet-empty">Not listed</span>'}
                </span>
            </li>
        `);
    }

    return htmlRows.join('');
}

function buildReplacementsRows(rows) {
    const replacements = rows
        .filter(row => Number(row?.number) >= 16)
        .sort((a, b) => Number(a?.number || 0) - Number(b?.number || 0));

    if (!replacements.length) {
        return '<li class="match-team-sheet-item match-team-sheet-item--empty"><span class="match-team-sheet-number-wrap"><span class="match-team-sheet-number">16+</span></span><span class="match-team-sheet-content"><span class="match-team-sheet-empty">No replacements listed</span></span></li>';
    }

    return replacements.map(row => {
        const number = Number(row?.number || 0);
        const playerName = String(row?.player || '').trim();
        const profile = profilesByName.get(canonicalizeName(playerName));
        return `
            <li class="match-team-sheet-item">
                <span class="match-team-sheet-number-wrap">
                    <span class="match-team-sheet-number">${number}</span>
                    ${positionLabelHtml(row?.position)}
                </span>
                <span class="match-team-sheet-content">
                    ${playerIdentityHtml(playerName, profile, !!row?.is_captain, !!row?.is_vice_captain, row)}
                </span>
            </li>
        `;
    }).join('');
}

function teamSheetSectionHtml(gameId) {
    const rows = (appearancesByGameId.get(String(gameId || '').trim()) || [])
        .slice()
        .sort((a, b) => Number(a?.number || 0) - Number(b?.number || 0));
    const showMilestoneLegend = hasAnyMilestone(rows);

    if (!rows.length) {
        return `
            <section class="match-team-sheet ${isCompactTeamSheetMode ? 'match-team-sheet--compact' : 'match-team-sheet--bold'}" aria-label="Team sheet">
                <div class="match-team-sheet-header-wrap">
                    <div class="match-team-sheet-header">Team Sheet</div>
                    <button type="button" class="match-team-sheet-mode-toggle" data-team-sheet-mode-toggle aria-pressed="${isCompactTeamSheetMode ? 'true' : 'false'}">${teamSheetModeToggleLabel()}</button>
                </div>
                <p class="match-team-sheet-empty-note">No team-sheet data is available for this match.</p>
            </section>
        `;
    }

    return `
        <section class="match-team-sheet ${isCompactTeamSheetMode ? 'match-team-sheet--compact' : 'match-team-sheet--bold'}" aria-label="Team sheet">
            <div class="match-team-sheet-header-wrap">
                <div class="match-team-sheet-header">Team Sheet</div>
                <button type="button" class="match-team-sheet-mode-toggle" data-team-sheet-mode-toggle aria-pressed="${isCompactTeamSheetMode ? 'true' : 'false'}">${teamSheetModeToggleLabel()}</button>
            </div>
            <div class="match-team-sheet-starting-header">
                <h3 class="match-team-sheet-title">Starting XV</h3>
            </div>
            <div class="match-team-sheet-top-grid">
                <div class="match-team-sheet-panel match-team-sheet-panel--forwards">
                    <h4 class="match-team-sheet-subtitle">Forwards</h4>
                    <ol class="match-team-sheet-list" start="1">
                        ${buildTeamSheetRows(rows, 1, 8)}
                    </ol>
                </div>
                <div class="match-team-sheet-panel match-team-sheet-panel--backs">
                    <h4 class="match-team-sheet-subtitle">Backs</h4>
                    <ol class="match-team-sheet-list" start="9">
                        ${buildTeamSheetRows(rows, 9, 15)}
                    </ol>
                </div>
            </div>
            <div class="match-team-sheet-panel match-team-sheet-panel--replacements">
                <div class="match-team-sheet-replacements-header-wrap">
                    <h3 class="match-team-sheet-title">Replacements</h3>
                </div>
                <ol class="match-team-sheet-list" start="16">
                    ${buildReplacementsRows(rows)}
                </ol>
            </div>
            ${milestoneLegendHtml(showMilestoneLegend)}
        </section>
    `;
}

// Strip trailing roman numeral / ordinal suffixes to get the base club name.
// e.g. "Hove III" → "Hove", "Eastbourne II" → "Eastbourne", "Crawley" → "Crawley"
function baseClubName(name) {
    return String(name || '').trim()
        .replace(/\s+(I{1,3}|IV|VI{0,3}|IX|XI{0,3}|[23456789](?:st|nd|rd|th)?|2nds?|3rds?|4ths?)$/i, '')
        .trim();
}

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

function getClubLogoSrc(name) {
    const clubName = String(name || '').trim();
    if (!clubName) return '';

    // Try normalized variations of the club name (with and without roman numerals removed)
    const keys = [
        normaliseLogoKey(clubName),
        normaliseLogoKey(baseClubName(clubName)),
    ].filter(Boolean);

    // Find the first key that exists in the manifest
    for (const key of keys) {
        if (key in clubLogosManifest) {
            return `img/logos/${clubLogosManifest[key]}`;
        }
    }

    return '';
}

function teamLogoSlotHtml(src, name, side) {
    const safeSide = side === 'away' ? 'away' : 'home';
    if (!src) {
        return `<span class="match-info-team-logo-wrap match-info-team-logo-wrap--${safeSide} match-info-team-logo-wrap--empty" aria-hidden="true"></span>`;
    }

    return `
        <span class="match-info-team-logo-wrap match-info-team-logo-wrap--${safeSide}">
            <img class="match-info-team-logo" src="${escapeHtml(src)}" alt="${escapeHtml(name)} club logo" loading="lazy">
        </span>
    `;
}

function scoreLogoSlotHtml(src, name, side) {
    const safeSide = side === 'away' ? 'away' : 'home';
    if (!src) {
        return `<span class="match-info-score-logo-wrap match-info-score-logo-wrap--${safeSide} match-info-score-logo-wrap--empty" aria-hidden="true"></span>`;
    }

    return `
        <span class="match-info-score-logo-wrap match-info-score-logo-wrap--${safeSide}">
            <img class="match-info-team-logo" src="${escapeHtml(src)}" alt="${escapeHtml(name)} club logo" loading="lazy">
        </span>
    `;
}

function getFilterValues() {
    const squad = String(document.getElementById('matchFilterSquad')?.value || 'All');
    const season = String(document.getElementById('matchFilterSeason')?.value || 'All');
    const opposition = String(document.getElementById('matchFilterOpposition')?.value || 'All');
    return { squad, season, opposition };
}

function applyFilters() {
    const { squad, season, opposition } = getFilterValues();
    filteredMatches = allMatches.filter(row => {
        if (squad !== 'All' && String(row?.squad || '') !== squad) return false;
        if (season !== 'All' && String(row?.season || '') !== season) return false;
        if (opposition !== 'All' && baseClubName(String(row?.opposition || '')) !== opposition) return false;
        return true;
    });

    filteredMatches.sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')));
    pagination.page = 1;
}

function updateSelectPicker(selectEl) {
    if (!selectEl || !isSelectPickerEnabled()) return;
    rebuildBootstrapSelect(selectEl);
}

function populateBaseFilters() {
    const squadSelect = document.getElementById('matchFilterSquad');
    const seasonSelect = document.getElementById('matchFilterSeason');
    const oppositionSelect = document.getElementById('matchFilterOpposition');

    if (!squadSelect || !seasonSelect || !oppositionSelect) return;

    const squads = [...new Set(allMatches.map(row => String(row?.squad || '').trim()).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b));
    const seasons = [...new Set(allMatches.map(row => String(row?.season || '').trim()).filter(Boolean))]
        .sort((a, b) => b.localeCompare(a));
    const oppositions = [...new Set(allMatches.map(row => baseClubName(row?.opposition)).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b));

    squadSelect.innerHTML = '<option value="All" selected>All squads</option>'
        + squads.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(formatSquadLabel(value))}</option>`).join('');
    seasonSelect.innerHTML = '<option value="All" selected>All seasons</option>'
        + seasons.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    oppositionSelect.innerHTML = '<option value="All" selected>All opposition</option>'
        + oppositions.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');

    updateSelectPicker(squadSelect);
    updateSelectPicker(seasonSelect);
    updateSelectPicker(oppositionSelect);
}

function updateMatchSelectOptions(preferredGameId) {
    const matchSelect = document.getElementById('matchSelect');
    if (!matchSelect) return;

    const previousValue = String(preferredGameId || matchSelect.value || '').trim();

    matchSelect.innerHTML = '<option value="">Select match...</option>' + filteredMatches
        .map(row => {
            const gameId = String(row?.game_id || '').trim();
            const label = fixtureLabel(row);
            return `<option value="${escapeHtml(gameId)}">${escapeHtml(label)}</option>`;
        })
        .join('');

    const hasPrevious = filteredMatches.some(row => String(row?.game_id || '').trim() === previousValue);
    matchSelect.value = hasPrevious ? previousValue : '';

    // Rebuild selectpicker to reflect new options and selection
    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker) {
        const $select = window.jQuery(matchSelect);
        if ($select.data('selectpicker')) {
            $select.selectpicker('destroy');
        }
        $select.selectpicker();
        if (matchSelect.value) {
            $select.selectpicker('val', matchSelect.value);
        }
    }
}

function pagedRows() {
    const pageSize = pagination.pageSize;
    const pageCount = Math.max(1, Math.ceil(filteredMatches.length / pageSize));
    const page = Math.min(pageCount, Math.max(1, pagination.page));
    pagination.page = page;
    const start = (page - 1) * pageSize;
    return {
        page,
        pageCount,
        rows: filteredMatches.slice(start, start + pageSize),
    };
}

function renderTable() {
    const tbody = document.getElementById('matchDataTableBody');
    if (!tbody) return;

    const paged = pagedRows();
    const rowsHtml = paged.rows.map(row => {
        const gameId = String(row?.game_id || '').trim();
        const squadKey = String(row?.squad || '').trim();
        const rowClass = 'full-profile-appearance-row';
        const squadPillClass = squadKey === '1st' ? 'squad-pill squad-pill--1st'
            : squadKey === '2nd' ? 'squad-pill squad-pill--2nd'
            : 'squad-pill squad-pill--unknown';
        const squadLabel = formatSquadLabel(row?.squad);
        return `
            <tr class="${rowClass}">
                <td>${escapeHtml(formatDisplayDate(row?.date))}</td>
                <td>${escapeHtml(String(row?.season || '-'))}</td>
                <td><span class="${squadPillClass}">${escapeHtml(squadLabel)}</span></td>
                <td>${escapeHtml(String(row?.opposition || '-'))}</td>
                <td>${escapeHtml(String(row?.game_type || '-'))}</td>
                <td>${resultBadgeHtml(normaliseResult(row))}</td>
                <td><a class="match-data-link" href="match-data.html?game=${encodeURIComponent(gameId)}"><i class="bi bi-box-arrow-up-right" aria-hidden="true"></i><span>Match Data</span></a></td>
            </tr>
        `;
    }).join('');

    tbody.innerHTML = rowsHtml || '<tr><td colspan="7" class="text-muted">No matches found for these filters.</td></tr>';

    const summary = document.getElementById('matchDataPaginationSummary');
    if (summary) {
        if (!filteredMatches.length) {
            summary.textContent = '0 matches';
        } else {
            const start = (paged.page - 1) * pagination.pageSize + 1;
            const end = Math.min(filteredMatches.length, paged.page * pagination.pageSize);
            summary.textContent = `${start}-${end} of ${filteredMatches.length} matches`;
        }
    }

    const prev = document.getElementById('matchDataPrev');
    const next = document.getElementById('matchDataNext');
    if (prev) prev.disabled = paged.page <= 1;
    if (next) next.disabled = paged.page >= paged.pageCount;
}

function updateUrlGame(gameId) {
    const url = new URL(window.location.href);
    if (gameId) url.searchParams.set('game', gameId);
    else url.searchParams.delete('game');
    window.history.replaceState({}, '', url.toString());
}

function renderMatchInfo(gameId) {
    const body = document.getElementById('matchDataInfoBody');
    const headerAction = document.getElementById('matchDataInfoHeaderAction');
    if (!body) return;

    const selected = allMatches.find(row => String(row?.game_id || '').trim() === String(gameId || '').trim());
    if (!selected) {
        body.innerHTML = '<p class="text-muted" style="margin: 0;">Select a match to load full match information.</p>';
        if (headerAction) headerAction.innerHTML = '';
        updateUrlGame('');
        return;
    }

    if (headerAction) headerAction.innerHTML = pitcheroLinkButtonHtml(selected);

    updateUrlGame(String(selected.game_id || ''));

    const hero = buildMatchHeroData(selected);

    body.innerHTML = `
        <section class="match-info-hero ${hero.resultClass}">
            <div class="match-info-hero-grid">
                <div class="match-info-team match-info-team--home">
                    <div class="match-info-team-shell match-info-team-shell--home">
                        ${teamLogoSlotHtml(hero.homeLogoSrc, hero.homeTeam, 'home')}
                        <div class="match-info-team-text">
                            <div class="match-info-team-label">Home</div>
                            <div class="match-info-team-name">${escapeHtml(hero.homeTeam)}</div>
                        </div>
                    </div>
                </div>
                <div class="match-info-score-wrap" aria-label="Final score ${escapeHtml(hero.homeScore)} to ${escapeHtml(hero.awayScore)}">
                    <div class="match-info-score-line">
                        ${scoreLogoSlotHtml(hero.homeLogoSrc, hero.homeTeam, 'home')}
                        <div class="match-info-score">${escapeHtml(hero.homeScore)}<span class="match-info-score-separator">-</span>${escapeHtml(hero.awayScore)}</div>
                        ${scoreLogoSlotHtml(hero.awayLogoSrc, hero.awayTeam, 'away')}
                    </div>
                </div>
                <div class="match-info-team match-info-team--away">
                    <div class="match-info-team-shell match-info-team-shell--away">
                        ${teamLogoSlotHtml(hero.awayLogoSrc, hero.awayTeam, 'away')}
                        <div class="match-info-team-text">
                            <div class="match-info-team-label">Away</div>
                            <div class="match-info-team-name">${escapeHtml(hero.awayTeam)}</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="match-info-meta">
                <div class="match-info-meta-row match-info-meta-row--paired">
                    <div class="match-info-meta-item">
                        <span class="match-info-meta-label">Date</span>
                        <span class="match-info-meta-value">${escapeHtml(hero.date)}</span>
                    </div>
                    <div class="match-info-meta-divider" aria-hidden="true"></div>
                    <div class="match-info-meta-item">
                        <span class="match-info-meta-label">Competition</span>
                        <span class="match-info-meta-value">${escapeHtml(hero.competition)}</span>
                    </div>
                </div>
                ${renderLeadershipMetaRow(selected)}
                ${renderScorerMetaRow(selected)}
            </div>
        </section>
        ${teamSheetSectionHtml(selected.game_id)}
    `;

    // Collapse the Filtered Matches panel when a game is selected
    collapseFilteredMatchesPanel();
}

function refreshFromFilters(preferredGameId) {
    applyFilters();
    updateMatchSelectOptions(preferredGameId);
    renderTable();

    const matchSelect = document.getElementById('matchSelect');
    const selectedGameId = String(matchSelect?.value || '').trim();
    renderMatchInfo(selectedGameId);
}

function collapseFilteredMatchesPanel() {
    const toggle = document.querySelector('.chart-panel-toggle[data-target="match-list-panel"]');
    const panel = document.getElementById('match-list-panel');
    if (!toggle || !panel) return;
    const isExpanded = toggle.getAttribute('aria-expanded') !== 'false';
    if (isExpanded) toggle.click();
}

function bindTeamSheetModeToggle() {
    const infoBody = document.getElementById('matchDataInfoBody');
    if (!infoBody || infoBody.__teamSheetToggleBound) return;

    infoBody.addEventListener('click', event => {
        const toggle = event.target.closest('[data-team-sheet-mode-toggle]');
        if (!toggle) return;
        isCompactTeamSheetMode = !isCompactTeamSheetMode;
        const matchSelect = document.getElementById('matchSelect');
        const selectedGameId = String(matchSelect?.value || '').trim();
        renderMatchInfo(selectedGameId);
    });

    infoBody.__teamSheetToggleBound = true;
}

function bindControls(initialGameId) {
    const squad = document.getElementById('matchFilterSquad');
    const season = document.getElementById('matchFilterSeason');
    const opposition = document.getElementById('matchFilterOpposition');
    const matchSelect = document.getElementById('matchSelect');
    const prev = document.getElementById('matchDataPrev');
    const next = document.getElementById('matchDataNext');

    // Handle filter changes (squad, season, opposition)
    [squad, season, opposition].forEach(selectEl => {
        if (!selectEl) return;
        if (isSelectPickerEnabled()) {
            window.jQuery(selectEl)
                .off('changed.bs.select.matchFilters')
                .on('changed.bs.select.matchFilters', () => {
                    if (isInitialisingControls) return;
                    refreshFromFilters('');
                });
        } else {
            selectEl.removeEventListener('change', null);
            selectEl.addEventListener('change', () => refreshFromFilters(''));
        }
    });

    // Handle match select changes - single unified listener
    if (matchSelect) {
        // Remove all existing listeners to prevent stacking
        matchSelect.removeEventListener('change', null);
        if (window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker) {
            window.jQuery(matchSelect).off('changed.bs.select.matchSelect');
        }

        // Add single change listener (works for both selectpicker and native select)
        matchSelect.addEventListener('change', () => {
            if (isInitialisingControls) return;
            const selectedGameId = String(matchSelect.value || '').trim();
            renderMatchInfo(selectedGameId);
        });

        // Also bind Bootstrap Select event if available
        if (isSelectPickerEnabled()) {
            window.jQuery(matchSelect)
                .on('changed.bs.select.matchSelect', () => {
                    if (isInitialisingControls) return;
                    const selectedGameId = String(matchSelect.value || '').trim();
                    renderMatchInfo(selectedGameId);
                });
        }
    }

    if (prev) {
        prev.addEventListener('click', () => {
            pagination.page = Math.max(1, pagination.page - 1);
            renderTable();
        });
    }

    if (next) {
        next.addEventListener('click', () => {
            pagination.page += 1;
            renderTable();
        });
    }

    isInitialisingControls = true;
    refreshFromFilters(initialGameId);
    isInitialisingControls = false;
}

async function loadPage() {
    const errorEl = document.getElementById('matchDataError');
    try {
        const [gamesResponse, appearancesResponse, profilesResponse] = await Promise.all([
            fetch('data/backend/games.json'),
            fetch('data/backend/player_appearances.json'),
            fetch('data/backend/player_profiles_canonical.json'),
            loadLogosManifest()  // Load in parallel
        ]);
        if (!gamesResponse.ok) throw new Error(`Failed to load games (${gamesResponse.status})`);

        const games = await gamesResponse.json();
        const appearances = appearancesResponse.ok ? await appearancesResponse.json() : [];
        const profiles = profilesResponse.ok ? await profilesResponse.json() : [];

        allMatches = Array.isArray(games) ? games.filter(row => row && row.game_id) : [];
        allMatches.sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')));

        appearancesByGameId = new Map();
        (Array.isArray(appearances) ? appearances : []).forEach(row => {
            const gameId = String(row?.game_id || '').trim();
            if (!gameId) return;
            if (!appearancesByGameId.has(gameId)) appearancesByGameId.set(gameId, []);
            appearancesByGameId.get(gameId).push(row);
        });

        profilesByName = new Map();
        (Array.isArray(profiles) ? profiles : []).forEach(profile => {
            const key = canonicalizeName(profile?.name);
            if (!key) return;
            const existing = profilesByName.get(key);
            profilesByName.set(key, choosePreferredProfile(existing, profile));
        });

        populateBaseFilters();

        const url = new URL(window.location.href);
        const initialGameId = String(url.searchParams.get('game') || '').trim();
        bindControls(initialGameId);
        bindTeamSheetModeToggle();

        initialiseChartPanelToggles();

        if (initialGameId && allMatches.some(row => String(row?.game_id || '').trim() === initialGameId)) {
            collapseFilteredMatchesPanel();
        }
    } catch (error) {
        console.error(error);
        if (errorEl) {
            errorEl.classList.remove('d-none');
            errorEl.textContent = 'Unable to load match data. Run python/update.py and refresh this page.';
        }
    }
}

document.addEventListener('DOMContentLoaded', loadPage);

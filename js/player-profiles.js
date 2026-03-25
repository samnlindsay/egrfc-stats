let playerProfilesData = [];
let playerProfilesControlsInitialised = false;

const SIX_MONTHS_MS = 182 * 24 * 60 * 60 * 1000;

function dedupeProfilesByName(rows) {
    const byName = new Map();

    (Array.isArray(rows) ? rows : []).forEach(row => {
        const name = String(row?.name || '').trim();
        if (!name) return;

        const current = byName.get(name);
        const candidateAppearances = Number(row?.total_appearances || 0);
        const currentAppearances = Number(current?.total_appearances || 0);

        if (!current || candidateAppearances > currentAppearances) {
            byName.set(name, row);
        }
    });

    return Array.from(byName.values()).sort(compareBySurnameThenName);
}

function surnamePart(name) {
    const tokens = String(name || '')
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    return tokens.length ? tokens[tokens.length - 1].toLowerCase() : '';
}

function firstNamePart(name) {
    const tokens = String(name || '')
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    return tokens.length ? tokens[0].toLowerCase() : '';
}

const POSITION_SORT_ORDER = [
    ['loosehead prop', 1],
    ['tighthead prop', 2],
    ['prop', 3],
    ['hooker', 4],
    ['lock', 5],
    ['second row', 6],
    ['blindside flanker', 7],
    ['openside flanker', 8],
    ['flanker', 9],
    ['number 8', 10],
    ['scrum half', 11],
    ['fly half', 12],
    ['centre', 13],
    ['back three', 14],
    ['wing', 15],
    ['full back', 16],
    ['bench', 99]
];

const POSITION_SECTION_ORDER = [
    'Prop',
    'Hooker',
    'Second Row',
    'Flanker',
    'Number 8',
    'Scrum Half',
    'Fly Half',
    'Centre',
    'Wing',
    'Full Back',
    'Bench',
    'Other'
];

function positionRank(position) {
    const normalized = String(position || '').trim().toLowerCase();
    if (!normalized) return 999;

    for (const [pattern, rank] of POSITION_SORT_ORDER) {
        if (normalized.includes(pattern)) return rank;
    }

    return 500;
}

function positionSectionTitle(position) {
    const normalized = String(position || '').trim().toLowerCase();
    if (!normalized) return 'Other';

    if (normalized.includes('prop')) return 'Prop';
    if (normalized.includes('hooker')) return 'Hooker';
    if (normalized.includes('lock') || normalized.includes('second row')) return 'Second Row';
    if (normalized.includes('flanker')) return 'Flanker';
    if (normalized.includes('number 8')) return 'Number 8';
    if (normalized.includes('scrum half')) return 'Scrum Half';
    if (normalized.includes('fly half')) return 'Fly Half';
    if (normalized.includes('centre')) return 'Centre';
    if (normalized.includes('wing') || normalized.includes('back three')) return 'Wing';
    if (normalized.includes('full back') || normalized.includes('fullback')) return 'Full Back';
    if (normalized.includes('bench')) return 'Bench';

    return 'Other';
}

function positionSectionRank(sectionTitle) {
    const index = POSITION_SECTION_ORDER.indexOf(sectionTitle);
    if (index === -1) return 999;
    return index + 1;
}

function compareBySurnameThenName(a, b) {
    const aSurname = surnamePart(a?.name);
    const bSurname = surnamePart(b?.name);
    const bySurname = aSurname.localeCompare(bSurname);
    if (bySurname !== 0) return bySurname;
    return String(a?.name || '').localeCompare(String(b?.name || ''));
}

function compareByFirstNameThenSurname(a, b) {
    const aFirstName = firstNamePart(a?.name);
    const bFirstName = firstNamePart(b?.name);
    const byFirstName = aFirstName.localeCompare(bFirstName);
    if (byFirstName !== 0) return byFirstName;
    return compareBySurnameThenName(a, b);
}

function compareByPositionThenName(a, b) {
    const byPosition = positionRank(a?.position) - positionRank(b?.position);
    if (byPosition !== 0) return byPosition;

    const byPositionName = String(a?.position || '').localeCompare(String(b?.position || ''));
    if (byPositionName !== 0) return byPositionName;

    return compareBySurnameThenName(a, b);
}

function compareByAppearancesDesc(a, b) {
    const byAppearances = Number(b?.totalAppearances || 0) - Number(a?.totalAppearances || 0);
    if (byAppearances !== 0) return byAppearances;
    return compareBySurnameThenName(a, b);
}

function sortedProfiles(rows, sortMode) {
    const copy = [...rows];

    if (sortMode === 'firstName') {
        return copy.sort(compareByFirstNameThenSurname);
    }

    if (sortMode === 'position') {
        return copy.sort(compareByPositionThenName);
    }

    if (sortMode === 'appearances') {
        return copy.sort(compareByAppearancesDesc);
    }

    return copy.sort(compareBySurnameThenName);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function createAvatarMarkup(profile) {
    const name = escapeHtml(profile?.name || 'Player');
    const photoUrl = String(profile?.photo_url || '').trim();

    if (photoUrl) {
        return `<img src="${escapeHtml(photoUrl)}" alt="${name}" class="player-profile-avatar" loading="lazy">`;
    }

    return '<div class="player-profile-avatar-placeholder"><i class="bi bi-person-fill" aria-hidden="true"></i></div>';
}

function headshotBackgroundClass(profile) {
    const squad = String(profile?.squad || '').trim().toLowerCase();
    return squad === '2nd'
        ? 'player-profile-headshot-wrap-2nd'
        : 'player-profile-headshot-wrap-1st';
}

function parseIsoDate(dateValue) {
    if (!dateValue) return null;
    const parsed = new Date(dateValue);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function ordinal(day) {
    const mod10 = day % 10;
    const mod100 = day % 100;
    if (mod10 === 1 && mod100 !== 11) return `${day}st`;
    if (mod10 === 2 && mod100 !== 12) return `${day}nd`;
    if (mod10 === 3 && mod100 !== 13) return `${day}rd`;
    return `${day}th`;
}

function formatDateForDebut(dateValue) {
    const parsed = parseIsoDate(dateValue);
    if (!parsed) return '-';
    const day = ordinal(parsed.getDate());
    const month = parsed.toLocaleString('en-GB', { month: 'short' });
    const year = parsed.getFullYear();
    return `${day} ${month} ${year}`;
}

function formatDebutLabel(appearanceRow, gamesById) {
    if (!appearanceRow) return '-';
    const game = gamesById.get(String(appearanceRow.game_id || ''));
    const opposition = game?.opposition || appearanceRow?.opposition || 'Unknown';
    const homeAway = game?.home_away || '?';
    return `${formatDateForDebut(appearanceRow.date)} v ${opposition} (${homeAway})`;
}

function formatPointsSummary(points, tries, conversions, penalties, dropGoals) {
    const totalPoints = Number(points || 0);
    const totalTries = Number(tries || 0);
    const totalConversions = Number(conversions || 0);
    const totalPenalties = Number(penalties || 0);
    const totalDropGoals = Number(dropGoals || 0);

    const components = [`${totalTries} tries`];
    if (totalConversions > 0) components.push(`${totalConversions} conversions`);
    if (totalPenalties > 0) components.push(`${totalPenalties} penalties`);
    if (totalDropGoals > 0) components.push(`${totalDropGoals} drop goals`);

    return `${totalPoints} (${components.join(', ')})`;
}

function buildPlayerContext(appearances, games, seasonScorers) {
    const appearancesByPlayer = new Map();
    (Array.isArray(appearances) ? appearances : []).forEach(row => {
        const player = String(row?.player || '').trim();
        if (!player) return;
        if (!appearancesByPlayer.has(player)) appearancesByPlayer.set(player, []);
        appearancesByPlayer.get(player).push(row);
    });

    appearancesByPlayer.forEach(rows => {
        rows.sort((a, b) => String(a?.date || '').localeCompare(String(b?.date || '')));
    });

    const gamesById = new Map();
    (Array.isArray(games) ? games : []).forEach(game => {
        gamesById.set(String(game?.game_id || ''), game);
    });

    const scoringByPlayerAndSeason = new Map();
    const scoringByPlayerCareer = new Map();
    (Array.isArray(seasonScorers) ? seasonScorers : []).forEach(row => {
        const player = String(row?.player || '').trim();
        const season = String(row?.season || '').trim();
        if (!player || !season) return;

        const key = `${player}::${season}`;
        if (!scoringByPlayerAndSeason.has(key)) {
            scoringByPlayerAndSeason.set(key, { tries: 0, conversions: 0, penalties: 0, drop_goals: 0, points: 0 });
        }
        const seasonBucket = scoringByPlayerAndSeason.get(key);
        seasonBucket.tries += Number(row?.tries || 0);
        seasonBucket.conversions += Number(row?.conversions || 0);
        seasonBucket.penalties += Number(row?.penalties || 0);
        seasonBucket.drop_goals += Number(row?.drop_goals || 0);
        seasonBucket.points += Number(row?.points || 0);

        if (!scoringByPlayerCareer.has(player)) {
            scoringByPlayerCareer.set(player, { tries: 0, conversions: 0, penalties: 0, drop_goals: 0, points: 0 });
        }
        const careerBucket = scoringByPlayerCareer.get(player);
        careerBucket.tries += Number(row?.tries || 0);
        careerBucket.conversions += Number(row?.conversions || 0);
        careerBucket.penalties += Number(row?.penalties || 0);
        careerBucket.drop_goals += Number(row?.drop_goals || 0);
        careerBucket.points += Number(row?.points || 0);
    });

    let currentSeason = '';
    let latestGameDate = null;
    (Array.isArray(games) ? games : []).forEach(game => {
        const parsed = parseIsoDate(game?.date);
        if (!parsed) return;
        if (!latestGameDate || parsed > latestGameDate) {
            latestGameDate = parsed;
            currentSeason = String(game?.season || '');
        }
    });

    return {
        appearancesByPlayer,
        gamesById,
        scoringByPlayerAndSeason,
        scoringByPlayerCareer,
        currentSeason,
        latestGameDate,
    };
}

function enrichProfile(profile, context) {
    const playerName = String(profile?.name || '').trim();
    const rows = context.appearancesByPlayer.get(playerName) || [];
    const firstRow = rows.length ? rows[0] : null;
    const first1stRow = rows.find(row => String(row?.squad || '') === '1st') || null;
    const lastRow = rows.length ? rows[rows.length - 1] : null;

    const totalAppearances = Number(profile?.total_appearances || rows.length || 0);
    const totalStarts = rows.reduce((acc, row) => acc + (row?.is_starter ? 1 : 0), 0) || Number(profile?.total_starts || 0);

    const firstXVRows = rows.filter(row => String(row?.squad || '') === '1st');
    const firstXVAppearances = firstXVRows.length;
    const firstXVStarts = firstXVRows.reduce((acc, row) => acc + (row?.is_starter ? 1 : 0), 0);

    const currentSeason = context.currentSeason;
    const seasonRows = rows.filter(row => String(row?.season || '') === currentSeason);
    const seasonAppearances = seasonRows.length;
    const seasonStarts = seasonRows.reduce((acc, row) => acc + (row?.is_starter ? 1 : 0), 0);

    const scoringCareer = context.scoringByPlayerCareer.get(playerName) || {
        tries: Number(profile?.career_points || 0) / 5,
        conversions: 0,
        penalties: 0,
        drop_goals: 0,
        points: Number(profile?.career_points || 0)
    };

    const scoringThisSeason = context.scoringByPlayerAndSeason.get(`${playerName}::${currentSeason}`) || {
        tries: 0,
        conversions: 0,
        penalties: 0,
        drop_goals: 0,
        points: 0
    };

    const positionCounts = new Map();
    rows
        .map(row => String(row?.position || '').trim())
        .filter(Boolean)
        .forEach(position => {
            positionCounts.set(position, (positionCounts.get(position) || 0) + 1);
        });
    const startingPositionCounts = new Map();
    rows
        .filter(row => Boolean(row?.is_starter))
        .map(row => String(row?.position || '').trim())
        .filter(position => position && position !== 'Bench')
        .forEach(position => {
            startingPositionCounts.set(position, (startingPositionCounts.get(position) || 0) + 1);
        });

    let primaryPosition = String(profile?.position || 'Unknown');
    if (startingPositionCounts.size > 0) {
        const sortedStartingPositions = Array.from(startingPositionCounts.entries())
            .sort((a, b) => {
                const byCount = b[1] - a[1];
                if (byCount !== 0) return byCount;
                return a[0].localeCompare(b[0]);
            });
        primaryPosition = sortedStartingPositions[0][0];
    }

    const otherPositions = Array.from(positionCounts.entries())
        .filter(([position, count]) => position !== primaryPosition && position !== 'Bench' && count > 1)
        .map(([position]) => position)
        .sort((a, b) => a.localeCompare(b));

    const lastAppearanceDate = parseIsoDate(lastRow?.date);
    const playedThisSeason = seasonRows.length > 0;
    const isActive = playedThisSeason || Boolean(lastAppearanceDate && (Date.now() - lastAppearanceDate.getTime()) <= SIX_MONTHS_MS);

    return {
        ...profile,
        position: primaryPosition,
        totalAppearances,
        totalStarts,
        firstXVAppearances,
        firstXVStarts,
        seasonAppearances,
        seasonStarts,
        scoringCareer,
        scoringThisSeason,
        debutOverall: formatDebutLabel(firstRow, context.gamesById),
        debutFirstXV: formatDebutLabel(first1stRow, context.gamesById),
        hasDifferentFirstXVDebut: Boolean(firstRow && first1stRow && firstRow.game_id !== first1stRow.game_id),
        otherPositions,
        isActive,
        lastAppearanceDate
    };
}

function cardDetailsMarkup(profile) {
    const totalTries = Number(profile?.scoringCareer?.tries || 0);
    const totalPoints = Number(profile?.scoringCareer?.points || 0);
    const conversions = Number(profile?.scoringCareer?.conversions || 0);
    const penalties = Number(profile?.scoringCareer?.penalties || 0);
    const dropGoals = Number(profile?.scoringCareer?.drop_goals || 0);
    const hasKickedPoints = conversions > 0 || penalties > 0 || dropGoals > 0;

    const lines = [];
    const sponsor = String(profile?.sponsor || '').trim();
    const hasCurrentSeasonSponsor = sponsor && Number(profile?.seasonAppearances || 0) > 0;

    if (hasCurrentSeasonSponsor) {
        lines.push(`<p class="player-profile-detail-line player-profile-detail-sponsor">sponsored by ${escapeHtml(sponsor)}</p>`);
    }

    if (profile.otherPositions.length > 0) {
        lines.push(`<p class="player-profile-detail-line"><strong>Other positions:</strong> ${escapeHtml(profile.otherPositions.join(', '))}</p>`);
    }

    lines.push(`<p class="player-profile-detail-line"><strong>Total appearances:</strong> ${profile.totalAppearances} (${profile.totalStarts} starts)</p>`);

    if (profile.firstXVAppearances > 0) {
        lines.push(`<p class="player-profile-detail-line"><strong>1st XV appearances:</strong> ${profile.firstXVAppearances} (${profile.firstXVStarts} starts)</p>`);
    }

    lines.push(`<p class="player-profile-detail-line"><strong>Debut:</strong> ${escapeHtml(profile.debutOverall)}</p>`);

    if (profile.hasDifferentFirstXVDebut) {
        lines.push(`<p class="player-profile-detail-line"><strong>1st XV debut:</strong> ${escapeHtml(profile.debutFirstXV)}</p>`);
    }

    lines.push(`<p class="player-profile-detail-line"><strong>Total tries:</strong> ${totalTries}</p>`);

    if (hasKickedPoints) {
        lines.push(`<p class="player-profile-detail-line"><strong>Total points:</strong> ${formatPointsSummary(totalPoints, totalTries, conversions, penalties, dropGoals)}</p>`);
    }

    lines.push(
        `<p class="player-profile-detail-line"><strong>This season:</strong> ${profile.seasonAppearances} appearances (${profile.seasonStarts} starts), ${Number(profile.scoringThisSeason.tries || 0)} tries</p>`
    );

    return lines.join('');
}

function profileCardMarkup(profile) {
    const displayName = escapeHtml(profile.name || 'Unknown player');
    const displayPosition = escapeHtml(profile.position || 'Unknown');
    const activeTag = profile.isActive
        ? '<span class="player-profile-active-tag">Active</span>'
        : '';
    const avatarMarkup = createAvatarMarkup(profile);
    const squadClass = String(profile.squad || '').trim().toLowerCase() === '2nd' ? '2nd' : '1st';

    return `
        <div class="player-profile-grid-item">
            <article class="card player-profile-card player-profile-card-${squadClass} squad-metric-card-${squadClass}" data-profile-card>
                <div class="player-profile-headshot-wrap ${headshotBackgroundClass(profile)}">
                    ${avatarMarkup}
                    ${activeTag ? `<span class="player-profile-active-tag player-profile-active-tag-headshot">Active</span>` : ''}
                </div>
                <button
                    type="button"
                    class="player-profile-summary player-profile-summary-${squadClass} league-team-title-${squadClass}"
                    data-profile-toggle
                    aria-expanded="false"
                >
                    <div class="player-profile-summary-left">
                        <div class="player-profile-summary-name">${displayName}</div>
                        <div class="player-profile-summary-subtitle">${displayPosition}</div>
                    </div>
                    <div class="player-profile-summary-right">
                        <div class="player-profile-summary-meta-row">
                            <span class="player-profile-summary-count">${profile.totalAppearances}</span>
                        </div>
                        <span class="player-profile-summary-label">apps</span>
                        <i class="bi bi-chevron-down player-profile-chevron" aria-hidden="true"></i>
                    </div>
                </button>
                <div class="player-profile-details" hidden>
                    ${cardDetailsMarkup(profile)}
                </div>
            </article>
        </div>
    `;
}

function renderGroupedByPosition(profiles) {
    const groups = new Map();

    profiles.forEach(profile => {
        const sectionTitle = positionSectionTitle(profile?.position);
        if (!groups.has(sectionTitle)) groups.set(sectionTitle, []);
        groups.get(sectionTitle).push(profile);
    });

    return Array.from(groups.entries())
        .sort((a, b) => {
            const byRank = positionSectionRank(a[0]) - positionSectionRank(b[0]);
            if (byRank !== 0) return byRank;
            return String(a[0]).localeCompare(String(b[0]));
        })
        .map(([sectionTitle, groupProfiles]) => {
            const cards = groupProfiles.map(profileCardMarkup).join('');
            return `
                <section class="player-profiles-position-section">
                    <h2 class="player-profiles-position-section-title">${escapeHtml(sectionTitle)}</h2>
                    <div class="player-profiles-grid">${cards}</div>
                </section>
            `;
        })
        .join('');
}

function renderPlayerProfiles() {
    const grid = document.getElementById('playerProfilesGrid');
    const emptyState = document.getElementById('playerProfilesEmptyState');
    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    const sortSelect = document.getElementById('playerProfileSortFilter');
    const activeOnlyToggle = document.getElementById('playerProfileActiveOnly');

    if (!grid || !emptyState) return;

    const selectedPlayers = new Set(
        Array.from(playerSelect?.selectedOptions || [])
            .map(option => String(option?.value || '').trim())
            .filter(Boolean)
    );
    const squadFilter = String(squadSelect?.value || 'All');
    const positionFilter = String(positionSelect?.value || 'All');
    const sortMode = String(sortSelect?.value || 'firstName');
    const activeOnly = Boolean(activeOnlyToggle?.checked);

    const filteredBase = playerProfilesData
        .filter(profile => {
            const name = String(profile.name || '');
            const position = String(profile.position || 'Unknown');
            const squad = String(profile.squad || 'Unknown');

            if (selectedPlayers.size > 0 && !selectedPlayers.has(name)) return false;
            if (squadFilter !== 'All' && squad !== squadFilter) return false;
            if (positionFilter !== 'All' && position !== positionFilter) return false;
            if (activeOnly && !profile.isActive) return false;
            return true;
        });

    const filtered = sortedProfiles(filteredBase, sortMode);

    if (filtered.length === 0) {
        grid.innerHTML = '';
        emptyState.classList.remove('d-none');
        return;
    }

    emptyState.classList.add('d-none');

    if (sortMode === 'position') {
        grid.innerHTML = `<div class="player-profiles-position-sections">${renderGroupedByPosition(filtered)}</div>`;
        return;
    }

    grid.innerHTML = filtered.map(profileCardMarkup).join('');
}

function populateFilters() {
    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    const sortSelect = document.getElementById('playerProfileSortFilter');
    if (!playerSelect || !squadSelect || !positionSelect) return;

    const playerNames = playerProfilesData
        .map(row => String(row.name || '').trim())
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b));
    const squads = Array.from(new Set(playerProfilesData.map(row => String(row.squad || 'Unknown'))))
        .filter(squad => {
            const normalized = String(squad || '').trim().toLowerCase();
            return normalized !== 'all' && normalized !== 'all squads';
        })
        .sort();
    const positions = Array.from(new Set(playerProfilesData.map(row => String(row.position || 'Unknown'))))
        .filter(position => {
            const normalized = String(position || '').trim().toLowerCase();
            return normalized !== 'all' && normalized !== 'all positions';
        })
        .sort();

    playerSelect.innerHTML = playerNames
        .map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
        .join('');
    squadSelect.innerHTML = '<option value="All">All squads</option>' +
        squads.map(squad => `<option value="${escapeHtml(squad)}">${escapeHtml(squad)}</option>`).join('');
    positionSelect.innerHTML = '<option value="All">All positions</option>' +
        positions.map(position => `<option value="${escapeHtml(position)}">${escapeHtml(position)}</option>`).join('');

    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker) {
        const $playerSelect = window.jQuery(playerSelect);
        const $squadSelect = window.jQuery(squadSelect);
        const $positionSelect = window.jQuery(positionSelect);
        const selectedSort = String(sortSelect?.value || 'firstName');

        [$playerSelect, $squadSelect, $positionSelect].forEach($el => {
            if ($el.data('selectpicker')) $el.selectpicker('destroy');
            $el.selectpicker();
            $el.off('changed.bs.select.playerProfiles').on('changed.bs.select.playerProfiles', renderPlayerProfiles);
        });
        $playerSelect.selectpicker('deselectAll');
        $squadSelect.selectpicker('val', 'All');
        $positionSelect.selectpicker('val', 'All');

        if (sortSelect) {
            const $sortSelect = window.jQuery(sortSelect);
            if ($sortSelect.data('selectpicker')) $sortSelect.selectpicker('destroy');
            $sortSelect.selectpicker();
            $sortSelect.selectpicker('val', selectedSort);
            $sortSelect.off('changed.bs.select.playerProfiles').on('changed.bs.select.playerProfiles', renderPlayerProfiles);
        }
    }
}

function initialisePlayerProfilesControls() {
    if (playerProfilesControlsInitialised) return;

    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    const sortSelect = document.getElementById('playerProfileSortFilter');
    const activeOnlyToggle = document.getElementById('playerProfileActiveOnly');

    if (!playerSelect || !squadSelect || !positionSelect || !sortSelect) return;

    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker) {
        const $playerSelect = window.jQuery(playerSelect);
        const $squadSelect = window.jQuery(squadSelect);
        const $positionSelect = window.jQuery(positionSelect);
        const $sortSelect = window.jQuery(sortSelect);

        [$playerSelect, $squadSelect, $positionSelect, $sortSelect].forEach($el => {
            if ($el.data('selectpicker')) $el.selectpicker('destroy');
            $el.selectpicker();
            $el.off('changed.bs.select.playerProfiles').on('changed.bs.select.playerProfiles', renderPlayerProfiles);
        });
    } else {
        playerSelect.addEventListener('change', renderPlayerProfiles);
        squadSelect.addEventListener('change', renderPlayerProfiles);
        positionSelect.addEventListener('change', renderPlayerProfiles);
        sortSelect.addEventListener('change', renderPlayerProfiles);
    }

    activeOnlyToggle?.addEventListener('change', renderPlayerProfiles);
    playerProfilesControlsInitialised = true;
}

function bindCardToggle() {
    const grid = document.getElementById('playerProfilesGrid');
    if (!grid) return;

    grid.addEventListener('click', event => {
        const toggleButton = event.target.closest('[data-profile-toggle]');
        if (!toggleButton) return;

        const card = toggleButton.closest('[data-profile-card]');
        const details = card?.querySelector('.player-profile-details');
        if (!card || !details) return;

        const isExpanded = card.classList.toggle('is-expanded');
        details.hidden = !isExpanded;
        toggleButton.setAttribute('aria-expanded', String(isExpanded));
    });
}

async function loadPlayerProfilesPage() {
    const loadingState = document.getElementById('playerProfilesLoadingState');
    const errorState = document.getElementById('playerProfilesErrorState');

    try {
            const [profilesRes, appearancesRes, gamesRes, scorersRes] = await Promise.all([
            fetch('data/backend/v_player_profiles.json'),
            fetch('data/backend/player_appearances.json'),
            fetch('data/backend/games.json'),
                fetch('data/backend/season_scorers.json')
        ]);

            if (!profilesRes.ok || !appearancesRes.ok || !gamesRes.ok || !scorersRes.ok) {
            throw new Error('One or more profile datasets failed to load');
        }

            const [rawProfiles, rawAppearances, rawGames, rawScorers] = await Promise.all([
            profilesRes.json(),
            appearancesRes.json(),
            gamesRes.json(),
                scorersRes.json()
        ]);

            const context = buildPlayerContext(rawAppearances, rawGames, rawScorers);
        playerProfilesData = dedupeProfilesByName(rawProfiles).map(profile => enrichProfile(profile, context));

        populateFilters();
        renderPlayerProfiles();

        if (loadingState) loadingState.classList.add('d-none');
        if (errorState) errorState.classList.add('d-none');
    } catch (error) {
        console.error('Unable to load player profiles:', error);
        if (loadingState) loadingState.classList.add('d-none');
        if (errorState) {
            errorState.classList.remove('d-none');
            errorState.textContent = 'Unable to load player profile data. Run python/update.py to rebuild data/backend exports.';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initialisePlayerProfilesControls();
    bindCardToggle();
    loadPlayerProfilesPage();
});

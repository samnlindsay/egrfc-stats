let playerProfilesData = [];

const THIRTEEN_MONTHS_MS = 365 * 24 * 60 * 60 * 1000;

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

function compareBySurnameThenName(a, b) {
    const aSurname = surnamePart(a?.name);
    const bSurname = surnamePart(b?.name);
    const bySurname = aSurname.localeCompare(bSurname);
    if (bySurname !== 0) return bySurname;
    return String(a?.name || '').localeCompare(String(b?.name || ''));
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

function buildPlayerContext(appearances, games, seasonScorers, appearanceReconciliation) {
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

    const reconciledByPlayerSeason = new Map();
    const reconciledByPlayerSquad = new Map();
    (Array.isArray(appearanceReconciliation) ? appearanceReconciliation : []).forEach(row => {
        const player = String(row?.player || '').trim();
        const season = String(row?.season || '').trim();
        const squad = String(row?.squad || '').trim();
        const pitchero = Number(row?.pitchero_appearances || 0);
        const scraped = Number(row?.scraped_appearances || 0);
        const effective = pitchero > 0 ? pitchero : scraped;
        if (!player || !season || !squad || !effective) return;

        const seasonKey = `${player}::${season}`;
        const squadKey = `${player}::${squad}`;
        reconciledByPlayerSeason.set(seasonKey, (reconciledByPlayerSeason.get(seasonKey) || 0) + effective);
        reconciledByPlayerSquad.set(squadKey, (reconciledByPlayerSquad.get(squadKey) || 0) + effective);
    });

    return {
        appearancesByPlayer,
        gamesById,
        scoringByPlayerAndSeason,
        scoringByPlayerCareer,
        currentSeason,
        latestGameDate,
        reconciledByPlayerSeason,
        reconciledByPlayerSquad
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
    const firstXVAppearances = Number(
        context.reconciledByPlayerSquad.get(`${playerName}::1st`) || firstXVRows.length || 0
    );
    const firstXVStarts = firstXVRows.reduce((acc, row) => acc + (row?.is_starter ? 1 : 0), 0);

    const currentSeason = context.currentSeason;
    const seasonRows = rows.filter(row => String(row?.season || '') === currentSeason);
    const seasonAppearances = Number(
        context.reconciledByPlayerSeason.get(`${playerName}::${currentSeason}`) || seasonRows.length || 0
    );
    const seasonStarts = seasonRows.reduce((acc, row) => acc + (row?.is_starter ? 1 : 0), 0);

    const scoringCareer = context.scoringByPlayerCareer.get(playerName) || {
        tries: Number(profile?.career_points || 0) / 5,
        conversions: 0,
        penalties: 0,
        drop_goals: 0,
        points: Number(profile?.career_points || 0)
    };

    const scoringThisSeason = context.scoringByPlayerAndSeason.get(`${playerName}::${currentSeason}`) || {
        tries: Number(profile?.latest_season_tries || 0),
        conversions: Number(profile?.latest_season_conversions || 0),
        penalties: Number(profile?.latest_season_penalties || 0),
        drop_goals: 0,
        points: Number(profile?.latest_season_points || 0)
    };

    const positions = Array.from(new Set(
        rows
            .map(row => String(row?.position || '').trim())
            .filter(Boolean)
    ));
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

    const otherPositions = positions.filter(position => position !== primaryPosition && position !== 'Bench');

    const lastAppearanceDate = parseIsoDate(lastRow?.date);
    const isActive = Boolean(lastAppearanceDate && (Date.now() - lastAppearanceDate.getTime()) <= THIRTEEN_MONTHS_MS);

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

function renderPlayerProfiles() {
    const grid = document.getElementById('playerProfilesGrid');
    const emptyState = document.getElementById('playerProfilesEmptyState');
    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    const activeOnlyToggle = document.getElementById('playerProfileActiveOnly');

    if (!grid || !emptyState) return;

    const selectedPlayers = new Set(
        Array.from(playerSelect?.selectedOptions || [])
            .map(option => String(option?.value || '').trim())
            .filter(Boolean)
    );
    const squadFilter = String(squadSelect?.value || 'All');
    const positionFilter = String(positionSelect?.value || 'All');
    const activeOnly = Boolean(activeOnlyToggle?.checked);

    const filtered = playerProfilesData
        .filter(profile => {
            const name = String(profile.name || '');
            const position = String(profile.position || 'Unknown');
            const squad = String(profile.squad || 'Unknown');

            if (selectedPlayers.size > 0 && !selectedPlayers.has(name)) return false;
            if (squadFilter !== 'All' && squad !== squadFilter) return false;
            if (positionFilter !== 'All' && position !== positionFilter) return false;
            if (activeOnly && !profile.isActive) return false;
            return true;
        })
        .sort(compareBySurnameThenName);

    if (filtered.length === 0) {
        grid.innerHTML = '';
        emptyState.classList.remove('d-none');
        return;
    }

    emptyState.classList.add('d-none');

    grid.innerHTML = filtered.map(profile => {
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
    }).join('');
}

function populateFilters() {
    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    if (!playerSelect || !squadSelect || !positionSelect) return;

    const playerNames = playerProfilesData
        .map(row => String(row.name || '').trim())
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b));
    const squads = Array.from(new Set(playerProfilesData.map(row => String(row.squad || 'Unknown')))).sort();
    const positions = Array.from(new Set(playerProfilesData.map(row => String(row.position || 'Unknown')))).sort();

    playerSelect.innerHTML = playerNames
        .map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
        .join('');
    squadSelect.innerHTML = '<option value="All">All squads</option>' +
        squads.map(squad => `<option value="${escapeHtml(squad)}">${escapeHtml(squad)}</option>`).join('');
    positionSelect.innerHTML = '<option value="All">All positions</option>' +
        positions.map(position => `<option value="${escapeHtml(position)}">${escapeHtml(position)}</option>`).join('');

    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.selectpicker) {
        window.jQuery(playerSelect).selectpicker('refresh');
    }
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
        const [profilesRes, appearancesRes, gamesRes, scorersRes, reconciledRes] = await Promise.all([
            fetch('data/backend/v_player_profiles.json'),
            fetch('data/backend/player_appearances.json'),
            fetch('data/backend/games.json'),
            fetch('data/backend/season_scorers.json'),
            fetch('data/backend/pitchero_appearance_reconciliation.json')
        ]);

        if (!profilesRes.ok || !appearancesRes.ok || !gamesRes.ok || !scorersRes.ok || !reconciledRes.ok) {
            throw new Error('One or more profile datasets failed to load');
        }

        const [rawProfiles, rawAppearances, rawGames, rawScorers, rawReconciled] = await Promise.all([
            profilesRes.json(),
            appearancesRes.json(),
            gamesRes.json(),
            scorersRes.json(),
            reconciledRes.json()
        ]);

        const context = buildPlayerContext(rawAppearances, rawGames, rawScorers, rawReconciled);
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
    const playerSelect = document.getElementById('playerProfileNameFilter');
    const squadSelect = document.getElementById('playerProfileSquadFilter');
    const positionSelect = document.getElementById('playerProfilePositionFilter');
    const activeOnlyToggle = document.getElementById('playerProfileActiveOnly');

    playerSelect?.addEventListener('change', renderPlayerProfiles);
    if (window.jQuery) {
        window.jQuery(playerSelect).on('changed.bs.select', renderPlayerProfiles);
    }
    squadSelect?.addEventListener('change', renderPlayerProfiles);
    positionSelect?.addEventListener('change', renderPlayerProfiles);
    activeOnlyToggle?.addEventListener('change', renderPlayerProfiles);

    bindCardToggle();
    loadPlayerProfilesPage();
});

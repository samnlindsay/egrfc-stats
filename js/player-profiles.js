let playerProfilesData = [];
let playerProfilesControlsInitialised = false;

const SIX_MONTHS_MS = 182 * 24 * 60 * 60 * 1000;

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
    return firstNamePart(a?.name).localeCompare(firstNamePart(b?.name));
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

    const bySquad = String(a?.squad || '').localeCompare(String(b?.squad || ''));
    if (bySquad !== 0) return bySquad;

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

function parseOtherPositions(value) {
    if (Array.isArray(value)) return value.filter(Boolean).map(String);
    const raw = String(value || '').trim();
    if (!raw) return [];
    if (raw.startsWith('[')) {
        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [];
        } catch {
            return [];
        }
    }
    return raw.split('|').map(s => String(s || '').trim()).filter(Boolean);
}

function parseScoringPayload(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        return {
            tries: Number(value.tries || 0),
            conversions: Number(value.conversions || 0),
            penalties: Number(value.penalties || 0),
            drop_goals: Number(value.drop_goals || 0),
            points: Number(value.points || 0)
        };
    }
    const raw = String(value || '').trim();
    if (!raw) {
        return { tries: 0, conversions: 0, penalties: 0, drop_goals: 0, points: 0 };
    }
    try {
        const parsed = JSON.parse(raw);
        return {
            tries: Number(parsed?.tries || 0),
            conversions: Number(parsed?.conversions || 0),
            penalties: Number(parsed?.penalties || 0),
            drop_goals: Number(parsed?.drop_goals || 0),
            points: Number(parsed?.points || 0)
        };
    } catch {
        return { tries: 0, conversions: 0, penalties: 0, drop_goals: 0, points: 0 };
    }
}

function cardDetailsMarkup(profile) {
    const careerScoring = parseScoringPayload(profile?.scoringCareer);
    const seasonScoring = parseScoringPayload(profile?.scoringThisSeason);
    const totalTries = Number(careerScoring.tries || 0);
    const totalPoints = Number(careerScoring.points || 0);
    const conversions = Number(careerScoring.conversions || 0);
    const penalties = Number(careerScoring.penalties || 0);
    const dropGoals = Number(careerScoring.drop_goals || 0);
    const hasKickedPoints = conversions > 0 || penalties > 0 || dropGoals > 0;

    const lines = [];
    const sponsor = String(profile?.sponsor || '').trim();
    const hasCurrentSeasonSponsor = sponsor && Number(profile?.seasonAppearances || 0) > 0;

    if (hasCurrentSeasonSponsor) {
        lines.push(`<p class="player-profile-detail-line player-profile-detail-sponsor">sponsored by ${escapeHtml(sponsor)}</p>`);
    }

    const otherPositions = parseOtherPositions(profile?.otherPositions);
    if (otherPositions.length > 0) {
        lines.push(`<p class="player-profile-detail-line"><strong>Other positions:</strong> ${escapeHtml(otherPositions.join(', '))}</p>`);
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
        `<p class="player-profile-detail-line"><strong>This season:</strong> ${profile.seasonAppearances} appearances (${profile.seasonStarts} starts, ${profile.seasonCompetitiveAppearances} competitive), ${Number(seasonScoring.tries || 0)} tries</p>`
    );

    const lastAppearanceDate = String(profile?.lastAppearanceDate || '').trim();
    if (lastAppearanceDate) {
        lines.push(`<p class="player-profile-detail-line"><strong>Last appearance:</strong> ${escapeHtml(lastAppearanceDate)}</p>`);
    }

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
        const profilesRes = await fetch('data/backend/player_profiles_canonical.json');

        if (!profilesRes.ok) {
            throw new Error('One or more profile datasets failed to load');
        }

        const rawProfiles = await profilesRes.json();
        playerProfilesData = (Array.isArray(rawProfiles) ? rawProfiles : [])
            .filter(row => String(row?.name || '').trim())
            .sort(compareBySurnameThenName);

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

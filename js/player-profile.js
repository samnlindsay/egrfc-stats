let fullProfiles = [];
let fullGamesById = new Map();
let fullAppearancesByPlayer = new Map();
let fullAppearancesByGame = new Map();
let fullProfilesByName = new Map();
let fullSponsorHistoryByPlayer = new Map();
let fullCurrentSeason = "";
let fullProfileAppearancesBySeasonSpecs = {
  Squad: null,
  Result: null,
  Position: null,
};
let fullProfilePositionDonutSpec = null;
let fullProfileCareerTimelineSpec = null;
let fullProfileAppearanceRows = [];
let fullProfileSortState = { key: "date", direction: "desc" };
let fullProfilePaginationState = { page: 1, pageSize: 10 };
let fullProfileTableSearch = "";

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function initializeLastTenTooltips(containerEl) {
  if (!containerEl || !window.bootstrap || !window.bootstrap.Tooltip) return;
  const tooltipEls = containerEl.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach((el) => {
    window.bootstrap.Tooltip.getOrCreateInstance(el, {
      container: "body",
      trigger: "hover focus",
    });
  });
}

function createAvatarMarkup(profile) {
  const name = escapeHtml(profile?.name || "Player");
  const photoUrl = String(profile?.photo_url || "").trim();

  if (photoUrl) {
    return `<img src="${escapeHtml(photoUrl)}" alt="${name}" class="player-profile-avatar" loading="lazy">`;
  }

  return '<div class="player-profile-avatar-placeholder"><i class="bi bi-person-fill" aria-hidden="true"></i></div>';
}

function headshotBackgroundClass(profile) {
  const squad = String(profile?.squad || "")
    .trim()
    .toLowerCase();
  return squad === "2nd"
    ? "player-profile-headshot-wrap-2nd"
    : "player-profile-headshot-wrap-1st";
}

function parseScoringPayload(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      tries: Number(value.tries || 0),
      conversions: Number(value.conversions || 0),
      penalties: Number(value.penalties || 0),
      dropGoals: Number(value.drop_goals || value.dropGoals || 0),
      points: Number(value.points || 0),
    };
  }

  const raw = String(value || "").trim();
  if (!raw)
    return { tries: 0, conversions: 0, penalties: 0, dropGoals: 0, points: 0 };

  try {
    const parsed = JSON.parse(raw);
    return {
      tries: Number(parsed?.tries || 0),
      conversions: Number(parsed?.conversions || 0),
      penalties: Number(parsed?.penalties || 0),
      dropGoals: Number(parsed?.drop_goals || parsed?.dropGoals || 0),
      points: Number(parsed?.points || 0),
    };
  } catch {
    return { tries: 0, conversions: 0, penalties: 0, dropGoals: 0, points: 0 };
  }
}

function parseOtherPositions(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  const raw = String(value || "").trim();
  if (!raw) return [];
  if (raw.startsWith("[")) {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [];
    } catch {
      return [];
    }
  }
  return raw
    .split("|")
    .map((v) => String(v || "").trim())
    .filter(Boolean);
}

function ordinalDay(day) {
  const n = Number(day);
  if (!Number.isFinite(n)) return "";
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  const rem10 = n % 10;
  if (rem10 === 1) return `${n}st`;
  if (rem10 === 2) return `${n}nd`;
  if (rem10 === 3) return `${n}rd`;
  return `${n}th`;
}

function formatDisplayDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";

  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const year = Number(isoMatch[1]);
    const month = Number(isoMatch[2]);
    const day = Number(isoMatch[3]);
    if (
      Number.isFinite(year) &&
      Number.isFinite(month) &&
      Number.isFinite(day)
    ) {
      const date = new Date(Date.UTC(year, month - 1, day));
      const monthLabel = date.toLocaleString("en-GB", {
        month: "short",
        timeZone: "UTC",
      });
      return `${ordinalDay(day)} ${monthLabel} ${year}`;
    }
  }

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  const day = parsed.getUTCDate();
  const monthLabel = parsed.toLocaleString("en-GB", {
    month: "short",
    timeZone: "UTC",
  });
  const year = parsed.getUTCFullYear();
  return `${ordinalDay(day)} ${monthLabel} ${year}`;
}

function playerHistory(name) {
  const rows = fullAppearancesByPlayer.get(String(name || "").trim()) || [];
  return rows
    .map((row) => ({
      ...row,
      game: fullGamesById.get(String(row?.game_id || "").trim()),
    }))
    .filter((row) => row.game)
    .sort((a, b) =>
      String(a.game.date || "").localeCompare(String(b.game.date || "")),
    );
}

function gameResultCode(game) {
  const result = String(game?.result || "")
    .trim()
    .toUpperCase();
  if (result === "W" || result === "L" || result === "D") return result;
  return "";
}

function lastTenResultsFromHistory(history) {
  return (Array.isArray(history) ? history : [])
    .map((row) => ({
      result: gameResultCode(row?.game),
      game: row?.game || null,
    }))
    .filter((entry) => entry.result)
    .slice(-10)
    .reverse();
}

function lastTenResultsMarkup(history) {
  const entries = lastTenResultsFromHistory(history);
  if (!entries.length) {
    return '<div class="season-results-last-ten-row"><div class="season-results-last-ten-label">Last 10 Results</div><div class="last-ten-results-strip last-ten-results-strip--single-row"><span class="last-ten-results-empty">No recent results</span></div></div>';
  }

  const tokens = entries
    .map((entry) => {
      const result = entry.result;
      const variant =
        result === "W"
          ? "last-ten-result--win"
          : result === "L"
            ? "last-ten-result--loss"
            : "last-ten-result--draw";
      const gameId = String(entry?.game?.game_id || "").trim();
      const title = fixtureText(entry.game, true).replace(/<[^>]+>/g, "");
      const score = scoreText(entry.game);
      const tooltipText = [
        title,
        `Result: ${result}${score ? ` (${score})` : ""}`,
        gameId ? "Click to open Match Info" : "",
      ]
        .filter(Boolean)
        .join("\n");
      const chip = `<span class="last-ten-result ${variant}" data-bs-toggle="tooltip" data-bs-custom-class="last-ten-result-tooltip" data-bs-title="${escapeAttribute(tooltipText)}">${result}</span>`;
      return gameId
        ? `<a class="last-ten-result-link" href="match-info.html?game=${encodeURIComponent(gameId)}" aria-label="Open Match Info for ${escapeHtml(title)}">${chip}</a>`
        : chip;
    })
    .join("");

  return `<div class="season-results-last-ten-row"><div class="season-results-last-ten-label">Last 10 Results</div><div class="last-ten-results-strip last-ten-results-strip--single-row">${tokens}</div></div>`;
}

function fixtureText(game, includeSquad) {
  if (!game) return "Unknown";
  const squadPrefix = includeSquad
    ? `${escapeHtml(String(game.squad || ""))} XV `
    : "";
  const opposition = escapeHtml(String(game.opposition || "Unknown"));
  const homeAway = escapeHtml(String(game.home_away || "?"));
  const dateText = escapeHtml(formatDisplayDate(game.date));
  return `${squadPrefix}v ${opposition} (${homeAway}) <span class="fixture-result-separator" aria-hidden="true">&bull;</span> ${dateText}`;
}

function scoreText(game) {
  const result = String(game?.result || "").toUpperCase();
  const forScore = Number(game?.score_for);
  const againstScore = Number(game?.score_against);
  if (!Number.isFinite(forScore) || !Number.isFinite(againstScore))
    return result || "-";
  return `${result} ${forScore}-${againstScore}`;
}

function resultBadgeHtml(score) {
  const text = String(score || "-").trim();
  const first = text.charAt(0).toUpperCase();
  const cls =
    first === "W"
      ? "result-badge--win"
      : first === "L"
        ? "result-badge--loss"
        : first === "D"
          ? "result-badge--draw"
          : "";
  if (!cls) return escapeHtml(text);
  return `<span class="result-badge ${cls}">${escapeHtml(text)}</span>`;
}

function gameLinkHref(gameId) {
  return `match-info.html?game=${encodeURIComponent(String(gameId || "").trim())}`;
}

function fixtureAndResultText(game, includeSquad) {
  if (!game) return "Unknown";
  return `<span class="fixture-result-inline"><span class="fixture-result-main">${fixtureText(game, includeSquad)}</span><span class="fixture-result-separator" aria-hidden="true">&bull;</span><span class="fixture-result-meta">${resultBadgeHtml(scoreText(game))}</span></span>`;
}

function fixtureAndResultLink(game, includeSquad) {
  if (!game) return "Unknown";
  const gameId = String(game?.game_id || "").trim();
  if (!gameId) return fixtureAndResultText(game, includeSquad);
  const fixtureHtml = fixtureText(game, includeSquad);
  const resultHtml = resultBadgeHtml(scoreText(game));
  return `<a class="fixture-result-link" href="${escapeAttribute(gameLinkHref(gameId))}" style="text-decoration: none; color: inherit;"><span class="fixture-result-inline"><span class="fixture-result-main">${fixtureHtml}</span><span class="fixture-result-separator" aria-hidden="true">&bull;</span><span class="fixture-result-meta">${resultHtml}</span></span></a>`;
}

function winRecordMarkup(wins, losses, draws) {
  const parts = [
    `<span class="record-chip record-chip--win"><span class="record-chip-label">W</span><span class="record-chip-value">${Number(wins || 0)}</span></span>`,
    `<span class="record-chip record-chip--loss"><span class="record-chip-label">L</span><span class="record-chip-value">${Number(losses || 0)}</span></span>`,
  ];
  if (Number(draws || 0) > 0) {
    parts.push(
      `<span class="record-chip record-chip--draw"><span class="record-chip-label">D</span><span class="record-chip-value">${Number(draws || 0)}</span></span>`,
    );
  }
  return `<span class="record-chip-group">${parts.join("")}</span>`;
}

function activeTagMarkup(isActive) {
  return isActive
    ? '<span class="player-profile-active-tag full-profile-active-tag">Active</span>'
    : "";
}

function formatSquadLabel(squadValue) {
  const raw = String(squadValue || "").trim();
  if (raw === "1st") return "1st XV";
  if (raw === "2nd") return "2nd XV";
  return raw || "Unknown Squad";
}

function squadTagMarkup(squadValue) {
  const raw = String(squadValue || "").trim();
  const label = formatSquadLabel(raw);
  const variant =
    raw === "2nd"
      ? "full-profile-squad-tag--2nd"
      : "full-profile-squad-tag--1st";
  return `<span class="player-profile-active-tag full-profile-active-tag full-profile-squad-tag ${variant}">${escapeHtml(label)}</span>`;
}

function renderPlayerProfileCaptains() {
  renderCaptainCards('captainCards', fullGamesById, fullAppearancesByGame, fullProfilesByName);
}

function canonicalizeName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function seasonSortKey(value) {
  const text = String(value || "").trim();
  const match = text.match(/^(\d{4})\/(\d{2}|\d{4})$/);
  return match ? Number(match[1]) : -Infinity;
}

function deriveCurrentSeason(games) {
  const seasons = (Array.isArray(games) ? games : [])
    .map((row) => String(row?.season || "").trim())
    .filter(Boolean)
    .sort((a, b) => seasonSortKey(b) - seasonSortKey(a));
  return seasons[0] || "";
}

function buildSponsorHistoryMap(rawSponsorsBySeason) {
  const historyByPlayer = new Map();
  if (!rawSponsorsBySeason || typeof rawSponsorsBySeason !== "object")
    return historyByPlayer;

  Object.entries(rawSponsorsBySeason).forEach(([season, seasonSponsors]) => {
    if (!seasonSponsors || typeof seasonSponsors !== "object") return;
    Object.entries(seasonSponsors).forEach(([playerName, sponsorName]) => {
      const normalizedName = canonicalizeName(playerName);
      const sponsor = String(sponsorName || "").trim();
      if (!normalizedName || !sponsor) return;
      if (!historyByPlayer.has(normalizedName))
        historyByPlayer.set(normalizedName, []);
      historyByPlayer
        .get(normalizedName)
        .push({ season: String(season || "").trim(), sponsor });
    });
  });

  return historyByPlayer;
}

function playerSponsorSnapshot(player) {
  const playerName = canonicalizeName(player?.name);
  const rawHistory = fullSponsorHistoryByPlayer.get(playerName) || [];
  const currentSeason = String(fullCurrentSeason || "").trim();
  const currentSeasonEntries = rawHistory.filter(
    (entry) => String(entry?.season || "").trim() === currentSeason,
  );
  const currentSponsor =
    currentSeasonEntries.length > 0
      ? String(
          currentSeasonEntries[currentSeasonEntries.length - 1]?.sponsor || "",
        ).trim()
      : "-";
  const uniqueBySponsor = new Map();

  rawHistory.forEach((entry) => {
    const sponsor = String(entry?.sponsor || "").trim();
    const season = String(entry?.season || "").trim();
    if (currentSeason && season === currentSeason) return;
    if (!sponsor || !season) return;
    if (!uniqueBySponsor.has(sponsor)) uniqueBySponsor.set(sponsor, []);
    uniqueBySponsor.get(sponsor).push(season);
  });

  const previousSponsors = [];
  uniqueBySponsor.forEach((seasons, sponsor) => {
    const orderedSeasons = [...new Set(seasons)].sort((a, b) =>
      a.localeCompare(b),
    );
    previousSponsors.push({ sponsor, seasons: orderedSeasons });
  });

  previousSponsors.sort((a, b) => a.sponsor.localeCompare(b.sponsor));

  return {
    currentSponsor,
    previousSponsors,
  };
}

function buildAppearanceRows(history) {
  return history.map((row) => {
    const game = row?.game || {};
    const gameId = String(game?.game_id || row?.game_id || "").trim();
    const rawDate = String(game?.date || row?.date || "");
    const season = String(game?.season || row?.season || "-");
    const gameType = String(game?.game_type || row?.game_type || "-");
    const competition = String(game?.competition || row?.competition || "-");
    const squad = String(row?.squad || game?.squad || "-");
    const position = String(row?.position || "-");
    const opposition = String(game?.opposition || "-");
    const homeAway = String(game?.home_away || "-");
    const shirtNumber =
      row?.shirt_number != null
        ? String(row.shirt_number)
        : row?.number != null
          ? String(row.number)
          : "-";
    const score = scoreText(game);
    return {
      date: rawDate,
      dateDisplay: formatDisplayDate(rawDate),
      season,
      gameType,
      competition,
      squad,
      opposition,
      homeAway,
      position,
      shirtNumber,
      result: score,
      gameId,
      sortTimestamp: new Date(rawDate).getTime(),
    };
  });
}

function compareAppearanceRows(a, b, key, direction) {
  const factor = direction === "asc" ? 1 : -1;
  if (key === "date") {
    const left = Number.isFinite(a.sortTimestamp) ? a.sortTimestamp : -Infinity;
    const right = Number.isFinite(b.sortTimestamp)
      ? b.sortTimestamp
      : -Infinity;
    if (left === right) return 0;
    return left > right ? factor : -factor;
  }

  const leftValue = String(a[key] || "").toLowerCase();
  const rightValue = String(b[key] || "").toLowerCase();
  if (leftValue === rightValue) return 0;
  return leftValue > rightValue ? factor : -factor;
}

function sortedAppearanceRows() {
  const rows = [...fullProfileAppearanceRows];
  const key = fullProfileSortState.key;
  const direction = fullProfileSortState.direction;
  rows.sort((a, b) => compareAppearanceRows(a, b, key, direction));
  return rows;
}

function pagedAppearanceRows(rows) {
  const pageSize = Math.max(
    5,
    Number(fullProfilePaginationState.pageSize) || 15,
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const page = Math.min(
    pageCount,
    Math.max(1, Number(fullProfilePaginationState.page) || 1),
  );
  fullProfilePaginationState.page = page;
  fullProfilePaginationState.pageSize = pageSize;
  const start = (page - 1) * pageSize;
  return {
    page,
    pageSize,
    pageCount,
    rows: rows.slice(start, start + pageSize),
  };
}

function updateSortHeaderUI() {
  document.querySelectorAll("[data-appearance-sort]").forEach((button) => {
    const key = String(button.getAttribute("data-appearance-sort") || "");
    const isActive = key === fullProfileSortState.key;
    const direction = isActive ? fullProfileSortState.direction : "none";
    const arrow = isActive ? (direction === "asc" ? " ▲" : " ▼") : "";
    const label = String(button.getAttribute("data-appearance-label") || key);
    button.textContent = `${label}${arrow}`;
    button.setAttribute(
      "aria-sort",
      isActive ? (direction === "asc" ? "ascending" : "descending") : "none",
    );
  });
}

function renderAppearanceTable() {
  const tbody = document.getElementById("fullProfileAppearancesTableBody");
  if (!tbody) return;

  const sortedRows = sortedAppearanceRows();
  const query = fullProfileTableSearch.trim().toLowerCase();
  const filteredRows = query
    ? sortedRows.filter((row) =>
        Object.values(row).some((v) =>
          String(v ?? "")
            .toLowerCase()
            .includes(query),
        ),
      )
    : sortedRows;
  const paged = pagedAppearanceRows(filteredRows);
  const html = paged.rows
    .map((row) => {
      const squadKey = String(row.squad || "").trim();
      const rowClass = "full-profile-appearance-row";
      const squadPillClass =
        squadKey === "1st"
          ? "squad-pill squad-pill--1st"
          : squadKey === "2nd"
            ? "squad-pill squad-pill--2nd"
            : "squad-pill squad-pill--unknown";
      const squadLabel =
        squadKey === "1st" || squadKey === "2nd"
          ? `${squadKey} XV`
          : squadKey || "-";
      const openMatchHtml = row.gameId
        ? `<a class="btn btn-outline-primary btn-sm rounded-circle p-0 d-inline-flex align-items-center justify-content-center match-open-btn" href="match-info.html?game=${encodeURIComponent(row.gameId)}" aria-label="View match detail"><i class="bi bi-search" aria-hidden="true"></i></a>`
        : '<span class="text-muted">-</span>';
      return `
        <tr class="${rowClass}">
            <td>${escapeHtml(row.dateDisplay || "-")}</td>
            <td>${escapeHtml(row.competition || "-")}</td>
            <td><span class="${squadPillClass}">${escapeHtml(squadLabel)}</span></td>
            <td>${escapeHtml(row.opposition || "-")}</td>
            <td>${escapeHtml(row.homeAway || "-")}</td>
            <td>${escapeHtml(row.position || "-")}</td>
            <td>${escapeHtml(row.shirtNumber || "-")}</td>
            <td>${resultBadgeHtml(row.result || "-")}</td>
            <td class="match-table-open-cell">${openMatchHtml}</td>
        </tr>
    `;
    })
    .join("");

  tbody.innerHTML =
    html ||
    '<tr><td colspan="9" class="text-muted">No appearances found for this player.</td></tr>';

  const summary = document.getElementById(
    "fullProfileAppearancesPaginationSummary",
  );
  if (summary) {
    if (filteredRows.length === 0) {
      summary.textContent = query ? "0 results" : "0 appearances";
    } else {
      const start = (paged.page - 1) * paged.pageSize + 1;
      const end = Math.min(filteredRows.length, paged.page * paged.pageSize);
      const total = filteredRows.length;
      const suffix =
        query && total !== sortedRows.length
          ? ` of ${sortedRows.length} appearances`
          : " appearances";
      summary.textContent = `${start}-${end} of ${total}${suffix}`;
    }
  }

  const prevButton = document.getElementById("fullProfileAppearancesPrev");
  const nextButton = document.getElementById("fullProfileAppearancesNext");
  if (prevButton) prevButton.disabled = paged.page <= 1;
  if (nextButton) nextButton.disabled = paged.page >= paged.pageCount;

  updateSortHeaderUI();
}

function renderAppearancesPerSeasonChart(playerName) {
  const colorByValue = String(
    document.querySelector('input[name="fullProfileColorBy"]:checked')?.value ||
      "Squad",
  );
  const selectedSpec =
    fullProfileAppearancesBySeasonSpecs[colorByValue] || null;
  if (!selectedSpec) {
    renderStaticSpecChart(
      "fullProfileAppearancesPerSeasonChart",
      null,
      "Unable to load appearances-per-season chart. Run python/update.py and refresh this page.",
    );
    return;
  }

  const filteredSpec = filterChartSpecDataset(
    JSON.parse(JSON.stringify(selectedSpec)),
    (row) => String(row?.player || "").trim() === playerName,
  );

  renderStaticSpecChart(
    "fullProfileAppearancesPerSeasonChart",
    filteredSpec,
    "No appearances available for this player.",
  );
}

function renderProfileFilteredChart(
  containerId,
  spec,
  playerName,
  emptyMessage,
) {
  if (!spec) {
    renderStaticSpecChart(containerId, null, emptyMessage);
    return;
  }

  const filteredSpec = filterChartSpecDataset(
    JSON.parse(JSON.stringify(spec)),
    (row) => String(row?.player || "").trim() === playerName,
  );

  renderStaticSpecChart(containerId, filteredSpec, emptyMessage);
}

function renderPositionDonutChart(playerName) {
  renderProfileFilteredChart(
    "fullProfilePositionDonutChart",
    fullProfilePositionDonutSpec,
    playerName,
    "No position data available for this player.",
  );
}

function fullProfileMilestoneLegendHtml() {
  const icon = (scopeClass, levelClass, text, title) => {
    const inner = text
      ? `<span class="match-team-sheet-milestone-text">${text}</span>`
      : "";
    return `<span class="match-team-sheet-milestone ${scopeClass} ${levelClass}" aria-hidden="true" title="${escapeAttribute(title)}"><span class="match-team-sheet-milestone-core">${inner}</span></span>`;
  };

  const pairedIcon = (levelClass, text, label) => `
        <span class="match-team-sheet-legend-pair" aria-hidden="true">
            <span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--club">${icon("match-team-sheet-milestone--scope-club", levelClass, text, `Club ${label}`)}</span>
            <span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--first-xv">${icon("match-team-sheet-milestone--scope-first-xv", levelClass, text, `1st XV ${label}`)}</span>
        </span>
    `;

  const eventGlyph = (letter, color, title) =>
    `<span class="full-profile-timeline-event-glyph" style="color:${color}" aria-hidden="true" title="${escapeAttribute(title)}">${letter}</span>`;

  return `
        <div class="match-team-sheet-legend full-profile-timeline-legend-block full-profile-timeline-legend-block--combined" aria-label="Timeline milestone and event key">
            <div class="full-profile-timeline-legend-groups">
                <div class="full-profile-timeline-legend-group full-profile-timeline-legend-group--appearance">
                    <h4 class="match-team-sheet-legend-title">Appearance milestones</h4>
                    <div class="match-team-sheet-legend-row full-profile-timeline-appearance-row">
                        <span class="match-team-sheet-legend-scopes">Club<br><strong>1st XV</strong></span>
                        <span class="match-team-sheet-legend-item">${pairedIcon("match-team-sheet-milestone--debut", "1", "debut")}<span class="match-team-sheet-legend-text">Debut</span></span>
                        <span class="match-team-sheet-legend-item">${pairedIcon("match-team-sheet-milestone--25", "25", "25th appearance")}<span class="match-team-sheet-legend-text">25th</span></span>
                        <span class="match-team-sheet-legend-item">${pairedIcon("match-team-sheet-milestone--50", "50", "50th appearance")}<span class="match-team-sheet-legend-text">50th</span></span>
                        <span class="match-team-sheet-legend-item">${pairedIcon("match-team-sheet-milestone--100", "100", "100th appearance")}<span class="match-team-sheet-legend-text">100th</span></span>
                        <span class="match-team-sheet-legend-item">${icon("match-team-sheet-milestone--last", "", "")}<span class="match-team-sheet-legend-text">Latest</span></span>
                    </div>
                </div>
                <div class="full-profile-timeline-legend-group full-profile-timeline-legend-group--events">
                    <h4 class="match-team-sheet-legend-title">Other events</h4>
                    <div class="match-team-sheet-legend-row full-profile-timeline-event-row">
                        <span class="match-team-sheet-legend-item">${eventGlyph("T", "#991515", "First try")}<span class="match-team-sheet-legend-text">1st try</span></span>
                        <span class="match-team-sheet-legend-item">${eventGlyph("C", "#7d96e8", "First captaincy")}<span class="match-team-sheet-legend-text">1st captain</span></span>
                        <span class="match-team-sheet-legend-item"><span class="full-profile-timeline-event-glyph full-profile-timeline-event-glyph--star" aria-hidden="true" title="First Man of the Match">★</span><span class="match-team-sheet-legend-text">MOTM</span></span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderCareerTimelineChart(playerName) {
  const containerId = "fullProfileCareerTimelineChart";
  if (!fullProfileCareerTimelineSpec) {
    renderStaticSpecChart(
      containerId,
      null,
      "No career milestones available for this player yet.",
    );
    return;
  }

  const filteredSpec = filterChartSpecDataset(
    JSON.parse(JSON.stringify(fullProfileCareerTimelineSpec)),
    (row) => String(row?.player || "").trim() === playerName,
  );

  // Desktop: use the actual host width so the chart fills the container.
  // Mobile: keep a larger intrinsic width so responsive scaling can shrink
  // precisely to the available width without horizontal overflow.
  const timelineHost = document.getElementById(containerId);
  const timelineSection = timelineHost?.closest(
    ".full-profile-timeline-section",
  );

  let containerWidth = Math.floor(timelineHost?.clientWidth || 0);
  if (!containerWidth && timelineSection && window?.getComputedStyle) {
    const sectionStyles = window.getComputedStyle(timelineSection);
    const sectionPaddingLeft =
      parseFloat(sectionStyles.paddingLeft || "0") || 0;
    const sectionPaddingRight =
      parseFloat(sectionStyles.paddingRight || "0") || 0;
    const sectionInnerWidth = Math.floor(
      (timelineSection.clientWidth || 0) -
        sectionPaddingLeft -
        sectionPaddingRight,
    );
    containerWidth = Math.max(0, sectionInnerWidth);
  }

  const isMobileViewport =
    typeof window !== "undefined" && window.innerWidth <= 900;
  const minMobileIntrinsicWidth = 500;
  const viewportWidth = Math.floor(
    (typeof window !== "undefined" ? window.innerWidth : 0) || 0,
  );
  const desktopFallbackWidth = Math.max(
    minMobileIntrinsicWidth,
    Math.floor(viewportWidth * 0.75) || 860,
  );
  const resolvedContainerWidth =
    containerWidth > 0 ? containerWidth : desktopFallbackWidth;

  // Mobile: use a smaller intrinsic base (500px) then scale-to-fit so marks
  // and labels stay more legible.
  // Desktop: match the container width natively to avoid right-side whitespace.
  filteredSpec.width = isMobileViewport
    ? Math.max(minMobileIntrinsicWidth, resolvedContainerWidth)
    : resolvedContainerWidth;

  renderStaticSpecChart(
    containerId,
    filteredSpec,
    "No career milestones available for this player yet.",
    {
      actions: false,
      // Always allow fitting to container width on small screens.
      responsiveScaleMin: 0.01,
      responsiveScaleMinXs: 0.01,
    },
  );

  const legendHost = document.getElementById("fullProfileCareerTimelineLegend");
  if (legendHost) {
    legendHost.innerHTML = fullProfileMilestoneLegendHtml();
  }
}

function bindAppearancePanelControls(playerName) {
  document
    .querySelectorAll('input[name="fullProfileColorBy"]')
    .forEach((radio) => {
      radio.addEventListener("change", () => {
        renderAppearancesPerSeasonChart(playerName);
      });
    });
  const tableHost = document.getElementById("fullProfileAppearancesTable");
  if (tableHost) {
    tableHost.addEventListener("click", (event) => {
      const target = event.target.closest("[data-appearance-sort]");
      if (!target) return;
      const key = String(
        target.getAttribute("data-appearance-sort") || "",
      ).trim();
      if (!key) return;
      if (fullProfileSortState.key === key) {
        fullProfileSortState.direction =
          fullProfileSortState.direction === "asc" ? "desc" : "asc";
      } else {
        fullProfileSortState = {
          key,
          direction: key === "date" ? "desc" : "asc",
        };
      }
      fullProfilePaginationState.page = 1;
      renderAppearanceTable();
    });
  }

  const searchInput = document.getElementById("fullProfileAppearancesSearch");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      fullProfileTableSearch = String(searchInput.value || "");
      fullProfilePaginationState.page = 1;
      renderAppearanceTable();
    });
  }

  const prevButton = document.getElementById("fullProfileAppearancesPrev");
  if (prevButton) {
    prevButton.addEventListener("click", () => {
      fullProfilePaginationState.page = Math.max(
        1,
        fullProfilePaginationState.page - 1,
      );
      renderAppearanceTable();
    });
  }

  const nextButton = document.getElementById("fullProfileAppearancesNext");
  if (nextButton) {
    nextButton.addEventListener("click", () => {
      fullProfilePaginationState.page += 1;
      renderAppearanceTable();
    });
  }
}

function renderProfile(player) {
  const root = document.getElementById("fullProfileRoot");
  if (!root) return;

  const history = playerHistory(player?.name);
  const firstGame = history[0]?.game;
  const firstXVGame = history.find(
    (row) => String(row?.squad || "") === "1st",
  )?.game;
  const latestGame = history[history.length - 1]?.game;

  let wins = 0;
  let losses = 0;
  let draws = 0;
  history.forEach((row) => {
    const result = String(row?.game?.result || "").toUpperCase();
    if (result === "W") wins += 1;
    if (result === "L") losses += 1;
    if (result === "D") draws += 1;
  });

  const scoringCareer = parseScoringPayload(player?.scoringCareer);
  const scoringSeason = parseScoringPayload(player?.scoringThisSeason);
  const otherPositions = parseOtherPositions(player?.otherPositions);
  const avatarUrl = String(player?.photo_url || "").trim();
  const squadValue = String(player?.squad || "").trim();
  const primarySquadLabel = formatSquadLabel(squadValue);
  const totalAppearances = Number(player?.totalAppearances || 0);
  const totalStarts = Number(player?.totalStarts || 0);
  const firstXVAppearances = Number(player?.firstXVAppearances || 0);
  const firstXVStarts = Number(player?.firstXVStarts || 0);
  const primarySquadAppearances =
    squadValue === "2nd"
      ? Math.max(0, totalAppearances - firstXVAppearances)
      : firstXVAppearances;
  const primarySquadStarts =
    squadValue === "2nd"
      ? Math.max(0, totalStarts - firstXVStarts)
      : firstXVStarts;
  const bannerBackgroundClass =
    squadValue === "2nd"
      ? "player-profile-headshot-wrap-2nd"
      : "player-profile-headshot-wrap-1st";
  const sponsorSnapshot = playerSponsorSnapshot(player);

  fullProfileAppearanceRows = buildAppearanceRows(history);
  fullProfileSortState = { key: "date", direction: "desc" };
  fullProfilePaginationState = { page: 1, pageSize: 10 };
  fullProfileTableSearch = "";

  const scoringParts = [];
  if (scoringCareer.tries > 0)
    scoringParts.push(
      `${scoringCareer.tries} ${scoringCareer.tries === 1 ? "try" : "tries"}`,
    );
  if (scoringCareer.conversions > 0)
    scoringParts.push(
      `${scoringCareer.conversions} ${scoringCareer.conversions === 1 ? "conversion" : "conversions"}`,
    );
  if (scoringCareer.penalties > 0)
    scoringParts.push(
      `${scoringCareer.penalties} ${scoringCareer.penalties === 1 ? "penalty" : "penalties"}`,
    );
  if (scoringCareer.dropGoals > 0)
    scoringParts.push(
      `${scoringCareer.dropGoals} ${scoringCareer.dropGoals === 1 ? "drop goal" : "drop goals"}`,
    );
  const scoringRecord = scoringParts.length
    ? scoringParts.join(", ")
    : "No scores recorded";
  const seasonParts = [];
  // "1 try", "2 tries", etc. - avoid pluralising "0 tries" or "1 tries"
  if (scoringSeason.tries > 0)
    seasonParts.push(
      `${Number(scoringSeason.tries)} ${scoringSeason.tries === 1 ? "try" : "tries"}`,
    );
  if (scoringSeason.conversions > 0)
    seasonParts.push(
      `${Number(scoringSeason.conversions)} ${scoringSeason.conversions === 1 ? "conversion" : "conversions"}`,
    );
  if (scoringSeason.penalties > 0)
    seasonParts.push(
      `${Number(scoringSeason.penalties)} ${scoringSeason.penalties === 1 ? "penalty" : "penalties"}`,
    );
  if (scoringSeason.dropGoals > 0)
    seasonParts.push(
      `${Number(scoringSeason.dropGoals)} ${scoringSeason.dropGoals === 1 ? "drop goal" : "drop goals"}`,
    );
  const seasonRecord = seasonParts.length
    ? seasonParts.join(", ")
    : "No scores recorded";
  const startingPositionCounts = new Map();
  let benchAppearances = 0;
  history.forEach((row) => {
    if (row?.is_starter) {
      const position = String(row?.position || "").trim();
      if (!position || position.toLowerCase() === "bench") return;
      startingPositionCounts.set(
        position,
        (startingPositionCounts.get(position) || 0) + 1,
      );
      return;
    }
    benchAppearances += 1;
  });
  const sortedPositions = [...startingPositionCounts.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
  const positionLines = sortedPositions.map(
    ([position, count]) =>
      `<p class="full-profile-position-line"><strong>${escapeHtml(position)}:</strong> ${count} starts</p>`,
  );
  if (benchAppearances > 0) {
    positionLines.push(
      `<p class="full-profile-position-line"><strong>Bench:</strong> ${benchAppearances} appearances</p>`,
    );
  }
  const sponsorshipSectionHtml = (() => {
    const sponsorshipLines = [];
    sponsorshipLines.push(
      `<p class="full-profile-copy-line"><strong>Current sponsor:</strong> ${escapeHtml(sponsorSnapshot.currentSponsor || "-")}</p>`,
    );
    if (sponsorSnapshot.previousSponsors.length > 0) {
      sponsorshipLines.push(
        `<p class="full-profile-copy-line"><strong>Previous sponsors:</strong> ${sponsorSnapshot.previousSponsors.map((item) => `${escapeHtml(item.sponsor)} (${escapeHtml(item.seasons.join(", "))})`).join("; ")}</p>`,
      );
    }
    return `<section class="full-profile-section-block"><div class="full-profile-section-title">Sponsorship</div>${sponsorshipLines.join("")}</section>`;
  })();

  root.innerHTML = `
        <article class="card full-profile-shell">
            <div class="player-profile-headshot-wrap ${bannerBackgroundClass} full-profile-banner">
                <div class="full-profile-banner-copy">
                    <h2 class="full-profile-banner-name">${escapeHtml(String(player?.name || "Unknown"))}</h2>
                    <p class="full-profile-banner-subtitle">${escapeHtml(String(player?.position || "Unknown"))}</p>
                    <div class="full-profile-active-row">${activeTagMarkup(player?.isActive)}${squadTagMarkup(squadValue)}</div>
                </div>
                <div class="full-profile-banner-headshot">
                    ${
                      avatarUrl
                        ? `<img src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(player?.name || "Player")}" class="player-profile-avatar" loading="lazy">`
                        : '<div class="player-profile-avatar-placeholder"><i class="bi bi-person-fill" aria-hidden="true"></i></div>'
                    }
                </div>
            </div>
            
            <div class="full-profile-sections-grid full-profile-sections-grid--body">
            <section class="full-profile-section-full chart-section" aria-labelledby="playerProfileCareerTimelineHeading">
                    <div class="chart-section-block chart-section-block--panel full-profile-table-card">
                    <h2 id="playerProfileCareerTimelineHeading" class="full-profile-section-title">Career Timeline</h2>
                    <p class="section-intro">Key milestones and events across the player's career</p>
                <div id="fullProfileCareerTimelineChart" class="chart-host chart-host--intrinsic full-profile-timeline-chart">Loading career timeline...</div>
                <div id="fullProfileCareerTimelineLegend" class="full-profile-timeline-legend"></div>
                </div>
            </section>

                <div class="full-profile-sections-column">
                    <section class="full-profile-section-block">
                        <div class="full-profile-section-title">Career Summary</div>
                        <p class="full-profile-copy-line"><strong>Total appearances:</strong> ${totalAppearances} (${totalStarts} starts)</p>
                        ${
                          primarySquadAppearances > 0
                            ? `<p class="full-profile-copy-line"><strong>${escapeHtml(primarySquadLabel)} appearances:</strong> ${primarySquadAppearances} (${primarySquadStarts} starts)</p>`
                            : ""
                        }
                        <p class="full-profile-copy-line"><strong>This season:</strong> ${Number(player?.seasonAppearances || 0)} apps (${Number(player?.seasonStarts || 0)} starts)</p>
                        <p class="full-profile-copy-line"><strong>Win record:</strong> ${winRecordMarkup(wins, losses, draws)}</p>
                        ${lastTenResultsMarkup(history)}
                    </section>

                    <section class="full-profile-section-block">
                        <div class="full-profile-section-title">First and Last Appearances</div>
                        <p class="full-profile-copy-line"><strong>Club debut:</strong> ${firstGame ? fixtureAndResultLink(firstGame, true) : escapeHtml(String(player?.debutOverall || "Unknown"))}</p>
                        ${
                          firstXVAppearances > 0
                            ? `<p class="full-profile-copy-line"><strong>1st XV debut:</strong> ${firstXVGame ? fixtureAndResultLink(firstXVGame, false) : escapeHtml(String(player?.debutFirstXV || "Unknown"))}</p>`
                            : ""
                        }
                        <p class="full-profile-copy-line"><strong>Last appearance:</strong> ${latestGame ? fixtureAndResultLink(latestGame, true) : escapeHtml(String(player?.lastAppearanceDate || "Unknown"))}</p>
                    </section>

                    <section class="full-profile-section-block">
                        <div class="full-profile-section-title">Scoring</div>
                        <p class="full-profile-copy-line"><strong>Scoring record:</strong> ${escapeHtml(scoringRecord)}</p>
                        <p class="full-profile-copy-line"><strong>Career points:</strong> ${Number(scoringCareer.points || 0)}</p>
                        <p class="full-profile-copy-line"><strong>This season:</strong> ${seasonRecord}</p>
                    </section>

                    ${sponsorshipSectionHtml}
                </div>

                <div class="full-profile-sections-column">
                    <section class="full-profile-section-block">
                        <div class="full-profile-section-title">Position</div>
                        <p class="full-profile-copy-line">Positions played across all recorded starts, along with bench appearances.</p>
                        <div id="fullProfilePositionDonutChart" class="chart-host chart-host--overflow-visible chart-host--intrinsic full-profile-inline-chart">Loading position chart...</div>
                    </section>

                    <section class="full-profile-section-block" aria-labelledby="playerProfileSeasonAppsHeading">
                        <div id="playerProfileSeasonAppsHeading" class="full-profile-section-title">Appearances Per Season</div>
                        <p class="full-profile-copy-line">Visual breakdown of appearances across seasons with interactive colour options.</p>
                        <div class="chart-section-head">
                            <div class="filter-item full-profile-chart-filter-item">
                                <div class="btn-group btn-group-sm" role="group" aria-label="Colour appearances chart by">
                                    <input type="radio" class="btn-check" name="fullProfileColorBy" id="fullProfileColorBySquad" value="Squad" checked autocomplete="off">
                                    <label class="btn btn-filter-segment" for="fullProfileColorBySquad">Squad</label>
                                    <input type="radio" class="btn-check" name="fullProfileColorBy" id="fullProfileColorByResult" value="Result" autocomplete="off">
                                    <label class="btn btn-filter-segment" for="fullProfileColorByResult">Result</label>
                                    <input type="radio" class="btn-check" name="fullProfileColorBy" id="fullProfileColorByPosition" value="Position" autocomplete="off">
                                    <label class="btn btn-filter-segment" for="fullProfileColorByPosition">Position</label>
                                </div>
                            </div>
                        </div>
                        <div id="fullProfileAppearancesPerSeasonChart" class="chart-host chart-host--overflow-visible chart-host--intrinsic player-stats-chart-container">Loading appearances chart...</div>
                    </section>
                </div>

                <section class="full-profile-section-full chart-section" aria-labelledby="playerProfileAppearancesHeading">
                    <div class="chart-section-block chart-section-block--panel full-profile-table-card">
                    <h2 id="playerProfileAppearancesHeading" class="full-profile-section-title">All Appearances</h2>
                    <p class="section-intro">Complete appearance history with search, sorting by any column, and pagination control.</p>
                        <div class="chart-panel-filters full-profile-table-filters">
                            <div class="filter-item database-search-item full-profile-table-filter-item">
                                <div class="input-group">
                                    <span class="input-group-text">Search</span>
                                    <input id="fullProfileAppearancesSearch" type="search" class="form-control flex-fill" placeholder="Filter rows..." autocomplete="off">
                                </div>
                            </div>
                        </div>
                        <div class="table-responsive database-table-responsive" id="fullProfileAppearancesTable">
                            <table class="table table-striped table-hover align-middle database-data-table">
                                <thead>
                                    <tr>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="date" data-appearance-label="Date"><span>Date</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="competition" data-appearance-label="Competition"><span>Competition</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="squad" data-appearance-label="Squad"><span>Squad</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="opposition" data-appearance-label="Opposition"><span>Opposition</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="homeAway" data-appearance-label="H/A"><span>H/A</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="position" data-appearance-label="Position"><span>Position</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="shirtNumber" data-appearance-label="Number"><span>Number</span></button></th>
                                        <th><button type="button" class="database-sort-button full-profile-sort-button" data-appearance-sort="result" data-appearance-label="Result"><span>Result</span></button></th>
                                        <th class="match-table-open-cell"><span class="visually-hidden">Open match</span></th>
                                    </tr>
                                </thead>
                                <tbody id="fullProfileAppearancesTableBody"></tbody>
                            </table>
                        </div>
                        <div class="database-pagination-bar full-profile-pagination-bar">
                            <div id="fullProfileAppearancesPaginationSummary" class="database-pagination-summary">0 appearances</div>
                            <div class="match-finder-pagination-controls" role="group" aria-label="Appearances pagination">
                                <button id="fullProfileAppearancesPrev" type="button" class="btn match-finder-pagination-btn prev-btn">Previous</button>
                                <button id="fullProfileAppearancesNext" type="button" class="btn match-finder-pagination-btn next-btn">Next</button>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </article>
    `;

  initializeLastTenTooltips(root);
  bindAppearancePanelControls(String(player?.name || "").trim());
  renderAppearanceTable();
  renderPositionDonutChart(String(player?.name || "").trim());
  renderCareerTimelineChart(String(player?.name || "").trim());
  renderAppearancesPerSeasonChart(String(player?.name || "").trim());
}

function updateUrlPlayer(name) {
  const next = String(name || "").trim();
  const url = new URL(window.location.href);
  if (next) url.searchParams.set("player", next);
  else url.searchParams.delete("player");
  window.history.replaceState({}, "", url.toString());
}

function renderSelectedPlayer() {
  const select = document.getElementById("fullProfilePlayerSelect");
  if (!select) return;

  const selectedName = String(select.value || "").trim();
  const player = fullProfiles.find(
    (row) => String(row?.name || "").trim() === selectedName,
  );
  const root = document.getElementById("fullProfileRoot");
  if (!root) return;

  if (!player) {
    root.classList.remove("d-none");
    root.innerHTML =
      '<div class="alert alert-light">Select a player to view their full profile.</div>';
    updateUrlPlayer("");
    return;
  }

  updateUrlPlayer(selectedName);
  renderProfile(player);
}

function initPlayerSelect() {
  const select = document.getElementById("fullProfilePlayerSelect");
  if (!select) return;

  const eligible = fullProfiles
    .filter((row) => Number(row?.totalAppearances || 0) >= 10)
    .sort((a, b) => String(a?.name || "").localeCompare(String(b?.name || "")));

  select.innerHTML =
    '<option value="">Select player...</option>' +
    eligible
      .map(
        (row) =>
          `<option value="${escapeHtml(String(row?.name || ""))}">${escapeHtml(String(row?.name || ""))}</option>`,
      )
      .join("");

  const useSelectPicker = rebuildBootstrapSelect(select);

  const url = new URL(window.location.href);
  const preselected = String(url.searchParams.get("player") || "").trim();
  if (
    preselected &&
    eligible.some((row) => String(row?.name || "").trim() === preselected)
  ) {
    if (useSelectPicker) window.jQuery(select).selectpicker("val", preselected);
    else select.value = preselected;
  } else if (useSelectPicker) {
    window.jQuery(select).selectpicker("val", "");
  }

  if (useSelectPicker) {
    window
      .jQuery(select)
      .off("changed.bs.select.fullProfile")
      .on("changed.bs.select.fullProfile", renderSelectedPlayer);
  } else {
    select.addEventListener("change", renderSelectedPlayer);
  }

  renderSelectedPlayer();
}

async function loadPage() {
  const loadingState = document.getElementById("fullProfileLoadingState");
  const errorState = document.getElementById("fullProfileErrorState");
  const root = document.getElementById("fullProfileRoot");

  try {
    const [profilesRes, gamesRes, appearancesRes, sponsorsRes] =
      await Promise.all([
        fetch("data/backend/player_profiles_canonical.json"),
        fetch("data/backend/games.json"),
        fetch("data/backend/player_appearances.json"),
        fetch("data/sponsors.json"),
      ]);

    if (!profilesRes.ok || !gamesRes.ok || !appearancesRes.ok) {
      throw new Error("Failed to load one or more profile datasets");
    }

    const [profiles, games, appearances, sponsorsBySeason] = await Promise.all([
      profilesRes.json(),
      gamesRes.json(),
      appearancesRes.json(),
      sponsorsRes.ok ? sponsorsRes.json() : Promise.resolve({}),
    ]);

    fullProfiles = Array.isArray(profiles) ? profiles : [];

    fullGamesById = new Map();
    (Array.isArray(games) ? games : []).forEach((game) => {
      const key = String(game?.game_id || "").trim();
      if (key) fullGamesById.set(key, game);
    });

    fullAppearancesByPlayer = new Map();
    fullAppearancesByGame = new Map();
    (Array.isArray(appearances) ? appearances : []).forEach((row) => {
      const key = String(row?.player || "").trim();
      if (!key) return;
      if (!fullAppearancesByPlayer.has(key))
        fullAppearancesByPlayer.set(key, []);
      fullAppearancesByPlayer.get(key).push(row);

      const gameId = String(row?.game_id || "").trim();
      if (!gameId) return;
      if (!fullAppearancesByGame.has(gameId))
        fullAppearancesByGame.set(gameId, []);
      fullAppearancesByGame.get(gameId).push(row);
    });

    fullProfilesByName = new Map(
      fullProfiles.map((profile) => [
        String(profile?.name || "").trim(),
        profile,
      ]),
    );

    fullSponsorHistoryByPlayer = buildSponsorHistoryMap(sponsorsBySeason);
    fullCurrentSeason = deriveCurrentSeason(games);

    const chartSpecEntries = await Promise.allSettled([
      loadChartSpec(
        "data/charts/player_full_profile_appearances_per_season_squad.json",
      ),
      loadChartSpec(
        "data/charts/player_full_profile_appearances_per_season_result.json",
      ),
      loadChartSpec(
        "data/charts/player_full_profile_appearances_per_season_position.json",
      ),
      loadChartSpec("data/charts/player_full_profile_position_donut.json"),
      loadChartSpec("data/charts/player_full_profile_career_timeline.json"),
    ]);
    fullProfileAppearancesBySeasonSpecs = {
      Squad:
        chartSpecEntries[0].status === "fulfilled"
          ? chartSpecEntries[0].value
          : null,
      Result:
        chartSpecEntries[1].status === "fulfilled"
          ? chartSpecEntries[1].value
          : null,
      Position:
        chartSpecEntries[2].status === "fulfilled"
          ? chartSpecEntries[2].value
          : null,
    };
    fullProfilePositionDonutSpec =
      chartSpecEntries[3].status === "fulfilled"
        ? chartSpecEntries[3].value
        : null;
    fullProfileCareerTimelineSpec =
      chartSpecEntries[4].status === "fulfilled"
        ? chartSpecEntries[4].value
        : null;
    if (
      !fullProfileAppearancesBySeasonSpecs.Squad ||
      !fullProfileAppearancesBySeasonSpecs.Result ||
      !fullProfileAppearancesBySeasonSpecs.Position
    ) {
      console.warn(
        "Unable to load one or more full profile appearances chart specs:",
        chartSpecEntries,
      );
    }

    renderPlayerProfileCaptains();
    initPlayerSelect();

    if (loadingState) loadingState.classList.add("d-none");
    if (errorState) errorState.classList.add("d-none");
    if (root) root.classList.remove("d-none");
  } catch (error) {
    console.error(error);
    if (loadingState) loadingState.classList.add("d-none");
    if (root) root.classList.add("d-none");
    if (errorState) {
      errorState.classList.remove("d-none");
      errorState.textContent =
        "Unable to load full profile data. Run python/update.py and try again.";
    }
  }
}

document.addEventListener("DOMContentLoaded", loadPage);

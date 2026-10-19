import { reportTimelineSpec, reportLeagueSpec, chartImage, leagueLegend } from "./player-report-charts.js";

const SCORE_FIELDS = ["tries", "conversions", "penalties", "drop_goals", "points"];
const SCOPES = ["1st XV", "2nd XV", "Overall"];
let reportSources;

function escapeHtml(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function slug(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "summary";
}

function playerKey(value) {
  const name = String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
  const overrides = { "sam lindsay": "s lindsay 2", "sam lindsay-mccall": "s lindsay-mccall", "james mitchell": "t mitchell" };
  if (overrides[name]) return overrides[name];
  const space = name.indexOf(" ");
  return space < 0 ? name : `${name[0]} ${name.slice(space + 1)}`;
}

async function loadSources() {
  if (!reportSources) {
    const names = ["lineouts", "set_piece", "season_scorers", ...["google", "pitchero", "rfu"].flatMap(source => [`scorers_stage_${source}`, `player_appearances_stage_${source}`])];
    reportSources = Promise.all(names.map(async name => {
      const response = await fetch(`data/backend/${name}.json`);
      if (!response.ok) throw new Error(`Unable to load report dataset: ${name}`);
      return [name, await response.json()];
    })).then(entries => Object.fromEntries(entries)).catch(error => {
      reportSources = null;
      throw error;
    });
  }
  return reportSources;
}

export function buildPlayerReportData({ player, appearances, games, sources }) {
  const nameKey = playerKey(player.name);
  const gameMap = new Map(games.map(game => [game.game_id, game]));
  const sameFixture = (left, right) => left.game_id === right.game_id || (left.date === right.date && left.squad === right.squad);
  const sourceRows = Object.fromEntries(["google", "pitchero", "rfu"].map(source => [source, (sources[`player_appearances_stage_${source}`] || []).filter(row => playerKey(row.player) === nameKey)]));
  const aliasFixtures = (player.name === "Sam Lindsay-McCall" ? sources.player_appearances_stage_pitchero || [] : []).filter(row => row.player === "Sam Lindsay" && sourceRows.google.some(other => sameFixture(row, other)));
  const scoreRows = ["google", "pitchero", "rfu"].flatMap((source, priority) => (sources[`scorers_stage_${source}`] || []).filter(row => {
    let key = playerKey(row.player);
    if (String(row.player).toLowerCase() === "s lindsay") key = row.season && row.season < "2021/22" ? "s lindsay 2" : "s lindsay-mccall";
    return key === nameKey;
  }).map(row => ({ ...row, priority })));
  const history = appearances.filter(row => row.player === player.name).map(row => {
    const game = gameMap.get(row.game_id) || {};
    const scores = scoreRows.filter(score => sameFixture(score, row));
    const exact = scores.filter(score => score.game_id === row.game_id);
    const candidates = exact.length ? exact : scores;
    const best = candidates.length ? Math.min(...candidates.map(score => score.priority)) : -1;
    const scoring = Object.fromEntries(SCORE_FIELDS.map(field => [field, candidates.filter(score => score.priority === best).reduce((sum, score) => sum + Number(score[field] || 0), 0)]));
    return { ...row, ...game, squad: row.squad, position: row.position, ...scoring,
      number: row.number ?? row.shirt_number,
      is_motm: String(game.motm || "").split(/\s*(?:[,/&+]|\band\b)\s*/i).some(name => playerKey(name) === nameKey),
      ...Object.fromEntries(["google", "pitchero", "rfu"].map(source => [`${source}_source`, sourceRows[source].some(other => sameFixture(row, other)) || (source === "pitchero" && aliasFixtures.some(other => sameFixture(row, other)))])),
    };
  }).sort((left, right) => String(left.date).localeCompare(String(right.date)) || String(left.squad).localeCompare(String(right.squad)));
  const positions = new Map();
  history.filter(row => row.is_starter && row.position && row.position !== "Bench").forEach(row => positions.set(row.position, (positions.get(row.position) || 0) + 1));
  const rankedPositions = [...positions].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  return { player, history, appearances, sources, aliasFixtures, rankedPositions };
}

function raw(html) {
  return { html };
}

function resultMarkup(result, label = result) {
  const type = { W: "win", L: "loss", D: "draw" }[result] || "";
  return `<span class="result-badge result-badge--${type}">${escapeHtml(label)}</span>`;
}

function scoreLabel(row) {
  return row.score_for != null && row.score_against != null ? `${row.result || ""} ${row.score_for}-${row.score_against}` : row.result || "-";
}

function record(rows) {
  return ["W", "L", "D"].map(result => {
    const count = rows.filter(row => row.result === result).length;
    return result === "D" && !count ? "" : `<span class="record-chip record-chip--${{ W: "win", L: "loss", D: "draw" }[result]}">${result} ${count}</span>`;
  }).join("");
}

function table(headers, rows, className = "") {
  const columns = headers.map(header => header.split("::"));
  const grouped = columns.some(column => column.length > 1);
  const groups = [];
  columns.forEach(column => {
    const title = grouped ? column[0] : "";
    if (groups.at(-1)?.title === title) groups.at(-1).count += 1;
    else groups.push({ title, count: 1 });
  });
  const columnClass = index => {
    const group = grouped ? columns[index][0] : "";
    return `group-${slug(group)} column-${slug(columns[index].at(-1))}${index === 0 || columns[index - 1][0] !== group ? " group-start" : ""}${index === columns.length - 1 || columns[index + 1][0] !== group ? " group-end" : ""}`;
  };
  const cell = (value, index) => {
    if (value?.html != null) return value.html;
    const title = columns[index].at(-1);
    if (typeof value === "number" && ["Apps", "Starts", "Tries", "Conversions", "Penalties", "Drop goals", "Points"].includes(title)) {
      const maximum = Math.max(1, ...rows.map(row => Number(row[index]) || 0));
      return `<span class="data-bar data-bar--${className === "scoring-table" ? "score" : "count"}${!value ? " zero-value" : ""}" style="--pct:${100 * value / maximum}%">${value}</span>`;
    }
    if (title === "Success" && String(value).endsWith("%")) {
      const percent = Number.parseFloat(value);
      return `<span class="data-bar data-bar--${percent >= 80 ? "high" : percent >= 60 ? "mid" : "low"}" style="--pct:${percent}%">${escapeHtml(value)}</span>`;
    }
    return escapeHtml(value);
  };
  return `<div class="table-wrap"><table class="table table-striped table-hover align-middle database-data-table ${className}"><thead>${grouped ? `<tr class="group-header">${groups.map(group => `<th colspan="${group.count}" class="group-${slug(group.title)}">${escapeHtml(group.title)}</th>`).join("")}</tr>` : ""}<tr>${columns.map((column, index) => `<th class="${columnClass(index)}">${escapeHtml(column.at(-1))}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((value, index) => `<td class="${columnClass(index)}">${cell(value, index)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function summary(model, firstXV) {
  const rows = model.history.filter(row => !firstXV || row.squad === "1st");
  const estimate = Number(model.player[firstXV ? "historicEstimatedFirstXVAppearances" : "historicEstimatedAppearances"] || 0);
  const scoring = SCORE_FIELDS.map(field => rows.reduce((sum, row) => sum + row[field], 0));
  const details = ["try", "conversion", "penalty", "drop goal"].flatMap((label, index) => scoring[index] ? [`${scoring[index]} ${scoring[index] === 1 ? label : index === 0 ? "tries" : `${label}s`}`] : []);
  const fixture = row => row ? `${escapeHtml(row.date)} vs ${escapeHtml(row.opposition || "Unknown")} (${escapeHtml(row.home_away || "?")}) &bull; ${resultMarkup(row.result, scoreLabel(row))}` : "-";
  return `<section class="profile-summary-group profile-summary-group--${firstXV ? "first-xv" : "overall"}"><h3>${firstXV ? "1st XV" : "Overall"}</h3><div class="profile-summary-lines"><p><strong>Appearances:</strong> ${rows.length + estimate}${estimate ? "*" : ""} (${rows.filter(row => row.is_starter).length} starts)</p><p><strong>Points:</strong> ${scoring[4]}${details.length ? ` (${escapeHtml(details.join(", "))})` : ""}</p><p><strong>Debut:</strong> ${fixture(rows[0])}</p><p><strong>Latest appearance:</strong> ${fixture(rows.at(-1))}</p><p><strong>Win record:</strong> <span class="record-chip-group">${record(rows)}</span></p></div></section>`;
}

function positionBar(model) {
  const colors = ["#202946", "#7d96e8", "#146f14", "#991515", "#333333", "#000000"];
  const positions = [...model.rankedPositions];
  const bench = model.history.filter(row => !row.is_starter).length;
  if (bench) positions.push(["Bench", bench]);
  return `<div class="position-appearance-wrap"><h3>Position</h3><div class="position-appearance-bar">${positions.map(([position, count], index) => `<div class="position-bar-segment" style="--segment-count:${count};--segment-color:${position === "Bench" ? "#6b7280" : colors[Math.min(index, colors.length - 1)]};--segment-text:${index === 1 ? "#111111" : "#ffffff"}">${escapeHtml(position)}<span>${count} appearances</span></div>`).join("")}</div></div>`;
}

function playingRecord(model) {
  const seasons = [...new Set(model.history.map(row => row.season))].sort();
  const headers = ["Game detail::Date", "Game detail::Competition", "Game detail::Squad", "Game detail::Opposition", "Game detail::H/A", "Game detail::Result", "Player detail::Position", "Player detail::Number", "Player detail::Captain", "Player detail::Scores", "Player detail::MOTM", "Data Source::Google", "Data Source::Pitchero", "Data Source::RFU"];
  return `<h2 class="playing-record-heading">Playing Record</h2>${seasons.map(season => {
    const rows = model.history.filter(row => row.season === season);
    return `<h3>${escapeHtml(season)} (${rows.length} appearances)</h3>${table(headers, rows.map(row => [row.date, row.competition || row.game_type, raw(`<span class="squad-pill">${escapeHtml(row.squad)}</span>`), row.opposition, row.home_away, raw(resultMarkup(row.result, scoreLabel(row))), row.is_starter ? row.position : "Bench", row.number || "", raw(row.is_captain ? '<span class="captain-marker">C</span>' : ""), raw(["tries", "penalties", "conversions", "drop_goals"].map((field, index) => row[field] ? `<span class="score-marker">${["T", "P", "C", "DG"][index]}${row[field] > 1 ? ` x${row[field]}` : ""}</span>` : "").join("")), raw(row.is_motm ? '<span class="motm-marker">&#9733;</span>' : ""), ...["google", "pitchero", "rfu"].map(source => raw(row[`${source}_source`] ? '<span class="source-flag">&#10003;</span>' : ""))]), "appearance-table")}`;
  }).join("")}`;
}

function seasonSummary(model) {
  const seasons = [...new Set(model.history.map(row => row.season))].sort();
  const headers = ["Season::Season", ...SCOPES.flatMap(scope => ["Apps", "Starts", "Results"].map(metric => `${scope}::${metric}`))];
  const rows = seasons.map(season => [season, ...SCOPES.flatMap(scope => {
    const selected = model.history.filter(row => row.season === season && (scope === "Overall" || `${row.squad} XV` === scope));
    return [selected.length, selected.filter(row => row.is_starter).length, raw(`<span class="record-chip-group">${record(selected)}</span>`)];
  })]);
  const historic = Number(model.player.historicEstimatedAppearances || 0);
  const first = Number(model.player.historicEstimatedFirstXVAppearances || 0);
  if (historic) rows.unshift(["Historic*", first, "-", "-", historic - first, "-", "-", historic, "-", "-"]);
  return `<h2>Season Summaries</h2>${table(headers, rows, "season-summary")}`;
}

function scoringRecord(model) {
  const scores = model.sources.season_scorers.filter(row => row.player === model.player.name);
  const metrics = SCORE_FIELDS.filter(field => field === "points" ? scores.some(row => row.conversions || row.penalties || row.drop_goals) : scores.some(row => row[field]));
  if (!metrics.length) return "";
  const squads = ["1st", "2nd"].filter(squad => scores.some(row => row.squad === squad && SCORE_FIELDS.some(field => row[field])));
  if (squads.length === 2) squads.push("Overall");
  const labels = { tries: "Tries", conversions: "Conversions", penalties: "Penalties", drop_goals: "Drop goals", points: "Points" };
  const headers = ["Season::Season", ...squads.flatMap(squad => metrics.map(field => `${squad === "Overall" ? squad : `${squad} XV`}::${labels[field]}`))];
  const rows = [...new Set(model.history.map(row => row.season))].sort().map(season => [season, ...squads.flatMap(squad => metrics.map(field => scores.filter(row => row.season === season && (squad === "Overall" || row.squad === squad)).reduce((sum, row) => sum + Number(row[field] || 0), 0)))]);
  return `<h2>Scoring Record</h2>${table(headers, rows, "scoring-table")}`;
}

function teammates(model) {
  const groups = new Map([["Overall", new Map()]]);
  const positionGroup = position => ({ Prop: "Front Row", Hooker: "Front Row", "Second Row": "Second Row", Flanker: "Back Row", "Number 8": "Back Row", "Scrum Half": "Half Back", "Fly Half": "Half Back", Wing: "Back Three", "Full Back": "Back Three" })[position];
  const positionStarts = new Map(model.rankedPositions);
  const groupStarts = new Map();
  for (const [position, starts] of positionStarts) {
    const group = positionGroup(position);
    if (group) groupStarts.set(group, (groupStarts.get(group) || 0) + starts);
  }
  for (const mine of model.history) {
    for (const other of model.appearances.filter(row => row.game_id === mine.game_id && row.player !== model.player.name)) {
      const titles = ["Overall"];
      if (mine.is_starter && positionStarts.get(mine.position) >= 5 && other.position === mine.position) titles.push(`${mine.position} Partners`);
      const group = positionGroup(mine.position);
      if (mine.is_starter && groupStarts.get(group) >= 5 && ["Front Row", "Back Row", "Half Back", "Back Three"].includes(group) && positionGroup(other.position) === group) titles.push(`${group} Partners`);
      for (const title of titles) {
        if (!groups.has(title)) groups.set(title, new Map());
        const counts = groups.get(title);
        if (!counts.has(other.player)) counts.set(other.player, new Set());
        counts.get(other.player).add(mine.game_id);
      }
    }
  }
  return `<h2>Most Common Teammates</h2><div class="teammate-layout">${[...groups].map(([title, counts]) => `<section class="teammate-card"><h3>${escapeHtml(title)}</h3>${table(["Player", "Games"], [...counts].sort((left, right) => right[1].size - left[1].size || left[0].localeCompare(right[0])).slice(0, 5).map(([name, games]) => [name, games.size]))}</section>`).join("")}</div>`;
}

function setPieceRecord(model) {
  const nameKey = playerKey(model.player.name);
  const jumping = model.sources.lineouts.filter(row => playerKey(row.jumper) === nameKey || model.aliasFixtures.some(alias => alias.game_id === row.game_id && alias.date === row.date && alias.squad === row.squad));
  const throwing = model.sources.lineouts.filter(row => playerKey(row.thrower) === nameKey);
  const starts = model.history.filter(row => row.is_starter);
  const includeScrum = starts.filter(row => ["prop", "hooker", "second row"].includes(String(row.position).toLowerCase())).length > starts.length / 2;
  const includeLineout = jumping.length >= 10;
  const started = model.sources.set_piece.filter(row => row.team === "EGRFC" && starts.some(start => start.game_id === row.game_id && start.squad === row.squad));
  const headers = ["Season::Season", ...SCOPES.flatMap(scope => ["Won", "Total", "Success"].map(metric => `${scope}::${metric}`))];
  const success = (won, total) => total ? `${(100 * won / total).toFixed(1)}%` : "-";
  const teamTable = kind => table(headers, [...new Set(started.map(row => row.season)), "Total"].sort((left, right) => left === "Total" ? 1 : right === "Total" ? -1 : left.localeCompare(right)).map(season => [season, ...SCOPES.flatMap(scope => {
    const selected = started.filter(row => (season === "Total" || row.season === season) && (scope === "Overall" || `${row.squad} XV` === scope));
    const won = selected.reduce((sum, row) => sum + Number(row[`${kind}_won`] || 0), 0);
    const total = selected.reduce((sum, row) => sum + Number(row[`${kind}_total`] || 0), 0);
    return [won, total, success(won, total)];
  })]), "season-summary");
  const breakdown = (rows, field, title, limit) => {
    const counts = new Map();
    rows.forEach(row => {
      const label = row[field] ?? "Unspecified";
      if (!counts.has(label)) counts.set(label, { attempts: 0, won: 0 });
      counts.get(label).attempts += 1;
      counts.get(label).won += Number(!!row.won);
    });
    return table([title, "Attempts", "Won", "Success"], [...counts].sort((left, right) => field === "season" ? left[0].localeCompare(right[0]) : right[1].attempts - left[1].attempts || left[0].localeCompare(right[0])).slice(0, limit).map(([label, counts]) => [label, counts.attempts, counts.won, success(counts.won, counts.attempts)]), "lineout-table");
  };
  let content = "";
  if (includeScrum && started.some(row => row.scrums_total)) content += `<h3>Team Scrum Success</h3><p>Team scrums in games the player started; shown because more than half of their career starts were in the tight five.</p>${teamTable("scrums")}`;
  if (includeLineout && started.some(row => row.lineouts_total)) content += `<h3>Team Lineout Success</h3><p>Team lineouts in games the player started; shown because they have at least 10 career lineout jump attempts.</p>${teamTable("lineouts")}`;
  if (includeLineout) content += `<h3>Jumping</h3><div class="lineout-grid">${breakdown(jumping, "season", "Season")}${breakdown(jumping, "area", "Area")}${breakdown(jumping, "thrower", "Thrower", 5)}</div>`;
  if (throwing.length) content += `<h3>Throwing</h3><div class="lineout-grid">${breakdown(throwing, "season", "Season")}${breakdown(throwing, "area", "Area")}${breakdown(throwing, "jumper", "Jumper", 5)}</div>`;
  return content ? `<h2>Set Piece Record</h2>${content}` : "";
}

export function playerReportBody(model, { timeline = "", league = "", timelineLegend = "" } = {}) {
  const position = model.rankedPositions[0]?.[0] || model.player.position || "Unknown";
  const date = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const crest = '<img class="hero-club" src="img/logos/EastGrinstead.png" alt="East Grinstead RFC">';
  const portrait = model.player.photo_url ? `<img class="hero-image" src="${escapeHtml(model.player.photo_url)}" alt="Player headshot">` : "";
  return `<main><header class="hero" style="background-image:linear-gradient(rgba(32,41,70,.42),rgba(32,41,70,.58)),url('img/EGRFC Background.png')">${crest}${portrait}<div class="hero-copy"><h1>${escapeHtml(model.player.name)}</h1><p class="hero-subtitle">${escapeHtml(position)}</p></div><div class="brand"><img class="brand-avatar" src="img/SLM_Avatar.png" alt="SLM"><span class="brand-url">eg-stats.uk</span><span class="report-date">Data as at<br>${escapeHtml(date)}</span></div></header><h2>Career Summary</h2><div class="career-summary-grid">${summary(model, true)}${summary(model, false)}</div>${model.player.historicEstimatedAppearances ? '<p>* estimated total</p>' : ""}${positionBar(model)}<h3>Timeline</h3><div class="career-chart career-chart--below-legend" style="padding:0;border:0;display:block">${timeline || '<p>No career milestones available.</p>'}${timelineLegend}</div><h3>League History</h3><div class="league-chart" style="padding:0;border:0">${league || '<p>No league history is available for this player.</p>'}</div>${playingRecord(model)}${seasonSummary(model)}${scoringRecord(model)}${teammates(model)}${setPieceRecord(model)}<footer><img class="brand-avatar" src="img/SLM_Avatar.png" alt="SLM"><span>eg-stats.uk</span></footer></main>`;
}

export async function buildPlayerReportHtml({ player, appearances, games, timelineSpec, timelineLegend }) {
  const [sources, cssResponse, leagueResponse] = await Promise.all([loadSources(), fetch("css/player-report.css", { cache: "no-cache" }), fetch("data/charts/league_history_progression.json")]);
  if (!cssResponse.ok || !leagueResponse.ok) throw new Error("Unable to load report styling or league history");
  const model = buildPlayerReportData({ player, appearances, games, sources });
  const timeline = timelineSpec ? await chartImage(reportTimelineSpec(timelineSpec, player.name)) : "";
  const leagueSpec = reportLeagueSpec(await leagueResponse.json(), model.history);
  const league = leagueSpec ? `${await chartImage(leagueSpec)}${leagueLegend(leagueSpec)}` : "";
  const body = playerReportBody(model, { timeline, league, timelineLegend });
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="${escapeHtml(new URL(".", document.baseURI).href)}"><title>${escapeHtml(player.name)} - Player Report</title><link href="https://fonts.googleapis.com/css2?family=PT+Sans+Narrow:wght@400;700&display=swap" rel="stylesheet"><style>${await cssResponse.text()}</style><style>.career-chart--below-legend>img{width:100%}.career-chart--below-legend .full-profile-timeline-legend-block{display:table;width:max-content;margin:4px 0 0 auto}.career-chart--below-legend .full-profile-timeline-legend-groups{display:flex;gap:34px}.report-chart-image{display:block;width:100%;height:auto}main{display:flow-root}.report-pdf-page{width:748px;margin:0;padding:0;box-shadow:none;background:#fff}.report-pdf-page .table-wrap{overflow:visible}.report-pdf-page .playing-record-heading{break-before:auto}</style></head><body>${body}</body></html>`;
}

function paginateReport(reportDocument) {
  const height = 1077;
  const source = reportDocument.querySelector("main");
  const blocks = [...source.children];
  source.remove();
  const pages = [];
  let page;
  const newPage = () => {
    page = reportDocument.createElement("main");
    page.className = "report-pdf-page";
    reportDocument.body.append(page);
    pages.push(page);
  };
  newPage();
  for (const block of blocks) {
    if (block.classList.contains("playing-record-heading") && page.children.length) newPage();
    const tableElement = block.matches(".table-wrap") ? block.querySelector("table") : null;
    if (tableElement) {
      const rows = [...tableElement.querySelectorAll("tbody>tr")];
      tableElement.querySelector("tbody").replaceChildren();
      let wrapper = block;
      page.append(wrapper);
      let body = wrapper.querySelector("tbody");
      for (const row of rows) {
        body.append(row);
        if (page.getBoundingClientRect().height > height && (page.children.length > 1 || body.children.length > 1)) {
          row.remove();
          const previousHeading = !body.children.length && wrapper.previousElementSibling?.matches("h2,h3") ? wrapper.previousElementSibling : null;
          if (!body.children.length) wrapper.remove();
          previousHeading?.remove();
          newPage();
          if (previousHeading) page.append(previousHeading);
          wrapper = block.cloneNode(true);
          body = wrapper.querySelector("tbody");
          body.replaceChildren(row);
          page.append(wrapper);
        }
      }
    } else {
      const previousHeading = page.lastElementChild?.matches("h2,h3") ? page.lastElementChild : null;
      page.append(block);
      if (page.getBoundingClientRect().height > height && page.children.length > 1) {
        block.remove();
        previousHeading?.remove();
        newPage();
        if (previousHeading) page.append(previousHeading);
        page.append(block);
      }
    }
  }
  return pages;
}

export async function downloadPlayerReport(options) {
  const [html, { jsPDF }, { default: html2canvas }] = await Promise.all([
    buildPlayerReportHtml(options), import("https://cdn.jsdelivr.net/npm/jspdf@3.0.3/+esm"), import("https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/+esm"),
  ]);
  const iframe = document.createElement("iframe");
  iframe.title = "Player report PDF renderer";
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.cssText = "position:fixed;left:-10000px;top:0;width:748px;height:1123px;border:0;pointer-events:none";
  try {
    const loaded = new Promise(resolve => { iframe.onload = resolve; });
    iframe.srcdoc = html;
    document.body.append(iframe);
    await loaded;
    const reportDocument = iframe.contentDocument;
    for (const sheet of reportDocument.styleSheets) {
      if (sheet.href) continue;
      for (const rule of sheet.cssRules) {
        if (rule.media?.mediaText === "print") rule.media.mediaText = "all";
      }
      sheet.ownerNode.textContent = [...sheet.cssRules].map(rule => rule.cssText).join("\n");
    }
    await reportDocument.fonts.ready;
    await Promise.all([...reportDocument.images].map(image => image.decode()));
    const pages = paginateReport(reportDocument);
    const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
    pdf.setProperties({ title: `${options.player.name} - Player Report`, author: "East Grinstead RFC", creator: "EGRFC Statistics" });
    for (const [index, page] of pages.entries()) {
      const canvas = await html2canvas(page, { scale: 2, useCORS: true, backgroundColor: "#ffffff", windowWidth: 748, windowHeight: 1123, logging: false });
      if (index) pdf.addPage();
      const height = canvas.height * 198 / canvas.width;
      if (height > 285.5) throw new Error("Report section exceeds a PDF page");
      pdf.addImage(canvas.toDataURL("image/png"), "PNG", 6, 6, 198, height);
    }
    await pdf.save(`${slug(options.player.name)}-report.pdf`, { returnPromise: true });
  } finally {
    iframe.remove();
  }
}
export function reportTimelineSpec(original, playerName) {
  const spec = structuredClone(original);
  const dataset = Object.keys(spec.datasets || {}).find(key => spec.datasets[key].some(row => "event_key" in row && "row_type" in row));
  if (!dataset) return null;
  const rows = spec.datasets[dataset].filter(row => String(row.player || "").trim() === playerName);
  if (!rows.length) return null;
  spec.datasets[dataset] = rows;
  const labelled = new Set();
  for (const row of [...rows].sort((left, right) => (left.event_sort || 0) - (right.event_sort || 0) || (left.event_rank || 0) - (right.event_rank || 0))) {
    const first = ["first_xv_debut", "milestone_25_1st", "milestone_50_1st", "milestone_100_1st"].includes(row.event_key);
    const club = ["debut", "milestone_25", "milestone_50", "milestone_100"].includes(row.event_key);
    row.milestone_y_offset = row.event_key === "last_game" ? 15 : club ? 7 : first ? 23 : 0;
    const key = JSON.stringify([row.game_id, row.date, row.detail]);
    row.detail_label = labelled.has(key) ? "" : row.detail;
    labelled.add(key);
    row.detail_y_offset = row.milestone_y_offset - 26;
    row.detail_label_color = ({ first_xv_debut: "#202946", first_try: "#991515", first_xv_try: "#991515", first_captaincy: "#7d96e8" })[row.event_key] || "#4a5568";
  }
  let previous;
  for (const row of [...rows].filter(row => row.detail_label).sort((left, right) => (left.event_sort || 0) - (right.event_sort || 0) || (left.event_rank || 0) - (right.event_rank || 0))) {
    row.detail_x_lane = 0;
    if (previous && (new Date(row.date) - new Date(previous.date)) / 86400000 < 45) {
      previous.detail_x_lane = -1;
      row.detail_x_lane = 1;
    }
    previous = row;
  }
  spec.width = 900;
  spec.height = 60;
  for (const index of [1, 2]) spec.layer[index].encoding.yOffset = { field: "milestone_y_offset", type: "quantitative", scale: null };
  const detail = spec.layer[5];
  spec.layer = [...spec.layer.slice(0, 5), ...[-1, 0, 1].map(lane => {
    const layer = structuredClone(detail);
    layer.transform = [{ filter: `datum.detail_label !== '' && datum.detail_x_lane == ${lane}` }];
    layer.encoding.text = { field: "detail_label", type: "nominal" };
    layer.encoding.color = { field: "detail_label_color", type: "nominal", scale: null, legend: null };
    layer.encoding.yOffset = { field: "detail_y_offset", type: "quantitative", scale: null };
    Object.assign(layer.mark, { align: "left", baseline: "middle", angle: 270, xOffset: lane * 8 });
    delete layer.mark.yOffset;
    return layer;
  })];
  return spec;
}

export function reportLeagueSpec(original, history) {
  const spec = structuredClone(original);
  const dataset = Object.keys(spec.datasets || {}).find(key => spec.datasets[key].some(row => ["season", "squad", "level", "rank"].every(field => field in row)));
  if (!dataset) return null;
  const counts = new Map();
  const active = new Map();
  for (const row of history) {
    const year = Number(String(row.season).slice(0, 4));
    if (!active.has(row.squad)) active.set(row.squad, new Set());
    active.get(row.squad).add(year);
    if (["League", "Cup"].includes(row.game_type)) {
      const key = `${row.season}:${row.squad}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  const rows = spec.datasets[dataset].filter(row => counts.has(`${row.season}:${row.squad}`) && !row.is_no_league);
  if (!rows.length) return null;
  const years = history.filter(row => ["League", "Cup"].includes(row.game_type)).map(row => Number(String(row.season).slice(0, 4))).filter(Number.isFinite);
  if (!years.length) return null;
  const firstYear = Math.min(...years);
  const lastYear = Math.max(...years);
  const seasonLabel = year => `${year}/${String((year + 1) % 100).padStart(2, "0")}`;
  const seasons = Array.from({ length: lastYear - firstYear + 1 }, (_, index) => seasonLabel(firstYear + index));
  const domain = [seasonLabel(firstYear - 1), ...seasons, seasonLabel(lastYear + 1)];
  const levels = [...new Set(rows.map(row => row.level).filter(level => level != null))].sort((left, right) => left - right);
  for (const squad of new Set(rows.map(row => row.squad))) {
    let segment = 0;
    let previous;
    for (const row of rows.filter(row => row.squad === squad).sort((left, right) => left.season.localeCompare(right.season))) {
      const year = Number(row.season.slice(0, 4));
      if (previous != null && Array.from({ length: Math.max(0, year - previous - 1) }, (_, index) => previous + index + 1).some(gap => !active.get(squad)?.has(gap))) segment += 1;
      row.line_segment = `${squad}-${segment}`;
      row.player_appearances = counts.get(`${row.season}:${row.squad}`);
      row.player_appearance_label = `${row.player_appearances} ${row.player_appearances === 1 ? "game" : "games"}`;
      previous = year;
    }
  }
  spec.datasets[dataset] = rows;
  for (const [key, values] of Object.entries(spec.datasets)) {
    if (values.some(row => "level" in row)) spec.datasets[key] = values.filter(row => row.level == null || levels.includes(row.level));
    for (const row of spec.datasets[key]) {
      if ("left_anchor" in row) Object.assign(row, { left_anchor: domain[0], right_anchor: domain.at(-1) });
    }
    if (values.some(row => "season_start" in row && "level_start" in row)) {
      const special = rows.filter(row => row.is_non_rfu && row.squad === "2nd").sort((left, right) => left.season.localeCompare(right.season));
      spec.datasets[key] = special.length ? [{ season_start: special[0].season, season_end: special.at(-1).season, level_start: Math.min(...special.map(row => row.level)), level_end: Math.max(...special.map(row => row.level)), label: "Non-RFU leagues" }] : [];
    }
  }
  function setDomains(value) {
    if (!value || typeof value !== "object") return;
    if (["season", "left_anchor", "right_anchor", "season_start", "season_end"].includes(value.field)) {
      value.sort = domain;
      value.scale = { ...value.scale, domain };
      if (value.field === "season") value.axis = { ...value.axis, values: seasons, title: null };
    }
    if (["level", "level_start", "level_end"].includes(value.field)) {
      value.sort = levels;
      value.scale = { ...value.scale, domain: levels };
    }
    Object.values(value).forEach(setDomains);
  }
  setDomains(spec.layer);
  delete spec.title;
  spec.width = { step: Math.min(70, Math.max(24, Math.floor(640 / domain.length))) };
  spec.height = { step: 44 };
  for (const layer of spec.layer) {
    const mark = layer.mark || {};
    const field = layer.encoding?.text?.field;
    if (mark.type === "point") mark.size = Math.min(mark.size || 500, 500);
    if (mark.type === "text") mark.fontSize = field === "rank_label" ? 12 : Math.min(mark.fontSize || 10, 10);
    if (field === "player_appearance_label") Object.assign(mark, { dy: 10, yOffset: 15 });
    if (mark.type === "line") layer.encoding.detail = { field: "line_segment", type: "nominal" };
  }
  for (const special of [false, true]) spec.layer.push({
    data: { name: dataset }, transform: [{ filter: `${special ? "" : "!"}(datum.is_non_rfu && datum.squad == '2nd')` }],
    mark: { type: "text", font: "PT Sans Narrow", fontSize: 10, fontWeight: "bold", dy: 14, ...(special ? { yOffset: 21 } : {}), color: "#414958", baseline: "top" },
    encoding: { x: { field: "season", type: "nominal", sort: domain, scale: { domain } }, y: { field: "level", type: "ordinal", sort: levels, scale: { domain: levels } }, text: { field: "player_appearance_label", type: "nominal" }, detail: { field: "squad", type: "nominal" } },
  });
  return spec;
}

export function leagueLegend(spec) {
  const shape = Object.values(spec.datasets).flat().find(row => String(row.marker_shape || "").startsWith("M"))?.marker_shape || "";
  const champion = ["#202946", "#7d96e8"].map(color => `<span class="league-history-legend-symbol"><svg viewBox="-8 -8 16 16"><g transform="scale(5)"><path d="${shape}" fill="${color}" stroke="${color === "#202946" ? "#7d96e8" : "#202946"}" stroke-width=".2"/></g></svg></span>`).join("");
  const squads = [["1st XV", "#202946", "#7d96e8"], ["2nd XV", "#7d96e8", "#202946"]].map(([label, fill, stroke]) => `<span class="performance-set-piece-legend-item"><span class="league-history-legend-symbol"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="${fill}" stroke="${stroke}"/></svg></span><span>${label}</span></span>`).join("");
  return `<div class="league-history-legend">${squads}<span class="performance-set-piece-legend-item">${champion}<span>League Champions</span></span><span class="performance-set-piece-legend-item"><span class="league-history-legend-position-text">3</span><span>League Position</span></span></div>`;
}

export async function chartImage(spec) {
  if (!spec) return "";
  const view = new window.vega.View(window.vega.parse(window.vegaLite.compile(spec).spec), { renderer: "none" }).initialize();
  try {
    await view.runAsync();
    const canvas = await view.toCanvas(2);
    return `<img class="report-chart-image" src="${canvas.toDataURL("image/png")}" alt="Player report chart">`;
  } finally {
    view.finalize();
  }
}
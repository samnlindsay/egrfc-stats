import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const chartSource = await readFile(new URL("../js/player-report-charts.js", import.meta.url), "utf8");
const chartModule = `data:text/javascript;base64,${Buffer.from(chartSource).toString("base64")}`;
const reportSource = (await readFile(new URL("../js/player-report-html.js", import.meta.url), "utf8"))
  .replace('"./player-report-charts.js"', JSON.stringify(chartModule));
const { buildPlayerReportData, playerReportBody } = await import(`data:text/javascript;base64,${Buffer.from(reportSource).toString("base64")}`);
const { reportTimelineSpec, reportLeagueSpec } = await import(chartModule);

function fixture(player = { name: "Mark Oliver", historicEstimatedAppearances: 120, historicEstimatedFirstXVAppearances: 12 }) {
  return {
    player,
    games: [{ game_id: "first", date: "2025-01-01", season: "2024/25", squad: "1st", game_type: "League", opposition: "Hove", result: "W", score_for: 20, score_against: 10, motm: `${player.name} and Other Player` }],
    appearances: [
      { player: player.name, game_id: "first", date: "2025-01-01", season: "2024/25", squad: "1st", position: "Hooker", number: 2, is_starter: true },
      { player: "Other Player", game_id: "first", date: "2025-01-01", season: "2024/25", squad: "1st", position: "Prop", number: 1, is_starter: true },
    ],
    sources: { season_scorers: [], lineouts: [], set_piece: [], scorers_stage_google: [], scorers_stage_pitchero: [], scorers_stage_rfu: [], player_appearances_stage_google: [], player_appearances_stage_pitchero: [], player_appearances_stage_rfu: [] },
  };
}

test("career totals retain historic estimates without inventing match records", () => {
  const model = buildPlayerReportData(fixture());
  const html = playerReportBody(model);
  assert.equal(model.history.length, 1);
  assert.match(html, /Appearances:<\/strong> 121\* \(1 starts\)/);
  assert.match(html, /Appearances:<\/strong> 13\* \(1 starts\)/);
  assert.match(html, /Historic\*/);
  assert.match(html, /\* estimated total/);
  for (const title of ["Career Summary", "Playing Record", "Season Summaries", "Most Common Teammates"]) assert.ok(html.includes(title));
  assert.equal(model.history[0].is_motm, true);
});

test("scorer selection prefers Google, retaining Pitchero provenance", () => {
  const input = fixture();
  const score = { player: "Mark Oliver", game_id: "first", date: "2025-01-01", squad: "1st" };
  input.sources.scorers_stage_google = [{ ...score, tries: 2, points: 10 }];
  input.sources.scorers_stage_pitchero = [{ ...score, tries: 1, points: 5 }];
  input.sources.player_appearances_stage_pitchero = [score];
  const model = buildPlayerReportData(input);
  assert.equal(model.history[0].tries, 2);
  assert.equal(model.history[0].points, 10);
  assert.equal(model.history[0].pitchero_source, true);
});

function teammateFixture(positions) {
  const input = fixture();
  const game = input.games[0];
  const mine = input.appearances[0];
  const other = input.appearances[1];
  input.games = positions.map((position, index) => ({ ...game, game_id: `game-${index}` }));
  input.appearances = positions.flatMap((position, index) => [
    { ...mine, game_id: `game-${index}`, position: position || "Hooker", is_starter: !!position },
    ...(index === 0 ? [{ ...other, game_id: `game-${index}`, position: "Hooker" }] : []),
  ]);
  return input;
}

test("position partners require five career starts, not appearances or shared games", () => {
  const input = teammateFixture(["Hooker", "Hooker", "Hooker", "Hooker", null, null]);
  const belowThreshold = playerReportBody(buildPlayerReportData(input));
  assert.doesNotMatch(belowThreshold, /<h3>Hooker Partners<\/h3>/);
  assert.doesNotMatch(belowThreshold, /<h3>Front Row Partners<\/h3>/);
  assert.match(belowThreshold, /<h3>Overall<\/h3>/);
  assert.match(belowThreshold, /Other Player/);
  input.appearances.find(row => row.game_id === "game-4" && row.player === input.player.name).is_starter = true;
  const atThreshold = playerReportBody(buildPlayerReportData(input));
  assert.match(atThreshold, /<h3>Hooker Partners<\/h3>/);
  assert.match(atThreshold, /<h3>Front Row Partners<\/h3>/);
});

test("group partners combine career starts across positions in that unit", () => {
  const input = teammateFixture(["Prop", "Prop", "Prop", "Hooker", "Hooker"]);
  const html = playerReportBody(buildPlayerReportData(input));
  assert.doesNotMatch(html, /<h3>(?:Prop|Hooker) Partners<\/h3>/);
  assert.match(html, /<h3>Front Row Partners<\/h3>/);
});

test("scrum success is limited to started games and majority tight-five careers", () => {
  const input = fixture();
  input.sources.set_piece = [
    { game_id: "first", season: "2024/25", squad: "1st", team: "EGRFC", scrums_won: 4, scrums_total: 5 },
    { game_id: "unplayed", season: "2024/25", squad: "1st", team: "EGRFC", scrums_won: 100, scrums_total: 100 },
  ];
  assert.match(playerReportBody(buildPlayerReportData(input)), /Team Scrum Success/);
  input.appearances[0].position = "Wing";
  assert.doesNotMatch(playerReportBody(buildPlayerReportData(input)), /Team Scrum Success/);
});

test("jumper section uses the ten-attempt threshold and no source data is mutated", () => {
  const input = fixture();
  input.sources.lineouts = Array.from({length: 9}, () => ({jumper: "Mark Oliver", won: true, season: "2024/25", area: "Front", thrower: "Other Player"}));
  assert.doesNotMatch(playerReportBody(buildPlayerReportData(input)), /<h3>Jumping<\/h3>/);
  input.sources.lineouts.push({...input.sources.lineouts[0]});
  const before = structuredClone(input);
  assert.match(playerReportBody(buildPlayerReportData(input)), /<h3>Jumping<\/h3>/);
  assert.deepEqual(input, before);
});

test("historic scorer alias distinguishes Sam Lindsay from Sam Lindsay-McCall", () => {
  const input = fixture({name: "Sam Lindsay"});
  input.sources.scorers_stage_pitchero = [{player: "S Lindsay", game_id: "first", season: "2019/20", tries: 1}];
  assert.equal(buildPlayerReportData(input).history[0].tries, 1);
  input.player.name = "Sam Lindsay-McCall";
  input.appearances[0].player = "Sam Lindsay-McCall";
  assert.equal(buildPlayerReportData(input).history[0].tries, 0);
});

test("report timeline uses Python print label offsets without mutating the site spec", () => {
  const original = {
    datasets: { events: [
      {player: "Mark Oliver", event_key: "debut", row_type: "event", date: "2025-01-01", event_sort: 1, detail: "First game"},
      {player: "Other Player", event_key: "debut", row_type: "event", date: "2025-01-01", event_sort: 1, detail: "Other game"},
    ] },
    layer: Array.from({length: 6}, () => ({mark: {type: "text"}, encoding: {}})),
  };
  const before = structuredClone(original);
  const printed = reportTimelineSpec(original, "Mark Oliver");
  assert.equal(printed.width, 900);
  assert.equal(printed.layer.length, 8);
  assert.equal(printed.datasets.events.length, 1);
  assert.equal(printed.datasets.events[0].milestone_y_offset, 7);
  assert.deepEqual(original, before);
});

test("league history is player-specific and breaks lines across inactive seasons", () => {
  const original = {
    datasets: { history: [
      {season: "2020/21", squad: "1st", level: 8, rank: 3},
      {season: "2022/23", squad: "1st", level: 8, rank: 2},
      {season: "2022/23", squad: "2nd", level: 9, rank: 1},
    ] },
    layer: [{mark: {type: "line"}, encoding: {x: {field: "season"}, y: {field: "level"}}}],
  };
  const history = ["2020/21", "2022/23"].map(season => ({season, squad: "1st", game_type: "League"}));
  const printed = reportLeagueSpec(original, history);
  assert.deepEqual(printed.datasets.history.map(row => row.line_segment), ["1st-0", "1st-1"]);
  assert.deepEqual(printed.layer[0].encoding.y.scale.domain, [8]);
  assert.equal(original.datasets.history.length, 3);
});
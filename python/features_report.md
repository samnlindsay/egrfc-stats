# EGRFC Website Feature Coverage Report

This report maps your feature vision in `python/features.md` against the current implementation, data sources, and generated materials in this repository.

## 1) Current Site Surface (what the live `index.html` exposes)

Current tabs/dropdowns in `index.html` and `js/charts.js`:

- **Results**
  - Vega-Lite JSON: `data/charts/results.json`
- **Team Sheets**
  - Vega-Lite JSON: `data/charts/team_sheets.json`
- **Player Stats**
  - Appearances: `data/charts/player_appearances.json`
  - Captains: `data/charts/captains.json`
  - Scorers: `data/charts/point_scorers.json`
  - Cards: `data/charts/cards.json`
- **Set Piece**
  - Lineout: `data/charts/lineout_success.json`
  - Scrum: `data/charts/scrum_success.json`
- **League**
  - League Results (HTML iframe dispatch): `Charts/league/results.html`
  - League table (paired under results): `Charts/league/table.html`
  - 1st XV League Squad Analysis (HTML iframe): `Charts/league/squad_analysis_1s.html`

Filter model is shared across tabs (squad, competition, season, position, include bench), with tab-specific enable/disable behavior in `js/filters.js`.

---

## 2) Data Sources and What They Currently Feed

## Google Sheets (`python/data.py` via `DataExtractor`)

From worksheets like `1st XV Players`, `2nd XV Players`, `1st XV Lineouts`, `2nd XV Lineouts`, set-piece sheets:

- `games` table (date/season/squad/competition/home-away/PF/PA/result/captain/VC)
- `player_appearances` table (player, shirt number, position, unit, starter/captain/VC)
- `lineouts` table (numbers/call type/setup/movement/area/hooker/jumper/won)
- `set_piece_stats` table (team, set piece, won/lost/total)

These power most non-league tabs via `python/update.py` -> `data/charts/*.json`.

## Pitchero (`extract_pitchero_stats` in `python/data.py`)

Fetched from team statistics pages, normalized to:

- season, squad, player_join, appearances (`A`), event (`T/Con/PK/DG/YC/RC`), count

Used in:

- point scorers chart
- cards chart
- historical augmentation for appearances (especially older seasons)

Cache material:

- `data/pitchero_stats_cache.json`
- `data/pitchero.json` (historical/source material)

## England Rugby (`python/league_data.py`)

Scrapes:

- league tables (`fetch_league_table`) -> `data/league_table_*_squad_*.csv`
- match lists/IDs (`fetch_match_ids`, `fetch_matches_from_results_page`)
- match details (`fetch_match_data`)

Consolidated outputs:

- `data/matches.json`
- `data/matches_summary.csv`
- optional backups in `data/match_data/*.json`

Rendered league assets (`python/league_stats.py`):

- `Charts/league/results_1s_combined.html`
- `Charts/league/results_2s_combined.html`
- `Charts/league/table_1s_combined.html`
- `Charts/league/table_2s_combined.html`
- dispatch files: `Charts/league/results.html`, `Charts/league/table.html`
- analysis: `Charts/league/squad_analysis_1s.html`

---

## 3) Feature Vision Coverage (Available / Partial / Missing)

### Tabular data

- **League tables (each squad/season)**: **Available (league-only seasons)**
  - Data exists as CSV by squad/season where scraped.
  - UI currently shows one combined League Results page with squad+season filter behavior.
- **Season results W/L/D split H/A and by game type**: **Partial**
  - Results chart exists and is filterable by squad/season/game type.
  - Dedicated explicit table view for W/L/D + home/away summary is not yet exposed.
- **Squad metrics (players per squad each season, by unit/position)**: **Partial**
  - League squad analysis contains squad-size/retention metrics (league context).
  - A dedicated non-league tabular squad-stats table is not in the main UI.
- **Player profiles page**: **Partial/Legacy**
  - `players.html` exists with photo + basic profile table.
  - Not integrated into `index.html` navigation shell.
  - Sponsor lookup currently uses wrong JSON shape (expects flat map, file is season-keyed), so sponsor display is likely inconsistent.

### Graphical data

- **League position over time (both squads)**: **Missing (good candidate)**
  - Raw table CSVs exist for required seasons/squads.
  - No current chart in main UI.
- **League results grid (season/squad)**: **Available**
  - Active in League Results page with unified routing.
- **League squad analysis (retention/squad size, filters)**: **Available for 1st XV; partial overall**
  - `squad_analysis_1s.html` exists and responds to season param.
  - Equivalent 2nd XV analysis is not currently exposed.
- **Squad-level results over time**: **Available**
  - `data/charts/results.json` + filters in main app.
- **Player appearances (filterable)**: **Available**
  - `data/charts/player_appearances.json` + filters.
- **Team sheets with player highlighting**: **Available**
  - `data/charts/team_sheets.json` + filters.
- **Video analysis set piece (per game + seasonal averages)**: **Partial**
  - Lineout and scrum success charts are present.
  - Broader “video analysis module” not yet a first-class section in main nav.
- **Red zone efficiency**: **Missing (data capture likely not in active schema/charts yet)**
- **Deep lineout analysis (area/thrower/jumper/call)**: **Partial**
  - Source fields exist in lineouts data; main UI currently exposes summary views.

### UI features

- **Landing page with section links/headline stats**: **Missing in current `index.html` pattern**
- **Bespoke filters per data view**: **Partial**
  - You already have strong tab-specific enable/disable logic.
  - Could be tightened further to hide irrelevant controls per view.
- **Intuitive URLs**: **Partial**
  - League pages already consume query params (`season`, `squad`, `competition`).
  - Other sections still stateful in tab/UI only.
- **Responsive design + brand consistency**: **Available/Partial**
  - Strong CSS system already in place; some legacy pages are stylistically separate.

---

## 4) Recommended Site Layout (pragmatic, fits current framework)

## Proposed information architecture

1. **Home**
   - Headline cards (current season W/L/D, league position, top appearances, top scorers)
   - Links into each section with pre-filtered URLs

2. **Season Hub** (single route pattern: season + squad)
   - Results timeline
   - Team sheets
   - Set piece summaries
   - Season summary table (W/L/D, home/away split)

3. **League Hub**
   - Results grid + table (already done)
   - League position over time (new)
   - League squad analysis (1st now, add 2nd if data quality supports)

4. **Players**
   - Player list + profile panel
   - Sponsor/headshot/debut + key stats
   - Optional embedded per-player trend charts

5. **Performance (Video Analysis)**
   - Set piece deep dive
   - Red zone efficiency (when dataset is ready)
   - Drill-down by season/squad/game type/opposition

## URL approach (works with your current pattern)

- Keep `index.html` as shell, use query params for state:
  - `?view=results&squad=1st&season=2025/26&competition=League`
  - `?view=league-results&squad=2nd&season=2025/26`
  - `?view=player&name=Sam%20Lindsay-McCall`
- Extend `js/navigation.js` + `js/charts.js` to hydrate filters/state from URL on load.

---

## 5) Implementation Notes: adding new charts/tables/pages cleanly

## A) Add a new Vega-Lite chart to main app

1. Generate output JSON from Python into `data/charts/<new_chart>.json`.
2. Add file in `js/config.js` under `CONFIG.dataFiles`.
3. Load it in `js/main.js` Promise list.
4. Add nav item in `index.html` with `data-chart-type="..."`.
5. Add render branch in `js/charts.js`.
6. Ensure source fields align with filter system if needed:
   - `squad`, `season`, `game_type`, `position`, `is_starter`.

## B) Add a new League HTML artifact (iframe style)

1. Generate HTML under `Charts/league/` from `python/league_stats.py`.
2. Ensure embed options and CSS patching are applied (`hack_params_css`, patch helper).
3. Route from `js/charts.js` using query params for season/squad.
4. Use `createAutoHeightLeagueIframe(...)` for consistent sizing behavior.

## C) Add a new table-first page

1. Build data source CSV/JSON in `data/`.
2. Render either:
   - direct HTML table (static), or
   - Vega-Lite text/table-style spec for unified filtering.
3. Keep column naming consistent for cross-filtering.

---

## 6) Placeholder Specs for unclear/new features

Use the following placeholders for items not yet fully defined.

### Placeholder: Red Zone Efficiency

- **Business definition needed**:
  - what counts as a red-zone entry?
  - denominator by possession, entries, or visits?
  - include penalties only, tries only, total points?
- **Minimum dataset contract**:
  - `game_id`, `date`, `season`, `squad`, `game_type`, `opposition`, `entries`, `points_from_entries`, `opp_entries`, `opp_points_from_entries`
- **Suggested outputs**:
  - per-game comparison chart
  - season rolling average chart
  - summary table card on Home/Season Hub

### Placeholder: League Position Over Time (Both Squads)

- **Dataset inputs available now**:
  - `data/league_table_*_squad_*.csv`
- **Additional decision needed**:
  - weekly snapshots vs end-of-season points only
- **Suggested first deliverable**:
  - end-of-season league finish by squad over seasons (line chart)

### Placeholder: Player Profile Advanced Panel

- **Need confirmed stats list**:
  - starts vs bench by season?
  - lineout personal metrics for specific positions?
- **Suggested data contract**:
  - one row per player-season with role/squad/appearance and key KPIs
- **Suggested route**:
  - `?view=player&name=<player>` in main shell rather than standalone `players.html`

---

## 7) Suggested Build Order (low-risk sequence)

1. **Unify navigation/state via URL params** in current shell.
2. **Add Season summary table view** (W/L/D, H/A, competition splits).
3. **Integrate player profiles into main shell** and fix sponsor map by season.
4. **Add league position-over-time chart** from existing table CSVs.
5. **Define and implement red-zone dataset + charts**.

---

## 8) Quick Wins found during audit

- Sponsor data in `data/sponsors.json` is season-keyed, while `players.html` currently looks up by player directly; aligning this will immediately improve profile fidelity.
- Existing filter framework is strong; adding URL hydration will make views shareable and directly support your “intuitive URLs” goal.
- You already have enough league artifacts to support a polished League Hub with minimal new scraping work.

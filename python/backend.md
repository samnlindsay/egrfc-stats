# EGRFC Canonical Backend

This backend is the canonical data model for powering website tables and charts.

It is designed to support both:
- live querying (DuckDB SQL), and
- static exports (JSON for frontend and static chart generation).

Google Sheets remains canonical for modern seasons. The builder supplements historic game + appearance rows by scraping Pitchero fixture and lineup pages for pre-2021 seasons (currently 2016/17 to 2019/20).

Current operating mode is cache-first for Pitchero-derived data:
- normal builds read local Pitchero cache files only,
- Pitchero web scraping is only run when `--refresh-pitchero` is explicitly provided.

## Build

Run from project root:

```bash
./env/bin/python python/build_backend.py
```

Optional flags:

```bash
./env/bin/python python/build_backend.py --refresh-pitchero
./env/bin/python python/build_backend.py --no-export
```

## Update runbook

### Standard database update (no Pitchero web)

```bash
./env/bin/python python/build_backend.py
```

This reads:
- Google Sheets (games, appearances, lineouts, set piece, 25/26 scorers)
- local cache `data/pitchero_stats_cache.json`
- local cache `data/pitchero_historic_team_sheets_cache.json`

### Explicit Pitchero refresh (only when required)

```bash
./env/bin/python python/build_backend.py --refresh-pitchero
```

This refreshes both Pitchero-derived caches from the web:
- season stats cache (`pitchero_stats_cache.json`)
- historic fixtures/lineups cache (`pitchero_historic_team_sheets_cache.json`)

### Chart regeneration from database

```bash
./env/bin/python python/update.py --backend-mode canonical
```

This should be run after the backend build to regenerate chart JSON from canonical tables/views.

Outputs:
- Database: `data/egrfc_backend.duckdb`
- Exports: `data/backend/*.json`

## Live backend table contract

This section is the living source of truth for backend datasets.
For each dataset, it captures:
- grain
- derivation
- key contents
- downstream usage

## Naming contract

Backend table naming is intentionally layered:
- Canonical frontend-facing entities keep stable business names (for example: `games`, `player_appearances`, `season_scorers`, `players`).
- Raw ingestion/staging tables must end with `_raw`.
- Cleaned/sanitized staging tables must end with `_clean`.
- Lookup/override tables must start with `ref_`.

This keeps extraction, cleanup, and canonical modeling clearly separated while preserving stable table names for downstream consumers.

### Pitchero reference tables

### `ref_pitchero_player_name_overrides`
- Grain: one row per explicit Pitchero-name override.
- Derived from: backend static override map.
- Key contents: `pitchero_name`, `canonical_name`.
- Downstream: name standardization for Pitchero player records.

### `ref_pitchero_opposition_overrides`
- Grain: one row per normalized opposition key override.
- Derived from: backend static opposition canonicalization map.
- Key contents: `opposition_key`, `canonical_opposition`.
- Downstream: opposition standardization in Pitchero game records.

### `ref_pitchero_match_url_overrides`
- Grain: one row per manual game URL override.
- Derived from: backend manual URL override map.
- Key contents: `game_id`, `pitchero_match_url`.
- Downstream: reconciliation/supplemental enrichment and traceability.

Pitchero raw/clean staging datasets are now in-memory build intermediates only. They are not persisted as DuckDB tables or exported datasets.

### Core canonical tables

### `games`
- Grain: one row per EGRFC game.
- Derived from: Google Sheets game sheets + historic Pitchero fixtures/results.
- Key contents: game metadata, scoreline, result, leadership fields.
- Downstream: joins for most other tables, season summary enrichment, chart generation.

### `player_appearances`
- Grain: one row per player per game.
- Derived from: canonical team sheets + historic Pitchero lineups (+ manual corrections where present).
- Key contents: shirt number, position/unit, starter/captain flags, season and game type.
- Downstream: players table, profile enrichment, squad enrichment, season summary appearance leaders.

### `lineouts`
- Grain: one row per attacking lineout event.
- Derived from: lineout coding sheets with normalization/mapping.
- Key contents: call/call type, area, setup flags, thrower/jumper, outcome.
- Downstream: lineout charts and lineout-related analysis.

### `set_piece`
- Grain: one row per team per game.
- Derived from: set piece sheets plus red zone inputs when present.
- Key contents: lineout/scrum totals and rates, 22m entry efficiency metrics.
- Downstream: set piece charts and season summary enrichment.

### `season_scorers`
- Grain: one row per squad/season/player.
- Derived from: match-level scorer payloads attached to canonical `games` (including 25/26 scorer-sheet payload integration).
- Key contents: tries, conversions, penalties, drop goals, points, source tag.
- Downstream: player profiles, season summary leaders, scorer charts.

### `players`
- Grain: one row per player.
- Derived from: appearances, games, lineouts, scorers.
- Key contents: player bio/profile metadata and career aggregates.
- Downstream: profile UIs and compatibility views.

### RFU canonical tables

### `games_rfu`
- Grain: one row per RFU match.
- Derived from: consolidated RFU scrape in data/matches.json.
- Key contents: league, teams, scoreline, walkover and lineup-availability flags.
- Downstream: RFU views for squad size and retention context charts.

### `player_appearances_rfu`
- Grain: one row per player per RFU match.
- Derived from: RFU lineups linked to RFU match register.
- Key contents: shirt number, derived position/unit, starter flag, previous match continuity marker.
- Downstream: RFU continuity and squad-size views.

### Frontend enriched tables

### `squad_stats_enriched`
- Grain: one row per season/gameTypeMode/squad/unit.
- Derived from: appearances filtered by game type mode.
- Key contents: playerCounts map and playersUsed totals for Total/Forwards/Backs.
- Downstream: squad stats page squad-size cards/table and threshold filtering.

### `squad_position_profiles_enriched`
- Grain: one row per season/gameTypeMode/squad/position.
- Derived from: starter appearances mapped to canonical positions.
- Key contents: playerCounts map and playersUsed by position.
- Downstream: squad stats page position cards and minimum-appearance filtering.

### `squad_continuity_enriched`
- Grain: one row per season/gameTypeMode/squad/unit.
- Derived from: match-to-match retained starters in appearances.
- Key contents: retained average and contributing gamePairs.
- Downstream: squad stats continuity cards and trend charts.

### `season_summary_enriched`
- Grain: one row per season/gameTypeMode/squad.
- Derived from: games + appearances + season_scorers + set_piece.
- Key contents: W/L/D totals, home/away and overall averages, tied top-scorer arrays, top appearances, set-piece seasonal means.
- Downstream: season summary page and performance stats red-zone line chart input.

### `squad_stats_with_thresholds_enriched`
- Grain: one row per season/gameTypeMode/squad/unit/minimumAppearances.
- Derived from: appearances filtered by unit and game type, with distinct player count grouped by appearance threshold (0-20).
- Key contents: minimumAppearances, playerCount, totalPlayed.
- Downstream: squad stats page appearance threshold filtering (eliminated need for client-side recalculation).
- **Status:** ✅ Implemented & exported (4,914 rows)

### `player_profiles_canonical`
- Grain: one row per player (deduplicated across squads).
- Derived from: canonical players + appearances + games + season_scorers, then deduplicated when a player appears in both 1st/2nd XV by selecting the record with most total appearances.
- Key contents: full profile-card payload (name, squad, position, starts/appearances, season counters, debut labels, scoring objects, otherPositions array, active status, lastAppearanceDate).
- Downstream: player profiles page canonical data source.
- **Status:** ✅ Implemented & exported (283 canonical records)

## Derived views

### Core views
- `v_season_results`: season/squad/game type result aggregates.

### RFU views
- `v_rfu_team_games`: team-perspective rows from each RFU match.
- `v_rfu_squad_size`: player usage totals by unit and team.
- `v_rfu_match_retention`: per-match retained-starter counts by unit.
- `v_rfu_average_retention`: averaged retained-starter counts by season/team/unit.
- `v_rfu_lineup_coverage`: lineup coverage summary by season/team.

## Downstream consumer map

- player-profiles page: data/backend/player_profiles_canonical.json (active; dedupe + profile payload owned by backend).
- squad-stats page: data/backend/squad_stats_enriched.json, data/backend/squad_position_profiles_enriched.json, data/backend/squad_continuity_enriched.json (active).
- squad-stats page: data/backend/squad_stats_with_thresholds_enriched.json (active for threshold filtering; eliminates client-side recalculation).
- season-summary page: data/backend/season_summary_enriched.json (active).
- performance-stats red-zone chart: data/backend/season_summary_enriched.json (1st XV, All games rows) (active).
- database explorer page: all exported tables and views in data/backend/*.json.

## Maintenance checklist for this live document

- If a table/view is added or removed in backend.py reset_schema/create_views, update this file in the same change.
- If export_tables adds/removes exported datasets, update downstream consumer map and dataset sections.
- If a frontend page switches data source, update the relevant downstream bullets.
- Keep gameTypeMode semantics aligned across enriched tables: All games, League + Cup, League only.

## Maintenance principles

- Keep extraction and modeling separate.
- Keep table names stable so frontend queries stay stable.
- Add new metrics as nullable columns first, then backfill.
- Preserve existing keys (squad, date, season, player) across related tables.
- **JSON columns deserialization**: Enriched tables may contain nested JSON objects/arrays stored as TEXT. Add any new JSON columns to `json_columns_map` in `export_tables()` to ensure they're properly deserialized during export. This keeps the exported JSON clean and avoids double-serialization in the frontend.
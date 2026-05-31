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

## Issue 3 Architecture Contract

To make data flow explicit while preserving auditability, the backend now adopts a three-layer model:

1. `stg_*` tables
- Source-native staging per upstream system (`google`, `pitchero`, `rfu`).
- Keep ingestion metadata and raw payload so records can be audited/replayed.

2. `int_*` tables
- Intermediate candidate + resolution layer for source overlap/conflicts.
- Includes source-to-canonical key mapping for deterministic incremental rebuilds.

3. Canonical tables
- Stable contract tables used by exports/charts: `games`, `players`, `player_appearances`, `lineouts`.
- Explicit PK/FK relationships and uniqueness constraints.

Reference SQL contract: `python/schema_contract.sql`

### Canonical relationship rules

- `games.game_id` is the join anchor for match-grain data.
- `player_appearances.game_id` must reference `games.game_id`.
- `player_appearances.player_id` must reference `players.player_id`.
- `lineouts.game_id` must reference `games.game_id`.
- Lineouts and appearances should never be loaded directly from staging into exports.
	They must flow through intermediate resolution + canonical keys.

### Staging tables

Staging tables hold source-system-native records after basic normalization (type casting, date parsing, opposition canonicalization) but before any cross-source deduplication or conflict resolution. One set per upstream system. They are persisted in the database for auditability and are exported as part of `data/backend/` for diagnostic use.

### `games_stage_google`
- Grain: one row per game record from Google Sheets.
- Derived from: Google Sheets game tabs (`1st XV Players`, `2nd XV Players`) via `DataExtractor`.
- Key contents: `game_id`, `squad`, `date`, `season`, `opposition`, `pf`, `pa`, `result`, leadership fields, scorer payloads.
- Notes: Google Sheets is the canonical source for all seasons from 2021/22 onwards. Records here take precedence over Pitchero and RFU in conflict resolution.

### `games_stage_pitchero`
- Grain: one row per game record from the Pitchero cache.
- Derived from: `data/pitchero_historic_team_sheets_cache.json` via `_load_pitchero_historic_cache()`.
- Key contents: `game_id`, `squad`, `date`, `season`, `opposition`, `pf`, `pa`, `result`, `pitchero_match_url`, scorer payloads.
- Notes: Primary source for historic seasons (`PITCHERO_PRIMARY_SOURCE_SEASONS`). Rows with null scores (walkovers, scrape failures, future fixtures) are dropped before canonical deduplication.

### `games_stage_rfu`
- Grain: one row per game record from the RFU results dataset.
- Derived from: `data/matches.json` and RFU CSV exports via `_load_rfu_historic_results_csvs()`.
- Key contents: `game_id`, `squad`, `date`, `season`, `opposition`, `pf`, `pa`, `result`, `home_away`.
- Notes: Lowest-priority source (`SOURCE_PRECEDENCE["rfu"] = 2`). Used mainly to fill gaps (scores, home/away) where neither Google nor Pitchero has a record.

### `player_appearances_stage_google`, `player_appearances_stage_pitchero`, `player_appearances_stage_rfu`
- Grain: one row per player per game per source system.
- Derived from: equivalent Google Sheets appearance tabs / Pitchero lineup cache / RFU lineup data.
- Key contents: `game_id`, `player`, `squad`, `shirt_number`, `position`, `unit`, `is_starter`, `is_captain`.
- Notes: Staging appearance tables are not currently used in the intermediate resolution layer — they feed `_build_player_appearances()` directly. Intermediate resolution for appearances is a planned future phase.

### `scorers_stage_google`, `scorers_stage_pitchero`, `scorers_stage_rfu`
- Grain: one row per scorer event per game per source system.
- Derived from: scorer tabs in Google Sheets / Pitchero scorer cache / RFU scorer data.
- Key contents: `game_id`, `squad`, `date`, `player`, `score_type`, `count`.
- Notes: Merged into `scorers_staged_all` before `_build_season_scorers()`.

---

### Intermediate tables

Intermediate tables sit between staging and canonical. They make source-overlap and conflict resolution explicit and auditable. Unlike staging tables (which preserve raw source payloads), intermediate tables represent active pipeline decisions — which source wins, and why.

### `int_game_candidates`
- Grain: one row per source-system candidate for each match. A single real-world fixture can have up to three rows here (one from Google, one from Pitchero, one from RFU).
- Derived from: `_build_int_game_candidates()` — concatenates the three `games_stage_*` tables, assigns `match_group_key` (= canonical `game_id` based on date + squad + opposition_club), ranks by `SOURCE_PRECEDENCE`, and computes per-row conflict flags by comparing each row against the highest-priority sibling in the same group.
- Key contents:
  - `candidate_id` — surrogate PK.
  - `source_system` — `"google"`, `"pitchero"`, or `"rfu"`.
  - `source_rank` — `0` (google) / `1` (pitchero) / `2` (rfu); lower wins.
  - `match_group_key` — shared key linking candidates for the same fixture.
  - `has_score_conflict` — `TRUE` if this candidate's `pf`/`pa` differ from the best-ranked sibling.
  - `has_result_conflict` — `TRUE` if `result` differs from best-ranked sibling.
  - `has_opposition_conflict` — `TRUE` if `opposition_club` differs from best-ranked sibling.
- Downstream: feeds `int_games_resolved`; useful for investigating data discrepancies between sources.
- Notes: Conflict flags are relative to the **highest-priority source** in the group, not a consensus. A Pitchero row flagged `has_score_conflict` means it disagrees with the Google record for that fixture.

### `int_games_resolved`
- Grain: one row per real-world fixture (one winner per `match_group_key`).
- Derived from: `_build_int_games_resolved()` — selects the candidate with the lowest `source_rank` per group, then aggregates conflict summary across all candidates in the group.
- Key contents:
  - `resolved_id` — surrogate PK.
  - `match_group_key` — same value as in `int_game_candidates`, unique here.
  - `winning_candidate_id` — FK to `int_game_candidates.candidate_id`.
  - `source_system` — source system of the winning candidate.
  - All match payload fields copied from the winning candidate.
  - `conflict_count` — number of distinct conflict types (`has_score`, `has_result`, `has_opposition`) that fired for any candidate in this group.
  - `has_any_score_conflict`, `has_any_result_conflict`, `has_any_opposition_conflict` — TRUE if any non-winning candidate disagreed with the winner on that field.
  - `source_count` — how many source systems contributed a candidate for this fixture.
- Downstream: `_build_games()` joins against this table to annotate each canonical game row with `_resolved_source`, `_resolved_winning_candidate_id`, and `_resolved_conflict_count`. These `_resolved_*` columns are not exported to the frontend — they are for internal audit and debugging only.
- Notes: The canonical `games` table still uses its own deduplication logic (quality scoring, appearance-count linkage, source priority). `int_games_resolved` currently supplements rather than replaces that logic. The intent is to incrementally shift deduplication decisions here so that `_build_games()` can simply consume the resolved winner rather than recomputing it.

---

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

### `squad_continuity_enriched`
- Grain: one row per season/gameTypeMode/squad/unit.
- Derived from: match-to-match retained starters in appearances.
- Key contents: retained average and contributing gamePairs.
- Downstream: squad stats continuity cards and trend charts.

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
- squad-stats page: data/backend/squad_stats_enriched.json, data/backend/squad_continuity_enriched.json (active).
- squad-stats page: data/backend/squad_stats_with_thresholds_enriched.json (active for threshold filtering; eliminates client-side recalculation).
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
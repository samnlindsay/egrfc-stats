# EGRFC Canonical Backend

This backend is the canonical data model for powering website tables and charts.

It is designed to support both:
- live querying (DuckDB SQL), and
- static exports (JSON/Parquet for frontend or static chart generation).

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
- Exports: `data/backend/*.json` and `data/backend/*.parquet`

## Canonical tables

### `games`
One row per EGRFC game.

Includes:
- Google Sheets games (canonical from 2021/22 onwards)
- Historic Pitchero fixture+result rows (2016/17 to 2019/20)

Key columns:
- `game_id`, `squad`, `date`, `season`, `competition`, `game_type`, `opposition`, `home_away`
- `score_for`, `score_against`, `result`
- `captain`, `vice_captain_1`, `vice_captain_2`

### `player_appearances`
One row per player per game appearance.

Includes:
- Google Sheets team sheets (canonical from 2021/22 onwards)
- Historic Pitchero lineup scrape (2016/17 to 2019/20)

Key columns:
- `squad`, `date`, `player`, `number`, `position`, `unit`
- `is_captain`, `is_vice_captain`, `is_starter`
- `game_id`, `season`, `game_type`

### `lineouts`
One row per attacking lineout event.

Key columns:
- `squad`, `date`, `seq_id`
- `numbers`, `call`, `call_type`, `dummy`, `area`
- `drive`, `crusaders`, `transfer`, `flyby`
- `thrower`, `jumper`, `won`
- `game_id`, `season`, `opposition`

### `set_piece`
One row per game/team with lineout+scrum summary.

Key columns:
- `squad`, `date`, `team`
- `lineouts_won`, `lineouts_total`, `lineouts_success_rate`
- `scrums_won`, `scrums_total`, `scrums_success_rate`
- `entries_22m`, `points_per_22m_entry`, `tries_per_22m_entry`
- `game_id`, `season`, `opposition`

### `season_scorers`
One row per player per season scoring summary.

Sources:
- `google_2526` for 2025/26 scorer sheet
- `pitchero` for historical seasons

Key columns:
- `squad`, `season`, `player`
- `tries`, `conversions`, `penalties`, `drop_goals`, `points`, `source`

### `players`
One summary row per player profile.

Key columns:
- `name`, `short_name`, `position`, `squad`
- `first_appearance_date`, `first_appearance_squad`, `first_appearance_opposition`
- `photo_url`, `sponsor`
- `total_appearances`, `total_starts`, `total_captaincies`, `total_vc_appointments`
- `total_lineouts_jumped`, `lineouts_won_as_jumper`, `career_points`

### `pitchero_appearance_reconciliation`
Season-level QA reconciliation between Pitchero aggregate appearances (`A`) and
scraped lineup-derived appearances for historic supplemented seasons.

Key columns:
- `squad`, `season`, `player_join`, `player`
- `pitchero_appearances`, `scraped_appearances`, `delta`, `abs_delta`
- `status`, `fix_type`

### `pitchero_appearance_backfill`
Safe season-count backfill rows where Pitchero shows more appearances than were
recovered from scraped lineups.

Key columns:
- `squad`, `season`, `player_join`, `player`
- `missing_appearances`, `applied_fix`

## Query views

Generated views for frontend consumption:
- `v_season_results`
- `v_set_piece_summary`
- `v_lineout_summary`
- `v_player_profiles`
- `v_pitchero_appearance_mismatches`
- `v_season_player_appearances_reconciled`
- `v_player_appearance_discrepancy_summary`

`v_season_player_appearances_reconciled` applies a season-level fix by using
Pitchero `A` as the effective count when scraped lineup data is under-counted
(`delta > 0`).

`v_player_appearance_discrepancy_summary` aggregates mismatch risk per player
across historic supplemented seasons so large net/absolute deltas are visible
in one place.

## Maintenance principles

- Keep extraction and modeling separate.
- Keep table names stable so frontend queries stay stable.
- Add new metrics as nullable columns first, then backfill.
- Preserve existing keys (`squad`, `date`, `season`, `player`) across tables.
# egrfc-stats

## Canonical backend build

This repo now includes a canonical DuckDB backend pipeline focused on stable, queryable tables for frontend features.

Build it from project root:

```bash
./env/bin/python python/build_backend.py
```

Default behavior is cache-first:
- Uses Google Sheets for current operational data.
- Uses local Pitchero cache files for historic/season Pitchero data.
- Does not scrape Pitchero web pages unless explicitly requested.
If the default DB file is locked by another process (for example an open notebook), either close that process or build to an alternate DB path:

```bash
./env/bin/python python/build_backend.py --db-path data/egrfc_backend_alt.duckdb
```

If you intentionally want to refresh Pitchero-derived caches from the web:

```bash
./env/bin/python python/build_backend.py --refresh-pitchero
```

## DuckDB lock-safe workflow (chat + CLI + notebooks)

DuckDB allows a single writer process per database file. To avoid lock conflicts:

- Use notebooks/read-only exploration against `data/egrfc_backend.duckdb` (or fallback `data/egrfc_backend_alt.duckdb`) in read-only mode.
- When the main DB is locked by an active notebook/chat process, build to the alternate file:

```bash
./env/bin/python python/build_backend.py --db-path data/egrfc_backend_alt.duckdb
```

- Point ad-hoc exploration to the same file you most recently built.

Recommended pattern:
1) Keep long-running notebooks read-only.
2) Run writes/builds in short-lived CLI commands.
3) If a lock appears, rebuild to `data/egrfc_backend_alt.duckdb` and continue reading from that file.

Main outputs:
- `data/egrfc_backend.duckdb`$$
- `data/backend/*.json`

Notable frontend-facing backend exports:
- `data/backend/player_profiles_canonical.json` (Player Profiles page)
- `data/backend/player_awards.json` (Player Stats Awards section and Data Explorer)

Backend schema and usage notes:
- `python/backend.md`

## Operational workflow

### 1) Regular update (single entry point)

```bash
./env/bin/python python/update.py --backend-mode canonical
```

This one command now runs, in order:
- RFU refresh for the current season (all active squads from League History) into `data/matches.json`
- canonical backend build/export
- headshot sync/recrop
- chart generation and frontend league table JSON export (current season refresh only; existing historic seasons are preserved)

Default behavior is intentionally incremental: once historic seasons are complete, routine updates only attempt current-season RFU league results/team sheets/tables.

### 2) RFU refresh options (still via update.py)

Refresh all seasons/squads from RFU before backend build:

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-all
```

Use this when you want to refresh historic seasons as well as the current season.

Refresh one season only:

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-season 2025/26
```

Refresh one squad only:

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-squad 1
```

Refresh one season+squad:

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-season 2025/26 --rfu-squad 1
```

Retry played fixtures missing lineups (improves league-wide squad-size/returners where RFU lineups exist):

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-all-teams
```

Skip RFU refresh and build from existing `data/matches.json`:

```bash
./env/bin/python python/update.py --backend-mode canonical --skip-rfu-refresh
```

This skips RFU league results/team-sheet scraping and skips RFU league table scraping for that run.

Use an alternate consolidated RFU matches file:

```bash
./env/bin/python python/update.py --backend-mode canonical --rfu-matches-file data/matches_alt.json
```

### 3) Optional: refresh Pitchero caches only when needed

```bash
./env/bin/python python/update.py --backend-mode canonical --refresh-pitchero
```

Use this only when intentionally changing Pitchero-derived inputs (or after scraper changes).

### 4) Optional: run headshot sync only

```bash
sync-headshots --write
```

Use this for quick headshot-only maintenance without a full data/chart rebuild.

### update.py CLI reference

```bash
./env/bin/python python/update.py --help
```

Key options:
- `--refresh-pitchero`: force Pitchero web cache refresh
- `--skip-rfu-refresh`: do not scrape RFU before build
- `--rfu-all`: refresh all League History seasons/squads
- `--rfu-season`: constrain RFU refresh to one season (`YYYY/YY` or `YYYY-YYYY`)
- `--rfu-squad`: constrain RFU refresh to one squad number
- `--rfu-all-teams`: re-fetch played fixtures missing one/both lineups
- `--rfu-matches-file`: path to consolidated RFU match JSON used by backend

## Tests and CI

Run fast local checks:

```bash
./env/bin/python -m py_compile python/backend.py python/build_backend.py python/update.py python/league_data.py python/league_stats.py
./env/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

GitHub Actions workflow:
- `.github/workflows/ci.yml`
- triggers on `push` to `main` and on pull requests
- runs compile checks + unit tests (no Google Sheets/Pitchero web calls)
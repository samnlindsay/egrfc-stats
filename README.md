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
- `data/egrfc_backend.duckdb`
- `data/backend/*.json`
- `data/backend/*.parquet`

Backend schema and usage notes:
- `python/backend.md`

## Operational workflow

### 1) Update database (no Pitchero web)

```bash
./env/bin/python python/build_backend.py
```

Use this for normal updates. This is the default path.

### 2) Regenerate charts from the database

```bash
./env/bin/python python/update.py --backend-mode canonical
```

This regenerates chart specs from canonical DB tables/views and does not require Pitchero web refresh.

### 3) Optional: refresh Pitchero caches only when needed

```bash
./env/bin/python python/build_backend.py --refresh-pitchero
./env/bin/python python/update.py --backend-mode canonical
```

Use this only when intentionally changing Pitchero-derived inputs (or after scraper changes).

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
# EGRFC Stats Data Pipeline - Complete Data Flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATA ASSEMBLY & PROCESSING                           │
└─────────────────────────────────────────────────────────────────────────────┘

EXTRACTION PHASE (Parallel data collection)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│
├─ Google Sheets (Current primary source)
│  ├─ extract_games_data()           → games_google_raw
│  ├─ extract_player_appearances()   → appearances_google_raw
│  ├─ extract_lineouts_data()        → lineouts_raw
│  ├─ extract_set_piece_stats()      → set_piece_raw
│  ├─ extract_league_history()       → league_history_raw
│  └─ extract_2526_scorers()         → scorers_2526_raw
│
├─ Pitchero Website (Historical: pre-2024 games + season stats)
│  ├─ extract_pitchero_stats()              → pitchero_stats_source
│  └─ extract_pitchero_historic_team_sheets() → historic_games_raw, historic_appearances_raw
│
└─ RFU Data (Alternative source for match info & lineups)
   ├─ load_consolidated_matches()  → rfu_matches_raw
   ├─ build_rfu_games_dataframe()  → games_rfu
   ├─ load_rfu_historic_results_csvs() → historic_rfu_csv
   └─ build_rfu_player_appearances_dataframe() → appearances_rfu


TRANSFORMATION PHASE (Clean and normalize)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│
│ Pitchero-specific cleaning:
├─ _build_pitchero_games_raw()           : historic_games_raw → pitchero_games_raw
├─ _build_pitchero_games_clean()         : pitchero_games_raw → pitchero_games_clean
├─ _build_pitchero_player_appearances_raw() : historic_appearances_raw → pitchero_appearances_raw
├─ _build_pitchero_player_appearances_clean() : pitchero_appearances_raw → pitchero_appearances_clean
├─ _build_pitchero_stats_raw()           : pitchero_stats_source → pitchero_stats_raw
├─ _build_pitchero_stats_clean()         : pitchero_stats_raw → pitchero_stats_clean
│
│ Reference data processing:
├─ _build_ref_pitchero_player_name_overrides()  → DB table
├─ _build_ref_pitchero_opposition_overrides()   → DB table
├─ _build_ref_pitchero_match_url_overrides()    → DB table
│
│ RFU-specific transformation:
├─ _build_canonical_games_from_rfu()      : games_rfu → rfu_games_for_canonical
└─ _build_canonical_appearances_from_rfu() : appearances_rfu → appearances_rfu_for_canonical


STAGING PHASE (Converge all sources to common schema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ Using _to_games_stage() and _to_appearance_stage() helper functions:
│
├─ Games staging (all sources → common columns):
│  ├─ games_google_raw → games_google_stage
│  ├─ pitchero_games_clean → games_pitchero_stage
│  ├─ rfu_games_for_canonical → games_rfu_stage
│  └─ All stage tables → pd.concat() → games_staged_all → games_raw
│
├─ Appearances staging:
│  ├─ appearances_google_raw → appearances_google_stage
│  ├─ pitchero_appearances_clean → appearances_pitchero_stage
│  ├─ appearances_rfu_for_canonical → appearances_rfu_stage
│  └─ All stage tables → pd.concat() → appearances_staged_all → appearances_raw
│
└─ Scorers staging (extracting points data):
   ├─ games_google_stage → scorers_google_stage_from_games
   ├─ scorers_2526_raw → scorers_google_stage_from_sheet
   ├─ games_pitchero_stage → scorers_pitchero_stage
   ├─ games_rfu_stage → scorers_rfu_stage
   └─ All scorer tables → pd.concat() → scorers_staged_all


CANONICALIZATION PHASE (Final merges with conflict resolution)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ Using SOURCE_PRECEDENCE = {"google": 0, "pitchero": 1, "rfu": 2}
│
├─ _build_games()
│  ├─ games_raw (concat of all sources)
│  ├─ Canonicalize opposition names
│  ├─ Reconcile duplicate matches (same date/squad/opposition/score → keep one)
│  ├─ Merge with appearances to fill in captains/MoTM if missing
│  └─ OUTPUT: games table (one row per match)
│
├─ _build_player_appearances()
│  ├─ appearances_raw (concat of all sources)
│  ├─ Join with games for season/date info
│  ├─ Resolve player aliases (same person, multiple names)
│  └─ OUTPUT: player_appearances table
│
├─ _build_lineouts() : lineouts_raw + games → lineouts table
├─ _build_set_piece() : set_piece_raw + games → set_piece table
├─ _build_league_history() : league_history_raw → league_history table
└─ _build_league_table_standings() : league_history → league_table_standings table


ENRICHMENT PHASE (Post-build data supplementation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Called by _apply_pitchero_supplemental_enrichment() after build()
│
├─ Manual URL overrides (MANUAL_PITCHERO_URL_OVERRIDES dict)
│  └─ UPDATE games.pitchero_match_url WHERE NULL
│
├─ Candidate URL backfill (from CSV: full_scrape_reconcile_candidates.csv)
│  └─ UPDATE games.pitchero_match_url WHERE NULL AND candidate_score >= 0.90
│
├─ Scorer backfill (from CSV: full_scrape_pitchero_games.csv)
│  └─ UPDATE games.{tries_scorers, conversions_scorers, penalties_scorers, drop_goals_scorers}
│     WHERE NULL
│
└─ Historic cache backfill (from JSON: pitchero_historic_team_sheets_cache.json)
   ├─ UPDATE games.{captain, motm, vice_captain_1, vice_captain_2}
   └─ UPDATE games.{tries_scorers, conversions_scorers, penalties_scorers, drop_goals_scorers}


EXPORT PHASE (JSON for frontend consumption)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│
├─ export_tables()
│  ├─ data/backend/games.json
│  ├─ data/backend/player_appearances.json
│  ├─ data/backend/lineouts.json
│  ├─ data/backend/set_piece.json
│  ├─ data/backend/season_summary.json
│  ├─ data/backend/squad_stats.json
│  ├─ data/backend/player_profiles.json
│  └─ ... (other JSON exports)
│
└─ Frontend loads JSON specs from data/charts/*.json
   └─ Rendered via Vega-Embed in JavaScript


CHART GENERATION (Python/Altair)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Called by update.py after backend build:

├─ Squad composition charts
├─ Player stats charts
├─ Results charts
├─ Team sheets charts
├─ Lineout analysis charts
├─ Set piece charts
├─ League history charts
└─ ... (40+ charts total)

└─ All saved to data/charts/*.json with responsive CSS injection
```

---

## Key Data Structures

### Games Table
```
game_id (TEXT PRIMARY KEY)         : YYYY-MM-DD_squad_opposition_club
squad (TEXT NOT NULL)              : "1st" or "2nd"
date (DATE NOT NULL)               : Match date
season (TEXT)                      : "YYYY/YY" format
competition (TEXT)                 : "League", "Cup", "Friendly"
game_type (TEXT)                   : Normalized competition category
opposition (TEXT NOT NULL)         : Canonical opposition name
opposition_club (TEXT)             : Club name without team suffix
opposition_squad (TEXT)            : Team number if applicable
home_away (TEXT)                   : "H" or "A"
pf (INT64)                         : Points for
pa (INT64)                         : Points against
result (TEXT)                      : "W", "L", "D", or NULL
captain (TEXT)                     : Captain name
motm (TEXT)                        : Man of the match
vice_captain_1, vice_captain_2     : VC names
tries_scorers (JSON)               : {"Player Name": count, ...}
conversions_scorers (JSON)         : {"Player Name": count, ...}
penalties_scorers (JSON)           : {"Player Name": count, ...}
drop_goals_scorers (JSON)          : {"Player Name": count, ...}
pitchero_match_url (TEXT)          : Link to Pitchero match page
_source (TEXT)                     : "google", "pitchero", or "rfu"
```

### Player Appearances Table
```
appearance_id (TEXT)               : game_id + "_" + shirt_number
game_id (TEXT)                     : Reference to games
squad (TEXT)                       : "1st" or "2nd"
player (TEXT)                      : Player name
shirt_number (INT64)               : 1-29
position (TEXT)                    : "Hooker", "Fly-half", etc.
position_group (TEXT)              : "Forwards" or "Backs"
unit (TEXT)                        : "Starter" (1-15) or "Bench" (16-29)
is_starter (BOOLEAN)               : shirt_number <= 15
is_captain (BOOLEAN)
is_vc (BOOLEAN)                    : Vice-captain
_source (TEXT)                     : "google", "pitchero", or "rfu"
```

---

## Data Source Precedence and Conflict Resolution

When the same match appears in multiple sources:

```python
SOURCE_PRECEDENCE = {
    "google": 0,   # Highest priority (most recent/accurate)
    "pitchero": 1,
    "rfu": 2,      # Lowest priority (least recent/detailed)
}
```

### Conflict Resolution Strategy

**For games (date/squad/opposition matches):**
1. Identify all potential duplicates by key: `date + squad + opposition_club`
2. If multiple sources report same match:
   - Use Google Sheets data if available
   - Fall back to Pitchero if Google missing
   - Use RFU as last resort
3. Merge fields from each source (Google provides structure, Pitchero provides details)

**For player appearances:**
- Google Sheets is primary source (current team sheets)
- Pitchero used for historical seasons (pre-2024)
- RFU used when Google/Pitchero unavailable

**For scorers:**
- Google Sheets: Manual entry (authoritative)
- Pitchero: Web-scraped (filled in if missing)
- RFU: Rarely has scorer data

---

## Intermediate Tables Explained

### Raw Tables (Post-extraction)
| Table | Source | Purpose | Transformation Required |
|-------|--------|---------|------------------------|
| `games_google_raw` | Google Sheets | Current match data | Normalize opposition names |
| `historic_games_raw` | Pitchero scrape | Historical games | Cleaning/validation |
| `appearances_google_raw` | Google Sheets | Current lineups | Join with games for season |
| `historic_appearances_raw` | Pitchero scrape | Historical lineups | Join with games for season |
| `lineouts_raw` | Google Sheets | Lineout calls | Join with games |
| `set_piece_raw` | Google Sheets | Set piece stats | Join with games |
| `rfu_matches_raw` | RFU JSON | RFU match data | Transform to canonical schema |
| `games_rfu` | `rfu_matches_raw` | RFU matches in standard format | Add squad/opposition columns |

### Cleaned Tables (After transformation)
| Table | Input | Purpose | Use Case |
|-------|-------|---------|----------|
| `pitchero_games_clean` | `pitchero_games_raw` | Validated Pitchero games | Merge with Google Sheets |
| `pitchero_appearances_clean` | `pitchero_appearances_raw` | Validated Pitchero lineups | Merge with Google Sheets |
| `pitchero_stats_clean` | `pitchero_stats_raw` | Validated season stats | Build player profiles |

### Staged Tables (Common schema across all sources)
| Table | Columns | Purpose | Feeding Into |
|-------|---------|---------|--------------|
| `games_*_stage` | [game_id, date, squad, opposition, pf, pa, result, captain, motm, vc1, vc2, scorers, source] | Unified games schema | `games_raw` (concatenated) |
| `appearances_*_stage` | [game_id, squad, player, shirt_number, position, unit, is_captain, is_vc, is_starter, source] | Unified appearances schema | `appearances_raw` (concatenated) |
| `scorers_*_stage` | [game_id, squad, date, season, game_type, player, tries, conversions, penalties, drop_goals, points, source] | Unified scorers schema | `scorers_staged_all` (concatenated) |

### Canonical Tables (Final merge with conflict resolution)
| Table | Rows | Key Uniqueness | Notes |
|-------|------|---|---|
| `games` | 300-400 | One per unique match | All sources merged, Google priority |
| `player_appearances` | 5000-7000 | One per player per game | Resolved aliases |
| `lineouts` | 1000-1500 | One per lineout | Linked to games |
| `set_piece` | 500-800 | One per match per piece type | Linked to games |
| `league_history` | 2000-3000 | Historical progression | League positions over seasons |
| `season_scorers` | 1000-1500 | One per player per season | Aggregated from games |

---

## Why So Many Intermediate Tables?

Each stage serves a specific purpose:

1. **Raw** - Preserves source data as-extracted (audit trail)
2. **Cleaned** - Fixes obvious errors, normalizes formats
3. **Staged** - Converges to common schema (enables concat)
4. **Raw concat** - All sources in one table (before conflict resolution)
5. **Canonical** - Deduplicated, conflict-resolved, final version

This approach is **defensive programming**: if something goes wrong, you can inspect intermediate stages to debug.

**Trade-off:** More tables = more code, but also more visibility into where errors occur.

---

## Data Quality Checkpoints

### During Extraction
- Validate dates parse correctly
- Check opposition names aren't empty
- Verify shirt numbers are 1-29
- Ensure game_id is unique per source

### During Cleaning
- Remove duplicate rows within same source
- Validate score_for > score_against not reversed
- Check player names aren't duplicated in same game

### During Staging
- Verify all mandatory columns populated
- Check source labels correct
- Validate data types before concat

### During Canonicalization
- Detect duplicate matches (same match, different sources)
- Apply precedence rules
- Merge results (e.g., captain from one source, scorers from another)

### During Export
- Verify JSON is valid
- Check row counts match expected ranges
- Validate primary key uniqueness

---

## Common Data Issues and How They're Handled

| Issue | Source | Handling | Table Updated |
|-------|--------|----------|---|
| Opposition name variants ("Haywards Heath" vs "Haywards Heath II") | All | Canonicalize to club name only in game_id | `games` |
| Player name variants ("S Lindsay 2" vs "Sam Lindsay-McCall") | Google + Pitchero | Manual mapping dict + season-aware resolver | `player_appearances` |
| Missing scorers | Google Sheets | Filled in by Pitchero scrape during enrichment | `games.tries_scorers`, etc. |
| Duplicate matches (same game reported twice) | Multiple sources | Deduplicate by date/squad/opposition, apply precedence | `games` |
| Missing captain/MoTM | Pitchero | Backfilled from historic cache JSON file | `games.captain`, `games.motm` |
| Season format inconsistency (YYYY/YY vs YYYY-YYYY) | RFU | Converted to YYYY/YY during RFU processing | All tables |
| Shirt numbers out of range | Google Sheets | Validated during extraction, warnings logged | `player_appearances` |

---

## How to Trace Data for a Specific Match

Example: Find all data for "2024-10-12 1st XV vs Haywards Heath (Home)"

```
1. Query games table:
   SELECT * FROM games 
   WHERE date = '2024-10-12' AND squad = '1st' AND opposition LIKE 'Haywards Heath%'
   
2. Get appearances:
   SELECT * FROM player_appearances 
   WHERE game_id = <result from step 1>
   
3. Get lineouts (if available):
   SELECT * FROM lineouts 
   WHERE game_id = <result from step 1>
   
4. Get set piece stats:
   SELECT * FROM set_piece 
   WHERE game_id = <result from step 1>
   
5. Check data source and pitchero URL:
   SELECT _source, pitchero_match_url FROM games 
   WHERE game_id = <result from step 1>
   
6. If missing data, check enrichment sources:
   - data/pitchero_historic_team_sheets_cache.json
   - data/full_scrape_reconcile_candidates.csv
   - data/MANUAL_PITCHERO_URL_OVERRIDES (in backend.py)
```

---

## Update Workflow (What Happens When You Run `python update.py`)

```bash
$ cd python && python update.py

1. Check backend DB lock (use alternate if needed)
2. Call BackendDatabase.build():
   ├─ reset_schema()                      [Drop all tables/views]
   ├─ Extract all data in parallel        [6+ extraction calls]
   ├─ Build reference tables              [Player/opposition overrides]
   ├─ Build cleaned tables                [Pitchero validation]
   ├─ Stage all sources                   [Convert to common schema]
   ├─ Canonicalize                        [Merge all sources, resolve conflicts]
   └─ Export to JSON                      [Frontend consumption]

3. Call _apply_pitchero_supplemental_enrichment():
   ├─ Apply manual URL overrides
   ├─ Apply candidate URL backfill
   ├─ Apply scorer backfill from scraped games
   └─ Apply historic cache backfill

4. Call rebuild_post_enrichment():
   ├─ Rebuild scorer-dependent tables
   ├─ Recalculate season_scorers
   ├─ Regenerate player_profiles_canonical
   └─ Re-export JSON

5. Generate all charts (40+)
   ├─ Squad composition
   ├─ Player stats
   ├─ Team sheets
   └─ League history

6. Sync headshots with exports

Done! Frontend loads new JSON specs and data.
```

**Total execution time:** ~30-60 seconds (depending on Pitchero scrape)

---

## Data Files on Disk

```
data/
├── egrfc_backend.duckdb         ← Main database (primary)
├── egrfc_backend_alt.duckdb     ← Fallback if primary is locked
│
├── backend/                      ← JSON exports for frontend
│   ├── games.json
│   ├── player_appearances.json
│   ├── lineouts.json
│   ├── set_piece.json
│   ├── season_summary.json
│   ├── squad_stats.json
│   ├── player_profiles.json
│   └── ... (other exports)
│
├── charts/                       ← Vega-Lite chart specs
│   ├── appearance_chart.json
│   ├── squad_position_composition.json
│   ├── team_sheets.json
│   └── ... (40+ chart specs)
│
├── match_data/                   ← Legacy individual match JSONs
│
├── metadata/                     ← Intermediate metadata
│
├── pitchero_stats_cache.json    ← Cached Pitchero season stats
├── pitchero_historic_team_sheets_cache.json  ← Cached lineups
├── matches.json                  ← RFU consolidated match data
│
├── full_scrape_pitchero_games.csv  ← Scraped games (enrichment)
├── full_scrape_reconcile_candidates.csv  ← URL candidates (enrichment)
└── ... (other support files)
```

---

## Accessing Data from Frontend

```javascript
// Frontend pattern:
async function loadData() {
    const games = await fetch('data/backend/games.json').then(r => r.json());
    const appearances = await fetch('data/backend/player_appearances.json').then(r => r.json());
    const chartSpec = await fetch('data/charts/team_sheets.json').then(r => r.json());
    
    // Use vegaEmbed to render
    vegaEmbed('#chart-container', chartSpec);
}
```

All frontend data is **pre-generated** at build time (no runtime queries to DuckDB).

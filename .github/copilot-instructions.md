# EGRFC Stats - AI Coding Agent Instructions

This is a rugby club statistics tracking system for East Grinstead RFC that pulls data from Google Sheets, processes it with Python/DuckDB, generates Altair visualizations, and serves them via a static HTML/JavaScript frontend.

## Architecture Overview

### Data Pipeline (Python → JSON → JavaScript)
1. **Data source**: Google Sheets (`client_secret.json` auth required)
   - Team sheets: `1st XV Players`, `2nd XV Players` 
   - Match data, player appearances, lineouts, set piece stats
2. **Processing**: Python scripts extract → transform with DuckDB → export to `data/*.json`
3. **Visualization**: Altair charts saved as Vega-Lite JSON specs
4. **Frontend**: Static HTML loads JSON specs and renders with Vega-Embed

### Key Python Scripts (located in `python/`)

**Data extraction & updates:**
- `new_update.py` - **PRIMARY UPDATE SCRIPT** - Generates all charts using `DatabaseManager`
- `database.py` - Defines schema and `DatabaseManager` class with DuckDB queries
- `new_data.py` - `DataExtractor` class pulls from Google Sheets, normalizes data
- `data_prep.py` - Legacy loader (being deprecated in favor of `new_data.py`)

**Chart generation:**
- `chart_helpers.py` - CSS injection helper `hack_params_css()` adds responsive scaling + custom param styling to Altair HTML
- Chart functions return Altair objects and save to `data/charts/*.json`
- All charts use custom theme via `alt_theme()` with PT Sans Narrow font

**League analysis:**
- `league_data.py` - Scrapes match data from Pitchero website
- `league_stats.py` - Generates league-specific charts (results matrix, squad analysis)

### Database Schema (DuckDB in-memory)

Core tables defined in `database.py`:
```python
games                # One row per match (game_id, date, season, squad, opposition, pf, pa, result)
player_appearances   # One row per player per game (appearance_id, game_id, player, position, shirt_number, is_starter, is_captain)
lineouts            # One row per lineout (lineout_id, game_id, jumper, won, call_type, setup)
pitchero_stats      # Historical stats from Pitchero (season, squad, player_join, event, count)
set_piece_stats     # Per-game set piece summary (game_id, team, set_piece, won, lost, total)
```

## Critical Workflows

### Running the full data update
```bash
cd python
python new_update.py  # Runs main() function - extracts data, generates all charts
```

This script:
1. Instantiates `DatabaseManager` and loads data from Google Sheets via `DataExtractor`
2. Creates database tables and loads data
3. Generates charts: `appearance_chart()`, `captains_chart()`, `results_chart()`, `team_sheets_chart()`, etc.
4. Saves output to `../data/charts/*.json`

### Python environment setup
- Virtual env exists at `env/` (Python 3.x)
- Key dependencies: `gspread`, `pandas`, `duckdb`, `altair`, `beautifulsoup4`
- Activate: `source env/bin/activate` (macOS/Linux)

### Testing frontend changes
1. Open `index.html` in browser (static file, no build step)
2. Uses Bootstrap 5, jQuery, and Vega-Embed CDN libraries
3. Main app: `js/main.js` - initializes charts, filters, navigation
4. Chart specs loaded from `data/charts/*.json` via fetch API

## Project-Specific Conventions

### Name Normalization Pattern
Player names have multiple formats across data sources. Use `clean_name()` function:
```python
# Converts "Sam Lindsay" → "S Lindsay 2" (handle duplicates)
# Converts full names to "Initial Surname" format
# Defined in both new_data.py and new_update.py
```

**Manual name mappings** exist in `other_names` dict (new_update.py:14-31) for historical Pitchero data.

### Squad Identification
- `squad` field: `"1st"` or `"2nd"` (strings, not integers)
- Games identified by: `f"{date}_{squad}_{opposition}".replace(' ', '_').replace('/', '')`
- Division lookup: See `divisions` dict in `league_stats.py` maps season+league → squad number

### Chart Styling Requirements

All Altair charts must:
1. Use custom theme from `charts.py`: `alt.themes.enable("my_custom_theme")`
2. Apply responsive CSS via `hack_params_css(output_file)` after saving
3. Brand colors: `#202946` (dark blue), `#7d96e8` (light blue), `#981515` (red)
4. Interactive params: Use Vega params with custom bindings styled in `hack_params_css()`

### Google Sheets Authentication
- Credentials: `python/client_secret.json` (not in git, required for updates)
- Sheet URL hardcoded in `new_data.py:40` and `data_prep.py:17`
- Uses service account with read access to specific spreadsheet

### Position/Unit Classification
Defined in `new_data.py:200-232`:
```python
_get_position(shirt_number)       # 1→Loosehead, 2→Hooker, 10→Fly-half, etc.
_get_position_group(shirt_number) # 1-8→Forwards, 9-15→Backs
_get_unit(shirt_number)          # 1-15→Starter, 16-29→Bench
```

## Integration Points

### Frontend Filter System
Filters in `index.html` use Bootstrap button groups:
- Squad: All / 1st / 2nd
- Season: Multi-select dropdown
- Game Type: League / Cup / Friendly / All
- Player: Autocomplete select

JavaScript in `js/filters.js` applies filters by:
1. Reading filter state from DOM
2. Transforming Vega spec data with filter predicates
3. Re-rendering charts via `vegaEmbed()`

### Google Apps Script
`googleappsscript.js` (3118 lines) manages:
- Player sign-up forms → `Players` sheet
- Training attendance tracking → `Attendance` sheet  
- Team selection interface → `Selection` sheet
- Form IDs hardcoded at top (lines 1-20)

Not directly integrated with stats pipeline but shares player data.

## Data File Locations

**Generated outputs** (git-ignored, regenerated via `new_update.py`):
```
data/charts/*.json          # Vega-Lite chart specifications
data/matches.json           # All match data
data/players.json           # Player aggregations
data/season_summaries.json  # Per-season stats
```

**Source data** (manual updates or scraped):
```
data/match_data/*.json      # Individual match files (legacy)
data/pitchero.json          # Historical Pitchero stats
```

## Common Gotchas

1. **DuckDB queries must use placeholders**: `db.con.execute("SELECT * WHERE season = ?", [season])`
2. **Date formats vary**: Google Sheets dates need `_parse_date()`, JSON exports use ISO strings
3. **Chart width/height**: Use `alt.Step()` for responsive bar charts, explicit pixels for fixed layouts
4. **Altair encoding types**: `:N` nominal, `:Q` quantitative, `:T` temporal, `:O` ordinal
5. **Player join key**: `player_join` field used to link modern records with historical Pitchero data
6. **Running updates requires Google Sheets access** - will fail without valid `client_secret.json`

## Key Files to Reference

- Schema definitions: [database.py](python/database.py#L10-L100)
- Chart generation patterns: [new_update.py](python/new_update.py#L50-L400)
- Frontend state management: [js/main.js](js/main.js)
- CSS variables and theme: [css/variables.css](css/variables.css)

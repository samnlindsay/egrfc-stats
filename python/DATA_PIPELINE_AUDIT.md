# Data Pipeline Audit: Inconsistencies, Redundancy, and Complexity

## Executive Summary

The EGRFC stats data pipeline (~20K lines of Python code) has become complex with significant redundancy and unclear data flows. This audit identifies critical areas for refactoring to improve clarity, maintainability, and correctness.

**Key Issues:**
- **7+ redundant normalization functions** across 3+ files doing nearly identical work
- **Unclear data staging flow** with 8+ intermediate tables between raw and final forms
- **Scattered opposition/player name mappings** across 4+ files and JavaScript
- **Implicit precedence rules** for multi-source data conflicts
- **Repetitive extraction code** for Google Sheets, Pitchero, RFU data

---

## 1. Redundant Data Normalization Functions

### 1.1 Team Name Normalization

**Problem:** Multiple identical implementations across files

| File | Function | Purpose |
|------|----------|---------|
| `data.py:271` | `DataExtractor._normalise_team_name()` | Normalize team names to lowercase alphanumeric |
| `backend.py:2980` | `_normalise_team_name()` (local in `_build_canonical_games_from_rfu`) | Same purpose |
| `league_data.py` | Embedded logic in parsing | Repeated inline |
| `merge_rfu_backend_games.py:37` | `_normalize_team_name()` | Same purpose |

**Impact:** If you need to change how team names normalize, you must update multiple places.

### 1.2 Key Normalization (Alphanumeric)

**Problem:** Multiple near-identical functions with inconsistent naming

| File | Function | Pattern |
|------|----------|---------|
| `backend.py:133` | `_normalise_key()` | `re.sub(r"[^a-z0-9]", "", name.lower())` |
| `data.py:154` | `_normalise_pitchero_key()` | Same regex pattern, explicit purpose |
| `merge_rfu_backend_games.py:47` | `_normalise_lookup_key()` | Same pattern |

**Impact:** Three names for the same operation; inconsistent naming makes it hard to understand code intent.

### 1.3 Season Format Normalization

**Problem:** Multiple implementations with different logic and formats

| File | Function | Format | Notes |
|------|----------|--------|-------|
| `backend.py:260` | `_season_sort_key()` | Sorts `YYYY-YYYY` or handles misc | Sort key, not normalization |
| `backend.py:267` | `_season_start_year()` | Extracts start year from `YYYY/YY` or `YYYY-YYYY` | Returns int |
| `league_data.py:477` | `_normalize_season()` | Converts `YYYY/YY` → `YYYY-YYYY` | Converts to dash format |
| `league_data.py:510` | `season_to_short_label()` | Converts to `YYYY/YY` format | Different output than above |
| `merge_rfu_backend_games.py:23` | `_season_dash_to_backend()` | Converts `YYYY-YYYY` → `YYYY/YY` | Opposite direction |
| JavaScript (`shared.js:1034`) | `normalizeSeasonLabel()` | `YYYY-YYYY` or `YYYY/YYYY` → `YYYY/YY` | Frontend version |

**Impact:** 
- Hard to know which function to use
- Formats are inconsistent: some use `YYYY/YY`, others `YYYY-YYYY`
- Frontend has its own copy of logic
- Risk of format mismatches when data flows through pipeline

### 1.4 Opposition Club Name Extraction

**Problem:** Team number extraction logic repeated in multiple places

| File | Location | Purpose |
|------|----------|---------|
| `backend.py:135-187` | `_OPPOSITION_TEAM_SUFFIX_RE` + functions | Parse "Haywards Heath II" → ("Haywards Heath", 2) |
| `data.py:233-289` | `_split_opposition_club_team()` + helpers | Same purpose |
| `merge_rfu_backend_games.py` | `_extract_team_number()` | Partial implementation |

**Impact:** Same regex logic defined in multiple places; risk of inconsistent parsing.

---

## 2. Opposition Name Canonicalization Scattered Across Files

### 2.1 Multiple Opposition Name Mappings

**Problem:** Opposition canonical names split across 3+ files with inconsistent loading

| File | Dictionary | Scope | Notes |
|------|-----------|-------|-------|
| `backend.py:31` | `PITCHERO_TO_GOOGLE_CANONICAL_NAMES` | Manual name rewrites | 30+ entries |
| `data.py:67-153` | `PITCHERO_OPPOSITION_CANONICAL_NAMES` | Opposition name mappings | 100+ entries |
| `merge_rfu_backend_games.py:23` | `EXTRA_RFU_OPPOSITION_CANONICAL_NAMES` | Additional RFU mappings | 6+ entries |

**Missing Documentation:**
- When is each mapping used?
- Why is `EXTRA_RFU_OPPOSITION_CANONICAL_NAMES` separate from the main mapping?
- What happens if an opposition appears in multiple mappings?

### 2.2 Canonicalization Functions

| File | Function | Purpose | Used By |
|------|----------|---------|---------|
| `data.py:160` | `canonical_pitchero_opposition()` | Normalize opposition names using dict lookup | `backend.py` |
| `backend.py:243` | `_canonical_pitchero_opposition_name()` | Wrapper that calls `data.canonical_pitchero_opposition()` | Internal |

**Impact:** Extra layer of indirection; unclear why wrapper exists.

---

## 3. Complex Multi-Source Data Merging

### 3.1 Data Sources and Precedence

Three data sources with implicit precedence:

```python
# backend.py:1366 - SOURCE_PRECEDENCE
SOURCE_PRECEDENCE = {
    "google": 0,      # Highest priority
    "pitchero": 1,
    "rfu": 2,         # Lowest priority
}
```

**Problem:** Source precedence is explicit only in one place, but data flow shows complex fallback patterns:

1. **Google Sheets** (primary source for current/recent games)
2. **Pitchero** (historical source for pre-2024 seasons)
3. **RFU** (alternative source, used when others unavailable)

### 3.2 Multiple Intermediate Tables in Build Pipeline

The `build()` method creates 8+ representations of the same data:

```
Raw extraction stage (6 parallel extractions):
├── games_google_raw
├── historic_games_raw (from Pitchero)
├── historic_appearances_raw (from Pitchero)
├── lineouts_raw
├── set_piece_raw
├── league_history_raw
├── pitchero_stats_source
├── scorers_2526_raw
├── rfu_matches_raw
└── rfu_games_raw (from RFU JSON)

Intermediate processing (3 stages for games):
├── pitchero_games_raw → pitchero_games_clean
├── pitchero_appearances_raw → pitchero_appearances_clean
├── pitchero_stats_raw → pitchero_stats_clean

Staging (converges sources to common schema):
├── games_google_stage
├── games_pitchero_stage
├── games_rfu_stage
└── games_staged_all → games_raw

Canonicalization (final merges):
└── games (with appearances reconciliation)
```

**Impact:** Hard to trace where data comes from; unclear when each table is used.

---

## 4. Player and Scorer Name Normalization

### 4.1 Inconsistent Name Cleaning Across Python

| File | Function | Purpose | Logic |
|------|----------|---------|-------|
| `data.py:199` | `clean_name()` | Convert full name to "Initial Surname" | `"Sam Lindsay"` → `"S Lindsay 2"` |
| `backend.py:230` | `_canonical_player_name()` | Map Pitchero name → Google name | Lookup in dict |
| `backend.py:237` | `_canonical_player_name_for_season()` | Resolve season-specific aliases | Handles "S Lindsay" ambiguity |

**Problem:**
- `clean_name()` produces `"S Lindsay 2"`, `_canonical_player_name()` produces `"Sam Lindsay"`
- Not clear when to use each function
- Manual mapping dictionary (`PITCHERO_TO_GOOGLE_CANONICAL_NAMES`) with 30+ entries

### 4.2 JavaScript Duplicate Logic

Frontend has its own player name normalization in multiple files:

- `match-info.js:49` - `canonicalizeName()` - Lowercases and normalizes spaces
- `opposition-profile.js:38` - `normaliseLogoKey()` - Logo name normalization
- `player-gallery.js:10` - `surnamePart()`, `firstNamePart()` - Name parsing

**Impact:**
- Any change to player name format requires coordinating Python + JavaScript
- Risk of divergence if maintenance isn't coordinated
- Scorer name resolution in `match-info.js:337` duplicates Python logic

---

## 5. Data Extraction Redundancy

### 5.1 Multiple Extract Entry Points

**Problem:** Unclear which extraction function should be used for which data type

| File | Class/Function | Extracts | Used By |
|------|---|----------|---------|
| `data.py:303` | `DataExtractor.extract_games_data()` | Games from Google Sheets | `backend.py:1358` |
| `data.py:392` | `DataExtractor.extract_player_appearances()` | Appearances from Google Sheets | `backend.py:1359` |
| `data.py:445` | `DataExtractor.extract_pitchero_stats()` | Pitchero season stats | Called but stats processing elsewhere |
| `data.py:527` | `DataExtractor.extract_pitchero_historic_team_sheets()` | Historic Pitchero data | `backend.py:1361-1366` |
| `data.py:896` | `DataExtractor.extract_lineouts_data()` | Lineout data from Google Sheets | `backend.py:1370` |
| `data.py:955` | `DataExtractor.extract_set_piece_stats()` | Set piece data from Google Sheets | `backend.py:1371` |
| `backend.py:1752` | `BackendDatabase._build_pitchero_games_raw()` | Converts historic Pitchero data | Internal |
| `backend.py:1829` | `BackendDatabase._build_pitchero_player_appearances_raw()` | Converts historic Pitchero data | Internal |

**Why It's Confusing:**
1. Some extraction happens in `DataExtractor`, some in `BackendDatabase`
2. `_build_pitchero_*_raw()` methods duplicate transformation logic already in `DataExtractor`
3. Not clear if you should use `DataExtractor` directly or through `BackendDatabase`

### 5.2 Parallel Stage Building with Similar Code

The `build()` method has repetitive patterns for each data source:

```python
# Repeated for google, pitchero, rfu:
scorers_google_stage = self._build_scorers_stage_from_games(games_google_stage, "google")
scorers_pitchero_stage = self._build_scorers_stage_from_games(games_pitchero_stage, "pitchero")
scorers_rfu_stage = self._build_scorers_stage_from_games(games_rfu_stage, "rfu")

# And appearances:
appearances_google_stage = _to_appearance_stage(appearances_google_raw, "google")
appearances_pitchero_stage = _to_appearance_stage(pitchero_appearances_clean, "pitchero")
appearances_rfu_stage = _to_appearance_stage(appearances_rfu_for_canonical, "rfu")

# And games:
games_google_stage = _to_games_stage(games_google_raw, "google")
games_pitchero_stage = _to_games_stage(pitchero_games_clean, "pitchero")
games_rfu_stage = _to_games_stage(rfu_games_for_canonical, "rfu")
```

**Impact:** If you add a 4th source, you must replicate this pattern 3 times.

---

## 6. Unclear Enrichment and Supplemental Data Flows

### 6.1 Post-Build Enrichment

After `backend.build()` completes, `_apply_pitchero_supplemental_enrichment()` applies updates:

1. **Manual URL overrides** from `MANUAL_PITCHERO_URL_OVERRIDES`
2. **Candidate URL backfill** from CSV files (`full_scrape_reconcile_candidates.csv`)
3. **Scorer backfill** from `full_scrape_pitchero_games.csv`
4. **Historic cache backfill** from JSON cache file

**Problem:**
- Why are these updates applied *after* build completes?
- Why not integrate them into the build process?
- How do you know which artifact files are needed?
- If a build fails mid-enrichment, DB can be left in inconsistent state

### 6.2 Reference Tables vs. Enrichment

Multiple reference tables stored in DB:

- `ref_pitchero_player_name_overrides` - Manual name corrections
- `ref_pitchero_opposition_overrides` - Manual opposition corrections
- `ref_pitchero_match_url_overrides` - Manual URL corrections

But also separate enrichment dictionaries in Python:

- `PITCHERO_TO_GOOGLE_CANONICAL_NAMES` (backend.py:31)
- `PITCHERO_OPPOSITION_CANONICAL_NAMES` (data.py:67)
- `MANUAL_PITCHERO_URL_OVERRIDES` (backend.py:82)

**Problem:** Data exists in both DuckDB tables and Python dicts; unclear which is source of truth.

---

## 7. Frontend/Backend Data Format Divergence

### 7.1 Season Format Inconsistency

Frontend normalizes season labels but Python produces them in different formats:

| Component | Format | Example |
|-----------|--------|---------|
| `league_data.py` | `YYYY/YY` | `"2024/25"` |
| `backend.py` | `YYYY/YY` | `"2024/25"` |
| Google Sheets (games) | `YYYY/YY` | `"2024/25"` |
| RFU data | Dash format | `"2024-2025"` |
| JavaScript | `YYYY/YY` | `"2024/25"` |

**Impact:** Data flowing from RFU through pipeline requires conversion at multiple points.

### 7.2 Opposition Name Format Divergence

- Python exports oppositions as full names: `"Haywards Heath II"`
- JavaScript logo keys use different normalization: lowercase alphanumeric with no suffix
- Match-info.js has to reconcile player profiles across different name formats

---

## 8. Documentation Gaps

| Area | Missing Documentation |
|------|----------------------|
| Data source precedence | Where and why Google > Pitchero > RFU |
| Staging vs. raw tables | When each table is valid/complete |
| Reference tables | How manual overrides flow into final DB |
| Enrichment artifacts | What files are needed, when, and why |
| Opposition canonicalization | Why mappings are split across files |
| Player name mapping | When `clean_name()` vs `_canonical_player_name()` should be used |
| Season format handling | Which format is expected at each stage |

---

## 9. Recommended Refactoring Priority

### Phase 1: Consolidate Normalization (High Impact)
1. **Create single `utils/normalization.py`** with canonical versions of:
   - `normalize_key()` - Alphanumeric key normalization
   - `normalize_team_name()` - Team name standardization
   - `normalize_season()` - Season format handling
   - `normalize_opposition_name()` - Opposition canonicalization
   - `normalize_player_name()` - Player name standardization
   - `extract_opposition_club_and_team()` - Opposition parsing

2. **Import everywhere** instead of duplicating

### Phase 2: Centralize Opposition/Player Mappings (Medium Impact)
1. **Merge all opposition mappings** into single `data/reference_opposition_names.json`
2. **Merge all player mappings** into single `data/reference_player_names.json`
3. **Load once at startup**, not inline in code
4. **Document why each mapping exists**

### Phase 3: Clarify Data Flow (High Impact)
1. **Create `DATA_FLOW.md`** documenting:
   - Each intermediate table's purpose
   - When it's populated and when it's complete
   - Which sources contribute to each table
   - Data transformations applied at each stage

2. **Simplify staging** - Consider collapsing some intermediate stages

### Phase 4: Consolidate Data Extraction (Medium Impact)
1. **Unify `DataExtractor` usage** - decide if it's public API or internal
2. **Create extraction registry** - map source (Google/Pitchero/RFU) → extraction function
3. **Apply consistent error handling** across all extraction paths

### Phase 5: Frontend/Backend Alignment (Low-Medium Impact)
1. **Export all normalization functions as JSON utilities** frontend can call
2. **Or: Document exact format contracts** so frontend can duplicate safely
3. **Use TypeScript + shared types** if possible

---

## 10. Quick Wins (Can Do Immediately)

1. **Add docstrings** to all normalization functions explaining purpose and parameters
2. **Create NORMALIZATION.md** documenting each function's contract
3. **Comment opposition mapping dicts** explaining why each entry exists
4. **Add explicit SOURCE_PRECEDENCE comments** near build logic
5. **Document the 8 intermediate tables** with a diagram in `backend.py`

---

## Files to Create/Refactor

### New Files
- `python/utils/normalization.py` - Canonical normalization functions
- `python/DATA_FLOW.md` - Complete pipeline documentation
- `python/NORMALIZATION.md` - Normalization contract reference

### Files to Update
- `python/backend.py` - Import from utils, document intermediate stages
- `python/data.py` - Import from utils
- `python/league_data.py` - Import from utils
- `python/merge_rfu_backend_games.py` - Import from utils
- `README.md` - Link to DATA_FLOW and NORMALIZATION docs

---

## Metrics Before/After Refactoring

| Metric | Before | After (Target) |
|--------|--------|---|
| Normalization function definitions | 8+ | 1 (utils module) |
| Opposition mapping locations | 3+ | 1 (JSON file) |
| Player name mapping locations | 3+ | 1 (JSON file) |
| "Normalize" functions with same logic | 7+ | 1 |
| Lines of duplicate code | ~200+ | ~0 |
| Data staging complexity | 8+ intermediate tables | Documented & simplified |

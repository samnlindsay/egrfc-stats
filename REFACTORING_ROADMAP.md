# Data Pipeline Refactoring Roadmap

## Progress summary

| Issue | Title | Status |
|-------|-------|--------|
| 1 | Redundant Normalization Functions | ✅ Complete |
| 2 | Opposition Mappings Scattered Across Files | ✅ Complete |
| 3 | Unclear Data Flow with 8+ Intermediate Tables | ✅ Complete |
| 4 | Complex Multi-Source Conflict Resolution | ✅ Complete |
| 5 | Post-Build Enrichment Complexity | ✅ Complete |
| 6 | Frontend/Backend Code Duplication | ✅ Complete |

---

## Executive Summary

The EGRFC stats data generation pipeline (20K lines of Python) has accumulated significant redundancy, scattered logic, and unclear data flows. This makes the codebase hard to maintain, debug, and extend.

**Root causes:**
1. Multiple independent implementations of the same normalization logic
2. Data sources (Google Sheets, Pitchero, RFU) handled with implicit precedence rules
3. 8+ intermediate tables between raw data and final output
4. Reference data (opposition/player name mappings) scattered across multiple files
5. Complex enrichment workflow applied after main build completes

**Impact:**
- High maintenance burden: Changes to normalization logic require updates in 5+ locations
- Hard to debug: Difficult to trace where data issues originate
- Risk of divergence: Frontend has duplicate normalization logic in JavaScript
- Inconsistent formats: Season formats (YYYY/YY vs YYYY-YYYY) cause confusion

---

## Documentation Provided

Three new documents created to support refactoring:

### 1. [DATA_PIPELINE_AUDIT.md](DATA_PIPELINE_AUDIT.md)
**What:** Detailed analysis of redundancy, inconsistencies, and unnecessary complexity

**Key sections:**
- 8+ redundant normalization functions identified
- Opposition name mappings split across 3+ files
- Player name normalization done 5+ ways
- 8 intermediate tables between raw and canonical data
- Post-build enrichment workflow complexity
- Quick wins that can be done immediately

**How to use:**
- **Quick scan:** Read Executive Summary + Recommended Refactoring Priority
- **Deep dive:** Study each numbered section
- **Reference:** Link to specific sections when discussing issues

### 2. [DATA_FLOW.md](DATA_FLOW.md)
**What:** Complete data pipeline documentation showing how data flows from extraction to export

**Key sections:**
- High-level ASCII architecture diagram
- Extraction phase (3 data sources in parallel)
- Transformation phase (cleaning, normalization)
- Staging phase (converge to common schema)
- Canonicalization phase (conflict resolution)
- Enrichment phase (post-build supplementation)
- Export phase (JSON for frontend)
- Detailed explanation of each intermediate table
- Why so many intermediate tables exist
- Data quality checkpoints
- Common data issues and handling

**How to use:**
- **Tracing data:** Use "How to trace data for a specific match" section
- **Understanding flow:** Start with high-level diagram, then read Extraction/Staging/Canonicalization
- **Debugging:** Check "Common Data Issues" table
- **Onboarding:** New contributors should read this first

### 3. [NORMALIZATION.md](NORMALIZATION.md)
**What:** Specification and reference for all data normalization functions

**Key sections:**
- Canonical approach for each normalization type (season format, opposition names, player names, etc.)
- Current implementations listed (often multiple per function)
- Implementation plan for consolidation
- Usage examples
- Testing strategy

**Normalization types covered:**
1. Alphanumeric key normalization
2. Season format standardization
3. Team name normalization
4. Opposition name canonicalization
5. Player name normalization (3 subtypes)
6. Game ID generation
7. EGRFC team detection
8. Position and unit classification

**How to use:**
- **Reference:** Look up which function to use for a task
- **Implementation:** Copy code patterns when adding new normalization
- **Consolidation:** Use as guide for creating utils/normalization.py module

---

## Key Issues Identified

### Issue 1: Redundant Normalization Functions ✅
**Severity:** HIGH | **Effort to fix:** MEDIUM | **Impact:** HIGH

**Resolved:** Created `python/utils/normalization.py` with canonical implementations of `normalize_lookup_key()`, `normalize_team_name()`, `is_egrfc_team_name()`, `season_to_dash_label()`, `season_to_short_label()`, `season_start_year()`. Updated `backend.py`, `data.py`, `league_data.py`, `merge_rfu_backend_games.py`, `sync_headshots.py` to import from the shared module. All duplicates removed. 6 unit tests passing.

```
normalize_key()               [3 implementations]
  - backend.py:133
  - data.py:154
  - merge_rfu_backend_games.py:47

normalize_season()            [5+ implementations]
  - backend.py:267
  - league_data.py:477
  - league_data.py:510
  - merge_rfu_backend_games.py:23
  - JavaScript: shared.js:1034

normalize_team_name()         [3 implementations]
  - data.py:271
  - backend.py:2980
  - merge_rfu_backend_games.py:37
```

**Fix:** Create `python/utils/normalization.py` with canonical versions.

### Issue 2: Opposition Mappings Scattered Across Files ✅
**Severity:** HIGH | **Effort to fix:** MEDIUM | **Impact:** MEDIUM

**Resolved:** Created `python/utils/opposition.py` as single source of truth for `OPPOSITION_CANONICAL_NAMES`, club/squad decomposition, and ordinal/roman numeral squad label formatting. Added `OPPOSITION_SQUAD_LABEL_STYLE = "ordinal"` single-line toggle. Updated `backend.py`, `data.py`, `merge_rfu_backend_games.py`. 10 unit tests passing.

```
Opposition canonical names in:
  - backend.py:31 (PITCHERO_TO_GOOGLE_CANONICAL_NAMES - 30+ entries)
  - data.py:67 (PITCHERO_OPPOSITION_CANONICAL_NAMES - 100+ entries)
  - merge_rfu_backend_games.py:23 (EXTRA_RFU_OPPOSITION_CANONICAL_NAMES - 6+ entries)

Player name mappings in:
  - backend.py:31 (PITCHERO_TO_GOOGLE_CANONICAL_NAMES - 30+ entries)
  - data.py:199 (clean_name function with hardcoded dict)
```

**Impact:** If you need to add a new opposition or fix a name, you have to know which file to edit.

**Fix:** Move to JSON reference files:
- `python/reference/opposition_names.json`
- `python/reference/player_names.json`
- `python/reference/player_names_by_season.json`

### Issue 3: Unclear Data Flow with 8+ Intermediate Tables ✅
**Severity:** MEDIUM | **Effort to fix:** MEDIUM | **Impact:** MEDIUM

**Resolved:** Introduced explicit three-layer architecture. Added `int_game_candidates` (all source candidates with per-row conflict flags) and `int_games_resolved` (one winner per fixture with aggregated conflict summary). Both tables are persisted to DuckDB and exported for audit. `_build_games()` now consumes `int_games_resolved` to annotate canonical game rows with `_resolved_source`, `_resolved_winning_candidate_id`, `_resolved_conflict_count`. Documented all staging and intermediate tables in `python/backend.md`. 22 unit tests passing.

```
Raw → Clean → Staged → Raw concat → Canonical → Enriched → Export
 ↓      ↓       ↓          ↓           ↓          ↓         ↓
games_  pitcher pitchero  games_raw   games    (enriched) games.json
google_ games_  games_    + rfu       resolved
raw     clean   staged    + google    conflicts

Hard to answer: "What's in games_raw vs games_rfu vs games_staged?"
```

**Impact:** Difficult to debug data issues; easy to use wrong table.

**Fix:** Document each intermediate table's purpose and add automated checks.

### Issue 4: Complex Multi-Source Conflict Resolution ✅
**Severity:** MEDIUM | **Effort to fix:** HARD | **Impact:** MEDIUM

**Resolved:** Added a comprehensive contract comment to `SOURCE_PRECEDENCE` mapping all five pipeline locations where it governs resolution. Extracted the five quality-score weights in `_build_games()` into named local constants (`_W_SOURCE`, `_W_APPS`, `_W_URL`, `_W_SCORERS`, `_W_SCORE`) with explanations of why each weight is sized as it is. Fixed an orphaned comment fragment left by a prior edit. All existing comments in `_build_player_appearances()`, `_build_season_scorers()`, and `_apply_pitchero_supplemental_enrichment()` were already adequate.

```python
SOURCE_PRECEDENCE = {
    "google": 0,      # Highest priority
    "pitchero": 1,
    "rfu": 2          # Lowest priority
}
```

**Problem:** Precedence is explicit only in one place. Logic for resolving conflicts is spread across:
- `_build_games()` - Deduplicates by game_id, applies precedence
- `_build_player_appearances()` - Resolves aliases
- `_apply_pitchero_supplemental_enrichment()` - Backfills missing fields

**Impact:** Hard to understand which source wins in edge cases.

**Fix:** Consolidate conflict resolution logic; add comments explaining each rule.

### Issue 5: Post-Build Enrichment Complexity ✅
**Severity:** MEDIUM | **Effort to fix:** MEDIUM | **Impact:** LOW-MEDIUM

**Resolved:** Added full docstrings to all three functions involved in the post-build enrichment sequence:
- `_apply_pitchero_supplemental_enrichment()` — now explains *why* it must run after `build()` (optional artefact files that only exist after the full-scrape workflow), lists each sub-step with its required input file and skip condition, and explicitly states the no-overwrite guarantee.
- `rebuild_post_enrichment()` — now lists which tables are rebuilt and which are intentionally left intact, and why.
- `build_backend()` — new docstring describing the four-phase sequence (build → enrich → rebuild → export) so callers understand what each phase does and when it runs.

```python
BackendDatabase.build()
  ↓
_apply_pitchero_supplemental_enrichment()  [After build completes!]
  ├─ Manual URL overrides
  ├─ Candidate URL backfill from CSV
  ├─ Scorer backfill from CSV
  └─ Historic cache backfill from JSON
  ↓
rebuild_post_enrichment()
  ├─ Rebuild scorer tables
  ├─ Recalculate season_scorers
  └─ Re-export JSON
```

**Problem:**
- Why are these updates applied *after* build completes?
- What if enrichment fails midway?
- Required artifact files are implicit (not documented)

**Fix:** Either integrate into main build, or document enrichment requirements clearly.

### Issue 6: Frontend/Backend Code Duplication ✅
**Severity:** LOW-MEDIUM | **Effort to fix:** MEDIUM | **Impact:** LOW

**Resolved:** Eliminated the duplicate season normalisation implementation in `database-explorer.js` by replacing `normalizeSeasonValue()` with a thin wrapper over `normalizeSeasonLabel()` from `shared.js` (which is the canonical JS implementation, equivalent to Python’s `season_to_short_label()`). The wrapper preserves the passthrough-for-unknowns return semantics that the database explorer’s filter logic requires.

Added contract comments to all four JS normalisation functions documenting their Python equivalent and, where they intentionally differ, explaining why:
- `normalizeSeasonLabel()` (shared.js) — maps to `season_to_short_label()`
- `normalizeSeasonValue()` (database-explorer.js) — now delegates to `normalizeSeasonLabel` with a passthrough fallback
- `canonicalizeName()` (match-info.js) — intentionally different from `normalize_lookup_key()`: keeps hyphens/apostrophes for display-name matching
- `normaliseLogoKey()` (opposition-profile.js) — extends the `normalize_lookup_key()` pattern with club-suffix stripping for logo key resolution

```
JavaScript normalization in:
  - match-info.js:49         canonicalizeName()
  - opposition-profile.js:38 normaliseLogoKey()
  - squad-stats.js           Season normalization
  - player-gallery.js        Name parsing
  - shared.js:1034           normalizeSeasonLabel()

Duplicates Python logic but uses different algorithms!
Risk of divergence if logic changes.
```

**Fix:** Export Python normalization functions as JSON utilities or document contract precisely.

---

## Recommended Action Plan

### Phase 1: Documentation ✅
- [x] Create DATA_FLOW.md explaining complete pipeline
- [x] Create DATA_PIPELINE_AUDIT.md listing all issues
- [x] Create NORMALIZATION.md specifying canonical approach

### Phase 2: Normalization consolidation ✅
- [x] Create `python/utils/normalization.py` with canonical implementations
- [x] Create `python/utils/opposition.py` as single source of truth for opposition aliases
- [x] Add `OPPOSITION_SQUAD_LABEL_STYLE` toggle for ordinal/roman label format
- [x] Update `backend.py`, `data.py`, `league_data.py`, `merge_rfu_backend_games.py`, `sync_headshots.py`
- [x] Add unit tests (16 tests across normalization + opposition modules)

### Phase 3: Layered schema architecture ✅
- [x] Add `int_game_candidates` DDL + builder with per-row conflict flags
- [x] Add `int_games_resolved` DDL + builder selecting winner per fixture
- [x] Wire into `build()` and persist to DuckDB + JSON export
- [x] Consume in `_build_games()` — annotate canonical rows with `_resolved_*` audit columns
- [x] Document all staging + intermediate tables in `python/backend.md`
- [x] Add 6 unit tests for new tables (22 total passing)

### Phase 6: Frontend/backend contract ✅
- [x] Replace duplicate `normalizeSeasonValue()` in `database-explorer.js` with a wrapper over `normalizeSeasonLabel()` from `shared.js`
- [x] Add contract comment to `normalizeSeasonLabel()` in `shared.js` documenting Python equivalent and delegation note
- [x] Add contract comment to `canonicalizeName()` in `match-info.js` explaining intentional divergence from Python’s `normalize_lookup_key()`
- [x] Add contract comment to `normaliseLogoKey()` in `opposition-profile.js` explaining how it extends the Python base pattern

---

---

## Completion summary

All six issues are resolved. Key outcomes:

| Area | Before | After |
|------|--------|-------|
| Season normalization | 5+ implementations across backend.py, league_data.py, merge_rfu_backend_games.py, JS | 1 canonical Python function (`season_to_short_label`) + 1 JS function (`normalizeSeasonLabel`) |
| Opposition aliases | 130+ entries split across 3 Python files | Single `OPPOSITION_CANONICAL_NAMES` dict in `python/utils/opposition.py` |
| Normalization utilities | Duplicated in 5 Python files | `python/utils/normalization.py` with 6 shared functions |
| Intermediate table visibility | No audit trail between sources and canonical | `int_game_candidates` + `int_games_resolved` persisted to DuckDB + exported |
| Conflict resolution rules | Magic numbers, undocumented precedence | Named constants, `SOURCE_PRECEDENCE` contract comment, weight explanations |
| Post-build enrichment | No explanation of why it runs post-build or what it reads | Full docstrings on all three functions in the pipeline |
| JS/Python contract | Duplicate season logic with different algorithms | Wrapper + contract comments on all four JS normalization functions |
| Test coverage | 16 passing tests | 22 passing tests |

---

## Reference documents

- **Data flow and pipeline stages** → [python/DATA_FLOW.md](python/DATA_FLOW.md)
- **Audit findings** → [python/DATA_PIPELINE_AUDIT.md](python/DATA_PIPELINE_AUDIT.md)
- **Normalization function reference** → [python/NORMALIZATION.md](python/NORMALIZATION.md)
- **Backend table contract** → [python/backend.md](python/backend.md)
- **Schema DDL reference** → [python/schema_contract.sql](python/schema_contract.sql)

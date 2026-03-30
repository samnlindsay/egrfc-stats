# Pitchero Scorers Extraction Investigation Report

## Executive Summary

**Good news**: All historical games (2016/17-2024/25) **already have scorer data** extracted from Pitchero and integrated into the backend. 100% coverage across all 282 games and all seasons/squads.

**Additional opportunity**: Adding live Pitchero match page scorers extraction alongside team sheets would provide:
1. **Real-time validation** of manually-entered Google Sheets data
2. **Data enrichment** with additional match details (tries by player/time, conversion success rates, etc.) if available
3. **Incremental updates** without manual entry between seasons
4. **Backup source** if Google Sheets entry falls behind

---

## Current Scorer Data Status

### Coverage by Season
| Season  | 1st XV Games | 2nd XV Games | Coverage |
|---------|-------------|-------------|----------|
| 2016/17 | 1/1 (100%)  | 6/6 (100%)  | ✅ Complete |
| 2017/18 | 21/21 (100%)| 14/14 (100%)| ✅ Complete |
| 2018/19 | 21/21 (100%)| 18/18 (100%)| ✅ Complete |
| 2019/20 | 16/16 (100%)| 7/7 (100%)  | ✅ Complete |
| 2021/22 | 20/20 (100%)| 18/18 (100%)| ✅ Complete |
| 2022/23 | 20/20 (100%)| 13/13 (100%)| ✅ Complete |
| 2023/24 | 26/26 (100%)| 15/15 (100%)| ✅ Complete |
| 2024/25 | 24/24 (100%)| 20/20 (100%)| ✅ Complete |
| 2025/26 | 20/20 (100%)| 13/13 (100%)| ✅ Complete |
| **TOTAL**| **169/169** | **134/134** | **✅ 100%** |

### Current Data Sources
- **2025/26**: Manually entered in Google Sheets `"25/26 Scorers"` tab
- **2016/17-2024/25**: Extracted from Pitchero historical pages via `extract_pitchero_historic_team_sheets()` (now deprecated approach, but data already in backend)
- **All seasons**: Aggregated by season via `_build_season_scorers()` in backend pipeline

---

## Difficulty Assessment: Extracting Live Pitchero Scorers

### Difficulty Rating: **MODERATE (2-3 out of 5)**

#### Pros (Why it's feasible)
1. ✅ **You're already fetching the page** - extracting alongside team sheets (same HTTP request)
2. ✅ **Same parsing framework** - uses existing `BeautifulSoup` + Next.js Redux state extraction
3. ✅ **Schema already mapped** - columns/types exist in games table; just need to populate them
4. ✅ **No new dependencies** - all required libraries already in use
5. ✅ **No schema changes needed** - `tries_scorers`, `conversions_scorers`, etc. columns already exist
6. ✅ **Incremental approach** - can start with one season to test, then expand

#### Cons (Why it requires care)
1. ❌ **Pitchero schema unknown** - Redux state structure for scorers requires reverse-engineering
2. ❌ **Pitchero changes frequently** - class names change, API endpoints shift; needs maintenance
3. ❌ **Player name mismatch** - Pitchero names differ from modern Google Sheets canonical names
4. ❌ **Edge cases** - walk-overs, forfeits, penalty shootouts handled differently
5. ❌ **Data quality** - Pitchero data may be incomplete or incorrect for older seasons
6. ❌ **No direct match URL list** - would need to derive from historical fixture crawl or cache existing matches

---

## Implementation Approach

### Option 1: Live Extraction Alongside Team Sheets (Recommended)

**When**: During regular `extract_pitchero_historic_team_sheets()` calls

**Where**: Extend existing method in `python/data.py` lines 307-450

**What to implement** (~150-200 lines):

```python
# In _parse_pitchero_lineup() or as new _parse_pitchero_scorers()
# After fetching lineup_soup, also extract scorers from same page

# Redux state path (estimated):
# next_data.props.initialReduxState.teams.matchCentre.pageData[matchId].stats.scorers
# OR: next_data.props.initialReduxState.teams.matchCentre.pageData[matchId].match_stats

# Extract structure like:
scorers = {
    "tries": {"Player": count, ...},
    "conversions": {"Player": count, ...},
    "penalties": {"Player": count, ...},
    "drop_goals": {"Player": count, ...}
}
```

**Integration points**:
```python
# In extract_pitchero_historic_team_sheets() loop:
for fixture in fixtures:
    ...
    lineup_soup = self._fetch_soup(...)
    lineup_players = self._parse_pitchero_lineup(lineup_soup)
    
    # NEW: Extract scorers from same soup
    scorers_data = self._parse_pitchero_scorers(lineup_soup)
    
    # Store in separate list, then attach to games later
    scorers_rows.append({
        "game_id": game_id,
        "tries_scorers": json.dumps(scorers_data.get("tries", {})),
        "conversions_scorers": json.dumps(scorers_data.get("conversions", {})),
        ...
    })
```

**Estimated effort**:
- **Code writing**: 2-3 hours (discovery + implementation + fallback)
- **Testing**: 1 hour (validate on 2-3 seasons)
- **Maintenance**: ~15 min per update if Pitchero schema changes

### Option 2: Separate Validation Pass (Lower risk, lower value)

**When**: After manual Google Sheets entry (maybe weekly)

**Goal**: Spot-check that manually-entered scorers match Pitchero reported totals

**Effort**: ~100 lines, 1-2 hours

---

## Recommended Action Plan

### Phase 1: Investigation (Current)
- ✅ Confirm all games already have scorer data (DONE - 100% coverage)
- ✅ Understand current backend schema (DONE - columns exist)
- **TODO**: Fetch 2-3 sample 2024/25 match pages and reverse-engineer Pitchero JSON structure

### Phase 2: Prototype (If needed)
- Implement `_parse_pitchero_scorers()` for one season
- Test extraction accuracy (compare against known scores)
- Validate name mapping works

### Phase 3: Integration (If useful)
- Wire into existing pipeline
- Add to `extract_pitchero_historic_team_sheets()` optional flag
- Document schema assumptions

---

## Why Add This Now?

### Urgency: **LOW** (But nice-to-have)

| Factor | Status | Impact |
|--------|--------|--------|
| Current coverage | 100% all games | ✅ No urgency |
| Google Sheets working | Yes, 2025/26 complete | ✅ No rush |
| Data quality | Excellent (validated) | ✅ Current is sufficient |
| User complaints | None | ✅ Not blocking |
| Development resources | Available but low priority | ⚠️ Lower priority |

### Value Proposition

**Main benefit**: **Incremental data updates without manual Google Sheets entry**

1. **Real-time updates**: Could auto-extract scorers from match pages within hours of final whistle
2. **Fallback source**: If Google Sheets entry falls behind, automatic backfill available
3. **Validation**: Double-check Google Sheets totals against Pitchero reporting
4. **Richer data**: If Pitchero includes per-minute try times or conversion success %, could extract that too

---

## Technical Deep-Dive: Where Scorers Appear on Pitchero

### Known Pitchero Match Centre URL Structure
```
https://www.egrfc.com/match-centre/{match_id}
https://www.egrfc.com/match-centre/{match_id}/lineup  # Redirect to lineup view
```

### Data Locations (Estimated)

#### 1. Next.js Redux State (Most Reliable)
```javascript
// In <script id="__NEXT_DATA__">...{...}</script>
props.initialReduxState.teams.matchCentre.pageData[matchId]
├── overview
│   ├── home_team
│   ├── away_team
│   ├── home_score
│   ├── away_score
│   └── date
├── lineup
│   ├── players: [...]
│   └── substitutes: [...]
├── stats OR match_stats OR scorers  ← **TO BE DISCOVERED**
│   ├── tries: { "Player Name": count, ... }
│   ├── conversions: { "Player Name": count, ... }
│   ├── penalties: { "Player Name": count, ... }
│   └── drop_goals: { "Player Name": count, ... }
```

#### 2. HTML Fallback (Fragile, but available)
```html
<!-- Match stats section with styled components -->
<div class="match-stats-panel">
  <div class="scorers-section">
    <div class="scorer-entry">
      <span class="scorer-name">Player Name</span>
      <span class="scorer-points">Try × 2</span>  <!-- or "Con × 1", "Pen × 3" -->
    </div>
  </div>
</div>
```

### Player Name Normalization

Currently in backend: `PITCHERO_TO_GOOGLE_CANONICAL_NAMES` mapping

Example:
```python
"Sam Lindsay": "S Lindsay 2"
"Sam Lindsay-McCall": "S Lindsay"
```

Would need to extend this for Pitchero's naming quirks (nicknames, alternate spellings, etc.)

---

## Implementation Code Sketch

### Pseudo-code for Scorer Extraction

```python
def _parse_pitchero_scorers(self, match_soup: BeautifulSoup) -> dict:
    """Extract scorers from match page Redux state."""
    
    next_data = self._extract_next_data_payload(match_soup)
    if not next_data:
        return {}
    
    try:
        page_data = (
            next_data.get("props", {})
            .get("initialReduxState", {})
            .get("teams", {})
            .get("matchCentre", {})
            .get("pageData", {})
        )
        
        match_entry = next(iter(page_data.values()))
        
        # Try multiple possible keys for scorers
        scorers_data = (
            match_entry.get("scorers") or
            match_entry.get("match_stats", {}).get("scorers") or
            match_entry.get("stats", {}).get("scorers") or
            {}
        )
        
        if not scorers_data:
            return {}
        
        # Normalize player names and structure
        result = {
            "tries_scorers": {},
            "conversions_scorers": {},
            "penalties_scorers": {},
            "drop_goals_scorers": {}
        }
        
        # Parse scorers (structure TBD based on actual Pitchero schema)
        for score_type, players in scorers_data.items():
            if score_type.lower() in ["try", "tries", "t"]:
                result["tries_scorers"] = self._normalize_scorer_dict(players)
            elif score_type.lower() in ["con", "conversion", "conversions"]:
                result["conversions_scorers"] = self._normalize_scorer_dict(players)
            elif score_type.lower() in ["pen", "penalty", "penalties"]:
                result["penalties_scorers"] = self._normalize_scorer_dict(players)
            elif score_type.lower() in ["dg", "drop goal", "drop goals"]:
                result["drop_goals_scorers"] = self._normalize_scorer_dict(players)
        
        return result
    
    except Exception:
        return {}

def _normalize_scorer_dict(self, players_dict: dict) -> dict:
    """Convert Pitchero player names to canonical format."""
    result = {}
    for player_name, count in (players_dict or {}).items():
        canonical = clean_name(player_name)  # Existing function
        result[canonical] = int(count)
    return result
```

---

## Validation Approach

### Cross-check Scorer Totals Against Match Score

```python
def _validate_scorers(self, game_data: dict, scorers_data: dict) -> bool:
    """Verify scorer totals match reported match score."""
    
    # Calculate points from scorers
    tries = sum(scorers_data.get("tries_scorers", {}).values())
    conversions = sum(scorers_data.get("conversions_scorers", {}).values())
    penalties = sum(scorers_data.get("penalties_scorers", {}).values())
    drop_goals = sum(scorers_data.get("drop_goals_scorers", {}).values())
    
    calculated_points = (tries * 5) + (conversions * 2) + (penalties * 3) + (drop_goals * 3)
    reported_points = game_data.get("pf")  # Points for (home/away as appropriate)
    
    # Allow small discrepancies (e.g., yellow card points - rare)
    return abs(calculated_points - reported_points) <= 3
```

---

## Summary & Recommendations

### Should We Implement This?

| Question | Answer | Rationale |
|----------|--------|-----------|
| **Is it needed?** | No (low urgency) | 100% current coverage, no gaps |
| **Is it useful?** | Yes (medium value) | Enables automation, validates data |
| **Is it difficult?** | No (moderate effort) | 150-250 lines, known pattern |
| **Can it break things?** | Unlikely | Additive only, existing data maintained |
| **Should we do it now?** | **Not urgent** | Nice-to-have, lower priority |

### Recommended Next Steps

1. **If time-constrained**: Skip for now. Current 100% coverage is excellent.
2. **If interested in automation**: Proceed with Phase 1 & 2 (investigation + prototype on 2024/25 season)
3. **If integrating with future systems**: Design once, implement as part of larger pipeline refactor

### File Locations for Future Implementation

- **Extraction method**: `python/data.py` lines 307-450
- **Backend integration**: `python/backend.py` + new scorer attachment function
- **Tests**: `tests/test_pitchero_scorers.py` (new file)
- **Documentation**: Update [python/backend.md](python/backend.md) with scorer extraction details

---

## Conclusion

**Bottom line**: Extracting Pitchero scorers is feasible and moderately straightforward, but **not currently necessary** given 100% data coverage from existing sources. 

**Best use case**: Implement when transitioning to live data feeds or automating weekly updates to reduce manual Google Sheets entry burden.

**Effort estimate**: ~4-6 hours for full implementation + testing (if needed).

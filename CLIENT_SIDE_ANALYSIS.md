# Client-Side Data Aggregations & Transformations Analysis

## Executive Summary
The frontend performs **minimal aggregations** (mostly filtering/display logic). Most heavy lifting has been appropriately moved to the backend. Key areas where *any* processing happens:
- **Caching/deduplication** (player profiles)
- **Conditional filtering** of pre-computed Vega-Lite specs
- **Sorting/grouping** for display organization
- **Minor calculations** for thresholds and metric counting

NO significant mathematical aggregations are happening client-side—data arrives pre-aggregated from JSON exports.

---

## File-by-File Analysis

### 1. **season-summary.js** (176 lines)
**Status**: ✅ Minimal aggregation (display-only)

#### Backend Data Sources
- `data/backend/season_summary_enriched.json` (line 15)
  - Contains pre-computed season metrics per squad/game-type

#### Data Fetching
```javascript
// Line 15: Single fetch of enriched season summary
fetch('data/backend/season_summary_enriched.json')
```

#### Aggregations/Transformations
1. **Season deduplication** (lines 28-29)
   ```javascript
   const seasons = [...new Set(summaryData.map(row => row?.season).filter(Boolean))].sort().reverse()
   ```
   - Simple set deduplication + sorting (display only, no calculation)

2. **Player parsing** (lines 72-82)
   ```javascript
   const parsePlayers = (value) => {
       if (Array.isArray(value)) return value.filter(Boolean);
       if (typeof value === 'string' && value.trim()) {
           try {
               const parsed = JSON.parse(value);
               return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
           }
       }
   }
   ```
   - Parses JSON-serialized player arrays from backend (string→array)
   - **Could migrate**: No—backend should export player arrays directly, not JSON strings

3. **Metric formatting** (lines 149-165)
   ```javascript
   const displayValue = (elementId, value, format = 'number') => {
       switch (format) {
           case 'percentage':
               formatted = Math.round(value * 10000) / 100 + '%';
               break;
           case 'decimal':
               formatted = Math.round(value * 100) / 100;
               break;
       }
   }
   ```
   - Display formatting (rounding, percentage conversion)
   - **Status**: Pure presentation, appropriate client-side

#### Recommendations
- **Minor cleanup**: Backend should export player arrays as JSON arrays, not stringified JSON

---

### 2. **squad-stats.js** (801 lines)
**Status**: ⚠️ **MODERATE aggregation** (should move to backend)

#### Backend Data Sources
```javascript
// Lines 18-25: Three enriched dataset fetches
fetch('data/backend/squad_stats_enriched.json')
fetch('data/backend/squad_position_profiles_enriched.json')
fetch('data/backend/squad_continuity_enriched.json')
```

#### Key Aggregations

1. **Player count map deduplication** (lines 51-66)
   ```javascript
   function parsePlayerCountsMap(value) {
       if (value && typeof value === 'object' && !Array.isArray(value)) {
           return new Map(Object.entries(value).map(([player, count]) => [player, Number(count) || 0]));
       }
       if (typeof value === 'string' && value.trim()) {
           try {
               const parsed = JSON.parse(value);
               // Creates Map from Object
           }
       }
       return new Map();
   }
   ```
   - **Lines 51-66**: Converts stringified player count objects to Maps
   - **Why this exists**: Backend exports `playerCounts` as JSON strings within JSON (double serialization)
   - **Could migrate**: YES—backend should export as proper nested objects

2. **Squad stats data bucketing** (lines 68-88)
   ```javascript
   function buildSquadStatsDataFromEnriched(rows, gameTypeMode) {
       const bySeason = {};
       (rows || []).forEach(row => {
           const season = normalizeSeasonLabel(row?.season);
           const squad = row?.squad;
           const unit = row?.unit;
           if (!['1st', '2nd', 'Total'].includes(squad)) return;
           if (!['Total', 'Forwards', 'Backs'].includes(unit)) return;
           if (!bySeason[season]) bySeason[season] = createSquadSeasonBucket();
           const bucket = bySeason[season][squad];
           const countMap = parsePlayerCountsMap(row?.playerCounts);
           if (unit === 'Total') bucket.players = countMap;
           if (unit === 'Forwards') bucket.forwards = countMap;
           if (unit === 'Backs') bucket.backs = countMap;
       });
       return bySeason;
   }
   ```
   - **Lines 68-88**: Re-bucketing pre-computed data by season/squad/unit
   - **Filtering**: `gameTypeMode` parameter filters rows
   - **Purpose**: Restructuring data for local fast lookup
   - **Could migrate**: PARTIALLY—backend could export already-bucketed structure

3. **Position count filtering with threshold** (lines 111-141)
   ```javascript
   function buildSquadPositionCounts(selectedSeason, minimumAppearances) {
       const counts = getEmptySquadPositionCounts();
       (squadPositionProfilesEnrichedData || []).forEach(row => {
           const season = normalizeSeasonLabel(row?.season);
           const squad = row?.squad;
           const position = row?.position;
           if (season !== selectedSeason || row?.gameTypeMode !== mode) return;
           if (!['1st', '2nd'].includes(squad)) return;
           if (!SQUAD_POSITION_ORDER.includes(position)) return;
           const playerMap = parsePlayerCountsMap(row?.playerCounts);
           if (threshold <= 0) {
               counts[squad][position] = playerMap.size;
               return;
           }
           let playerCount = 0;
           playerMap.forEach(value => { if (value >= threshold) playerCount += 1; });
           counts[squad][position] = playerCount;
       });
   }
   ```
   - **Lines 111-141**: Counts players per position with **minimum appearances threshold**
   - **Aggregation**: `playerMap.forEach(value => { if (value >= threshold) playerCount += 1; })`
     - Counts players with ≥N appearances
   - **Could migrate**: YES—backend should pre-compute all threshold variants or compute dynamically

4. **Squad metric value extraction with threshold** (lines 200-218)
   ```javascript
   function getSquadMetricValue(unit, bucket, minimumAppearances = 0) {
       if (!bucket) return 0;
       const threshold = Math.max(0, Number(minimumAppearances) || 0);
       const countPlayersAboveThreshold = countMap => {
           if (!(countMap instanceof Map)) return 0;
           if (threshold <= 0) return countMap.size;
           let count = 0;
           countMap.forEach(value => { if (value >= threshold) count += 1; });
           return count;
       };
       if (unit === 'Forwards') return countPlayersAboveThreshold(bucket.forwards);
       if (unit === 'Backs') return countPlayersAboveThreshold(bucket.backs);
       return countPlayersAboveThreshold(bucket.players);
   }
   ```
   - **Lines 200-218**: Core aggregation—counts players where appearances ≥ threshold
   - **Called by**:
     - `renderSquadMetricCards()` (line 263, 268, 269)
     - `renderSquadStatsTable()` (line 291+)
     - `buildSquadSizeTrendRows()` (line 410+)

5. **Squad size trend rows construction** (lines 406-422)
   ```javascript
   function buildSquadSizeTrendRows(selectedSeason, minimumAppearances) {
       const seasons = getSortedSquadStatsSeasons(squadStatsData).slice().reverse();
       const rows = [];
       const toTrendValue = value => (value === 0 ? null : value);
       seasons.forEach(season => {
           const seasonData = squadStatsData?.[season];
           if (!seasonData) return;
           ['1st', '2nd'].forEach(squadKey => {
               const bucket = seasonData[squadKey];
               if (!bucket) return;
               const isSelected = season === selectedSeason;
               rows.push({ season, squad: squadKey, unit: 'Total', players: toTrendValue(getSquadMetricValue('Total', bucket, minimumAppearances)), isSelected });
               rows.push({ season, squad: squadKey, unit: 'Forwards', players: toTrendValue(getSquadMetricValue('Forwards', bucket, minimumAppearances)), isSelected });
               rows.push({ season, squad: squadKey, unit: 'Backs', players: toTrendValue(getSquadMetricValue('Backs', bucket, minimumAppearances)), isSelected });
           });
       });
       return rows;
   }
   ```
   - **Lines 406-422**: Transforms bucketed data into Vega-Lite row format
   - **Transformation**: Calls `getSquadMetricValue()` repeatedly to build chart data
   - **Could migrate**: PARTIALLY—backend could export trend-ready format

6. **Continuity trend rows building** (lines 448-459)
   ```javascript
   function buildContinuityAverageTrendRows() {
       const mode = getSquadStatsGameTypeMode();
       return (squadContinuityEnrichedData || [])
           .filter(row => row?.gameTypeMode === mode && ['1st', '2nd'].includes(row?.squad) && ['Total', 'Forwards', 'Backs'].includes(row?.unit))
           .map(row => ({
               season: normalizeSeasonLabel(row?.season),
               squad: row?.squad,
               unit: row?.unit,
               retained: Number(row?.retained) || 0
           }));
   }
   ```
   - **Lines 448-459**: Filter + map transformation (minimal)
   - **No calculations**, just reshaping

#### Recommendations
1. **MIGRATE to backend**: 
   - Threshold-based player counting (lines 111-141, 200-218)
   - Instead: Export `squad_stats_by_threshold.json` with pre-computed counts for thresholds 0-20
   
2. **FIX double serialization**:
   - Backend should export `playerCounts` as object/array, not JSON string

3. **Pre-format trend data**:
   - Backend could export chart rows directly instead of requiring `buildSquadSizeTrendRows()` transformation

---

### 3. **player-profiles.js** (804 lines)
**Status**: ✅ Mostly display logic, some deduplication

#### Backend Data Sources
```javascript
// Line 726: Single enriched dataset
fetch('data/backend/player_profiles_enriched.json')
```

#### Aggregations/Transformations

1. **Profile deduplication by name** (lines 10-27)
   ```javascript
   function dedupeProfilesByName(rows) {
       const byName = new Map();
       (Array.isArray(rows) ? rows : []).forEach(row => {
           const name = String(row?.name || '').trim();
           if (!name) return;
           const current = byName.get(name);
           const candidateAppearances = Number(row?.totalAppearances || row?.total_appearances || 0);
           const currentAppearances = Number(current?.totalAppearances || current?.total_appearances || 0);
           if (!current || candidateAppearances > currentAppearances) {
               byName.set(name, row);
           }
       });
       return Array.from(byName.values()).sort(compareBySurnameThenName);
   }
   ```
   - **Lines 10-27**: Deduplicates players by name, keeping record with most appearances
   - **Why**: Multiple squad records for same player (1st/2nd XV)
   - **Could migrate**: YES—backend should deduplicate, or use unified player key

2. **Scoring payload parsing** (lines 207-234)
   ```javascript
   function parseScoringPayload(value) {
       if (value && typeof value === 'object' && !Array.isArray(value)) {
           return {
               tries: Number(value.tries || 0),
               conversions: Number(value.conversions || 0),
               penalties: Number(value.penalties || 0),
               drop_goals: Number(value.drop_goals || 0),
               points: Number(value.points || 0)
           };
       }
       const raw = String(value || '').trim();
       if (!raw) {
           return { tries: 0, conversions: 0, penalties: 0, drop_goals: 0, points: 0 };
       }
       try {
           const parsed = JSON.parse(raw);
           return {
               tries: Number(parsed?.tries || 0),
               // ...
           };
       }
   }
   ```
   - **Lines 207-234**: Parses JSON-stringified scoring objects
   - **Why**: Double serialization in backend export
   - **Could migrate**: NO—fix backend export format

3. **Points summary formatting** (lines 178-192)
   ```javascript
   function formatPointsSummary(points, tries, conversions, penalties, dropGoals) {
       const totalPoints = Number(points || 0);
       const totalTries = Number(tries || 0);
       const totalConversions = Number(conversions || 0);
       const totalPenalties = Number(penalties || 0);
       const totalDropGoals = Number(dropGoals || 0);
       const components = [`${totalTries} tries`];
       if (totalConversions > 0) components.push(`${totalConversions} conversions`);
       if (totalPenalties > 0) components.push(`${totalPenalties} penalties`);
       if (totalDropGoals > 0) components.push(`${totalDropGoals} drop goals`);
       return `${totalPoints} (${components.join(', ')})`;
   }
   ```
   - **Lines 178-192**: Display formatting only

4. **Other positions parsing** (lines 194-205)
   ```javascript
   function parseOtherPositions(value) {
       if (Array.isArray(value)) return value.filter(Boolean).map(String);
       const raw = String(value || '').trim();
       if (!raw) return [];
       if (raw.startsWith('[')) {
           try {
               const parsed = JSON.parse(raw);
               return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [];
           }
       }
       return raw.split('|').map(s => String(s || '').trim()).filter(Boolean);
   }
   ```
   - **Lines 194-205**: Parses multiple formats (array, JSON string, pipe-delimited)
   - **Could migrate**: FIX backend to export consistent format

5. **Profile filtering & sorting** (lines 459-490)
   ```javascript
   const filteredBase = playerProfilesData
       .filter(profile => {
           const name = String(profile.name || '');
           const position = String(profile.position || 'Unknown');
           const squad = String(profile.squad || 'Unknown');
           if (selectedPlayers.size > 0 && !selectedPlayers.has(name)) return false;
           if (squadFilter !== 'All' && squad !== squadFilter) return false;
           if (positionFilter !== 'All' && position !== positionFilter) return false;
           if (activeOnly && !profile.isActive) return false;
           return true;
       });
   const filtered = sortedProfiles(filteredBase, sortMode);
   ```
   - **Lines 459-475**: Standard client-side filtering (appropriate)

6. **Position-based grouping** (lines 511-532)
   ```javascript
   function renderGroupedByPosition(profiles) {
       const groups = new Map();
       profiles.forEach(profile => {
           const sectionTitle = positionSectionTitle(profile?.position);
           if (!groups.has(sectionTitle)) groups.set(sectionTitle, []);
           groups.get(sectionTitle).push(profile);
       });
       return Array.from(groups.entries())
           .sort((a, b) => {
               const byRank = positionSectionRank(a[0]) - positionSectionRank(b[0]);
               // ...
           })
           .map(([sectionTitle, groupProfiles]) => {
               // build HTML
           })
   }
   ```
   - **Lines 511-532**: Grouping for display (no aggregation)

#### Recommendations
1. **Backend should deduplicate players** before exporting to `player_profiles_enriched.json`
2. **Fix serialization**: Export `otherPositions` and `scoring*` as proper objects/arrays, not JSON strings

---

### 4. **performance-stats.js** (265 lines)
**Status**: ✅ Minimal aggregation (display-only)

#### Backend Data Sources
```javascript
// Line 109: Season summary enriched export
fetch('data/backend/season_summary_enriched.json')
```

#### Aggregations/Transformations

1. **Red Zone metric extraction & transformation** (lines 13-38)
   ```javascript
   function buildRedZoneSpec(setPieceRows) {
       const rows = setPieceRows
           .map((row) => ({
               season: row.season,
               squad: row.squad,
               metric: 'Points per 22m entry',
               value: Number(row.avg_points_per_22m_entry),
           }))
           .concat(
               setPieceRows.map((row) => ({
                   season: row.season,
                   squad: row.squad,
                   metric: 'Tries per 22m entry',
                   value: Number(row.avg_tries_per_22m_entry),
               }))
           )
           .filter((row) => Number.isFinite(row.value));
   }
   ```
   - **Lines 13-38**: Transforms rows for Vega-Lite consumption
   - **Duplication**: Maps each row twice (once for points, once for tries metric)
   - **Could migrate**: Backend could export in this format directly

2. **Season ordering** (lines 40-47)
   ```javascript
   const orderedSeasons = Array.from(new Set(rows.map((row) => String(row.season)))).sort((a, b) => {
       const ay = parseInt(String(a).slice(0, 4), 10);
       const by = parseInt(String(b).slice(0, 4), 10);
       return ay - by;
   });
   ```
   - **Lines 40-47**: Deduplicates and sorts seasons (display only)

#### Recommendations
- Backend could export chart rows directly (with both metrics pre-expanded)
- Current approach is reasonable given Vega-Lite structure requirements

---

### 5. **shared.js** (454 lines)
**Status**: ⚠️ Moderate filtering/transformation (mostly appropriate, some could move)

#### Key Functions

1. **Season normalization** (lines 28-38)
   ```javascript
   function normalizeSeasonLabel(value) {
       if (!value) return null;
       const season = String(value).trim().replace('-', '/');
       const match = season.match(/^(\d{4})\/(\d{2}|\d{4})$/);
       if (!match) return null;
       const startYear = match[1];
       const endPart = match[2];
       const endSuffix = endPart.length === 4 ? endPart.slice(-2) : endPart;
       return `${startYear}/${endSuffix}`;
   }
   ```
   - **Lines 28-38**: Normalizes season format (e.g., "2024-25" → "2024/25")
   - **Why**: Multiple formats in data sources
   - **Could migrate**: Normalize at backend on export

2. **Season sorting** (lines 40-53)
   ```javascript
   function getSortedSquadStatsSeasons(dataBySeason) {
       const seasons = Object.keys(dataBySeason || {});
       if (seasons.length === 0) return [];
       return seasons.sort((a, b) => {
           const startA = parseInt(String(a).split('/')[0], 10);
           const startB = parseInt(String(b).split('/')[0], 10);
           if (!Number.isFinite(startA) || !Number.isFinite(startB)) return String(b).localeCompare(String(a));
           return startB - startA;  // Descending: newest first
       });
   }
   ```
   - **Lines 40-53**: Sorts seasons by start year (descending)
   - **Status**: Appropriate client-side

3. **Game type filtering** (lines 55-60)
   ```javascript
   function getAllowedGameTypes(mode) {
       if (mode === 'League + Cup') return new Set(['League', 'Cup']);
       if (mode === 'League only') return new Set(['League']);
       return null;
   }
   ```
   - **Lines 55-60**: Maps filter mode to game types
   - **Status**: Fine

4. **Chart spec filtering** (lines 76-106)
   ```javascript
   function filterChartSpecDataset(spec, predicate) {
       const clonedSpec = JSON.parse(JSON.stringify(spec));
       if (clonedSpec.datasets) {
           Object.keys(clonedSpec.datasets).forEach(key => {
               const rows = clonedSpec.datasets[key];
               if (Array.isArray(rows)) clonedSpec.datasets[key] = rows.filter(predicate);
           });
       }
       if (clonedSpec.data && Array.isArray(clonedSpec.data.values)) {
           clonedSpec.data.values = clonedSpec.data.values.filter(predicate);
       }
       return clonedSpec;
   }
   ```
   - **Lines 76-106**: Filters Vega-Lite spec data in-place
   - **Called by**: Squad stats, player stats pages
   - **Alternative**: Backend could export pre-filtered specs for each combination (expensive in storage)
   - **Current approach**: Reasonable for dynamic filtering

5. **League results iframe height calculation** (lines 136-199)
   ```javascript
   function updateLeagueResultsIframeHeight(iframe) {
       if (!iframe) return;
       try {
           const doc = iframe.contentDocument || iframe.contentWindow?.document;
           if (!doc) return;
           // [Complex SVG measurement logic...]
           const contentWidth = Math.max(
               svg?.getBoundingClientRect ? svg.getBoundingClientRect().width : 0,
               // ...
           );
           // [Scale calculation...]
       }
   }
   ```
   - **Lines 136-199**: Responsive iframe sizing (NOT data aggregation)
   - **Status**: Legitimate DOM measurement for UI layout

#### Recommendations
- Season normalization could happen at backend export time

---

## Summary: Aggregations by Category

### ✅ Appropriate Client-Side (No Change Needed)
- Display-level filtering (season, squad, position selects)
- Sorting for UI display
- HTML markup generation
- CSV deduplication (season names, positions)
- Vega-Lite chart filtering (dynamic ranges are expensive to pre-compute)

### ⚠️ Could Move to Backend (Performance Impact: Medium)
1. **Squad stats thresholds** (squad-stats.js, lines 111-141, 200-218)
   - Player count above N appearances
   - **Recommendation**: Export `squad_stats_thresholds.json` with 0-20 appearance thresholds pre-computed

2. **Trend row formatting** (squad-stats.js, lines 406-422)
   - Restructure backend export to match Vega-Lite format directly

3. **Red Zone metric expansion** (performance-stats.js, lines 13-38)
   - Backend should export metrics pre-expanded (points + tries rows)

### 🔧 Fix Data Format Issues
1. **Double serialization**:
   - `playerCounts` exported as JSON strings, then parsed client-side
   - `otherPositions` exported in mixed formats (array, string, JSON)
   - `scoring*` fields exported as JSON strings
   - **Fix**: Export as proper objects/arrays instead

2. **Season format normalization**:
   - Export seasons in consistent format from backend
   - Remove need for `normalizeSeasonLabel()` function

### Deduplication Needed
1. **Player profiles deduplication** (player-profiles.js, lines 10-27)
   - Backend should merge 1st/2nd XV records into single player profile before export

---

## Specific Line Numbers Reference

| File | Lines | Operation | Type | Move to Backend? |
|------|-------|-----------|------|-----------------|
| season-summary.js | 28-29 | Season set dedup | Filtering | No |
| season-summary.js | 72-82 | Player array parsing | Format fix | Yes |
| season-summary.js | 149-165 | Display formatting | Display | No |
| squad-stats.js | 51-66 | PlayerCounts string→Map | Format fix | Yes |
| squad-stats.js | 68-88 | Bucketing by season/unit | Restructuring | Partial |
| squad-stats.js | 111-141 | Position count threshold | Aggregation | Yes |
| squad-stats.js | 200-218 | Squad metric threshold count | Aggregation | Yes |
| squad-stats.js | 406-422 | Trend row construction | Restructuring | Partial |
| squad-stats.js | 448-459 | Continuity trend filtering | Filtering | No |
| player-profiles.js | 10-27 | Profile deduplication | Aggregation | Yes |
| player-profiles.js | 178-192 | Points summary format | Display | No |
| player-profiles.js | 194-205 | Other positions parsing | Format fix | Yes |
| player-profiles.js | 207-234 | Scoring payload parsing | Format fix | Yes |
| player-profiles.js | 459-490 | Profile filtering | Filtering | No |
| player-profiles.js | 511-532 | Position grouping | Grouping | No |
| performance-stats.js | 13-38 | Red Zone spec building | Restructuring | Partial |
| shared.js | 28-38 | Season normalization | Format fix | Yes |
| shared.js | 40-53 | Season sorting | Sorting | No |
| shared.js | 76-106 | Chart spec filtering | Filtering | No* |

*Dynamic filtering expensive to pre-compute; current approach is efficient.

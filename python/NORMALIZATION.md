# Data Normalization - Standards and Reference

This document specifies the canonical approach for each type of data normalization in the EGRFC stats pipeline.

## Overview

Data normalization is used to:
1. **Deduplicate** - Treat "Haywards Heath" and "Haywards Heath II" as variants of the same opposition
2. **Cross-match** - Resolve player names across sources ("Sam Lindsay" in Google vs "S Lindsay" in Pitchero)
3. **Standardize formats** - Season "2024-2025" → "2024/25"
4. **Generate keys** - Create lookup keys for dictionaries and database joins

---

## 1. Alphanumeric Key Normalization

**Purpose:** Create a case-insensitive lookup key stripped of special characters.

**Formula:** Lowercase + remove all non-alphanumeric characters

```python
def normalize_key(value: str) -> str:
    """Alphanumeric key for dictionary lookups and comparisons.
    
    'Haywards Heath II' → 'haywardshealthii'
    'Brighton & Hove' → 'brightonhove'
    'St. Leonards (CP)' → 'stleonardscp'
    """
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())
```

**Current Implementations (to be consolidated):**
- `backend.py:133` - `_normalise_key()`
- `data.py:154` - `_normalise_pitchero_key()`
- `merge_rfu_backend_games.py:47` - `_normalise_lookup_key()`

**Used for:** Opposition name lookups, team name comparisons

---

## 2. Season Format Standardization

**Purpose:** Ensure seasons are in consistent format across pipeline.

**Canonical Format:** `YYYY/YY` (e.g., "2024/25", "2023/24")
- Always short suffix (2 digits, not 4)
- Always forward slash, never dash
- Must be sortable (YYYY numeric comparison)

**Conversions:**

| Input Format | Example Input | → | Output |
|---|---|---|---|
| Slash short | `"2024/25"` | → | `"2024/25"` (already canonical) |
| Slash long | `"2024/2025"` | → | `"2024/25"` (strip to 2 digits) |
| Dash | `"2024-2025"` | → | `"2024/25"` (convert dash to slash) |
| Implied (RFU) | `"2024"` | → | `"2024/25"` (infer next year) |

```python
def normalize_season(value: str) -> str:
    """Convert any season format to canonical YYYY/YY.
    
    '2024/25' → '2024/25'
    '2024/2025' → '2024/25'
    '2024-2025' → '2024/25'
    '2024' → '2024/25'  (implied from context)
    """
    text = str(value or "").strip()
    if not text:
        return None
    
    # Already canonical?
    if re.match(r'^\d{4}/\d{2}$', text):
        return text
    
    # Convert slash-long format
    match = re.match(r'^(\d{4})/(\d{4})$', text)
    if match:
        return f"{match.group(1)}/{match.group(2)[-2:]}"
    
    # Convert dash format
    match = re.match(r'^(\d{4})-(\d{4})$', text)
    if match:
        return f"{match.group(1)}/{match.group(2)[-2:]}"
    
    return text  # Return as-is if unrecognized
```

**Current Implementations (to be consolidated):**
- `backend.py:260` - `_season_sort_key()` (sorts, not normalizes)
- `backend.py:267` - `_season_start_year()` (extracts start year)
- `league_data.py:477` - `_normalize_season()` (converts to dash format - WRONG)
- `league_data.py:510` - `season_to_short_label()` (converts to slash short)
- `merge_rfu_backend_games.py:23` - `_season_dash_to_backend()` (converts dash to slash)

**Decision:** Use `YYYY/YY` everywhere. Convert `league_data.py:477` to use forward slash instead of dash.

---

## 3. Team Name Normalization

**Purpose:** Standardize team/club names for comparison.

**Pattern:** Lowercase + normalize whitespace + remove alphanumeric characters

```python
def normalize_team_name(value: str) -> str:
    """Normalize team name for comparison.
    
    'Haywards Heath' → 'haywards heath'
    'East Grinstead RFC' → 'east grinstead rfc'
    'Brighton  &  Hove' → 'brighton and hove'  (with & expansion)
    """
    text = str(value or "").lower().strip()
    # Expand ampersands
    text = text.replace('&', ' and ')
    # Normalize whitespace
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()
```

**Current Implementations:**
- `data.py:271` - `DataExtractor._normalise_team_name()`
- `backend.py:2980` - Local function in `_build_canonical_games_from_rfu()`
- `merge_rfu_backend_games.py:37` - `_normalize_team_name()`

**Used for:** EGRFC team detection, comparison in conflict resolution

---

## 4. Opposition Name Canonicalization

**Purpose:** Map raw opposition names to canonical club names (strip team suffixes).

**Examples:**
- "Haywards Heath II" → "Haywards Heath"
- "Brighton 2s" → "Brighton II" (then strip to "Brighton")
- "Old Rutlishians RFC" → "Old Rutlishians"

**Two-step process:**
1. **Map to canonical form** using lookup dictionary
2. **Extract club name** (remove team suffix)

```python
def canonicalize_opposition_name(value: str, 
                                  mapping: dict[str, str] = None) -> str:
    """Map raw opposition name to canonical club name.
    
    Lookup dictionary maps _normalise_pitchero_key(value) → canonical name.
    Then extracts club name by removing team suffixes (II, 2nd, 3s, etc).
    """
    if not value or pd.isna(value):
        return value
    
    text = str(value).strip()
    
    # Step 1: Apply mapping dictionary if provided
    if mapping:
        key = normalize_key(text)
        text = mapping.get(key, text)
    
    # Step 2: Extract club name (remove team suffix)
    return extract_opposition_club_name(text)


def extract_opposition_club_name(value: str) -> str:
    """Extract club name by removing team suffixes.
    
    'Haywards Heath II' → 'Haywards Heath'
    'Brighton 2s' → 'Brighton'
    'Old Rutlishians RFC' → 'Old Rutlishians'
    'Croydon' → 'Croydon'  (no suffix to remove)
    """
    text = str(value or "").strip()
    if not text:
        return ""
    
    # Remove team suffix patterns
    # Matches: II, III, IV, V, VI, 1st, 2nd, 3rd, 4th, 5th, 2s, 3s, etc.
    text = re.sub(
        r'\s+(?:I{1,6}|IV|V|VI|' +  # Roman numerals
        r'\d+(?:st|nd|rd|th)?|' +    # Numeric with suffix
        r'\d+s|' +                    # Numeric with 's'
        r'XV|XXIII?)\s*$',            # XV suffixes
        '',
        text,
        flags=re.IGNORECASE
    )
    
    # Remove "RFC" suffix
    text = re.sub(r'\s*RFC\s*$', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def extract_opposition_team_number(value: str) -> int | None:
    """Extract team number from opposition name.
    
    'Haywards Heath II' → 2
    'Brighton 2s' → 2
    'Old Rutlishians' → None  (no team number)
    'Croydon III' → 3
    """
    text = str(value or "").strip()
    
    # Match roman numerals
    match = re.search(r'\b(I{1,6}|IV|V|VI)\b$', text, flags=re.IGNORECASE)
    if match:
        roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}
        return roman_map.get(match.group(1).upper())
    
    # Match numeric: "2nd", "3rd", "2s", etc.
    match = re.search(r'\b(\d+)(?:st|nd|rd|th)?s?\b$', text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return None
```

**Mapping Dictionaries:**

All opposition mappings should be consolidated into:

```python
# File: python/reference/opposition_names.json
{
  "brighton3": "Brighton III",
  "brighton2ndxv": "Brighton II",
  "bognor2": "Bognor II",
  # ... 100+ entries ...
  "papajohnsquarterfinalbromley": "Bromley",
  # ... RFU-specific extras ...
  "stleonardscinqueports": "St. Leonards CP",
  "horshamlions": "Horsham II"
}
```

**Load at startup:**

```python
# In backend.py or data.py __init__
_OPPOSITION_NAME_MAPPING = load_json('python/reference/opposition_names.json')
```

**Current Implementations:**
- `data.py:67-153` - `PITCHERO_OPPOSITION_CANONICAL_NAMES` dict
- `data.py:160` - `canonical_pitchero_opposition()` function
- `backend.py:243` - `_canonical_pitchero_opposition_name()` wrapper
- `backend.py:135-187` - Opposition parsing regex and helpers
- `merge_rfu_backend_games.py:23` - `EXTRA_RFU_OPPOSITION_CANONICAL_NAMES`

---

## 5. Player Name Normalization

**Purpose:** Standardize player names for lookup and matching.

### 5.1 Initial Surname Format

Convert full names to "Initial Surname" format for display in profiles.

```python
def player_initial_surname(name: str) -> str:
    """Convert full name to 'Initial Surname' format.
    
    'Sam Lindsay' → 'S Lindsay'
    'Christopher Pentney' → 'C Pentney'
    'Tom Halligey' → 'T Halligey'
    
    Note: Some players have duplicate names, resolved with _2 suffix:
    'Sam Lindsay' → 'S Lindsay 2'  (when second player exists)
    """
    if not name:
        return None
    
    tokens = str(name).strip().split()
    if len(tokens) < 2:
        return name
    
    initial = tokens[0][0].upper()
    surname = ' '.join(tokens[1:]).title()
    # Preserve apostrophes in names
    surname = surname.replace("'", "'")  # Normalize to curly quote
    
    return f"{initial} {surname}"
```

**Examples:**
- "Sam Lindsay" → "S Lindsay"
- "James Mitchell" → "J Mitchell"
- "Eoin O'Donoghue" → "E O'Donoghue"

### 5.2 Canonical Name Mapping

Map Pitchero names → Google Sheets names for deduplication.

```python
def canonical_player_name(name: str, 
                         mapping: dict[str, str] = None) -> str:
    """Map raw player name to canonical Google Sheets name.
    
    'Daniel Arnold' (Pitchero) → 'Dan Arnold' (Google)
    'Josh Brimmecombe' (Pitchero typo) → 'Josh Brimecombe' (Google)
    """
    if not name or pd.isna(name):
        return name
    
    text = str(name).strip()
    
    # Use provided mapping or load default
    if mapping is None:
        mapping = load_json('python/reference/player_names.json')
    
    return mapping.get(text, text)
```

### 5.3 Season-Aware Disambiguation

For ambiguous names across seasons (e.g., "S Lindsay" used by multiple people).

```python
def canonical_player_name_for_season(name: str, season: str,
                                     mapping: dict = None) -> str:
    """Resolve season-specific player aliases.
    
    'S Lindsay' in season 2020/21 → 'Sam Lindsay'
    'S Lindsay' in season 2021/22 → 'Sam Lindsay-McCall'
    """
    canonical = canonical_player_name(name, mapping)
    
    # Load season-specific aliases
    seasonal_map = load_json('python/reference/player_names_by_season.json')
    
    season_key = (str(name).strip(), season)
    return seasonal_map.get(season_key, canonical)
```

**Mapping Dictionaries:**

```json
// python/reference/player_names.json - Pitchero → Google mapping
{
  "Daniel Arnold": "Dan Arnold",
  "Christopher Pentney": "Chris Pentney",
  "Joshua Brimecombe": "Josh Brimecombe",
  // ... 30+ entries
}

// python/reference/player_names_by_season.json - Season-specific
{
  ["S Lindsay", "2020/21"]: "Sam Lindsay",
  ["S Lindsay", "2021/22"]: "Sam Lindsay-McCall",
  // ...
}
```

**Current Implementations:**
- `data.py:199` - `clean_name()` - converts to "Initial Surname"
- `backend.py:230` - `_canonical_player_name()` - maps Pitchero → Google
- `backend.py:237` - `_canonical_player_name_for_season()` - season-aware
- `backend.py:31` - `PITCHERO_TO_GOOGLE_CANONICAL_NAMES` dict

---

## 6. Game ID Generation

**Purpose:** Create unique, stable identifier for matches.

**Formula:** `YYYY-MM-DD_squad_opposition_club`

```python
def generate_game_id(date: date | str, squad: str, opposition: str) -> str:
    """Generate canonical game ID from match components.
    
    (2024-10-12, '1st', 'Haywards Heath II') 
    → '2024-10-12_1st_HaywardsHeath'
    
    Opposition is normalized to club name only (team suffix removed).
    """
    if isinstance(date, str):
        date = pd.to_datetime(date).date()
    
    date_str = date.strftime('%Y-%m-%d')
    squad_str = str(squad).strip()
    opposition_club = extract_opposition_club_name(opposition)
    
    # Replace spaces with underscores, remove slashes
    opposition_key = opposition_club.replace(' ', '_').replace('/', '')
    
    return f"{date_str}_{squad_str}_{opposition_key}"


def parse_game_id(game_id: str) -> dict | None:
    """Parse components from game ID.
    
    '2024-10-12_1st_HaywardsHeath' → {
        'date': date(2024, 10, 12),
        'squad': '1st',
        'opposition_club': 'Haywards Heath'
    }
    """
    match = re.match(r'^(\d{4}-\d{2}-\d{2})_([^_]+)_(.+)$', game_id)
    if not match:
        return None
    
    return {
        'date': pd.to_datetime(match.group(1)).date(),
        'squad': match.group(2),
        'opposition_club': match.group(3).replace('_', ' ')
    }
```

**Current Implementations:**
- `backend.py:220` - `_canonical_game_id()`
- `backend.py:226` - `_canonicalize_game_id()` - normalize legacy IDs
- `data.py:242` - Game ID construction in extraction

---

## 7. EGRFC Team Detection

**Purpose:** Determine if a team name refers to EGRFC.

```python
def is_egrfc_team(value: str) -> bool:
    """Check if team name refers to East Grinstead RFC.
    
    True for: 'East Grinstead', 'EGRFC', 'e grinstead', 'EG Men'
    False for: 'Brighton', 'Haywards Heath', etc.
    """
    text = normalize_team_name(value)
    
    aliases = [
        'east grinstead',
        'e grinstead',
        'eg men',
        'egrfc'
    ]
    
    return any(alias in text for alias in aliases)
```

**Used for:** Determining home/away in RFU data

---

## 8. Position and Unit Classification

**Purpose:** Standardize rugby positions and squad unit (Starter vs Bench).

```python
def get_position(shirt_number: int) -> str:
    """Get rugby position from shirt number.
    
    1 → 'Loosehead Prop'
    2 → 'Hooker'
    3 → 'Tighthead Prop'
    ...
    10 → 'Fly-half'
    ...
    16-29 → Based on position pattern
    """
    shirt_map = {
        1: 'Loosehead Prop',
        2: 'Hooker',
        3: 'Tighthead Prop',
        4: 'Lock',
        5: 'Lock',
        6: 'Blindside Flanker',
        7: 'Openside Flanker',
        8: 'Number 8',
        9: 'Scrum Half',
        10: 'Fly-half',
        11: 'Left Wing',
        12: 'Inside Centre',
        13: 'Outside Centre',
        14: 'Right Wing',
        15: 'Full Back',
        # Bench (16-29) repeat starter positions
        16: 'Loosehead Prop',
        17: 'Hooker',
        18: 'Tighthead Prop',
        # ... etc
    }
    return shirt_map.get(shirt_number, None)


def get_unit(shirt_number: int) -> str:
    """Get squad unit (Starter vs Bench) from shirt number.
    
    1-15 → 'Starter'
    16-29 → 'Bench'
    """
    num = int(shirt_number)
    if 1 <= num <= 15:
        return 'Starter'
    elif 16 <= num <= 29:
        return 'Bench'
    return None


def get_position_group(shirt_number: int) -> str:
    """Get position group (Forwards vs Backs).
    
    1-8 → 'Forwards'
    9-15 → 'Backs'
    16-23 → 'Forwards'  (bench)
    24-29 → 'Backs'  (bench)
    """
    num = int(shirt_number)
    if num in [1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18, 19, 20, 21, 22, 23]:
        return 'Forwards'
    elif num in [9, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29]:
        return 'Backs'
    return None
```

**Current Implementations:**
- `data.py:224-232` - Position/unit/group classification
- `league_data.py:141` - RFU position mapping
- `backend.py` - Various positions in queries

---

## Implementation Plan

### Step 1: Create Centralized Module

Create `python/utils/normalization.py` with all canonical functions above.

### Step 2: Consolidate Reference Data

Create JSON files:
- `python/reference/opposition_names.json` - Opposition mappings
- `python/reference/player_names.json` - Player name mappings
- `python/reference/player_names_by_season.json` - Season-specific aliases

### Step 3: Update All Imports

Replace in-file functions with imports:
```python
from python.utils.normalization import (
    normalize_key,
    normalize_season,
    normalize_team_name,
    canonicalize_opposition_name,
    extract_opposition_club_name,
    canonical_player_name,
    player_initial_surname,
    generate_game_id,
    is_egrfc_team,
    get_position,
    get_unit,
    get_position_group,
)
```

### Step 4: Update Tests

Add test cases for edge cases:
```python
def test_season_normalization():
    assert normalize_season("2024/25") == "2024/25"
    assert normalize_season("2024/2025") == "2024/25"
    assert normalize_season("2024-2025") == "2024/25"
    # ... etc

def test_opposition_parsing():
    assert extract_opposition_club_name("Haywards Heath II") == "Haywards Heath"
    assert extract_opposition_club_name("Brighton 2s") == "Brighton"
    assert extract_opposition_team_number("Haywards Heath II") == 2
    # ... etc
```

---

## Benefit Analysis

| Metric | Before | After |
|--------|--------|-------|
| Normalization function definitions | 8+ | 1 module |
| Lines of duplicate code | ~200 | ~0 |
| Files containing normalization logic | 5+ | 1 |
| Places to update if logic changes | 5+ | 1 |
| Time to debug normalization issue | 30-60 min | 5-10 min |
| New developer ramp-up time | High | Low (single reference) |

---

## Usage Examples

### Backend Example

```python
from python.utils.normalization import (
    canonicalize_opposition_name,
    canonical_player_name,
    normalize_season,
    generate_game_id
)

# Consolidate opposition names
opposition_canon = canonicalize_opposition_name("Haywards Heath II")

# Map player names
google_name = canonical_player_name("Daniel Arnold")

# Standardize season
canonical_season = normalize_season("2024-2025")

# Generate game ID
game_id = generate_game_id(date(2024, 10, 12), "1st", "Haywards Heath II")
```

### Frontend Example

Export normalization functions as JSON utilities:
```javascript
import { normalizeOppositionName, normalizeSeasonLabel } from './utils/normalization.js';

const canonicalName = normalizeOppositionName("Brighton 2s");
const season = normalizeSeasonLabel("2024-2025");
```

---

## Testing Strategy

1. **Unit tests** for each normalization function
2. **Integration tests** that trace data through full pipeline
3. **Regression tests** for known edge cases (player duplicates, opposition variants, season formats)
4. **Property-based tests** (fuzz testing with random inputs)

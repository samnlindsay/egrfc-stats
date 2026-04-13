# EGRFC Frontend House Style V2 Blueprint

## Purpose
This document translates prototype learnings into a practical design blueprint for the next site version.

It complements the existing [FRONTEND_HOUSE_STYLE_AND_MOBILE_PLAN.md](FRONTEND_HOUSE_STYLE_AND_MOBILE_PLAN.md) and adds interaction-level standards discovered during UX prototyping.

## Design Direction Summary
1. Keep the current EGRFC brand identity, typography direction (PT Sans Narrow), and data-first visual style.
2. Move from page proliferation to section-rich pages with clear jump navigation.
3. Make filter visibility adaptive by screen size: persistent on desktop, tucked behind offcanvas on mobile.
4. Treat filter scope transparency as non-negotiable: each chart/table container must display its own active filter chips.
5. Prioritise high-signal KPI framing (for example win rate) before detailed breakdowns.
6. Maintain one canonical prototype only (`ux-lab.html`) and evolve it across breakpoints rather than splitting concepts across multiple prototype pages.

## Core UX Decisions

### 1. Adaptive Filter Model
1. Mobile (under lg):
- Filters should default to hidden in an offcanvas drawer.
- A dedicated navbar button opens filters from anywhere on the page.
- Apply/reset actions must be obvious and one-tap.

2. Desktop (lg and up):
- Keep filters visible as either a top control bar or a compact cockpit panel.
- No offcanvas dependency for core filtering on large screens.

### 2. Per-Container Filter Context
1. Every analytical container (chart, table, list, KPI card group) should expose active filter chips.
2. Chips should be scoped to the filters that actually affect that element.
3. Global filter ribbon is still useful, but does not replace container chips.

### 3. Section-First Navigation
1. Long pages should use in-page rails/anchors to jump to sections.
2. Rail links should remain sticky where practical and switch to horizontal scrollers on narrow screens.
3. Fewer pages, more coherent section sequencing.

### 4. Terminology Standards
1. Use "Average Returners" as the default label for selection continuity metrics.
2. Keep continuity language in supporting text where needed, but lead with the clearer phrase.

### 5. Hero + KPI Pattern
1. Keep a strong visual hero at top of analytical pages.
2. Place a compact KPI strip below hero copy.
3. Include win rate as a standard top-level KPI where match data exists.

### 6. Focus/Inspect Pattern (Beta)
1. The previous focus modal should be treated as beta.
2. Keep it optional until a concrete use case is validated with real chart content.
3. Do not make focus mode a primary navigation path.

## Component Standards

### A. Navbar Filter Trigger
1. Include a `Filters` button in the navbar for pages using mobile offcanvas filters.
2. Show on mobile/tablet widths only.
3. Keep iconography and wording consistent site-wide.

### B. Desktop Filter Cockpit / Workspace Controlbar
1. Reuse shared spacing, border radius, and card surfaces.
2. Prefer segmented controls for 2-4 option toggles.
3. Use selects for long-option lists (season, player, opposition).

### C. Active Filter Chips
1. Provide two chip variants:
- Global active filters ribbon.
- Per-container scoped chips.
2. Chips should display key + value, not just labels.
3. Chip ordering should be stable: squad, season, game scope, threshold, toggles.

### D. Section Rail
1. Each section gets a clear id and short title.
2. Rail label should be task-oriented (for example "Average Returners", "Set Piece").
3. Keep rail interaction available on touch and keyboard.

## Single Prototype Iteration Requirements

### Canonical Prototype (ux-lab)
1. Keep hero + rail + section card architecture as the single design sandbox.
2. Desktop (lg+) uses visible cockpit controls.
3. Mobile (<lg) uses navbar-opened offcanvas filters.
4. Keep scoped chips on every analytical container.
5. Keep "Average Returners" terminology for continuity-focused analysis.
6. Keep win-rate as a standard headline KPI.

### Responsive Feature Matrix
1. Mobile:
- Offcanvas filter drawer opened from navbar.
- Horizontal rail links for section jump.
- Optional inspect mode treated as beta.
2. Desktop:
- Inline filter cockpit remains visible.
- Sticky side rail where space allows.
- Full section card grid density.

## Rollout Plan to Production Pages
1. Build shared CSS/JS primitives from prototype patterns:
- `mobile-filter-trigger`
- `panel-filter-chips`
- `renderScopedFilterChips()` helper
2. Pilot on one production analytics page with dense content (`squad-stats.html` suggested).
3. Validate mobile behavior at 360, 390, 414 and desktop at 1280+.
4. Apply to remaining pages incrementally.

### Page-by-Page Iteration Method
1. Work on real production pages in place, one page at a time.
2. For each page, complete one vertical slice:
- responsive filter behavior
- section spacing and hierarchy
- chart/table container pattern
- mobile fit at 360/390/414
3. Update this blueprint after each page pass with confirmed improvements and any adjustments needed.

### Chart Title Display Policy
1. Default policy: hide Vega/Altair chart titles at embed-time on production pages.
2. Page-level HTML headings/subheadings become the canonical source for titles and explanatory copy.
3. Do not require chart regeneration in `charts.py` just to change display titles.
4. Keep this behavior configurable in shared JS so individual pages can opt in or out.

## Acceptance Criteria
1. Mobile: filters are hidden by default and reachable from navbar.
2. Desktop: filters are visible without opening a drawer.
3. Every content container shows scoped active chips.
4. Win rate appears in top KPI layer where match outcome data exists.
5. Rail navigation reliably jumps to all major sections.
6. PT Sans Narrow remains the only prototype typography family.

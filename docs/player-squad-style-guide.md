# Player Stats and Squad Stats Style Guide

This guide captures the layout, interaction, and styling conventions used on the Player Stats and Squad Stats pages.

## 1) Page structure

- Use the shared page shell and page header pattern.
- Keep analysis pages in the two-part layout:
  - Analysis rail (left/top depending on viewport)
  - Main stacked chart content
- Keep section order and hierarchy explicit with clear headings and short explanatory copy.

## 2) Analysis rail

- Keep rail links as in-page anchors with stable section ids.
- Use the pinned-rail behavior already implemented in page JS (with placeholder + hysteresis).
- Support mobile by showing short labels from data-short and hiding long labels.

## 3) Hero block and metric cards

- Use the shared hero card language and color tokens.
- Keep one compact metadata line under hero title showing active scope (season, game type, squad/unit, threshold).
- Metric cards should remain concise and comparable side-by-side.

## 4) Filter architecture

- Keep filters inside offcanvas for dense analytical pages.
- Offcanvas controls are source-of-truth; chips are a summary and quick reopen affordance.
- Keep hidden native selects/ranges for state, with button groups as rich UI controls.
- Chips should use consistent label order:
  - Season
  - Game Type
  - Squad or Unit
  - Position (where relevant)
  - Min Appearances

## 5) Position picker (Player Stats)

- Use Bootstrap button groups for grouped controls.
- Top row is overall scope:
  - Total (primary weight/width)
  - Bench (secondary weight/width)
- Second row is two grouped columns:
  - Forwards group
  - Backs group
- Forwards and Backs groups should:
  - Keep stronger, color-coded borders
  - Keep subtle gradient headers
  - Maintain two-column layout on mobile
- Individual position buttons stay within their group containers.
- Bench selection maps to position Bench in data.

## 6) Chart panel pattern

- Use panel blocks for each chart area.
- Keep explanatory hints short and actionable.
- Avoid adding page-specific one-off containers when an existing chart panel or chart host class works.

## 7) Responsive conventions

- Put responsive overrides in css/responsive.css.
- Keep css/components.css focused on base component styles.
- For Player Stats and Squad Stats specifically:
  - Preserve compact spacing at <= 768px
  - Keep position picker groups in two columns on mobile
  - Keep rails and chips readable with reduced padding/font sizes

## 8) Bootstrap-first rule

- Prefer Bootstrap primitives where equivalent behavior exists:
  - btn-group / btn-group-sm for grouped controls
  - utility display classes for responsive text swaps
  - standard layout utilities before custom wrappers
- Add custom CSS only for branding, hierarchy, or behavior Bootstrap does not cover.

## 9) Chart responsibility split (Python vs JS)

- Default chart behavior and semantics belong in python/charts.py:
  - Label content logic
  - Unit naming
  - Sort order
  - Baseline mark behavior
- JS should primarily handle:
  - User-selected filtering
  - Param updates
  - Responsive rendering/layout tweaks
- Avoid post-render DOM surgery unless there is no feasible chart-spec alternative.

## 10) Aggregated MOTM chart conventions

- Unit rows are:
  - Forwards
  - Backs
  - Bench
- Bench row does not render in-segment text label.
- Position labels use multiline/compact fallback logic in charts.py for segment fit.

## 11) Naming and text conventions

- Default long label for threshold is Min Appearances.
- Mobile chip can use short label Min Apps.
- Keep button text concise and scannable.

## 12) Pre-commit checklist for new analytical pages

- Reused existing component classes before creating new ones
- Bootstrap primitives used where possible
- Responsive rules added to css/responsive.css, not css/components.css
- Chart defaults encoded in charts.py where feasible
- JS intervention limited to filtering, params, and view state
- Active filter chips match actual control scope
- Mobile rail, chips, and grouped controls remain usable at <= 768px

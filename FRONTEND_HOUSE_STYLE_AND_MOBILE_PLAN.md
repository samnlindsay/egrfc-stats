# EGRFC Frontend House Style and Mobile-Fit Plan

## Purpose
This document is the implementation baseline for frontend consistency and mobile usability improvements across HTML, CSS, and JS in the EGRFC stats site.

Use this as the starting point for a fresh AI/dev conversation and as the source-of-truth backlog for refactoring.

## Primary Goal
Create a consistent, maintainable house style where:
1. Shared UI patterns are implemented once and reused.
2. Inline style duplication is removed.
3. Charts and tables fit mobile screens without horizontal scrolling wherever practical.
4. Horizontal scrolling is allowed only for explicitly exempted wide-density visualizations (notably Team Sheets).

## Non-Goals
1. Redesigning brand identity, colors, or typography.
2. Replacing Vega/Vega-Lite.
3. Rewriting all page JS from scratch.

## Current Issues (Summary)
1. Extensive inline style duplication in page markup (containers, section spacing, card surfaces, navbar style).
2. Inconsistent implementation of similar functional patterns (headers, filters, panel spacing).
3. CSS complexity from overlapping rules and heavy use of !important.
4. Some likely dead or legacy code paths (unused selectors and duplicate logic patterns).
5. Mobile behavior is good in many places, but not yet policy-driven for chart/table fit.

## House Style Standard (Target)

### 1. Design Tokens and Color Rules
1. Use CSS variables in css/variables.css as the only source for brand/system colors.
2. Remove hard-coded repeated color literals where equivalent token exists.
3. Standardize red usage to one token-driven value unless intentional semantic split is documented.

### 2. Layout and Surface Rules
1. No inline styles for layout, spacing, borders, shadows, or typography.
2. Page container widths/padding defined by reusable utility classes.
3. Shared panel/card surface classes for white card, chart-surface card, and neutral info card.
4. Prefer Bootstrap layout utilities for spacing/alignment before adding custom CSS.

### 3. Header and Filter Composition
1. All pages use the same page header scaffold:
   - header text block
   - optional actions block
   - filters block
2. Filter controls use one standard markup pattern with input-group + label + control.
3. Avoid page-specific custom filter geometry unless there is a documented exception.

### 4. Collapsible Panels
1. Prefer Bootstrap-native expand/collapse primitives where they can replace custom behavior without UX regression.
2. Evaluate migration of custom chart-panel toggles to Bootstrap Accordion/Collapse as a Phase 1/2 decision gate.
3. Keep toggle color semantics:
   - primary: 1st XV
   - accent: 2nd XV
   - black: neutral/combined/supporting
4. Panel behavior should be managed by shared utilities and Bootstrap data attributes (minimize bespoke toggle JS).
5. If custom chart-panel implementation is retained, document why Bootstrap Collapse was not selected.

### 5. JS Behavior Conventions
1. Shared bootstrap-select lifecycle helper should be used everywhere.
2. Shared panel toggle initializer should be used everywhere.
3. Avoid duplicate per-page implementations for common interactions.
4. Keep page-specific JS focused on data shaping and rendering only.

## Mobile-Fit Policy (Highest Priority)

### Principle
For each page view, each chart and table should fit the viewport width without horizontal scrolling whenever practical.

### Allowed Exceptions
1. Team Sheets style dense matrices that are intrinsically wide.
2. Any chart/table where reducing width would break readability or correctness.
3. Exemptions must be explicitly tagged and documented in code comments/CSS class naming.

### Required Mobile Behavior by Component Type

#### A) Vega Charts
1. Default behavior:
   - container width 100%
   - chart scales to available width
   - preserve legibility (minimum font thresholds)
2. Preferred approach order:
   - use responsive container sizing
   - tune chart spec width/step for mobile
   - reduce axis label density or rotate labels
   - use facet/stacked panels instead of oversized single plots
3. Avoid relying on transform: scale as first resort.
4. If fallback scaling is used, ensure touch targets and text remain readable.

#### B) Data Tables
1. Default behavior: no horizontal scroll on mobile.
2. Preferred techniques:
   - hide non-critical columns on small screens
   - reflow rows into card/list format on small screens
   - shorten header labels and use tooltips for full descriptions
   - adjust numeric column widths and typography
3. If table must scroll horizontally, add explicit exempt class and rationale.

#### C) Filter Rows
1. Controls wrap cleanly and remain usable at small widths.
2. Labels should not force control truncation.
3. Tap targets remain accessible and consistent.

## Bootstrap-First Simplification Rules
1. Use Bootstrap utility classes for spacing, alignment, width, text, and borders where possible.
2. Use custom CSS only for:
   - brand-specific themes
   - bespoke chart/table components
   - behavior not expressible with Bootstrap utilities
3. Remove inline equivalents once utility/custom class is in place.
4. Keep HTML readable by avoiding long style attributes and deeply custom wrappers.

### Bootstrap Component Exploration (UX Improvement Track)
Use this track to selectively adopt Bootstrap components that improve consistency and accessibility while keeping the existing visual identity.

#### A) Collapse / Accordion (Highest Priority)
1. Candidate replacement for current custom chart-panel expand/collapse implementation.
2. Prototype with Bootstrap accordion semantics:
   - `accordion`, `accordion-item`, `accordion-button`, `accordion-collapse`
   - use `data-bs-parent` for one-open-at-a-time groups where needed
3. Success criteria:
   - equal or better keyboard accessibility and screen-reader behavior
   - less custom JS for toggling and accordion-group logic
   - color variants for 1st/2nd/neutral preserved through lightweight class wrappers
4. Migration options:
   - Full migration: replace chart-panel markup everywhere
   - Hybrid: keep existing visual classes, switch behavior to Bootstrap Collapse
   - No migration: retain current component with explicit rationale

#### B) Tooltip
1. Expand use of Bootstrap tooltips for abbreviated headers, dense table labels, and compact mobile labels.
2. Ensure tooltip content is supplementary (not the only place critical info exists).
3. Standardize init pattern in shared JS to avoid per-page duplication.

#### C) Carousel
1. Treat as optional and narrowly used (for curated, sequential content only).
2. Do not use for core analytics comparison where side-by-side visibility is important.
3. Candidate use cases:
   - mobile-only narrative highlights on home page
   - explanatory walkthrough cards

#### D) Offcanvas (Mobile Filter Drawer)
1. Candidate for moving dense filter rows into a slide-in offcanvas panel on narrow screens.
2. Benefit: reduces visual noise above charts on mobile; filter row is one tap away rather than consuming vertical space.
3. Candidate pages: `squad-stats`, `player-stats`, `lineout-performance`, `performance-stats` — any page where the filter row competes with chart visibility on a small screen.
4. Decision gate: adopt if it measurably reduces above-the-fold clutter on mobile without increasing confusion about how to reach filters.

#### E) Sticky Utilities (`sticky-top`, `position-sticky`)
1. Candidate for pinning the filter row while a user scrolls through multiple panels on a long page.
2. Benefit: avoids the need to scroll back to the top to change a filter.
3. Candidate pages: `squad-stats`, `performance-stats`, `lineout-performance`.
4. Constraint: must not cover chart content on small screens; test z-index at 360/390 widths.

#### F) Placeholder / Spinner (Loading States)
1. Use Bootstrap placeholders or spinners while JSON data is being fetched.
2. Prevents jarring layout shifts and communicates to users that content is loading.
3. Apply to any chart container that renders after an async fetch.

#### G) Toast / Alert (Status Feedback)
1. Use Bootstrap toasts for transient status messages (e.g. filter applied, no results found).
2. Use Bootstrap alerts for inline contextual messages (e.g. "No data available for this filter combination") replacing any ad-hoc text nodes.

#### H) Input Components
1. Expand use of Bootstrap input groups, switches, floating labels, and validation states where useful.
2. Keep selectpicker usage where multi-select/search UX is required.
3. Prefer standard native/select controls where selectpicker is not adding clear value.

#### I) Utilities and Typography
1. Replace repeated inline spacing and display styles with Bootstrap utilities (`d-*`, `gap-*`, `w-*`, `text-*`, `align-*`, `justify-*`).
2. Standardize heading rhythm and body copy scale with a small typography utility map per page type.
3. Keep PT Sans Narrow as the primary UI type direction unless a deliberate redesign is approved.

#### J) Decision Rules for Bootstrap Adoption
1. Adopt a Bootstrap component when it reduces custom code and improves accessibility/consistency.
2. Avoid adoption when it harms analytical readability, mobile fit, or brand clarity.
3. Every adoption should include:
   - before/after UX note
   - mobile behavior check (360/390/414)
   - impact on custom CSS/JS complexity

## Proposed Refactor Plan (Phased)

## Phase 0: Safety Baseline
1. Capture visual baseline screenshots for key pages in desktop + mobile widths.
2. Define target mobile breakpoints to test (at minimum 360, 390, 414, 768 widths).
3. Create a page-by-page inventory of:
   - inline styles
   - scroll-causing charts/tables
   - exemptions

Deliverable:
1. Baseline checklist and screenshot set committed under a docs or qa folder.

### Phase 0 Initial Inventory (Code-Inspection Baseline)
This inventory is the starting hypothesis before device-level validation. Status values below should be confirmed with screenshots at 360, 390, 414, and 768 widths.

Legend:
1. Likely Pass: expected to fit without horizontal scroll.
2. At Risk: likely overflow or readability compression on small screens.
3. Exempt Candidate: acceptable horizontal scrolling if justified and documented.

#### Page-by-Page Baseline

| Page | Component | Type | Initial Status | Exempt Candidate | Reason / Notes |
|---|---|---|---|---|---|
| index | Season Summary cards and strips | Mixed cards/charts | Likely Pass | No | Card-first layout likely to fit; validate last-ten strips at 360. |
| squad-stats | Overlap and trend charts | Charts | At Risk | No | Multiple inline chart containers and panelized visuals may exceed width depending on Vega specs. |
| squad-stats | League context charts | Charts | At Risk | No | Comparison/trend charts with richer axes often overflow without mobile spec tuning. |
| league-tables | 1st/2nd league tables | Tables | At Risk | No | Many numeric columns; likely needs responsive column strategy or card transform on small screens. |
| match-info | Filtered Matches table | Table | At Risk | No | 7-column table likely too wide on 360 unless reflow/hide-column strategy is added. |
| match-info | Match detail hero + team sheet view | Mixed | At Risk | No | Hero is responsive, but team-sheet-like data sections may still pinch depending on content density. |
| opposition-profile | Top opposition table | Table | At Risk | No | High column count and colored metric columns likely force horizontal scroll on narrow devices. |
| opposition-profile | Previous Matches table | Table | At Risk | No | 8-column row format likely too wide for small screens. |
| opposition-profile | Embedded team sheets panel | Chart/table-like | Exempt Candidate | Yes | Team-sheet matrix behavior is inherently wide; keep scroll intentional and isolated. |
| opposition-profile | Results and H2H charts | Charts | At Risk | No | Some likely fixable with responsive width + axis density adjustments. |
| player-stats | Appearances / points / captains / MOTM charts | Charts | At Risk | No | Chart containers are panelized, but spec widths/step may still overflow at 360. |
| player-info | Profile card grid | Card grid | Likely Pass | No | Card-based format should fit with stacked layout; verify filter row wrapping. |
| player-profile | Full profile panels and history table | Mixed | At Risk | No | History table likely needs column prioritization or stacked mobile format. |
| team-sheets | Team Sheets visualization | Chart/table-like | Exempt Candidate | Yes | Explicitly accepted wide-density view; preserve horizontal scrolling with improved affordance. |
| performance-stats | Lineout/scrum/red-zone summary charts | Charts | At Risk | No | Likely solvable with responsive chart policy; verify each panel output at 360/390. |
| lineout-performance | Breakdown tables (numbers/zone/jumper/thrower/play) | Tables | At Risk | No | Repeated dense tables in panel cards; likely need mobile table reflow strategy. |
| lineout-performance | Trend and breakdown charts | Charts | At Risk | No | High-detail analytical charts typically need mobile-specific width/axis handling. |
| database | Column guide table | Table | At Risk | No | Metadata table may overflow; likely needs column collapse or row-card format on small screens. |
| database | Main data explorer table | Table | Exempt Candidate (narrow scope) | Conditional | For arbitrary datasets, horizontal scroll may be unavoidable; if exempted, scope must be explicit and UX-supported. |

#### Known Exemption Candidates (Pre-Approved Direction)
1. Team Sheets primary view.
2. Team-sheet-like embedded views on other pages (for example, opposition team sheets).
3. Data Explorer main table only when filtering cannot reduce width sufficiently, and only with explicit justification.

#### Components Requiring Immediate Mobile Validation
1. All tables with 6 or more visible columns on mobile.
2. All chart containers that rely on intrinsic Vega width/step defaults.
3. All panels with inline overflow or fixed/min-width controls in header/filter rows.

### Phase 0 Screenshot and Validation Checklist

#### Required Viewports
1. 360x800
2. 390x844
3. 414x896
4. 768x1024

#### Capture Checklist Per Page
1. Top of page header + filters.
2. First visible chart/table panel expanded.
3. Widest chart or table state on page.
4. Any component with horizontal scroll present.

#### Pass/Fail Rules (Mobile-Fit)
1. Pass: no horizontal scrolling required to consume chart/table content.
2. Pass with Exemption: horizontal scrolling exists only on approved exempt components.
3. Fail: non-exempt chart/table requires horizontal scroll or truncates critical content.

#### Artifact Folder Structure (Suggested)
1. docs/qa/mobile-baseline/360/
2. docs/qa/mobile-baseline/390/
3. docs/qa/mobile-baseline/414/
4. docs/qa/mobile-baseline/768/
5. docs/qa/mobile-baseline/mobile-fit-matrix.csv

#### Matrix Fields for Tracking
1. page
2. component
3. viewport
4. horizontal_scroll (yes/no)
5. exempt (yes/no)
6. status (pass/fail)
7. fix_strategy (responsive-width/spec-tuning/table-reflow/column-priority/exempt)
8. notes

## Phase 1: Shared Foundations
1. Introduce reusable classes for:
   - page shell containers
   - section heading blocks
   - card/panel surfaces
   - common margins/padding currently inlined
2. Move duplicated navbar inline style to CSS class rule.
3. Consolidate overlapping filter rules and remove contradictory declarations.
4. Reduce !important usage where straightforward.
5. Run Bootstrap Collapse/Accordion spike and choose migration path for panel toggles.

Deliverable:
1. All pages use shared container and navbar style classes.
2. Noticeable reduction in inline styles and !important count.
3. Recorded decision on panel component strategy (Bootstrap collapse/accordion vs retained custom chart-panel).

## Phase 2: Header and Filter Unification
1. Normalize all page headers to one structural pattern.
2. Normalize all filter groups to the canonical markup pattern.
3. Replace one-off min-width/spacing hacks with shared responsive classes.
4. Ensure controls remain legible and touch-friendly on mobile.
5. Introduce shared tooltip initialization and usage conventions.

Deliverable:
1. Header/filter pattern consistent across all pages.
2. No page-specific inline filter geometry unless documented exception.
3. Shared UX utility layer for tooltips and common Bootstrap input behavior.

## Phase 3: Chart Mobile-Fit Pass
1. Audit every chart container for overflow at target mobile widths.
2. For each overflowing chart, apply preferred strategy order:
   - responsive width
   - spec tuning (step/axis/facet)
   - compact label strategy
   - controlled fallback scaling
3. Add explicit exemption class only where genuinely necessary.

Deliverable:
1. Mobile chart-fit matrix with pass/fail status by chart.
2. Horizontal scrolling removed for all non-exempt charts.

## Phase 4: Table Mobile-Fit Pass
1. Audit all tables for overflow at target mobile widths.
2. Convert high-density tables to mobile-friendly card/stack layouts where practical.
3. For tabular views that remain true tables, hide low-priority columns on mobile.
4. Add explicit exemptions for unavoidable wide tables.

Deliverable:
1. Mobile table-fit matrix with pass/fail status by table.
2. Horizontal scrolling removed for all non-exempt tables.

## Phase 5: JS Simplification
1. Replace duplicated selectpicker init/destroy/value logic with shared helper usage.
2. Remove duplicate panel toggle handling where shared initializer already exists.
3. Identify and remove legacy or unused script paths after verification.

Deliverable:
1. Lower JS duplication and clearer page-specific responsibilities.

## Phase 6: Cleanup and Guardrails
1. Remove dead CSS selectors and stale component rules not used in markup.
2. Remove dead/legacy JS files only after import/reference audit.
3. Add lint/check guidance for:
   - inline style prevention
   - color literal detection (prefer tokens)
   - mobile overflow regressions

Deliverable:
1. Maintainer guardrails to prevent regression.

## Suggested Work Order by Impact
1. Shared CSS foundations (fastest consistency gains).
2. Header/filter normalization.
3. Mobile chart-fit remediation.
4. Mobile table-fit remediation.
5. JS deduplication and dead code cleanup.

## Acceptance Criteria

### A) Consistency
1. No repeated inline navbar/container/panel styling in HTML.
2. Header/filter structures are uniform across pages.
3. Color usage is token-driven except documented exceptions.

### B) Mobile Usability
1. At 360 to 414 width, charts fit without horizontal scrolling except exempt classes.
2. At 360 to 414 width, tables fit without horizontal scrolling except exempt classes.
3. Exemptions are documented and intentional.

### C) Maintainability
1. Measurable reduction in inline style count.
2. Measurable reduction in !important usage.
3. Shared utilities used for common JS behaviors.

## QA Matrix Template
Use this table while implementing:

| Page | Component | Type (Chart/Table) | Mobile Fit (360) | Mobile Fit (390) | Exempt? | Notes |
|---|---|---|---|---|---|---|
| match-info | Filtered Matches | Table | Pass/Fail | Pass/Fail | Y/N | ... |
| team-sheets | Team Sheets grid | Chart/table-like | Pass/Fail | Pass/Fail | Y | Wide matrix exemption |
| ... | ... | ... | ... | ... | ... | ... |

## Implementation Notes for New Additions
1. Start from existing shared page-header and filter patterns.
2. Use Bootstrap utility classes first.
3. If custom class is needed, add it to shared stylesheet areas, not per-page inline style.
4. Test at mobile widths before considering feature complete.
5. If mobile horizontal scrolling is unavoidable, mark as explicit exemption and explain why.

## Fresh Conversation Kickoff Prompt
Use this prompt to start a new implementation conversation:

"Implement the plan in FRONTEND_HOUSE_STYLE_AND_MOBILE_PLAN.md in phased commits. Prioritize mobile fit so charts/tables do not horizontally scroll on small screens, except explicitly exempted wide-density views like Team Sheets. Start with shared CSS foundations and header/filter normalization, then perform chart/table mobile-fit passes with a QA matrix. Keep brand tokens and current visual language, reduce inline styles and !important usage, and centralize duplicated JS helper logic."

## Notes on Team Sheets Exception
Team Sheets is a valid exemption due to intrinsic matrix width and information density. It should still:
1. Use the cleanest possible overflow affordance.
2. Avoid accidental overflow in surrounding controls.
3. Be clearly identified as intentional horizontal-scroll behavior.

## Fresh Chat Handoff Pack (Final)

Use the block below as the opening prompt in a fresh chat.

### Copy/Paste Starter Prompt
You are implementing the plan in FRONTEND_HOUSE_STYLE_AND_MOBILE_PLAN.md for the EGRFC stats frontend.

Execution requirements:
1. Work in phased commits following Phase 0 through Phase 6.
2. Mobile-fit is the top priority: charts and tables must fit viewport width at 360/390/414 without horizontal scrolling, except explicit exemptions.
3. Team Sheets is an explicit exemption candidate and must keep intentional, well-signposted horizontal scrolling.
4. Explore Bootstrap-first replacements where they improve consistency and accessibility, including a decision spike for replacing custom chart panels with Bootstrap Collapse/Accordion.
5. Preserve current brand direction, color tokens, and overall visual language.
6. Reduce inline styles, reduce !important usage, and centralize duplicated JS helper logic.

Do this first:
1. Create/confirm a Phase 0 mobile baseline matrix and screenshot checklist artifacts.
2. Propose and implement the smallest safe shared CSS foundation changes for containers/navbar/header/filter structure.
3. Run the Collapse/Accordion spike and record decision with rationale.

Definition of done:
1. Non-exempt charts/tables pass mobile-fit checks.
2. Exemptions are explicitly documented.
3. Header/filter/panel patterns are standardized.
4. Duplication and specificity pressure are measurably reduced.

### Non-Negotiable Constraints for the Fresh Chat
1. Do not perform broad redesign.
2. Do not change data logic unless needed for UI/mobile fit.
3. Prefer incremental, verifiable refactors over large rewrites.
4. Every phase should end with a concise verification note.

### Required Deliverables in the Fresh Chat
1. Updated mobile-fit matrix with real pass/fail values per viewport.
2. Explicit exemption register with reasons.
3. Before/after summary for Bootstrap adoption decisions.
4. List of removed inline style patterns and removed/reduced !important rules.
5. Final changelog mapped to the phases in this document.

### Recommended Execution Sequence (Operational)
1. Phase 0 validation and artifact setup.
2. Phase 1 shared CSS foundations + panel decision spike.
3. Phase 2 header/filter unification and tooltip standardization.
4. Phase 3 chart mobile-fit remediation.
5. Phase 4 table mobile-fit remediation.
6. Phase 5 JS simplification.
7. Phase 6 dead code cleanup and guardrails.

### Quick Success Checks
1. At 360 width, each non-exempt chart/table is fully consumable without horizontal page-level scrolling.
2. Team Sheets scroll behavior is intentional, isolated, and visually signposted.
3. Bootstrap utilities/components replace repeated custom patterns where beneficial.
4. The codebase is simpler to extend for new pages/components while preserving house style.

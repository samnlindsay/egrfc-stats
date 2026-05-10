---
applyTo: "*.html,*.css,*.js,python/*.py"
---

# EGRFC Custom Agent Standards (Draft)

## Core goals
- Prefer shared utilities and existing patterns over new one-off classes/functions.
- Remove dead code when touching nearby areas.
- Keep Bootstrap-first markup where Bootstrap utilities/components are sufficient.
- Keep chart shaping in Python/Altair when possible; avoid avoidable JS spec mutation.

## HTML standards
- Avoid inline styles unless values are truly dynamic at runtime.
- Prefer Bootstrap utility classes (`mb-*`, `mt-*`, `d-*`, `justify-content-*`, `gap-*`) for spacing/layout.
- Keep page shell and hero/filter patterns consistent with existing pages.
- Do not introduce a second icon library when Bootstrap Icons can cover the need.

## CSS standards
- Reuse design tokens from `css/variables.css`.
- Reuse existing component classes before adding new selectors.
- Scope interaction styles to explicit variants (e.g. interactive cards) instead of global element overrides.
- Remove selectors with no in-repo usage when discovered.
- Keep responsive rules grouped by breakpoint to avoid fragmented overrides.

## JavaScript standards
- Keep page-specific logic in that page module; shared cross-page behavior belongs in `js/shared.js`.
- Remove files no longer referenced by HTML pages.
- Favor declarative chart specs and filter params; avoid manual post-processing unless required.
- Keep script includes minimal: `nav-layout.js`, `shared.js`, and the page script.

## Python chart pipeline standards
- Prefer generating clean Vega-Lite JSON directly from `python/charts.py`.
- Do not add HTML/CSS post-processing hacks for chart output.
- Keep embed options centralized in `python/chart_helpers.py`.
- If frontend repeatedly patches chart structure in JS, move that logic upstream into chart generation.

## Naming and structure
- Use page-to-file naming that reflects user-facing navigation labels.
- For any route rename, keep a compatibility redirect page to avoid broken links.
- Keep one primary JS module per page and avoid legacy duplicates.

## Validation checklist for agent changes
- Confirm referenced JS files are loaded by at least one HTML page.
- Confirm new CSS selectors have an in-repo usage site.
- Confirm no duplicate HTML attributes were introduced.
- Run `git diff --name-only` and scan for accidental broad edits.

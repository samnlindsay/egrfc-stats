# Player Report Generation

## Download From A Player Profile

Each Player Profile has a **Download PDF** button. The browser generates the report
on demand from the selected player's loaded data and chart specifications, then
downloads `<player-slug>-report.pdf`. No pre-generated PDFs, Python process, or
server-side PDF endpoint are required for this feature on GitHub Pages.

The browser first builds report HTML using the Python report's structure and the
shared `css/player-report.css` stylesheet. It includes the branded photo header,
career summaries, position bar, print-specific timeline and League History charts,
grouped playing record, season and scoring summaries, teammate rankings, and
conditional scrum, jumping and throwing records. Historic estimates retain their
asterisk and footnote. Match history is not limited by the page's search or pagination.

Position-specific teammate sections require at least five documented career starts
in that position. Grouped partner sections (such as Front Row) require five starts
across the unit. Positional rankings count starts only; the Overall ranking continues
to include all appearances. The same rule applies to Python-generated reports.

`js/player-report-html.js` loads the additional backend JSON sources on demand;
`js/player-report-charts.js` applies the Python report's print chart transformations.
Pinned jsPDF and html2canvas modules are lazy-loaded from jsDelivr. An internet
connection is required for the first download. The button shows generation progress
and can be retried on failure. HTML pages are split at section and table-row boundaries,
with repeated table headers, then captured into the PDF. Browser PDF pages are images;
the Python/Chrome export below retains native PDF text. Pagination can differ between
the two renderers, but they share report styling rather than separate PDF themes.

Run report regression checks with:

```bash
node --test tests/test_player_report.mjs
python -m unittest tests.test_player_report_set_piece
```

## Python Reports

`python/reports.py` generates branded player reports from the canonical DuckDB backend.

## Requirements

- The project virtual environment at `.venv/`.
- `vl-convert-python` for rendering Vega-Lite chart specifications.
- Google Chrome for PDF export. Set `CHROME_BIN` if Chrome is installed at a non-standard path.
- A current `data/egrfc_backend.duckdb`.

## Generate A Report

Run from the project root:

```bash
./.venv/bin/python python/reports.py player "Tim Morris"
```

PDF generation is the default. The command also writes the intermediate HTML file under `reports/generated/player/`.

To generate HTML only:

```bash
./.venv/bin/python python/reports.py player "Tim Morris" --format html
```

Optional arguments:

- `--db-path PATH` selects an alternate DuckDB database.
- `--output PATH` selects the report output path.
- `--top-n N` controls the number of common teammates shown.

## Outputs

Default player outputs are:

```text
reports/generated/player/<player-slug>.html
reports/generated/player/<player-slug>.pdf
```

The report reuses the website Vega-Lite specifications for the career timeline and League History chart. Player-specific filtering, labels, legends, and print layout are applied during report generation.

## Validation

Compile the report generator before exporting:

```bash
./.venv/bin/python -m py_compile python/reports.py
```

For a generated report, verify that the HTML contains the expected player and that the PDF begins with `%PDF-`. The PDF exporter uses a fresh temporary PDF before replacing the target file.

## Notes

- Data updates require access to the canonical backend database; report generation does not refresh Google Sheets or RFU data.
- Generated reports are local artifacts and should be reviewed before being added to a commit.
- If DuckDB reports a lock, use a read-only connection for inspection or pass `--db-path` to an alternate database.

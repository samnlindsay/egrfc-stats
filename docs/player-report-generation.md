# Player Report Generation

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

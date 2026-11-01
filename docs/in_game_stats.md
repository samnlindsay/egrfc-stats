# In-game statistics source

The externally maintained [statistics workbook](https://docs.google.com/spreadsheets/d/1anXzVX7sC1Z5fFJIKLttb2vqsKaruSLY/edit)
is an Excel file (`Stats.xlsx`) hosted on Google Drive, not a native Google Sheet.
The Sheets API/gspread cannot read it directly. `python.in_game_stats` downloads
an in-memory copy through the Drive API and reads it with openpyxl. It does not
convert, edit, or change sharing on the source.

## Access

The existing service account in `python/client_secret.json` already has download
access (verified against the live source). Credentials remain untracked. The
loader requests only the `drive.readonly` OAuth scope. This does not grant new
permissions: a workbook owner must share any replacement file with the service
account's `client_email` as Viewer. Do not publish the workbook or commit keys.
Paths passed with `--credentials` are relative to the calling directory; the
default credential path is resolved relative to the Python module.

## Fetch and export

Install project dependencies in your chosen Python environment, then from the
repository root run:

```bash
python -m python.in_game_stats
python -m python.in_game_stats --game-id YOUR_CANONICAL_GAME_ID
```

Options: `--credentials PATH`, `--file-id DRIVE_FILE_ID`, `--output-dir PATH`.
Outputs default to the ignored `reports/generated/in_game_stats/` directory:

- `raw_workbook.json`: cell values, worksheet titles and merged ranges.
- `in_game_stats.json`: source metadata, fetch time, warnings and normalized tables.
- `summary.csv`, `possession.csv`, `events.csv`: the same normalized records.

Each normalized row includes the source file ID, worksheet, one-based row number
and optional `game_id`. Missing values remain null; numeric zero is preserved.
The command overwrites its output files on each run. Use distinct output
directories to retain historical snapshots. Date cells are exported as strings;
formulas use Excel's stored results, not recalculated values.

## Observed structure

- **Stats Summary**: three vertically stacked blocks, `Full Game`, `Halves`,
  `Quarters`. Each has a `Name` header followed by team/period columns and `Total`.
  Named rows are metric counts; subsequent `+`, `-` and `Miss` rows belong to the
  preceding metric. The normalized table keeps metric, outcome, team, period,
  section and count separate. Total rows have `is_total=true`, no team and
  `period=all_periods`. Totals repeat across sections; never sum all sections or
  combine totals with team records.
- **Possession & Time**: introductory rows, then a `Measure` header. Rows measure
  team possession/territory, ball out of play and total ball in play. Columns
  represent full game, halves and quarters. `MM:SS` values become integer seconds,
  including durations above 59 minutes. Measure and period labels are preserved.
- **Events**: one header row (`Code`, `Labels`, `Start`, `End`, `Notes`, `Clip ID`,
  `Team`), then individual tagged video clips. Start/end values are retained as
  seconds; their difference is a **clip duration**, not ruck speed or time in play.
  Blank tackle labels are valid and are not automatically classified as negative
  or missed tackles. Events are not necessarily globally sorted by time.

Observed metrics: Scrum, Ruck Speed, Tackles, Red Zone Entry Def, Red Zone Entry,
Lineout. Observed team names: EG and Horsham. No match date or squad is supplied,
so canonical match linking is explicit rather than inferred from the opposition.
Meanings of `+`/`-`, the thresholds used for ruck speed, and the definition of red
zone outcomes still require confirmation from the person tagging the footage.
Rounded possession durations may not sum exactly across periods.

## Analysis

```python
import pandas as pd
from python.in_game_stats import InGameStatsSource, parse_workbook

stats = parse_workbook(InGameStatsSource().read_workbook())
events = pd.DataFrame(stats["events"])
summary = pd.DataFrame(stats["summary"])
full_game = summary[(summary.section == "Full Game") & ~summary.is_total]
print(events.groupby(["team", "code", "label"], dropna=False).size())
```

This is a standalone ingestion step. It does not rebuild the canonical backend
or replace existing statistics. Unexpected extra worksheets are reported;
missing/empty required tables or malformed values raise errors with source
locations. Do not treat the summary blocks as independent matches.

Offline tests: `python -m unittest discover -s tests -p 'test_in_game_stats.py'`.
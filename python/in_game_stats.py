"""Read the externally maintained in-game statistics workbook without modifying it."""

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Union

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from openpyxl import load_workbook


DEFAULT_FILE_ID = "1anXzVX7sC1Z5fFJIKLttb2vqsKaruSLY"
DEFAULT_CREDENTIALS = Path(__file__).with_name("client_secret.json")
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class InGameStatsSource:
    """Access the Excel source through Drive using a read-only service account."""

    def __init__(
        self,
        credentials_path: Union[str, Path] = DEFAULT_CREDENTIALS,
        file_id: str = DEFAULT_FILE_ID,
        session: Optional[AuthorizedSession] = None,
    ) -> None:
        """Use existing project credentials, or an injected authenticated session."""
        self.file_id = file_id
        if session is None:
            credentials = Credentials.from_service_account_file(
                str(credentials_path), scopes=[DRIVE_READONLY_SCOPE]
            )
            session = AuthorizedSession(credentials)
        self.session = session

    def metadata(self) -> Dict[str, Any]:
        """Return the source name, format and download permission."""
        response = self.session.get(
            f"https://www.googleapis.com/drive/v3/files/{self.file_id}",
            params={
                "fields": "id,name,mimeType,capabilities(canDownload)",
                "supportsAllDrives": "true",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def read_workbook(self) -> Dict[str, Any]:
        """Download an in-memory snapshot, preserving row and column positions."""
        metadata = self.metadata()
        if metadata["mimeType"] != XLSX_MIME_TYPE:
            raise ValueError(f"Expected an Excel workbook, got {metadata['mimeType']}")
        if not metadata.get("capabilities", {}).get("canDownload", False):
            raise PermissionError("The service account cannot download this workbook.")
        response = self.session.get(
            f"https://www.googleapis.com/drive/v3/files/{self.file_id}",
            params={"alt": "media", "supportsAllDrives": "true"},
            timeout=60,
        )
        response.raise_for_status()
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        try:
            return {
                "source": metadata,
                "worksheets": [
                    {
                        "title": worksheet.title,
                        "merged_ranges": [str(area) for area in worksheet.merged_cells.ranges],
                        "rows": [list(row) for row in worksheet.iter_rows(values_only=True)],
                    }
                    for worksheet in workbook.worksheets
                ],
            }
        finally:
            workbook.close()


def _text(value: Any) -> str:
    """Normalize cell whitespace without assigning meaning to source labels."""
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float:
    """Require finite numeric data rather than silently replacing missing values."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite numeric value: {value!r}")
    return number


def _duration_seconds(value: Any) -> int:
    """Parse the source's minutes:seconds format, including minutes above 59."""
    match = re.fullmatch(r"(\d+):([0-5]\d)", _text(value))
    if match is None:
        raise ValueError(f"Expected minutes:seconds, got {value!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def parse_workbook(
    snapshot: Dict[str, Any], game_id: Optional[str] = None
) -> Dict[str, Any]:
    """Normalize the three observed layouts into separate analysis-ready tables."""
    tables: Dict[str, Any] = {"summary": [], "possession": [], "events": []}
    warnings = []
    recognized = set()
    for sheet in snapshot["worksheets"]:
        title = sheet["title"]
        if title not in {"Stats Summary", "Possession & Time", "Events"}:
            warnings.append(f"Unparsed worksheet: {title}")
            continue
        recognized.add(title)
        headers = []
        section = None
        metric = None
        for row_number, row in enumerate(sheet["rows"], 1):
            cells = [_text(value) for value in row]
            if not any(cells):
                continue
            first = cells[0]
            origin = {
                "source_file_id": snapshot["source"]["id"],
                "worksheet": title,
                "source_row": row_number,
                "game_id": game_id,
            }
            try:
                if title == "Stats Summary":
                    if first in {"Full Game", "Halves", "Quarters"}:
                        section, metric, headers = first, None, []
                        continue
                    if first == "Name":
                        headers = cells
                        continue
                    if not headers or section is None:
                        raise ValueError("Summary data has no section/header")
                    outcome = first if first in {"+", "-", "Miss"} else None
                    if outcome is None:
                        metric = first
                    if metric is None:
                        raise ValueError("Outcome has no parent metric")
                    for column, header in enumerate(headers[1:], 1):
                        if not header or column >= len(cells) or not cells[column]:
                            continue
                        team, period = header, "full_game"
                        if section == "Halves" and header != "Total":
                            match = re.fullmatch(r"(.+) (1st|2nd)", header)
                            if match is None:
                                raise ValueError(f"Unknown half header: {header}")
                            team, half = match.groups()
                            period = {"1st": "first_half", "2nd": "second_half"}[half]
                        elif section == "Quarters" and header != "Total":
                            match = re.fullmatch(r"(.+) Q([1-4])", header)
                            if match is None:
                                raise ValueError(f"Unknown quarter header: {header}")
                            team, quarter = match.groups()
                            period = f"quarter_{quarter}"
                        tables["summary"].append({
                            **origin, "section": section, "metric": metric,
                            "outcome": outcome, "team": None if header == "Total" else team,
                            "period": "all_periods" if header == "Total" else period,
                            "is_total": header == "Total", "source_header": header,
                            "count": _number(cells[column]),
                        })
                elif title == "Possession & Time":
                    if first == "Measure":
                        headers = cells
                        continue
                    if not headers:
                        continue
                    for column, header in enumerate(headers[1:], 1):
                        if not header or column >= len(cells) or not cells[column]:
                            continue
                        tables["possession"].append({
                            **origin, "measure": first, "period": header,
                            "duration_text": cells[column],
                            "duration_seconds": _duration_seconds(cells[column]),
                        })
                else:
                    if first == "Code":
                        headers = cells
                        if not {"Code", "Labels", "Start", "End", "Notes", "Clip ID", "Team"}.issubset(headers):
                            raise ValueError("Missing required event columns")
                        continue
                    if not headers:
                        raise ValueError("Events have no header")
                    values = dict(zip(headers, cells))
                    start = _number(values["Start"])
                    end = _number(values["End"])
                    if start < 0 or end < start:
                        raise ValueError("Invalid event clip interval")
                    tables["events"].append({
                        **origin, "code": values["Code"], "label": values["Labels"] or None,
                        "team": values["Team"] or None, "start_seconds": start,
                        "end_seconds": end, "clip_duration_seconds": round(end - start, 6),
                        "notes": values["Notes"] or None, "clip_id": values["Clip ID"] or None,
                    })
            except (ValueError, KeyError) as error:
                raise ValueError(f"{title}, row {row_number}: {error}") from error
    for title, table in [("Stats Summary", "summary"), ("Possession & Time", "possession"), ("Events", "events")]:
        if title not in recognized or not tables[table]:
            raise ValueError(f"Missing or empty required worksheet: {title}")
    if game_id is None:
        warnings.append("No game_id supplied; match date and squad are not inferred.")
    return {"source": snapshot["source"], "warnings": warnings, **tables}


def main() -> None:
    """Fetch a read-only snapshot and export JSON plus one CSV per normalized table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--file-id", default=DEFAULT_FILE_ID)
    parser.add_argument("--game-id", help="Explicit canonical match ID; never inferred")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/in_game_stats"))
    arguments = parser.parse_args()
    source = InGameStatsSource(arguments.credentials, arguments.file_id)
    snapshot = source.read_workbook()
    parsed = parse_workbook(snapshot, game_id=arguments.game_id)
    parsed["fetched_at"] = datetime.now(timezone.utc).isoformat()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in [("raw_workbook.json", snapshot), ("in_game_stats.json", parsed)]:
        (arguments.output_dir / filename).write_text(
            json.dumps(payload, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8"
        )
    for table in ["summary", "possession", "events"]:
        records = parsed[table]
        with (arguments.output_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        print(f"{table}: {len(records)} rows")
    for warning in parsed["warnings"]:
        print(f"Warning: {warning}")
    print(f"Exported to {arguments.output_dir}")


if __name__ == "__main__":
    main()
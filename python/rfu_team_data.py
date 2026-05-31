import argparse
import csv
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "https://www.englandrugby.com/fixtures-and-results/search-results"
DEFAULT_TEAM_ID = 7134
DEFAULT_START_SEASON_YEAR = 2003

# RFU team IDs for each EGRFC squad.
# The 1st XV ID (7134) is confirmed. Set the 2nd and 3rd XV IDs when known.
EGRFC_SQUAD_TEAM_IDS: dict[str, int | None] = {
    "1st": 7134,
    "2nd": 7136, 
    "3rd": 7137, 
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def _current_season_start_year() -> int:
    """Return season start year, where season switches in July."""
    today = datetime.today()
    return today.year if today.month >= 7 else today.year - 1


def _season_label(start_year: int) -> str:
    """Convert season start year to RFU API format (YYYY-YYYY)."""
    return f"{start_year}-{start_year + 1}"


def _iter_seasons(start_year: int, end_year: int) -> list[str]:
    """Generate RFU season labels in ascending order."""
    if end_year < start_year:
        raise ValueError(f"end_year ({end_year}) must be >= start_year ({start_year})")
    return [_season_label(year) for year in range(start_year, end_year + 1)]


def _extract_match_id(href: str) -> str | None:
    """Extract numeric matchId query parameter from a URL."""
    if not href:
        return None
    match = re.search(r"(?:\?|&)matchId=(\d+)", href)
    return match.group(1) if match else None


def _parse_date_to_iso(raw_date: str | None) -> str | None:
    """Parse RFU card date text into ISO format."""
    if not raw_date:
        return None

    text = " ".join(raw_date.split())
    for fmt in ("%A, %d %b %Y", "%a, %d %b %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _has_class_token(value: str | None, token: str) -> bool:
    if not value:
        return False
    return token in str(value)


def _extract_header_fields(card) -> tuple[str | None, str | None]:
    """Get date and competition from the closest header associated with a card."""
    header = card.find_previous_sibling(
        "div", class_=lambda class_name: _has_class_token(class_name, "coh-style-cardheaderlayout")
    )
    if not header:
        # Some page variants nest cards under wrappers where sibling traversal skips the header.
        header = card.find_previous(
            "div", class_=lambda class_name: _has_class_token(class_name, "coh-style-cardheaderlayout")
        )

    date_node = None
    comp_node = None
    if header:
        date_node = header.select_one(
            ".coh-style-mobile-width.coh-style-card-left-date, .coh-style-card-left-date"
        )
        comp_node = header.select_one(
            ".coh-style-sub-header-right.c035-link, .coh-style-sub-header-right.c065-link, .coh-style-sub-header-right"
        )

    # Fallback: some templates include competition/date directly in card body.
    if not comp_node:
        comp_node = card.select_one(".coh-style-sub-header-right, .fnr-competition, [data-competition]")
    if not date_node:
        date_node = card.select_one(".coh-style-card-left-date, .fnr-date")

    date_text = date_node.get_text(" ", strip=True) if date_node else None
    competition = comp_node.get_text(" ", strip=True) if comp_node else None
    return date_text, competition


def _extract_match_row(card, season: str) -> dict | None:
    """Extract one match record from a result card."""
    home_node = card.select_one(".coh-style-right-comp-name.fnr-align-right.c065-link")
    away_node = card.select_one(".coh-style-right-comp-name.fnr-align-left.c065-link")
    if not home_node or not away_node:
        return None

    score_nodes = card.select(".fnr-scores a")
    home_score = score_nodes[0].get_text(strip=True) if len(score_nodes) > 0 else None
    away_score = score_nodes[1].get_text(strip=True) if len(score_nodes) > 1 else None

    match_link = card.select_one("a.c065-match-link[href*='matchId=']") or card.select_one(
        "a[href*='match-centre-community'][href*='matchId=']"
    )
    match_id = _extract_match_id(match_link.get("href", "")) if match_link else None

    date_text, competition = _extract_header_fields(card)

    return {
        "match_id": match_id,
        "season": season,
        "date": _parse_date_to_iso(date_text),
        "date_raw": date_text,
        "competition": competition,
        "home_team": home_node.get_text(" ", strip=True),
        "away_team": away_node.get_text(" ", strip=True),
        "home_score": home_score,
        "away_score": away_score,
    }


def fetch_team_results_for_season(team_id: int, season: str, timeout: int = 30) -> list[dict]:
    """Fetch and parse one season of RFU results for a team."""
    url = f"{BASE_URL}?team={team_id}&season={season}#results"

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Failed to fetch season %s for team %s: %s", season, team_id, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_=lambda class_name: class_name and "dataContainer" in class_name)
    rows = []
    for card in cards:
        row = _extract_match_row(card, season)
        if row:
            rows.append(row)

    deduped = {}
    for row in rows:
        # Match IDs are globally unique in RFU data; fallback key handles rare missing IDs.
        key = row["match_id"] or "|".join(
            [
                row.get("season") or "",
                row.get("date") or row.get("date_raw") or "",
                row.get("home_team") or "",
                row.get("away_team") or "",
            ]
        )
        deduped[key] = row

    season_rows = sorted(
        deduped.values(),
        key=lambda r: (r.get("date") or "", r.get("home_team") or "", r.get("away_team") or ""),
    )
    logging.info("Season %s: parsed %d cards, %d unique matches", season, len(rows), len(season_rows))
    return season_rows


def fetch_team_results_all_seasons(
    team_id: int = DEFAULT_TEAM_ID,
    start_year: int = DEFAULT_START_SEASON_YEAR,
    end_year: int | None = None,
    delay_seconds: float = 1.0,
) -> list[dict]:
    """Fetch team results for all seasons from start_year to end_year (inclusive)."""
    if end_year is None:
        end_year = _current_season_start_year()

    seasons = _iter_seasons(start_year, end_year)
    all_rows: list[dict] = []
    for i, season in enumerate(seasons):
        all_rows.extend(fetch_team_results_for_season(team_id=team_id, season=season))
        if i < len(seasons) - 1:
            # Add small jitter so requests are less bursty.
            jitter = random.uniform(0.0, 0.5)
            time.sleep(max(delay_seconds + jitter, 0.0))

    all_rows.sort(key=lambda r: (r.get("season") or "", r.get("date") or "", r.get("match_id") or ""))
    return all_rows


# ---------------------------------------------------------------------------
# League table scraping
# ---------------------------------------------------------------------------

_LEAGUE_TABLE_COLUMN_RENAMES = {"+/-": "PD", "Unnamed: 0": "#"}
_LEAGUE_TABLE_FIELDNAMES = ["season", "team_id", "#", "TEAM", "P", "W", "D", "L", "PF", "PA", "PD", "BP", "Pts"]
_RFU_ID_REFERENCE_FIELDNAMES = [
    "season",
    "team_id",
    "competition_id",
    "division_id",
    "competition_name",
    "division_name",
    "source_url",
]


def _extract_rfu_search_params(href: str) -> dict | None:
    """Extract competition/division/team/season query params from an RFU URL."""
    if not href:
        return None

    parsed = urlparse(href)
    if "englandrugby.com" not in parsed.netloc and not parsed.path.startswith("/fixtures-and-results"):
        return None
    if "search-results" not in parsed.path:
        return None

    query = parse_qs(parsed.query)
    competition = query.get("competition", [None])[0]
    division = query.get("division", [None])[0]
    season = query.get("season", [None])[0]
    team = query.get("team", [None])[0]
    if not competition or not division:
        return None

    normalized_url = (
        f"https://www.englandrugby.com/fixtures-and-results/search-results"
        f"?competition={competition}&season={season or ''}&division={division}"
    )
    if team:
        normalized_url = f"{normalized_url}&team={team}"

    return {
        "competition_id": int(competition),
        "division_id": int(division),
        "season": season,
        "team_id": int(team) if team and str(team).isdigit() else None,
        "source_url": normalized_url,
    }


def _extract_rfu_id_references_from_soup(soup, default_season: str, default_team_id: int) -> list[dict]:
    """Extract deduplicated competition/division id references from RFU links on a page."""
    refs: list[dict] = []
    seen: set[tuple] = set()

    for link in soup.find_all("a", href=True):
        params = _extract_rfu_search_params(link.get("href", ""))
        if params is None:
            continue

        season = str(params.get("season") or default_season)
        team_id = params.get("team_id") or default_team_id
        competition_name = link.get_text(" ", strip=True) or None

        row = {
            "season": season,
            "team_id": int(team_id),
            "competition_id": int(params["competition_id"]),
            "division_id": int(params["division_id"]),
            "competition_name": competition_name,
            "division_name": None,
            "source_url": params["source_url"],
        }
        key = (row["season"], row["team_id"], row["competition_id"], row["division_id"])
        if key in seen:
            continue
        seen.add(key)
        refs.append(row)

    refs.sort(key=lambda r: (r["season"], r["team_id"], r["competition_id"], r["division_id"]))
    return refs


def fetch_rfu_id_references_for_season(team_id: int, season: str, timeout: int = 30) -> list[dict]:
    """Fetch one team-season page and extract competition/division ids from embedded URLs."""
    url = f"{BASE_URL}?team={team_id}&season={season}#results"

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Failed to fetch RFU id references for season %s team %s: %s", season, team_id, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    refs = _extract_rfu_id_references_from_soup(
        soup=soup,
        default_season=season,
        default_team_id=team_id,
    )
    logging.info("Season %s team %s: extracted %d competition/division references", season, team_id, len(refs))
    return refs


def fetch_rfu_id_references_all_seasons(
    team_id: int = DEFAULT_TEAM_ID,
    start_year: int = DEFAULT_START_SEASON_YEAR,
    end_year: int | None = None,
    delay_seconds: float = 1.0,
) -> list[dict]:
    """Fetch competition/division id references across seasons for one team."""
    if end_year is None:
        end_year = _current_season_start_year()

    seasons = _iter_seasons(start_year, end_year)
    all_rows: list[dict] = []
    for i, season in enumerate(seasons):
        all_rows.extend(fetch_rfu_id_references_for_season(team_id=team_id, season=season))
        if i < len(seasons) - 1:
            jitter = random.uniform(0.0, 0.5)
            time.sleep(max(delay_seconds + jitter, 0.0))

    deduped: dict[tuple, dict] = {}
    for row in all_rows:
        key = (row["season"], row["team_id"], row["competition_id"], row["division_id"])
        deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda r: (r["season"], r["team_id"], r["competition_id"], r["division_id"]),
    )


def save_rfu_id_references(rows: list[dict], output_json: Path, output_csv: Path) -> None:
    """Write competition/division id reference rows to JSON and CSV."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_RFU_ID_REFERENCE_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_league_table_for_season(team_id: int, season: str, timeout: int = 30) -> list[dict]:
    """Fetch and parse the league table for a team in a given season.

    Uses the same ``?team={team_id}&season={season}`` URL pattern as the results
    scraper but navigates to the ``#tables`` section of the page.

    Returns a list of row dicts (one per team in the table) with keys:
    season, team_id, #, TEAM, P, W, D, L, PF, PA, PD, BP, Pts.
    Returns an empty list on any error or when no table is found.
    """
    url = f"{BASE_URL}?team={team_id}&season={season}#tables"

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Failed to fetch league table for season %s team %s: %s", season, team_id, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        logging.warning("No league table found for season %s team %s", season, team_id)
        return []

    try:
        df = pd.read_html(str(tables[0]))[0]
    except Exception as exc:
        logging.error("Failed to parse league table HTML for season %s team %s: %s", season, team_id, exc)
        return []

    df = df.rename(columns=_LEAGUE_TABLE_COLUMN_RENAMES)

    # Derive bonus points from try bonus + losing bonus columns when BP absent
    if "BP" not in df.columns:
        tb = pd.to_numeric(df.get("TB", 0), errors="coerce").fillna(0)
        lb = pd.to_numeric(df.get("LB", 0), errors="coerce").fillna(0)
        df["BP"] = (tb + lb).astype(int)

    # Retain only the canonical columns that exist in this table
    keep = [c for c in _LEAGUE_TABLE_FIELDNAMES if c in df.columns and c not in ("season", "team_id")]
    if "TEAM" not in keep:
        # Some RFU table variants use a different team column name
        for candidate in ("Club", "Team", "NAME"):
            if candidate in df.columns:
                df = df.rename(columns={candidate: "TEAM"})
                keep.append("TEAM")
                break

    if "TEAM" not in keep or "#" not in keep:
        logging.warning("League table for season %s team %s missing required columns", season, team_id)
        return []

    df = df[keep].copy()
    df.insert(0, "team_id", team_id)
    df.insert(0, "season", season)

    rows = []
    for _, row in df.iterrows():
        entry: dict = {"season": season, "team_id": team_id}
        for col in keep:
            val = row[col]
            if col in ("#", "P", "W", "D", "L", "PF", "PA", "PD", "BP", "Pts"):
                entry[col] = int(val) if pd.notna(val) else None
            else:
                entry[col] = str(val).strip() if pd.notna(val) else None
        rows.append(entry)

    logging.info("Season %s team %s: parsed %d league table rows", season, team_id, len(rows))
    return rows


def fetch_league_tables_all_seasons(
    team_id: int = DEFAULT_TEAM_ID,
    start_year: int = DEFAULT_START_SEASON_YEAR,
    end_year: int | None = None,
    delay_seconds: float = 1.0,
) -> list[dict]:
    """Fetch league tables for all seasons from start_year to end_year (inclusive)."""
    if end_year is None:
        end_year = _current_season_start_year()

    seasons = _iter_seasons(start_year, end_year)
    all_rows: list[dict] = []
    for i, season in enumerate(seasons):
        all_rows.extend(fetch_league_table_for_season(team_id=team_id, season=season))
        if i < len(seasons) - 1:
            jitter = random.uniform(0.0, 0.5)
            time.sleep(max(delay_seconds + jitter, 0.0))

    return all_rows


def save_league_tables(rows: list[dict], output_json: Path, output_csv: Path) -> None:
    """Write league table rows to JSON and CSV output files."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)

    fieldnames = [f for f in _LEAGUE_TABLE_FIELDNAMES if f != "team_id"] + ["team_id"]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save_results(rows: list[dict], output_json: Path, output_csv: Path) -> None:
    """Write results to JSON and CSV output files."""
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)

    fieldnames = [
        "match_id",
        "season",
        "date",
        "date_raw",
        "competition",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape RFU fixtures/results pages for a team across multiple seasons."
    )
    parser.add_argument(
        "--team-id",
        type=int,
        default=None,
        help="RFU team ID for single-team mode (omit to run all squads from EGRFC_SQUAD_TEAM_IDS)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_SEASON_YEAR,
        help="Season start year, e.g. 2003 for 2003-2004",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Season start year for the final season (defaults to current season)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Base delay between season requests",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DATA_DIR / "east_grinstead_1st_rfu_results.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DATA_DIR / "east_grinstead_1st_rfu_results.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--output-league-table-json",
        type=Path,
        default=None,
        help="Output JSON path for league tables (optional; omit to skip league table scraping)",
    )
    parser.add_argument(
        "--output-league-table-csv",
        type=Path,
        default=None,
        help="Output CSV path for league tables (optional; omit to skip league table scraping)",
    )
    parser.add_argument(
        "--skip-league-tables",
        action="store_true",
        help="Do not scrape league tables even when output paths are configured",
    )
    parser.add_argument(
        "--skip-rfu-id-references",
        action="store_true",
        help="Do not extract/save competition/division reference IDs from RFU links",
    )
    parser.add_argument(
        "--output-rfu-id-json",
        type=Path,
        default=None,
        help="Output JSON path for extracted RFU competition/division references",
    )
    parser.add_argument(
        "--output-rfu-id-csv",
        type=Path,
        default=None,
        help="Output CSV path for extracted RFU competition/division references",
    )
    return parser.parse_args()


def _run_single_team(
    team_id: int,
    start_year: int,
    end_year: int | None,
    delay_seconds: float,
    output_json: Path,
    output_csv: Path,
    output_league_table_json: Path | None,
    output_league_table_csv: Path | None,
    skip_league_tables: bool,
    output_rfu_id_json: Path | None,
    output_rfu_id_csv: Path | None,
    skip_rfu_id_references: bool,
) -> None:
    rows = fetch_team_results_all_seasons(
        team_id=team_id,
        start_year=start_year,
        end_year=end_year,
        delay_seconds=delay_seconds,
    )
    save_results(rows=rows, output_json=output_json, output_csv=output_csv)
    logging.info("Saved %d rows", len(rows))
    logging.info("JSON output: %s", output_json)
    logging.info("CSV output: %s", output_csv)

    if not skip_league_tables and (output_league_table_json or output_league_table_csv):
        table_rows = fetch_league_tables_all_seasons(
            team_id=team_id,
            start_year=start_year,
            end_year=end_year,
            delay_seconds=delay_seconds,
        )
        lt_json = output_league_table_json or output_json.with_name(output_json.stem + "_league_tables.json")
        lt_csv = output_league_table_csv or output_csv.with_name(output_csv.stem + "_league_tables.csv")
        save_league_tables(rows=table_rows, output_json=lt_json, output_csv=lt_csv)
        logging.info("Saved %d league table rows", len(table_rows))
        logging.info("League table JSON: %s", lt_json)
        logging.info("League table CSV: %s", lt_csv)

    if not skip_rfu_id_references:
        id_rows = fetch_rfu_id_references_all_seasons(
            team_id=team_id,
            start_year=start_year,
            end_year=end_year,
            delay_seconds=delay_seconds,
        )
        id_json = output_rfu_id_json or output_json.with_name(output_json.stem + "_id_references.json")
        id_csv = output_rfu_id_csv or output_csv.with_name(output_csv.stem + "_id_references.csv")
        save_rfu_id_references(rows=id_rows, output_json=id_json, output_csv=id_csv)
        logging.info("Saved %d competition/division id reference rows", len(id_rows))
        logging.info("RFU id reference JSON: %s", id_json)
        logging.info("RFU id reference CSV: %s", id_csv)


def main() -> None:
    args = parse_args()
    # Single-team mode: explicit team id supplied.
    if args.team_id is not None:
        _run_single_team(
            team_id=args.team_id,
            start_year=args.start_year,
            end_year=args.end_year,
            delay_seconds=args.delay_seconds,
            output_json=args.output_json,
            output_csv=args.output_csv,
            output_league_table_json=args.output_league_table_json,
            output_league_table_csv=args.output_league_table_csv,
            skip_league_tables=args.skip_league_tables,
            output_rfu_id_json=args.output_rfu_id_json,
            output_rfu_id_csv=args.output_rfu_id_csv,
            skip_rfu_id_references=args.skip_rfu_id_references,
        )
        return

    # Default mode: run all configured EGRFC squads.
    for squad, team_id in EGRFC_SQUAD_TEAM_IDS.items():
        if team_id is None:
            logging.warning("Skipping %s XV: no team ID configured", squad)
            continue

        logging.info("=== Running squad %s (team_id=%s) ===", squad, team_id)
        _run_single_team(
            team_id=team_id,
            start_year=args.start_year,
            end_year=args.end_year,
            delay_seconds=args.delay_seconds,
            output_json=DATA_DIR / f"east_grinstead_{squad}_rfu_results.json",
            output_csv=DATA_DIR / f"east_grinstead_{squad}_rfu_results.csv",
            output_league_table_json=None if args.skip_league_tables else DATA_DIR / f"east_grinstead_{squad}_league_tables.json",
            output_league_table_csv=None if args.skip_league_tables else DATA_DIR / f"east_grinstead_{squad}_league_tables.csv",
            skip_league_tables=args.skip_league_tables,
            output_rfu_id_json=None if args.skip_rfu_id_references else DATA_DIR / f"east_grinstead_{squad}_rfu_id_references.json",
            output_rfu_id_csv=None if args.skip_rfu_id_references else DATA_DIR / f"east_grinstead_{squad}_rfu_id_references.csv",
            skip_rfu_id_references=args.skip_rfu_id_references,
        )


if __name__ == "__main__":
    main()

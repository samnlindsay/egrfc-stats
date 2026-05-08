import argparse
import csv
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "https://www.englandrugby.com/fixtures-and-results/search-results"
DEFAULT_TEAM_ID = 7134
DEFAULT_START_SEASON_YEAR = 2003

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
    parser.add_argument("--team-id", type=int, default=DEFAULT_TEAM_ID, help="RFU team ID (default: 7134)")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = fetch_team_results_all_seasons(
        team_id=args.team_id,
        start_year=args.start_year,
        end_year=args.end_year,
        delay_seconds=args.delay_seconds,
    )
    save_results(rows=rows, output_json=args.output_json, output_csv=args.output_csv)
    logging.info("Saved %d rows", len(rows))
    logging.info("JSON output: %s", args.output_json)
    logging.info("CSV output: %s", args.output_csv)


if __name__ == "__main__":
    main()

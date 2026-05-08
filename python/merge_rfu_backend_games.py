import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKEND_GAMES_PATH = REPO_ROOT / "data" / "backend" / "games.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "data" / "backend" / "rfu_backend_merge_report.json"
DEFAULT_CONFLICTS_CSV_PATH = REPO_ROOT / "data" / "backend" / "rfu_backend_conflicts.csv"
DEFAULT_UNMATCHED_CSV_PATH = REPO_ROOT / "data" / "backend" / "rfu_backend_unmatched_2017_plus.csv"
DEFAULT_DISCARDED_CSV_PATH = REPO_ROOT / "data" / "backend" / "rfu_backend_discarded_expected.csv"

try:
    # Reuse the same opposition canonicalisation table used elsewhere in the pipeline.
    from data import PITCHERO_OPPOSITION_CANONICAL_NAMES  # type: ignore
except Exception:
    PITCHERO_OPPOSITION_CANONICAL_NAMES = {}


EXTRA_RFU_OPPOSITION_CANONICAL_NAMES: dict[str, str] = {
    "stleonardscinqueports": "St. Leonards CP",
    "brightonsussexmedics": "Brighton & SM",
    "brightonandsussexmedics": "Brighton & SM",
    "horshambarbarians": "Horsham",
    "horshamlions": "Horsham II",
    "worthingraidersa": "Worthing II",
}


def _season_dash_to_backend(season_dash: str | None) -> str | None:
    if not season_dash:
        return None
    match = re.match(r"^(\d{4})-(\d{4})$", season_dash.strip())
    if not match:
        return season_dash
    start_year = int(match.group(1))
    end_year = int(match.group(2))
    return f"{start_year}/{str(end_year)[-2:]}"


def _season_start_year(season: str | None) -> int | None:
    if not season:
        return None
    match = re.match(r"^(\d{4})[/-](\d{2}|\d{4})$", season.strip())
    if not match:
        return None
    return int(match.group(1))


def _normalize_team_name(name: str | None) -> str:
    club_name = _opposition_club_name(name)
    if not club_name:
        return ""
    return _normalise_lookup_key(club_name)


def _normalise_lookup_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _roman_from_team_number(number: int | None) -> str | None:
    if number is None:
        return None
    roman_map = {2: "II", 3: "III", 4: "IV", 5: "V"}
    return roman_map.get(number)


def _extract_team_number(value: str) -> tuple[str, int | None]:
    text = value.strip()
    if not text:
        return "", None

    # Prefer explicit bracket hints such as "(2nd XV)".
    bracketed = re.search(r"\(([^)]*)\)", text)
    bracket_team_number: int | None = None
    if bracketed:
        inner = bracketed.group(1)
        digit_match = re.search(r"\b([2-5])(?:st|nd|rd|th)?\b", inner, flags=re.IGNORECASE)
        if digit_match:
            bracket_team_number = int(digit_match.group(1))
        else:
            roman_match = re.search(r"\b(II|III|IV|V)\b", inner, flags=re.IGNORECASE)
            if roman_match:
                roman_to_num = {"II": 2, "III": 3, "IV": 4, "V": 5}
                bracket_team_number = roman_to_num[roman_match.group(1).upper()]

    text_without_brackets = re.sub(r"\([^)]*\)", " ", text).strip()

    # If no explicit bracketed team number was found, detect shorthand suffixes.
    suffix_match = re.match(
        r"^(?P<base>.+?)\s*(?P<num>[2-5])(?:st|nd|rd|th)?(?:xv|s)?\s*$",
        text_without_brackets,
        flags=re.IGNORECASE,
    )
    if suffix_match and bracket_team_number is None:
        return suffix_match.group("base").strip(), int(suffix_match.group("num"))

    return text_without_brackets, bracket_team_number


def _canonical_opposition_name(name: str | None) -> str:
    if not name:
        return ""

    value = str(name).strip()
    if not value:
        return ""

    base_name, team_number = _extract_team_number(value)
    cleaned = re.sub(r"\bmen\b", "", base_name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\brfc\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")

    lookup_key = _normalise_lookup_key(cleaned)
    canonical = (
        PITCHERO_OPPOSITION_CANONICAL_NAMES.get(lookup_key)
        or EXTRA_RFU_OPPOSITION_CANONICAL_NAMES.get(lookup_key)
        or cleaned
    )

    if canonical:
        canonical_team_suffix = re.search(r"\b(II|III|IV|V)\b", canonical)
        if team_number is not None and canonical_team_suffix is None:
            roman = _roman_from_team_number(team_number)
            if roman:
                canonical = f"{canonical} {roman}".strip()

    return canonical


def _opposition_club_name(name: str | None) -> str:
    """Return opposition at club level (strip team suffixes like II/III/1st XV)."""
    canonical = _canonical_opposition_name(name)
    if not canonical:
        return ""

    club = str(canonical).strip()
    # Remove common trailing team indicators and standalone Roman numeral suffixes.
    club = re.sub(r"\b[1-5](?:st|nd|rd|th)?\s*xv\b", "", club, flags=re.IGNORECASE)
    club = re.sub(r"\b(II|III|IV|V)\b$", "", club, flags=re.IGNORECASE)
    club = re.sub(r"\b(II|III|IV|V)\b", "", club, flags=re.IGNORECASE)
    club = re.sub(r"\s+", " ", club).strip(" -")
    return club


def _discard_reason_from_scores(score_for: int | None, score_against: int | None) -> str | None:
    if score_for is None or score_against is None:
        return "missing_score"
    if score_for == 0 and score_against == 0:
        return "nil_nil_fixture"
    return None


def _determine_game_type(competition: str | None) -> str:
    text = (competition or "").strip().lower()
    if any(token in text for token in ["friendly"]):
        return "Friendly"
    if any(token in text for token in ["cup", "championship", "shield", "plate", "vase", "bob rogers"]):
        return "Cup"
    return "League"


def _build_game_id(date_str: str, squad: str, opposition: str) -> str:
    return f"{date_str}_{squad}_{opposition}".replace(" ", "_").replace("/", "")


def _result_from_scores(score_for: Any, score_against: Any) -> str | None:
    if score_for is None or score_against is None:
        return None
    try:
        sf = int(score_for)
        sa = int(score_against)
    except (ValueError, TypeError):
        return None
    if sf > sa:
        return "W"
    if sf < sa:
        return "L"
    return "D"


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _rfu_row_to_backend_row(rfu_row: dict[str, Any], squad: str) -> dict[str, Any] | None:
    home = (rfu_row.get("home_team") or "").strip()
    away = (rfu_row.get("away_team") or "").strip()
    if not home or not away:
        return None

    # RFU cards for these team pages always include East Grinstead side as either home or away.
    egr_is_home = "east grinstead" in home.lower()
    egr_is_away = "east grinstead" in away.lower()
    if not egr_is_home and not egr_is_away:
        return None

    opposition = away if egr_is_home else home
    opposition = _opposition_club_name(opposition)
    home_score = _coerce_int(rfu_row.get("home_score"))
    away_score = _coerce_int(rfu_row.get("away_score"))
    score_for = home_score if egr_is_home else away_score
    score_against = away_score if egr_is_home else home_score

    season_backend = _season_dash_to_backend(rfu_row.get("season"))
    date_str = (rfu_row.get("date") or "").strip()
    if not season_backend or not date_str:
        return None

    game_type = _determine_game_type(rfu_row.get("competition"))

    return {
        "game_id": _build_game_id(date_str, squad, opposition),
        "squad": squad,
        "date": date_str,
        "season": season_backend,
        "competition": rfu_row.get("competition"),
        "game_type": game_type,
        "opposition": opposition,
        "home_away": "H" if egr_is_home else "A",
        "score_for": score_for,
        "score_against": score_against,
        "result": _result_from_scores(score_for, score_against),
        "captain": None,
        "motm": None,
        "vice_captain_1": None,
        "vice_captain_2": None,
        "tries_scorers": {},
        "conversions_scorers": {},
        "penalties_scorers": {},
        "drop_goals_scorers": {},
        "pitchero_match_url": None,
    }


def _pick_backend_match(rfu_game: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    if not candidates:
        return None, "no_candidate"

    rfu_opp_key = _normalize_team_name(rfu_game.get("opposition"))
    opp_matches = [row for row in candidates if _normalize_team_name(row.get("opposition")) == rfu_opp_key]
    if len(opp_matches) == 1:
        return opp_matches[0], None
    if len(opp_matches) > 1:
        return opp_matches[0], "ambiguous_opposition"

    sf = rfu_game.get("score_for")
    sa = rfu_game.get("score_against")
    if sf is not None and sa is not None:
        score_matches = [
            row
            for row in candidates
            if row.get("score_for") == sf and row.get("score_against") == sa
        ]
        if len(score_matches) == 1:
            return score_matches[0], None
        if len(score_matches) > 1:
            return score_matches[0], "ambiguous_score"

    if len(candidates) == 1:
        return candidates[0], "fallback_single_candidate"

    return candidates[0], "ambiguous_multiple_candidates"


def _replace_backend_fixture_fields(backend_match: dict[str, Any], mapped_row: dict[str, Any]) -> None:
    """Replace the core fixture fields on an existing backend row with RFU values.

    Keeps backend `game_id` and non-fixture enrichment payload intact.
    """
    for field in [
        "season",
        "date",
        "competition",
        "game_type",
        "opposition",
        "home_away",
        "score_for",
        "score_against",
        "result",
    ]:
        backend_match[field] = mapped_row.get(field)


def merge_rfu_into_backend(
    backend_games_path: Path,
    rfu_sources: list[tuple[str, Path]],
    report_path: Path,
    conflicts_csv_path: Path,
    unmatched_csv_path: Path,
    discarded_csv_path: Path,
) -> dict[str, Any]:
    backend_games = json.loads(backend_games_path.read_text(encoding="utf-8"))
    backend_game_ids_before = {
        str(row.get("game_id") or "").strip()
        for row in backend_games
        if str(row.get("game_id") or "").strip()
    }

    backend_by_squad_date: dict[tuple[str, str], list[dict[str, Any]]] = {}
    backend_seasons_by_squad: dict[str, set[str]] = {}
    for row in backend_games:
        squad = str(row.get("squad") or "").strip()
        date_str = str(row.get("date") or "").strip()
        season = str(row.get("season") or "").strip()
        backend_by_squad_date.setdefault((squad, date_str), []).append(row)
        backend_seasons_by_squad.setdefault(squad, set()).add(season)

    report: dict[str, Any] = {
        "summary": {
            "backend_games_before": len(backend_games),
            "backend_games_after": None,
            "appended_rows": 0,
            "mapped_rows": 0,
            "updated_rows": 0,
            "replaced_rows": 0,
            "replaced_conflict_2017_2020_rows": 0,
            "pre2017_upsert_replaced_rows": 0,
            "conflicts": 0,
            "unmatched_2017_plus": 0,
            "discarded_expected_rows": 0,
        },
        "per_squad": {},
        "conflicts": [],
        "rfu_unmatched_2017_plus": [],
        "rfu_discarded_expected": [],
    }

    for squad, source_path in rfu_sources:
        if not source_path.exists():
            report["per_squad"][squad] = {
                "source": str(source_path),
                "error": "source_not_found",
            }
            continue

        rfu_rows = json.loads(source_path.read_text(encoding="utf-8"))
        squad_stats = {
            "source": str(source_path),
            "rfu_rows": len(rfu_rows),
            "mapped": 0,
            "updated": 0,
            "replaced": 0,
            "replaced_conflict_2017_2020": 0,
            "pre2017_upsert_replaced": 0,
            "appended": 0,
            "conflicts": 0,
            "unmatched_2017_plus": 0,
            "discarded_expected": 0,
        }

        known_seasons = backend_seasons_by_squad.get(squad, set())

        for rfu_row in rfu_rows:
            mapped_row = _rfu_row_to_backend_row(rfu_row, squad=squad)
            if not mapped_row:
                continue

            discard_reason = _discard_reason_from_scores(mapped_row.get("score_for"), mapped_row.get("score_against"))
            if discard_reason:
                squad_stats["discarded_expected"] += 1
                report["rfu_discarded_expected"].append(
                    {
                        "squad": squad,
                        "season": mapped_row.get("season"),
                        "date": mapped_row.get("date"),
                        "opposition": mapped_row.get("opposition"),
                        "score_for": mapped_row.get("score_for"),
                        "score_against": mapped_row.get("score_against"),
                        "rfu_match_id": rfu_row.get("match_id"),
                        "reason": discard_reason,
                    }
                )
                continue

            season = mapped_row["season"]
            date_str = mapped_row["date"]
            start_year = _season_start_year(season)

            # Policy: 2017+ RFU fixtures not already present by game_id are always flagged.
            if start_year is not None and start_year >= 2017 and mapped_row["game_id"] not in backend_game_ids_before:
                squad_stats["unmatched_2017_plus"] += 1
                report["rfu_unmatched_2017_plus"].append(
                    {
                        "squad": squad,
                        "season": season,
                        "date": date_str,
                        "opposition": mapped_row["opposition"],
                        "score_for": mapped_row["score_for"],
                        "score_against": mapped_row["score_against"],
                        "rfu_match_id": rfu_row.get("match_id"),
                        "reason": "game_id_not_in_backend_before_merge",
                    }
                )

            # Policy: pre-2017 rows are always added/upserted from RFU.
            if start_year is not None and start_year < 2017:
                existing_by_game_id = next(
                    (
                        row
                        for row in backend_games
                        if str(row.get("game_id") or "").strip() == mapped_row["game_id"]
                    ),
                    None,
                )
                if existing_by_game_id is None:
                    backend_games.append(mapped_row)
                    backend_by_squad_date.setdefault((squad, date_str), []).append(mapped_row)
                    backend_seasons_by_squad.setdefault(squad, set()).add(season)
                    known_seasons.add(season)
                    squad_stats["appended"] += 1
                else:
                    _replace_backend_fixture_fields(existing_by_game_id, mapped_row)
                    squad_stats["replaced"] += 1
                    squad_stats["pre2017_upsert_replaced"] += 1
                continue

            candidates = backend_by_squad_date.get((squad, date_str), [])

            if season in known_seasons:
                backend_match, match_note = _pick_backend_match(mapped_row, candidates)
                if not backend_match:
                    continue

                squad_stats["mapped"] += 1

                # Fill missing backend values from RFU where safe.
                updated = False
                for field in ["competition", "game_type", "home_away", "score_for", "score_against", "result"]:
                    if backend_match.get(field) is None and mapped_row.get(field) is not None:
                        backend_match[field] = mapped_row[field]
                        updated = True
                if updated:
                    squad_stats["updated"] += 1

                # Flag mismatches on mapped rows.
                mismatch_fields = []
                for field in ["opposition", "home_away", "score_for", "score_against", "result"]:
                    backend_value = backend_match.get(field)
                    rfu_value = mapped_row.get(field)
                    if field == "opposition":
                        if _normalize_team_name(str(backend_value or "")) != _normalize_team_name(str(rfu_value or "")):
                            mismatch_fields.append(field)
                    elif backend_value is not None and rfu_value is not None and backend_value != rfu_value:
                        mismatch_fields.append(field)

                if mismatch_fields or match_note:
                    squad_stats["conflicts"] += 1

                    backend_before = {
                        "opposition": backend_match.get("opposition"),
                        "home_away": backend_match.get("home_away"),
                        "score_for": backend_match.get("score_for"),
                        "score_against": backend_match.get("score_against"),
                        "result": backend_match.get("result"),
                    }

                    resolution_action = "retain_backend"
                    is_home_away_only_mismatch = bool(mismatch_fields) and set(mismatch_fields) == {"home_away"}
                    if start_year is not None and 2017 <= start_year <= 2020 and not is_home_away_only_mismatch:
                        _replace_backend_fixture_fields(backend_match, mapped_row)
                        squad_stats["replaced"] += 1
                        squad_stats["replaced_conflict_2017_2020"] += 1
                        resolution_action = "replace_backend_fixture_with_rfu"
                    elif is_home_away_only_mismatch:
                        resolution_action = "retain_backend_home_away_only"

                    report["conflicts"].append(
                        {
                            "squad": squad,
                            "season": season,
                            "date": date_str,
                            "rfu_match_id": rfu_row.get("match_id"),
                            "backend_game_id": backend_match.get("game_id"),
                            "match_note": match_note,
                            "resolution_action": resolution_action,
                            "mismatch_fields": mismatch_fields,
                            "backend": backend_before,
                            "rfu": {
                                "opposition": mapped_row.get("opposition"),
                                "home_away": mapped_row.get("home_away"),
                                "score_for": mapped_row.get("score_for"),
                                "score_against": mapped_row.get("score_against"),
                                "result": mapped_row.get("result"),
                            },
                        }
                    )
            else:
                # For non-known seasons we only auto-append when pre-2017 (handled above).
                continue

        report["per_squad"][squad] = squad_stats

    backend_games.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("squad") or ""), str(row.get("game_id") or "")))

    report["summary"]["backend_games_after"] = len(backend_games)
    report["summary"]["appended_rows"] = sum(v.get("appended", 0) for v in report["per_squad"].values())
    report["summary"]["mapped_rows"] = sum(v.get("mapped", 0) for v in report["per_squad"].values())
    report["summary"]["updated_rows"] = sum(v.get("updated", 0) for v in report["per_squad"].values())
    report["summary"]["replaced_rows"] = sum(v.get("replaced", 0) for v in report["per_squad"].values())
    report["summary"]["replaced_conflict_2017_2020_rows"] = sum(
        v.get("replaced_conflict_2017_2020", 0) for v in report["per_squad"].values()
    )
    report["summary"]["pre2017_upsert_replaced_rows"] = sum(
        v.get("pre2017_upsert_replaced", 0) for v in report["per_squad"].values()
    )
    report["summary"]["conflicts"] = len(report["conflicts"])
    report["summary"]["unmatched_2017_plus"] = len(report["rfu_unmatched_2017_plus"])
    report["summary"]["discarded_expected_rows"] = len(report["rfu_discarded_expected"])

    backend_games_path.write_text(json.dumps(backend_games, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _write_conflicts_csv(conflicts_csv_path, report["conflicts"])
    _write_unmatched_csv(unmatched_csv_path, report["rfu_unmatched_2017_plus"])
    _write_discarded_csv(discarded_csv_path, report["rfu_discarded_expected"])

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge RFU extracted team results into backend games export.")
    parser.add_argument(
        "--backend-games",
        type=Path,
        default=DEFAULT_BACKEND_GAMES_PATH,
        help="Path to backend games.json export",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write conflict/unmatched merge report JSON",
    )
    parser.add_argument(
        "--conflicts-csv",
        type=Path,
        default=DEFAULT_CONFLICTS_CSV_PATH,
        help="Path to write a flattened conflicts CSV report",
    )
    parser.add_argument(
        "--unmatched-csv",
        type=Path,
        default=DEFAULT_UNMATCHED_CSV_PATH,
        help="Path to write unmatched 2017+ RFU rows CSV report",
    )
    parser.add_argument(
        "--discarded-csv",
        type=Path,
        default=DEFAULT_DISCARDED_CSV_PATH,
        help="Path to write discarded expected RFU fixtures CSV report",
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="RFU source definition in form squad_label:path_to_json, e.g. 1st:data/east_grinstead_1st_rfu_results.json",
    )
    return parser.parse_args()


def _parse_source_arg(source_arg: str) -> tuple[str, Path]:
    if ":" not in source_arg:
        raise ValueError(f"Invalid --source value: {source_arg}")
    squad, path_text = source_arg.split(":", 1)
    squad = squad.strip()
    path_text = path_text.strip()
    if not squad or not path_text:
        raise ValueError(f"Invalid --source value: {source_arg}")

    path = Path(path_text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return squad, path


def _write_conflicts_csv(path: Path, conflicts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "squad",
        "season",
        "date",
        "rfu_match_id",
        "backend_game_id",
        "match_note",
        "resolution_action",
        "mismatch_fields",
        "backend_opposition",
        "rfu_opposition",
        "backend_home_away",
        "rfu_home_away",
        "backend_score_for",
        "rfu_score_for",
        "backend_score_against",
        "rfu_score_against",
        "backend_result",
        "rfu_result",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in conflicts:
            backend = row.get("backend") or {}
            rfu = row.get("rfu") or {}
            writer.writerow(
                {
                    "squad": row.get("squad"),
                    "season": row.get("season"),
                    "date": row.get("date"),
                    "rfu_match_id": row.get("rfu_match_id"),
                    "backend_game_id": row.get("backend_game_id"),
                    "match_note": row.get("match_note"),
                    "resolution_action": row.get("resolution_action"),
                    "mismatch_fields": "|".join(row.get("mismatch_fields") or []),
                    "backend_opposition": backend.get("opposition"),
                    "rfu_opposition": rfu.get("opposition"),
                    "backend_home_away": backend.get("home_away"),
                    "rfu_home_away": rfu.get("home_away"),
                    "backend_score_for": backend.get("score_for"),
                    "rfu_score_for": rfu.get("score_for"),
                    "backend_score_against": backend.get("score_against"),
                    "rfu_score_against": rfu.get("score_against"),
                    "backend_result": backend.get("result"),
                    "rfu_result": rfu.get("result"),
                }
            )


def _write_unmatched_csv(path: Path, unmatched_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "squad",
        "season",
        "date",
        "opposition",
        "score_for",
        "score_against",
        "rfu_match_id",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in unmatched_rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def _write_discarded_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "squad",
        "season",
        "date",
        "opposition",
        "score_for",
        "score_against",
        "rfu_match_id",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def main() -> None:
    args = parse_args()
    rfu_sources = [_parse_source_arg(source_arg) for source_arg in args.source]

    backend_path = args.backend_games
    if not backend_path.is_absolute():
        backend_path = REPO_ROOT / backend_path

    report_path = args.report_path
    if not report_path.is_absolute():
        report_path = REPO_ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)

    conflicts_csv_path = args.conflicts_csv
    if not conflicts_csv_path.is_absolute():
        conflicts_csv_path = REPO_ROOT / conflicts_csv_path

    unmatched_csv_path = args.unmatched_csv
    if not unmatched_csv_path.is_absolute():
        unmatched_csv_path = REPO_ROOT / unmatched_csv_path

    discarded_csv_path = args.discarded_csv
    if not discarded_csv_path.is_absolute():
        discarded_csv_path = REPO_ROOT / discarded_csv_path

    report = merge_rfu_into_backend(
        backend_games_path=backend_path,
        rfu_sources=rfu_sources,
        report_path=report_path,
        conflicts_csv_path=conflicts_csv_path,
        unmatched_csv_path=unmatched_csv_path,
        discarded_csv_path=discarded_csv_path,
    )

    print("Merge complete")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {report_path}")
    print(f"Conflicts CSV: {conflicts_csv_path}")
    print(f"Unmatched CSV: {unmatched_csv_path}")
    print(f"Discarded CSV: {discarded_csv_path}")


if __name__ == "__main__":
    main()

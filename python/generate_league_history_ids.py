import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from python.data import DataExtractor
from python.league_data import normalize_league_name
from python.rfu_team_data import (
    EGRFC_SQUAD_TEAM_IDS,
    fetch_league_table_for_season,
    fetch_rfu_id_references_for_season,
)


def _season_to_dash_label(season: str) -> str:
    text = str(season or "").strip()
    if not text:
        return text
    # 2025/26 -> 2025-2026
    match_short = re.match(r"^(\d{4})/(\d{2})$", text)
    if match_short:
        start = int(match_short.group(1))
        end_short = int(match_short.group(2))
        end_full = (start // 100) * 100 + end_short
        if end_full < start:
            end_full += 100
        return f"{start}-{end_full}"

    # 2025-26 -> 2025-2026
    match_dash_short = re.match(r"^(\d{4})-(\d{2})$", text)
    if match_dash_short:
        start = int(match_dash_short.group(1))
        end_short = int(match_dash_short.group(2))
        end_full = (start // 100) * 100 + end_short
        if end_full < start:
            end_full += 100
        return f"{start}-{end_full}"

    # Already 2025-2026
    match_long = re.match(r"^(\d{4})-(\d{4})$", text)
    if match_long:
        return text

    return text.replace("/", "-")


def _squad_to_team_id(squad: str) -> int | None:
    key = str(squad or "").strip()
    return EGRFC_SQUAD_TEAM_IDS.get(key)


def _squad_to_number(squad: str) -> int | None:
    text = str(squad or "").strip().lower()
    if text.startswith("1"):
        return 1
    if text.startswith("2"):
        return 2
    if text.startswith("3"):
        return 3
    return None


def _season_to_csv_token(season: str) -> str | None:
    match = re.match(r"^(\d{4})/(\d{2})$", str(season or "").strip())
    if not match:
        return None
    return f"{match.group(1)}_{match.group(2)}"


def _infer_teams_from_local_csv(season: str, squad: str) -> int | None:
    squad_num = _squad_to_number(squad)
    token = _season_to_csv_token(season)
    if squad_num is None or token is None:
        return None

    csv_path = project_root / "data" / f"league_table_{token}_squad_{squad_num}.csv"
    if not csv_path.exists():
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None

    if df.empty:
        return None
    return int(len(df.index))


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok}


def _pick_league_reference(league_name: str, refs: list[dict]) -> dict | None:
    if not refs:
        return None

    target = normalize_league_name(league_name or "")
    target_tokens = _tokenize(target)

    def norm_comp_name(row: dict) -> str:
        return normalize_league_name(str(row.get("competition_name") or ""))

    # 1) exact normalized match
    exact = [row for row in refs if norm_comp_name(row) == target and target]
    if exact:
        return exact[0]

    # 2) all target tokens contained in competition name
    token_match = []
    if target_tokens:
        for row in refs:
            comp_tokens = _tokenize(norm_comp_name(row))
            if target_tokens.issubset(comp_tokens):
                token_match.append(row)
    if token_match:
        return token_match[0]

    # 3) fallback to known league competition ids
    league_comp_candidates = [row for row in refs if int(row.get("competition_id") or 0) in {206, 261, 1782}]
    if league_comp_candidates:
        return league_comp_candidates[0]

    # 4) final fallback: first available reference
    return refs[0]


def build_league_history_with_ids() -> pd.DataFrame:
    extractor = DataExtractor()
    history = extractor.extract_league_history().copy()
    if history.empty:
        return pd.DataFrame(
            columns=[
                "season",
                "squad",
                "league",
                "level",
                "rank",
                "teams",
                "team_id",
                "competition_id",
                "division_id",
            ]
        )

    cache: dict[tuple[int, str], list[dict]] = {}
    table_cache: dict[tuple[int, str], int | None] = {}
    out_rows: list[dict] = []

    for _, row in history.iterrows():
        season = str(row.get("season") or "").strip()
        squad = str(row.get("squad") or "").strip()
        league = str(row.get("league") or "").strip()

        team_id = pd.to_numeric(row.get("team_id"), errors="coerce")
        if pd.isna(team_id):
            team_id = _squad_to_team_id(squad)
        else:
            team_id = int(team_id)

        competition_id = pd.to_numeric(row.get("competition_id"), errors="coerce")
        division_id = pd.to_numeric(row.get("division_id"), errors="coerce")
        teams_count = pd.to_numeric(row.get("teams"), errors="coerce")

        if pd.isna(teams_count):
            teams_count = _infer_teams_from_local_csv(season=season, squad=squad)

        if pd.isna(teams_count) and team_id:
            season_dash = _season_to_dash_label(season)
            tkey = (int(team_id), season_dash)
            if tkey not in table_cache:
                table_rows = fetch_league_table_for_season(team_id=int(team_id), season=season_dash)
                table_cache[tkey] = int(len(table_rows)) if table_rows else None
            if table_cache[tkey] is not None:
                teams_count = table_cache[tkey]

        if team_id and (pd.isna(competition_id) or pd.isna(division_id)):
            season_dash = _season_to_dash_label(season)
            cache_key = (int(team_id), season_dash)
            if cache_key not in cache:
                refs = fetch_rfu_id_references_for_season(team_id=int(team_id), season=season_dash)
                cache[cache_key] = refs
            picked = _pick_league_reference(league, cache.get(cache_key, []))
            if picked is not None:
                if pd.isna(competition_id):
                    competition_id = int(picked.get("competition_id")) if picked.get("competition_id") is not None else pd.NA
                if pd.isna(division_id):
                    division_id = int(picked.get("division_id")) if picked.get("division_id") is not None else pd.NA

        out_rows.append(
            {
                "season": season,
                "squad": squad,
                "league": row.get("league"),
                "level": row.get("level"),
                "rank": row.get("rank"),
                "teams": int(teams_count) if pd.notna(teams_count) else None,
                "team_id": int(team_id) if team_id is not None and not pd.isna(team_id) else None,
                "competition_id": int(competition_id) if pd.notna(competition_id) else None,
                "division_id": int(division_id) if pd.notna(division_id) else None,
            }
        )

    return pd.DataFrame(
        out_rows,
        columns=[
            "season",
            "squad",
            "league",
            "level",
            "rank",
            "teams",
            "team_id",
            "competition_id",
            "division_id",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate League History rows with RFU IDs (A-I schema)")
    parser.add_argument("--output-csv", default="data/league_history_with_ids.csv", help="CSV output path")
    parser.add_argument("--output-json", default="data/league_history_with_ids.json", help="JSON output path")
    args = parser.parse_args()

    df = build_league_history_with_ids()

    for col in ["level", "rank", "teams", "team_id", "competition_id", "division_id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_csv, index=False, na_rep="")
    output_json.write_text(json.dumps(df.to_dict(orient="records"), indent=2), encoding="utf-8")

    missing_ids = int(df[(df["competition_id"].isna()) | (df["division_id"].isna())].shape[0]) if not df.empty else 0
    print(f"Wrote {len(df)} rows to {output_csv} and {output_json}")
    print(f"Rows still missing competition/division IDs: {missing_ids}")


if __name__ == "__main__":
    main()

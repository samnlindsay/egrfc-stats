"""Opening appearance balances for careers predating available team sheets."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ESTIMATES_PATH = Path(__file__).resolve().parents[1] / "data" / "historic_appearance_estimates.json"


def load_appearance_estimates(path: Path = ESTIMATES_PATH) -> pd.DataFrame:
    """Load validated additional appearances, never documented match records."""
    records = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    seen = set()
    for record in records:
        player = record["player"].strip()
        if not player or player in seen:
            raise ValueError(f"Missing or duplicate historic estimate player: {player!r}")
        seen.add(player)
        for field in ("first_xv", "second_xv"):
            value = record[field]
            if type(value) is not int or value < 0:
                raise ValueError(f"{player}: {field} must be a non-negative integer")
        rows.append({
            "player": player,
            "first_xv": record["first_xv"],
            "second_xv": record["second_xv"],
            "total": record["first_xv"] + record["second_xv"],
        })
    return pd.DataFrame(rows, columns=["player", "first_xv", "second_xv", "total"])


def historic_appearance_seasons() -> pd.DataFrame:
    """Return estimated season aggregates without inventing results or positions."""
    rows = []
    for estimate in load_appearance_estimates().to_dict("records"):
        for squad, field in (("1st", "first_xv"), ("2nd", "second_xv")):
            if estimate[field]:
                rows.append({
                    "player": estimate["player"], "season": "Historic", "squad": squad,
                    "result": "Estimated", "position": "Unknown", "apps": estimate[field],
                })
    return pd.DataFrame(rows, columns=["player", "season", "squad", "result", "position", "apps"])
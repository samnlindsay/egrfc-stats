"""Shared normalization helpers used across the data pipeline."""

from __future__ import annotations

import re
from typing import Any


EGRFC_TEAM_ALIASES = (
    "east grinstead",
    "e grinstead",
    "eg men",
    "egrfc",
)


def normalize_lookup_key(value: Any) -> str:
    """Return a lowercase alphanumeric key for fuzzy lookups."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def normalize_team_name(value: Any) -> str:
    """Return a whitespace-normalized lowercase team name for comparisons."""
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def is_egrfc_team_name(value: Any, aliases: tuple[str, ...] = EGRFC_TEAM_ALIASES) -> bool:
    """Return True when a team label refers to East Grinstead RFC."""
    normalized = normalize_team_name(value)
    if not normalized:
        return False
    return any(alias in normalized for alias in aliases)


def season_start_year(season: Any) -> int | None:
    """Extract the start year from canonical season strings."""
    text = str(season or "").strip()
    if not text:
        return None
    match = re.match(r"^(\d{4})[/-](\d{2}|\d{4})$", text)
    if not match:
        return None
    return int(match.group(1))


def season_to_dash_label(season: Any) -> str | None:
    """Normalize season labels to YYYY-YYYY when possible."""
    text = str(season or "").strip()
    if not text:
        return None

    dash_match = re.match(r"^(\d{4})-(\d{4})$", text)
    if dash_match:
        return f"{int(dash_match.group(1)):04d}-{int(dash_match.group(2)):04d}"

    slash_short_match = re.match(r"^(\d{4})/(\d{2})$", text)
    if slash_short_match:
        start_year = int(slash_short_match.group(1))
        end_suffix = int(slash_short_match.group(2))
        century_base = (start_year // 100) * 100
        end_year = century_base + end_suffix
        if end_year < start_year:
            end_year += 100
        return f"{start_year:04d}-{end_year:04d}"

    slash_long_match = re.match(r"^(\d{4})/(\d{4})$", text)
    if slash_long_match:
        return f"{int(slash_long_match.group(1)):04d}-{int(slash_long_match.group(2)):04d}"

    return text


def season_to_short_label(season: Any) -> str | None:
    """Normalize season labels to canonical YYYY/YY when possible."""
    text = str(season or "").strip()
    if not text:
        return None

    short_match = re.match(r"^(\d{4})/(\d{2})$", text)
    if short_match:
        return f"{int(short_match.group(1)):04d}/{short_match.group(2)}"

    dash_label = season_to_dash_label(text)
    dash_match = re.match(r"^(\d{4})-(\d{4})$", str(dash_label or ""))
    if not dash_match:
        return dash_label
    return f"{dash_match.group(1)}/{dash_match.group(2)[-2:]}"

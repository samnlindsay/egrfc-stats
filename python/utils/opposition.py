"""Shared opposition canonicalization and decomposition helpers."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from python.utils.normalization import normalize_lookup_key


# Keys are lowercase alphanumeric lookup keys produced by normalize_lookup_key.
# Values are canonical opposition display names.
OPPOSITION_CANONICAL_NAMES: dict[str, str] = {
    # Brighton / Sussex
    "brighton3": "Brighton III",
    "brighton2ndxv": "Brighton II",
    # Bognor
    "bognor2": "Bognor II",
    # Bromley (cup match)
    "papajohnsquarterfinalbromley": "Bromley",
    # Burgess Hill
    "burgesshill2": "Burgess Hill II",
    "burgesshill": "Burgess Hill",
    "burgesshillrfc": "Burgess Hill",
    # Cheshunt (cup match suffix)
    "cheshuntnationalcupquarterfinal": "Cheshunt",
    # Chipstead
    "chipsteadrfc": "Chipstead",
    # Cranleigh
    "cranleighrfc": "Cranleigh",
    # Crawley
    "crawleycupfinal": "Crawley",
    "crawley2": "Crawley II",
    "crawley2s3s": "Crawley II",
    "crawleyii": "Crawley II",
    # Crowborough
    "crowboro2": "Crowborough II",
    "crowborough2ndxv": "Crowborough II",
    "crowborough2s": "Crowborough II",
    "crowboroughii": "Crowborough II",
    # Croydon
    "croydonrfc": "Croydon",
    # Ditchling
    "ditchlingrfc": "Ditchling",
    "ditchling": "Ditchling",
    # Eastbourne
    "eastbourneiirfc": "Eastbourne II",
    "eastbourne2": "Eastbourne II",
    "eastbourne2s": "Eastbourne II",
    "eastbournerfc": "Eastbourne",
    # Haywards Heath
    "haywardsheath2xv": "Haywards Heath II",
    "haywardsheath2xy": "Haywards Heath II",
    "haywardsheath2s": "Haywards Heath II",
    "haywardsheath1stxv": "Haywards Heath",
    # Heathfield
    "heathfield": "Heathfield & Waldron",
    "heathfldwal": "Heathfield & Waldron",
    "heathfield2": "Heathfield & Waldron II",
    "heathfieldii": "Heathfield & Waldron II",
    "heathfield3s": "Heathfield & Waldron III",
    "heathfieldiii": "Heathfield & Waldron III",
    "heathfieldwaldron3": "Heathfield & Waldron III",
    "heathfldwal3": "Heathfield & Waldron III",
    "heathfieldwaldronii": "Heathfield & Waldron II",
    # Hellingly
    "hellingly2": "Hellingly II",
    # Horsham
    "horsham2s": "Horsham II",
    "horshamii": "Horsham II",
    "horshamiiicasuals": "Horsham III",
    "horshambarbarians": "Horsham",
    "horshamlions": "Horsham II",
    # Hove
    "hove2": "Hove II",
    "hove2xv": "Hove II",
    "hove2xy": "Hove II",
    "hoveii": "Hove II",
    "hove3": "Hove III",
    "hove3rdxv": "Hove III",
    # Jersey / Royals
    "jerseyroyals": "Royals",
    "royalsrfc": "Royals",
    # Lewes
    "lewes2": "Lewes II",
    # Midhurst (cup match suffix)
    "sussexcupfinalmidhurst": "Midhurst",
    # Newick
    "newickrfc": "Newick",
    # Oakmedians
    "oakmediansrfc": "Oakmedians",
    # Old Caterhamians
    "oldcaterhamians2s": "Old Caterhamians II",
    # Old Haileyburians (and common misspelling)
    "oldhaileyburians": "Old Haileyburians",
    "oldhaileybarians": "Old Haileyburians",
    # Old Rutlishians
    "oldrutlishians2s": "Old Rutlishians II",
    "oldrutlishiansrfc": "Old Rutlishians",
    # Pulborough
    "pulborough2": "Pulborough II",
    "pulborough3": "Pulborough III",
    "pulborough2ssussexjuniorvase": "Pulborough II",
    # Rye
    "ryerfc": "Rye",
    # Shoreham
    "shoreham2ndxv": "Shoreham II",
    # St Leonards / Brighton SM / Worthing aliases (RFU variants)
    "stleonardscinqueports": "St. Leonards CP",
    "brightonsussexmedics": "Brighton & SM",
    "brightonandsussexmedics": "Brighton & SM",
    "worthingraidersa": "Worthing II",
    # Trinity
    "trinity2s": "Trinity II",
    # Uckfield
    "uckfieldiirfc": "Uckfield II",
    "uckfield2s": "Uckfield II",
    "uckfield12s": "Uckfield",
    "uckfieldrfc": "Uckfield",
    # Warlingham
    "warlingham3s": "Warlingham III",
    # Wensleydale (cup match suffix)
    "wensleydalepapajohnscupsemifinal": "Wensleydale",
}


_OPPOSITION_TEAM_SUFFIX_RE = re.compile(
    r"""
    ^\s*(?P<club>.*?)\s*
    (?P<team>
        (?:(?P<team_num>[1-6])(?:st|nd|rd|th)?(?:\s*(?:xv|s|['\u2019]s))?)
        |
        (?P<team_roman>i{1,3}|iv|v|vi)
    )\s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

_ROMAN_TO_TEAM_NUMBER = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
}

_TEAM_NUMBER_TO_ROMAN = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
    5: "V",
    6: "VI",
}

# Single toggle for how opposition_squad labels are rendered.
# Allowed values: "ordinal" (1st/2nd/3rd) or "roman" (I/II/III).
OPPOSITION_SQUAD_LABEL_STYLE = "ordinal"


def canonicalize_opposition_name(name: Any) -> Any:
    """Return a canonical opposition display name for messy source values."""
    if name is None or pd.isna(name):
        return name

    cleaned = str(name).strip()
    canonical = OPPOSITION_CANONICAL_NAMES.get(normalize_lookup_key(cleaned), cleaned)

    # Fallback for unmapped shorthand like "Club 2"/"Club 3s".
    if canonical == cleaned:
        suffix_match = re.match(
            r"^(?P<base>.+?)\s*(?P<num>[2-5])(?:st|nd|rd|th)?(?:xv|s)?\s*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if suffix_match:
            base = suffix_match.group("base").strip()
            roman = _TEAM_NUMBER_TO_ROMAN.get(int(suffix_match.group("num")))
            if roman:
                canonical = f"{base} {roman}"

    if isinstance(canonical, str) and canonical.upper().endswith(" RFC"):
        canonical = canonical[:-4].strip()
    return canonical


def split_opposition_components(name: Any) -> tuple[str, int | None]:
    """Return opposition as (club_name, team_number)."""
    if name is None or pd.isna(name):
        return "", None

    canonical = str(canonicalize_opposition_name(name)).strip()
    if not canonical:
        return "", None

    collapsed = re.sub(r"\s+", " ", canonical)
    match = _OPPOSITION_TEAM_SUFFIX_RE.match(collapsed)
    if not match:
        return collapsed, None

    club = re.sub(r"\s+", " ", (match.group("club") or "").strip(" -"))
    if not club:
        return collapsed, None

    team_num = match.group("team_num")
    if team_num:
        return club, int(team_num)

    team_roman = (match.group("team_roman") or "").upper()
    return club, _ROMAN_TO_TEAM_NUMBER.get(team_roman)


def opposition_club_name(name: Any) -> str:
    club, _team = split_opposition_components(name)
    return club


def team_number_to_ordinal_label(team_number: int | None) -> str | None:
    """Return squad label using OPPOSITION_SQUAD_LABEL_STYLE.

    Keep this function name for backwards compatibility with existing callers.
    """
    if team_number is None:
        return None

    if OPPOSITION_SQUAD_LABEL_STYLE == "roman":
        return team_number_to_roman(team_number)

    if OPPOSITION_SQUAD_LABEL_STYLE != "ordinal":
        raise ValueError(
            "OPPOSITION_SQUAD_LABEL_STYLE must be 'ordinal' or 'roman'"
        )

    if team_number == 1:
        return "1st"
    if team_number == 2:
        return "2nd"
    if team_number == 3:
        return "3rd"
    return f"{team_number}th"


def team_number_to_roman(team_number: int | None) -> str | None:
    return _TEAM_NUMBER_TO_ROMAN.get(team_number)

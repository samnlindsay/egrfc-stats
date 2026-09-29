"""Generate player and opposition reports from the canonical EGRFC database."""

import argparse
import base64
import copy
from datetime import date, datetime
from datetime import date
import html
import json
import os
import re
import mimetypes
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import duckdb
import vl_convert as vlc

from python.backend import IN_GAME_PLAYER_ALIAS_CANONICAL, _canonical_player_name_for_season

from python.backend import IN_GAME_PLAYER_ALIAS_CANONICAL, _canonical_player_name_for_season


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = "data/egrfc_backend.duckdb"
DEFAULT_REPORT_DIR = Path("reports/generated")
SITE_COLORS = {"navy": "#202946", "blue": "#7d96e8", "red": "#981515", "paper": "#f2f1f4"}
MIN_JUMPER_ATTEMPTS = 10
TIGHT5_POSITIONS = {"prop", "hooker", "second row"}


def _markdown(value):
    if value is None:
        return "-"
    text = str(value).strip()
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _date(value):
    return value.isoformat() if value else "-"


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_markdown(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "summary"


def _check(value):
    return "✓" if value else ""


def _score_markers(row):
    markers = []
    for column, glyph in (("tries", "T"), ("penalties", "P"), ("conversions", "C"), ("drop_goals", "DG")):
        count = int(row.get(column) or 0)
        if count:
            markers.append(f"{glyph}{f' x{count}' if count > 1 else ''}")
    return ", ".join(markers)


def _position_appearance_bar(appearances):
    position_counts = {}
    bench_count = 0
    for row in appearances:
        if row.get("is_starter"):
            position = str(row.get("position") or "").strip()
            if position and position.casefold() != "bench":
                position_counts[position] = position_counts.get(position, 0) + 1
        else:
            bench_count += 1
    segments = [
        {"label": position, "count": count, "detail": "start" if count == 1 else "starts"}
        for position, count in sorted(position_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    if bench_count:
        segments.append({"label": "Bench", "count": bench_count, "detail": "appearance" if bench_count == 1 else "appearances"})
    total = sum(segment["count"] for segment in segments)
    if not total:
        return '<p class="text-muted">No position data available.</p>'
    colors = ["#202946", "#7d96e8", "#981515", "#146f14", "#62666e", "#4c6b84"]
    output = ['<div class="position-appearance-wrap" style="margin-top:0"><h3>Position</h3>', f'<div class="position-appearance-bar" role="img" aria-label="{total} appearances by position">']
    for index, segment in enumerate(segments):
        color = colors[index % len(colors)]
        text_color = "#202124" if color == "#7d96e8" else "#fff"
        output.append(
            f'<div class="position-bar-segment" style="--segment-count:{segment["count"]};--segment-color:{color};--segment-text:{text_color}" '
            f'title="{html.escape(segment["label"])}: {segment["count"]} {segment["detail"]}">'
            f'<strong>{html.escape(segment["label"])}</strong><span>{segment["count"]} {segment["detail"]}</span></div>'
        )
    output.append("</div></div>")
    return "".join(output)


def _has_majority_tight5_starts(appearances):
    starts = [row for row in appearances if row.get("is_starter")]
    tight5_starts = sum(
        str(row.get("position") or "").strip().casefold() in TIGHT5_POSITIONS
        for row in starts
    )
    return bool(starts) and tight5_starts * 2 > len(starts)


def _meets_jumper_attempt_threshold(attempts):
    return int(attempts or 0) >= MIN_JUMPER_ATTEMPTS


def _started_set_piece_summary_rows(rows, won_field, total_field):
    by_season_squad = {
        (row["season"], row["squad"]): row
        for row in rows
    }
    summary_rows = []
    for season in sorted({row["season"] for row in rows if row.get("season")}):
        values = [season]
        overall_won = 0
        overall_total = 0
        for squad in ("1st", "2nd"):
            row = by_season_squad.get((season, squad), {})
            won = int(row.get(won_field) or 0)
            total = int(row.get(total_field) or 0)
            overall_won += won
            overall_total += total
            values.extend(
                [won, total, f"{100 * won / total:.1f}%"] if total > 0 else ["", "", ""]
            )
        values.extend(
            [overall_won, overall_total, f"{100 * overall_won / overall_total:.1f}%"]
            if overall_total > 0 else ["", "", ""]
        )
        summary_rows.append(values)
    totals_by_squad = {squad: {"won": 0, "total": 0} for squad in ("1st", "2nd")}
    for row in rows:
        squad = row.get("squad")
        if squad not in totals_by_squad:
            continue
        totals_by_squad[squad]["won"] += int(row.get(won_field) or 0)
        totals_by_squad[squad]["total"] += int(row.get(total_field) or 0)

    total_values = ["Total"]
    overall_won = 0
    overall_total = 0
    for squad in ("1st", "2nd"):
        won = totals_by_squad[squad]["won"]
        total = totals_by_squad[squad]["total"]
        overall_won += won
        overall_total += total
        total_values.extend(
            [won, total, f"{100 * won / total:.1f}%"] if total > 0 else ["", "", ""]
        )
    total_values.extend(
        [overall_won, overall_total, f"{100 * overall_won / overall_total:.1f}%"]
        if overall_total > 0 else ["", "", ""]
    )
    if rows:
        summary_rows.append(total_values)
    return summary_rows


def _matches_motm(motm, player_name):
    candidates = re.split(r"\s*(?:,|/|&|\band\b|\+)\s*", str(motm or ""), flags=re.IGNORECASE)
    return any(_player_name_key(candidate) == _player_name_key(player_name) for candidate in candidates)


def _player_name_key(value):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    overrides = {
        "sam lindsay": "s lindsay 2",
        "sam lindsay-mccall": "s lindsay-mccall",
        "james mitchell": "t mitchell",
    }
    if name.casefold() in overrides:
        return overrides[name.casefold()]
    parts = name.split(" ", 1)
    return f"{parts[0][0]} {parts[1]}".casefold() if len(parts) == 2 else name.casefold()


def _report_scorer_player_key(value, season):
    return _player_name_key(_canonical_player_name_for_season(value, season))


def _report_scorer_player_key(value, season):
    return _player_name_key(_canonical_player_name_for_season(value, season))


def _load_chart_spec(filename):
    path = PROJECT_ROOT / "data" / "charts" / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _profile_timeline_chart(player_name):
    spec = _load_chart_spec("player_full_profile_career_timeline.json")
    if not spec:
        return '<p class="empty-chart">No career milestones available.</p>'
    dataset_key = next(
        (key for key, rows in spec.get("datasets", {}).items() if rows and {"player", "event_key", "row_type"} <= rows[0].keys()),
        None,
    )
    if not dataset_key:
        return '<p class="empty-chart">No career milestones available.</p>'
    spec["datasets"][dataset_key] = [
        row for row in spec["datasets"][dataset_key]
        if str(row.get("player") or "").strip() == player_name
    ]
    if not spec["datasets"][dataset_key]:
        return '<p class="empty-chart">No career milestones available.</p>'
    labelled_games = set()
    for row in sorted(spec["datasets"][dataset_key], key=lambda item: (item.get("event_sort") or 0, item.get("event_rank") or 0)):
        first_xv_milestone = row.get("event_key") in {"first_xv_debut", "milestone_25_1st", "milestone_50_1st", "milestone_100_1st"}
        club_milestone = row.get("event_key") in {"debut", "milestone_25", "milestone_50", "milestone_100"}
        row["milestone_y_offset"] = 15 if row.get("event_key") == "last_game" else 7 if club_milestone else 23 if first_xv_milestone else 0
        game_key = (row.get("game_id"), row.get("date"), row.get("detail"))
        row["detail_label"] = row.get("detail") if game_key not in labelled_games else ""
        labelled_games.add(game_key)
        row["detail_y_offset"] = row["milestone_y_offset"] - 26
        row["detail_label_color"] = {
            "first_xv_debut": "#202946",
            "first_try": "#991515",
            "first_xv_try": "#991515",
            "first_captaincy": "#7d96e8",
        }.get(row.get("event_key"), "#4a5568")
    labelled_rows = sorted(
        (row for row in spec["datasets"][dataset_key] if row["detail_label"]),
        key=lambda row: (row.get("event_sort") or 0, row.get("event_rank") or 0),
    )
    previous_date = None
    previous_label_row = None
    for row in labelled_rows:
        event_date = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00")).date()
        days_since_previous = (event_date - previous_date).days if previous_date else None
        if days_since_previous is None or days_since_previous >= 45:
            row["detail_x_lane"] = 0
        else:
            previous_label_row["detail_x_lane"] = -1
            row["detail_x_lane"] = 1
        previous_date = event_date
        previous_label_row = row
    spec["width"] = 900
    spec["height"] = 60
    spec["layer"][1].setdefault("encoding", {})["yOffset"] = {
        "field": "milestone_y_offset",
        "type": "quantitative",
        "scale": None,
    }
    spec["layer"][2].setdefault("encoding", {})["yOffset"] = {
        "field": "milestone_y_offset",
        "type": "quantitative",
        "scale": None,
    }
    detail_layer = spec["layer"][5]
    detail_layers = []
    for x_lane in (-1, 0, 1):
        lane_layer = copy.deepcopy(detail_layer)
        lane_layer["transform"] = [{"filter": f"datum.detail_label !== '' && datum.detail_x_lane == {x_lane}"}]
        lane_layer.setdefault("encoding", {})["text"] = {"field": "detail_label", "type": "nominal"}
        lane_layer.setdefault("encoding", {})["color"] = {
            "field": "detail_label_color",
            "type": "nominal",
            "scale": None,
            "legend": None,
        }
        lane_layer.setdefault("encoding", {})["yOffset"] = {
            "field": "detail_y_offset",
            "type": "quantitative",
            "scale": None,
        }
        lane_layer["mark"]["align"] = "left"
        lane_layer["mark"]["baseline"] = "middle"
        lane_layer["mark"]["angle"] = 270
        lane_layer["mark"]["xOffset"] = x_lane * 8
        lane_layer["mark"].pop("yOffset", None)
        detail_layers.append(lane_layer)
    spec["layer"] = spec["layer"][:5] + detail_layers
    return f'<div class="career-chart career-chart--below-legend" style="padding:0;border:0;display:block"><style>@media print{{.career-chart--below-legend>svg{{width:100%!important}}.career-chart--below-legend .full-profile-timeline-legend-block{{display:table;width:max-content;margin:4px 0 0 auto}}.career-chart--below-legend .full-profile-timeline-legend-groups{{display:flex;gap:34px}}.career-chart--below-legend .full-profile-timeline-legend-group{{margin-bottom:0}}}}</style>{vlc.vegalite_to_svg(spec)}{_timeline_legend_html()}</div>'


def _timeline_legend_html():
    def icon(scope_class, level_class, text=""):
        inner = f'<span class="match-team-sheet-milestone-text">{text}</span>' if text else ""
        return f'<span class="match-team-sheet-milestone {scope_class} {level_class}"><span class="match-team-sheet-milestone-core">{inner}</span></span>'

    def paired_icon(level_class, text):
        return (
            '<span class="match-team-sheet-legend-pair">'
            f'<span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--club">{icon("match-team-sheet-milestone--scope-club", level_class, text)}</span>'
            f'<span class="match-team-sheet-legend-pair-icon match-team-sheet-legend-pair-icon--first-xv">{icon("match-team-sheet-milestone--scope-first-xv", level_class, text)}</span>'
            '</span>'
        )

    def event_glyph(letter, color):
        return f'<span class="full-profile-timeline-event-glyph" style="color:{color}">{letter}</span>'

    return f'''<style>.full-profile-timeline-legend-block .match-team-sheet-milestone{{width:18px;height:18px}}.full-profile-timeline-legend-block .match-team-sheet-milestone-text{{font-size:7px}}.full-profile-timeline-legend-block .full-profile-timeline-event-glyph{{width:18px;height:18px;font-size:14px}}.full-profile-timeline-legend-block .full-profile-timeline-event-glyph--star{{font-size:15px}}.full-profile-timeline-legend-block .match-team-sheet-legend-item,.full-profile-timeline-legend-block .match-team-sheet-legend-text{{font-size:9px}}</style><div class="match-team-sheet-legend full-profile-timeline-legend-block full-profile-timeline-legend-block--combined" aria-label="Timeline milestone and event key">
        <div class="full-profile-timeline-legend-groups">
            <div class="full-profile-timeline-legend-group full-profile-timeline-legend-group--appearance">
                <h4 class="match-team-sheet-legend-title">Appearance milestones</h4>
                <div class="match-team-sheet-legend-row full-profile-timeline-appearance-row">
                    <span class="match-team-sheet-legend-scopes">Club<br><strong>1st XV</strong></span>
                    <span class="match-team-sheet-legend-item">{paired_icon("match-team-sheet-milestone--debut", "1")}<span class="match-team-sheet-legend-text">Debut</span></span>
                    <span class="match-team-sheet-legend-item">{paired_icon("match-team-sheet-milestone--25", "25")}<span class="match-team-sheet-legend-text">25th</span></span>
                    <span class="match-team-sheet-legend-item">{paired_icon("match-team-sheet-milestone--50", "50")}<span class="match-team-sheet-legend-text">50th</span></span>
                    <span class="match-team-sheet-legend-item">{paired_icon("match-team-sheet-milestone--100", "100")}<span class="match-team-sheet-legend-text">100th</span></span>
                    <span class="match-team-sheet-legend-item">{icon("match-team-sheet-milestone--last", "")}<span class="match-team-sheet-legend-text">Latest</span></span>
                </div>
            </div>
            <div class="full-profile-timeline-legend-group full-profile-timeline-legend-group--events">
                <h4 class="match-team-sheet-legend-title">Other events</h4>
                <div class="match-team-sheet-legend-row full-profile-timeline-event-row">
                    <span class="match-team-sheet-legend-item">{event_glyph("T", "#991515")}<span class="match-team-sheet-legend-text">1st try</span></span>
                    <span class="match-team-sheet-legend-item">{event_glyph("C", "#7d96e8")}<span class="match-team-sheet-legend-text">1st captain</span></span>
                    <span class="match-team-sheet-legend-item"><span class="full-profile-timeline-event-glyph full-profile-timeline-event-glyph--star">★</span><span class="match-team-sheet-legend-text">MOTM</span></span>
                </div>
            </div>
        </div>
    </div>'''


def _league_history_legend_html(star_shape):
    star_path = html.escape(str(star_shape or ""), quote=True)

    def squad_symbol(fill, stroke, text=""):
        text_svg = f'<text class="league-history-legend-position-text" x="8" y="12" text-anchor="middle" fill="{text}">3</text>' if text else ""
        return f'<span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="8" fill="{fill}" stroke="{stroke}"/>{text_svg}</svg></span>'

    champion_symbols = []
    for fill, stroke in (("#202946", "#7d96e8"), ("#7d96e8", "#202946")):
        champion_symbols.append(
            f'<span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="-8 -8 16 16"><g transform="scale(5)"><path d="{star_path}" fill="{fill}" stroke="{stroke}" stroke-width=".2"/></g></svg></span>'
        )
    return (
        '<div class="performance-set-piece-legend performance-trend-legend league-history-legend" aria-label="League history chart legend">'
        '<span class="performance-set-piece-legend-item performance-trend-legend-item">'
        '<span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#202946" stroke="#7d96e8" stroke-width="1"/></svg></span><span>1st XV</span></span>'
        '<span class="performance-set-piece-legend-item performance-trend-legend-item">'
        '<span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#7d96e8" stroke="#202946" stroke-width="1"/></svg></span><span>2nd XV</span></span>'
        '<span class="performance-set-piece-legend-item performance-trend-legend-item">'
        + "".join(champion_symbols) + '<span>League Champions</span></span>'
        '<span class="performance-set-piece-legend-item performance-trend-legend-item">'
        + squad_symbol("#202946", "none", "#ffffff")
        + squad_symbol("#7d96e8", "none", "#202946")
        + '<span>League Position</span></span></div>'
    )


def _profile_league_history_chart(appearances):
    spec = _load_chart_spec("league_history_progression.json")
    if not spec:
        return '<p class="empty-chart">No league history is available for this player.</p>'
    competitive_appearances = [
        appearance for appearance in appearances
        if str(appearance.get("game_type") or "").casefold() in {"league", "cup"}
    ]
    appearance_counts = {}
    for appearance in competitive_appearances:
        key = (appearance["season"], appearance["squad"])
        appearance_counts[key] = appearance_counts.get(key, 0) + 1
    dataset_key = next(
        (key for key, rows in spec.get("datasets", {}).items() if rows and {"season", "squad", "level", "rank"} <= rows[0].keys()),
        None,
    )
    if not dataset_key:
        return '<p class="empty-chart">No league history is available for this player.</p>'
    champion_shape = next(
        (row.get("marker_shape") for row in spec["datasets"][dataset_key] if str(row.get("marker_shape") or "").startswith("M")),
        "",
    )
    history_rows = [
        row for row in spec["datasets"][dataset_key]
        if (row.get("season"), row.get("squad")) in appearance_counts and not row.get("is_no_league")
    ]
    if not history_rows:
        return '<p class="empty-chart">No league history is available for this player.</p>'
    levels = sorted({int(row["level"]) for row in history_rows if row.get("level") is not None})
    appearance_seasons = [str(row.get("season") or "") for row in competitive_appearances]
    appearance_years = [int(match.group(1)) for season in appearance_seasons if (match := re.match(r"^(\d{4})/", season))]
    if not appearance_years:
        return '<p class="empty-chart">No season labels are available for this player.</p>'
    first_year, last_year = min(appearance_years), max(appearance_years)
    seasons = [f"{year}/{(year + 1) % 100:02d}" for year in range(first_year, last_year + 1)]
    chart_seasons = [f"{first_year - 1}/{first_year % 100:02d}", *seasons, f"{last_year + 1}/{(last_year + 2) % 100:02d}"]
    season_year = {season: first_year + index for index, season in enumerate(seasons)}
    for row in history_rows:
        count = appearance_counts[(row["season"], row["squad"])]
        row["player_appearances"] = count
        row["player_appearance_label"] = f"{count} game" if count == 1 else f"{count} games"
    active_years_by_squad = {}
    for appearance in appearances:
        match = re.match(r"^(\d{4})/", str(appearance.get("season") or ""))
        if match:
            active_years_by_squad.setdefault(appearance["squad"], set()).add(int(match.group(1)))
    for squad in {row["squad"] for row in history_rows}:
        squad_rows = sorted((row for row in history_rows if row["squad"] == squad), key=lambda row: season_year.get(row["season"], 0))
        line_segment = 0
        previous_year = None
        for row in squad_rows:
            current_year = season_year.get(row["season"])
            intervening_years = range(previous_year + 1, current_year) if previous_year is not None and current_year is not None else ()
            has_inactive_gap = any(year not in active_years_by_squad.get(squad, set()) for year in intervening_years)
            if has_inactive_gap:
                line_segment += 1
            row["line_segment"] = f"{squad}-{line_segment}"
            previous_year = current_year
    spec["datasets"][dataset_key] = history_rows
    for key, rows in spec.get("datasets", {}).items():
        if rows and "level" in rows[0]:
            spec["datasets"][key] = [row for row in rows if row.get("level") is None or int(row["level"]) in levels]
            rows = spec["datasets"][key]
        if rows and {"historic", "current", "left_anchor", "right_anchor"} <= rows[0].keys():
            for row in rows:
                row["left_anchor"] = chart_seasons[0]
                row["right_anchor"] = chart_seasons[-1]
        elif rows and {"season_start", "season_end", "level_start", "level_end", "label"} <= rows[0].keys():
            special = [row for row in history_rows if row.get("is_non_rfu") and row.get("squad") == "2nd"]
            if special:
                special_seasons = sorted(special, key=lambda row: (int(str(row["season"])[:4]), row["season"]))
                rows[:] = [{
                    "season_start": special_seasons[0]["season"],
                    "season_end": special_seasons[-1]["season"],
                    "level_start": min(int(row["level"]) for row in special),
                    "level_end": max(int(row["level"]) for row in special),
                    "label": "Non-RFU leagues",
                }]
            else:
                rows[:] = []

    def set_season_domain(value):
        if isinstance(value, dict):
            if value.get("field") in {"season", "left_anchor", "right_anchor", "season_start", "season_end"}:
                value["sort"] = chart_seasons
                value.setdefault("scale", {})["domain"] = chart_seasons
                if value.get("field") == "season":
                    value.setdefault("axis", {})["values"] = seasons
                    value["axis"]["title"] = None
            if value.get("field") in {"level", "level_start", "level_end"}:
                value["sort"] = levels
                value.setdefault("scale", {})["domain"] = levels
            for child in value.values():
                set_season_domain(child)
        elif isinstance(value, list):
            for child in value:
                set_season_domain(child)

    set_season_domain(spec.get("layer", []))
    spec.pop("title", None)
    chart_step_width = min(70, max(24, (700 - 60) // max(len(chart_seasons), 1)))
    spec["width"] = {"step": chart_step_width}
    spec["height"] = {"step": 44}
    for layer in spec.get("layer", []):
        mark = layer.get("mark", {})
        encoding = layer.get("encoding", {})
        text_field = encoding.get("text", {}).get("field")
        if mark.get("type") == "point":
            mark["size"] = min(mark.get("size", 500), 500)
        if mark.get("type") == "text":
            mark["fontSize"] = min(mark.get("fontSize", 10), 10)
            if text_field == "rank_label":
                mark["fontSize"] = 12
            if text_field == "player_appearance_label":
                mark["dy"] = 10
                mark["yOffset"] = 15
    for layer in spec.get("layer", []):
        mark = layer.get("mark", {})
        if mark.get("type") == "line":
            layer.setdefault("encoding", {})["detail"] = {"field": "line_segment", "type": "nominal"}
    text_layer = {
        "data": {"name": dataset_key},
        "transform": [{"filter": "!(datum.is_non_rfu && datum.squad == '2nd')"}],
        "mark": {"type": "text", "font": "PT Sans Narrow", "fontSize": 10, "fontWeight": "bold", "dy": 14, "color": "#414958", "baseline": "top"},
        "encoding": {
            "x": {"field": "season", "type": "nominal", "sort": chart_seasons, "scale": {"domain": chart_seasons}},
            "y": {"field": "level", "type": "ordinal", "sort": levels, "scale": {"domain": levels}},
            "text": {"field": "player_appearance_label", "type": "nominal"},
            "detail": {"field": "squad", "type": "nominal"},
        },
    }
    non_rfu_text_layer = {
        "data": {"name": dataset_key},
        "transform": [{"filter": "datum.is_non_rfu && datum.squad == '2nd'"}],
        "mark": {"type": "text", "font": "PT Sans Narrow", "fontSize": 10, "fontWeight": "bold", "dy": 14, "yOffset": 21, "color": "#414958", "baseline": "top"},
        "encoding": {
            "x": {"field": "season", "type": "nominal", "sort": chart_seasons, "scale": {"domain": chart_seasons}},
            "y": {"field": "level", "type": "ordinal", "sort": levels, "scale": {"domain": levels}},
            "text": {"field": "player_appearance_label", "type": "nominal"},
            "detail": {"field": "squad", "type": "nominal"},
        },
    }
    spec["layer"].extend([text_layer, non_rfu_text_layer])
    svg = vlc.vegalite_to_svg(spec)
    _legacy_legend_markup = '''<div class="performance-set-piece-legend performance-trend-legend league-history-legend" aria-label="League history chart legend">
            <span class="performance-set-piece-legend-item performance-trend-legend-item"><span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#202946" stroke="#7d96e8" stroke-width="1"/></svg></span><span>1st XV</span></span>
            <span class="performance-set-piece-legend-item performance-trend-legend-item"><span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#7d96e8" stroke="#202946" stroke-width="1"/></svg></span><span>2nd XV</span></span>
            <span class="performance-set-piece-legend-item performance-trend-legend-item"><span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#ffffff" stroke="#202946" stroke-width="1"/></svg></span><span>3rd XV</span></span>
            <span class="performance-set-piece-legend-item performance-trend-legend-item">
                <span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="-8 -8 16 16"><g transform="scale(5)"><path d="M-.1041-1.3497-.0786-1.4111-.0554-1.4668C-.0349-1.5161.0349-1.5161.0554-1.4668L.0786-1.4111.1041-1.3497.1083-1.3396.3827-.6799C.3913-.6591.4109-.645.4333-.6432L1.1455-.5861 1.1563-.5852 1.2226-.5799 1.2828-.5751C1.336-.5708 1.3576-.5044 1.317-.4697L1.2712-.4304 1.2207-.3871 1.2124-.3801.6698.0847C.6527.0994.6453.1223.6505.1442L.8162.8392.8188.8498.8342.9145.8482.9732C.8606 1.0251.8041 1.0661.7586 1.0383L.7071 1.0069.6503.9722.641.9665.0313.5941C.0121.5824-.0121.5824-.0313.5941L-.641.9665-.6503.9722-.707 1.0069-.7585 1.0383C-.804-.8606-.5044-.8606.0164.0952.6295-.595 1.0393Z" fill="#202946" stroke="#7d96e8" stroke-width=".2"/></g></svg></span>
                <span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="-8 -8 16 16"><g transform="scale(5)"><path d="M-.1041-1.3497-.0786-1.4111-.0554-1.4668C-.0349-1.5161.0349-1.5161.0554-1.4668L.0786-1.4111.1041-1.3497.1083-1.3396.3827-.6799C.3913-.6591.4109-.645.4333-.6432L1.1455-.5861 1.1563-.5852 1.2226-.5799 1.2828-.5751C1.336-.5708 1.3576-.5044 1.317-.4697L1.2712-.4304 1.2207-.3871 1.2124-.3801.6698.0847C.6527.0994.6453.1223.6505.1442L.8162.8392.8188.8498.8342.9145.8482.9732C.8606 1.0251.8041 1.0661.7586 1.0383L.7071 1.0069.6503.9722.641.9665.0313.5941C.0121.5824-.0121.5824-.0313.5941L-.641.9665-.6503.9722-.707 1.0069-.7585 1.0383C-.804-.8606-.5044-.8606.0164.0952.6295-.595 1.0393Z" stroke="#202946" fill="#7d96e8" stroke-width=".2"/></g></svg></span>
                <span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="-8 -8 16 16"><g transform="scale(5)"><path d="M-.1041-1.3497-.0786-1.4111-.0554-1.4668C-.0349-1.5161.0349-1.5161.0554-1.4668L.0786-1.4111.1041-1.3497.1083-1.3396.3827-.6799C.3913-.6591.4109-.645.4333-.6432L1.1455-.5861 1.1563-.5852 1.2226-.5799 1.2828-.5751C1.336-.5708 1.3576-.5044 1.317-.4697L1.2712-.4304 1.2207-.3871 1.2124-.3801.6698.0847C.6527.0994.6453.1223.6505.1442L.8162.8392.8188.8498.8342.9145.8482.9732C.8606 1.0251.8041 1.0661.7586 1.0383L.7071 1.0069.6503.9722.641.9665.0313.5941C.0121.5824-.0121.5824-.0313.5941L-.641.9665-.6503.9722-.707 1.0069-.7585 1.0383C-.804-.8606-.5044-.8606.0164.0952.6295-.595 1.0393Z" stroke="#202946" fill="#ffffff" stroke-width=".2"/></g></svg></span>
                <span>League Champions</span>
            </span>
            <span class="performance-set-piece-legend-item performance-trend-legend-item">
                <span class="league-history-legend-symbol" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="8" fill="#202946"/><text class="league-history-legend-position-text" x="8" y="12" text-anchor="middle" fill="#ffffff">3</text></svg></span>
            star_shape = next((row.get("marker_shape") for row in _chart_dataset_rows("league_history_progression.json", ("marker_shape",)) if str(row.get("marker_shape") or "").startswith("M")), "")
            return f'<div class="league-chart" style="padding:0;border:0">{svg}{_league_history_legend_html(star_shape)}</div>'
      <div class="timeline-legend-group"><strong>Other events</strong>
        <span class="timeline-event timeline-event--try">T <em>First try</em></span>
        <span class="timeline-event timeline-event--captain">C <em>First captaincy</em></span>
        <span class="timeline-event timeline-event--motm">★ <em>MOTM</em></span>
      </div>
    </div>'''
    return f'<div class="league-chart" style="padding:0;border:0">{svg}{_league_history_legend_html(champion_shape)}</div>'


def _embedded_image(path):
    if not path or not Path(path).is_file():
        return ""
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _markdown_html(markdown, custom_sections=None):
    custom_sections = custom_sections or {}
    lines = markdown.splitlines()
    output = []
    index = 0
    in_summary = False
    in_summary_card = False
    in_teammates = False
    in_teammate_card = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("@@") and line.endswith("@@"):
            output.append(custom_sections.get(line[2:-2], ""))
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            rows = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in table_lines]
            rows = [row for row in rows if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in row)]
            if rows:
                grouped_headers = [cell.split("::", 1) if "::" in cell else ("", cell) for cell in rows[0]]
                header_groups = {group for group, _ in grouped_headers}
                table_kind = "season-summary" if {"1st XV", "2nd XV"}.issubset(header_groups) else "grouped-table" if any(header_groups) else ""
                labels = [label.strip().casefold() for _, label in grouped_headers]
                if "scores" in labels:
                    table_kind += " appearance-table"
                elif any(label in {"tries", "conversions", "penalties", "drop goals", "points"} for label in labels):
                    table_kind += " scoring-table"
                scoring_table_style = ' style="width:max-content;max-width:100%"' if "scoring-table" in table_kind else ""
                lineout_class = " lineout-table" if {"attempts", "success"} <= set(labels) else ""
                output.append(f'<div class="table-wrap"><table class="table table-striped table-hover align-middle database-data-table {table_kind.strip()}{lineout_class}"{scoring_table_style}>')
                if "scoring-table" in table_kind:
                    output.append('<colgroup><col style="width:24ch">' + ''.join('<col style="width:20ch">' for _ in grouped_headers[1:]) + '</colgroup>')
                output.append("<thead>")
                if table_kind:
                    output.append("<tr class=\"group-header\">")
                    header_group_names = list(dict.fromkeys(group for group, _ in grouped_headers))
                    for group_index, group in enumerate(header_group_names):
                        span = sum(1 for current, _ in grouped_headers if current == group)
                        boundary_classes = "group-start group-end"
                        output.append(f'<th colspan="{span}" class="group-{_slug(group)} {boundary_classes}">{html.escape(group)}</th>')
                    output.append("</tr><tr>")
                else:
                    output.append("<tr>")
                for index_header, (group, label) in enumerate(grouped_headers):
                    classes = [f"group-{_slug(group)}", f"column-{_slug(label)}"] if group else [f"column-{_slug(label)}"]
                    if group and (index_header == 0 or grouped_headers[index_header - 1][0] != group):
                        classes.append("group-start")
                    if group and (index_header == len(grouped_headers) - 1 or grouped_headers[index_header + 1][0] != group):
                        classes.append("group-end")
                    output.append(f'<th class="{" ".join(classes)}">{html.escape(label)}</th>')
                output.append("</tr></thead><tbody>")
                games_index = next((i for i, (_, label) in enumerate(grouped_headers) if label.strip().casefold() == "games"), None)
                games_max = max((int(r[games_index]) for r in rows[1:] if games_index is not None and games_index < len(r) and r[games_index].isdigit()), default=0)
                column_max = {
                    i: max((int(r[i]) for r in rows[1:] if i < len(r) and r[i].isdigit()), default=0)
                    for i in range(1, len(grouped_headers))
                } if "scoring-table" in table_kind else {}
                for row in rows[1:]:
                    cells = row + [""] * (len(grouped_headers) - len(row))
                    squad_index = next((i for i, (_, label) in enumerate(grouped_headers) if label.strip().casefold() == "squad"), None)
                    squad_value = cells[squad_index].strip().casefold() if squad_index is not None else ""
                    row_class = "squad-1st" if squad_value == "1st" else "squad-2nd" if squad_value == "2nd" else ""
                    output.append(f'<tr class="{row_class}">')
                    for index_cell, (group, label) in enumerate(grouped_headers):
                        value = cells[index_cell]
                        classes = [f"group-{_slug(group)}", f"column-{_slug(label)}"] if group else [f"column-{_slug(label)}"]
                        if group and (index_cell == 0 or grouped_headers[index_cell - 1][0] != group):
                            classes.append("group-start")
                        if group and (index_cell == len(grouped_headers) - 1 or grouped_headers[index_cell + 1][0] != group):
                            classes.append("group-end")
                        label_key = label.strip().casefold()
                        if label_key in {"h/a", "result", "results", "captain", "motm", "google sheets", "pitchero", "rfu", "data source"}:
                            classes.append("categorical")
                        if value.strip() == "✓":
                            classes.append("source-flag")
                        rendered_value = html.escape(value).replace("✓", "&#10003;")
                        if label_key == "success" and value.endswith("%"):
                            pct = float(value.rstrip("%"))
                            tier = "high" if pct >= 85 else "mid" if pct >= 70 else "low"
                            rendered_value = f'<span class="data-bar data-bar--{tier}" style="--pct:{pct:.1f}%">{html.escape(value)}</span>'
                        elif label_key == "games" and games_max and value.isdigit():
                            rendered_value = f'<span class="data-bar data-bar--count" style="--pct:{100 * int(value) / games_max:.1f}%">{html.escape(value)}</span>'
                        elif "scoring-table" in table_kind and index_cell and value.isdigit():
                            rendered_value = f'<span class="data-bar data-bar--score" style="--pct:{100 * int(value) / column_max[index_cell]:.1f}%">{value}</span>' if int(value) else '<span class="zero-value">0</span>'
                        if label_key == "squad" and value:
                            rendered_value = f'<span class="squad-pill">{html.escape(value)} XV</span>'
                        elif label_key == "captain" and value:
                            rendered_value = '<span class="captain-marker">C</span>'
                        elif label_key == "motm" and value:
                            rendered_value = '<span class="motm-marker">★</span>'
                        elif label_key == "scores" and value:
                            rendered_value = " ".join(f'<span class="score-marker">{html.escape(marker.strip())}</span>' for marker in value.split(","))
                        elif label_key in {"result", "results"} and value:
                            if re.match(r"^W\s+\d+\s+L\s+\d+", value.strip(), re.IGNORECASE):
                                chips = re.findall(r"([WLD])\s+(\d+)", value.strip(), re.IGNORECASE)
                                outcome_classes = {"W": "win", "L": "loss", "D": "draw"}
                                rendered_value = " ".join(
                                    f'<span class="record-chip record-chip--{outcome_classes[outcome.upper()]}">{outcome.upper()} {count}</span>'
                                    for outcome, count in chips
                                )
                            else:
                                match = re.match(r"^([WLD])(?:\s+(.*))?$", value.strip(), re.IGNORECASE)
                                if match:
                                    outcome = match.group(1).upper()
                                    result_class = {"W": "win", "L": "loss", "D": "draw"}[outcome]
                                    detail = f" {html.escape(match.group(2))}" if match.group(2) else ""
                                    rendered_value = f'<span class="result-badge result-badge--{result_class}">{outcome}{detail}</span>'
                        output.append(f'<td class="{" ".join(classes)}">{rendered_value}</td>')
                    output.append("</tr>")
                output.append("</tbody></table></div>")
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            heading_class = ' class="page-break-heading" style="break-before:page"' if title.casefold() in {"playing record", "season summaries"} else ""
            heading_written = False
            if level == 2:
                if in_summary_card:
                    output.append("</section>")
                    in_summary_card = False
                if in_summary:
                    output.append("</div>")
                in_summary = title.casefold() == "summary"
                if in_teammate_card:
                    output.append("</section>")
                    in_teammate_card = False
                if in_teammates:
                    output.append("</div>")
                in_teammates = title.casefold() == "most common teammates"
                if level > 1:
                    output.append(f"<h{level}{heading_class}>{html.escape(title)}</h{level}>")
                    heading_written = True
                if in_summary:
                    output.append('<div class="summary-layout">')
                if in_teammates:
                    output.append('<div class="teammate-layout">')
            elif in_summary and level == 3:
                if in_summary_card:
                    output.append("</section>")
                    in_summary_card = False
                if title.casefold() == "profile detail":
                    output.append("</div>")
                    in_summary = False
                else:
                    output.append('<section class="summary-card">')
                    in_summary_card = True
            elif in_teammates and level == 3:
                if in_teammate_card:
                    output.append("</section>")
                output.append('<section class="teammate-card">')
                in_teammate_card = True
            if level > 1 and not heading_written:
                output.append(f"<h{level}{heading_class}>{html.escape(title)}</h{level}>")
        elif line.strip():
            if line.startswith("Main position:"):
                parts = re.split(r"\.\s+(?=(?:Secondary position|Career scoring):)", line)
                output.append('<div class="profile-detail-list">' + "".join(f"<p>{html.escape(part.rstrip('.'))}</p>" for part in parts) + "</div>")
            else:
                output.append(f"<p>{html.escape(line)}</p>")
        index += 1
    if in_summary_card:
        output.append("</section>")
    if in_summary:
        output.append("</div>")
    if in_teammate_card:
        output.append("</section>")
    if in_teammates:
        output.append("</div>")
    return "\n".join(output)


def _html_document(markdown, entity, image_data, image_alt, avatar_data, custom_sections=None, background_data=""):
    rendered = _markdown_html(markdown, custom_sections)
    crest_path = PROJECT_ROOT / "img" / "logos" / "EastGrinstead.png"
    crest_data = _embedded_image(crest_path)
    club_image = f'<img class="hero-club" src="{crest_data}" alt="East Grinstead RFC">' if crest_data else ""
    hero_image = f'<img class="hero-image" src="{image_data}" alt="{html.escape(image_alt)}">' if image_data else ""
    avatar = f'<img class="brand-avatar" src="{avatar_data}" alt="SLM">' if avatar_data else ""
    brand_header = f'<div class="brand"><img class="brand-avatar" src="{avatar_data}" alt="SLM"><span class="brand-url">eg-stats.uk</span><span class="report-date">Data as at<br>{date.today().strftime("%-d %B %Y")}</span></div>'
    hero_background = f'background-image:linear-gradient(rgba(32,41,70,.42),rgba(32,41,70,.58)),url("{background_data}");' if background_data else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EGRFC Stats Report</title>
<style>
:root{{--navy:{SITE_COLORS['navy']};--accent:{SITE_COLORS['blue']};--red:{SITE_COLORS['red']};--paper:{SITE_COLORS['paper']};--ink:#202124;--muted:#60656d}}
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}body{{margin:0;background-color:#e9ebef;color:var(--ink);font:15px/1.45 "PT Sans Narrow","Aptos",sans-serif}}
main{{max-width:1280px;margin:24px auto;background:rgba(255,255,255,.94);box-shadow:0 8px 32px #2029461c;padding:0 34px 30px}}
.hero{{display:flex;align-items:center;gap:18px;margin:0 -34px 26px;padding:8px 26px 0;background-color:var(--navy);{hero_background}background-size:cover;background-position:center 25%;color:white;border-bottom:7px solid var(--accent);min-height:172px;position:relative;overflow:hidden}}
.hero-club{{position:absolute;top:8px;left:26px;width:104px;height:104px;object-fit:contain;z-index:1}}.hero-image{{width:170px;height:180px;object-fit:contain;object-position:center bottom;align-self:flex-end;flex:0 0 auto;margin-left:88px;background:transparent;position:relative;z-index:2}}
.hero-copy{{flex:1;min-width:0;padding:16px 0 10px}}h1{{color:#fff;font-size:34px;line-height:1.05;margin:0}}.hero-subtitle{{margin:6px 0 0;color:#d9dfed;font-size:18px;font-weight:400;line-height:1.1}}
.brand{{display:flex;flex-direction:column;align-items:center;gap:3px;text-align:center;color:#fff;font-weight:700;white-space:nowrap;align-self:center}}.brand-avatar{{height:88px;width:88px;object-fit:contain;flex:0 0 auto}}
.report-date{{font-size:12px;font-weight:400;color:#d9dfed;text-align:center}}
.brand-url{{font-size:20px}}footer{{display:flex;justify-content:flex-end;align-items:center;gap:8px;border-top:2px solid var(--navy);padding-top:10px;margin-top:32px;color:var(--navy);font-weight:700}}
h2{{color:var(--navy);font-size:23px;margin:30px 0 11px;padding-bottom:0;border-bottom:0}}h3{{color:var(--accent);font-size:17px;margin:15px 0 8px;padding-top:6px;border-top:1px solid #d6d9df}}p{{margin:8px 0}}
.career-summary-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 18px}}.career-summary-subtitle{{color:var(--navy);font-size:18px;margin:18px 0 7px;padding-bottom:4px;border-bottom:1px solid #d6d9df}}.profile-summary-group{{border:1px solid #d8e2f3;border-radius:5px;background:#fff;padding:9px 12px;min-width:0}}.profile-summary-group h3{{margin:0 0 3px;padding-top:0;border-top:0;color:#23325a;font-size:17px;font-weight:800;text-transform:uppercase}}.profile-summary-group--first-xv{{border-color:var(--navy);background:var(--navy);color:#fff}}.profile-summary-group--first-xv h3,.profile-summary-group--first-xv p,.profile-summary-group--first-xv strong{{color:#fff}}.profile-summary-lines{{display:grid;gap:2px}}.profile-summary-lines p{{margin:2px 0;line-height:1.35}}.summary-result{{font-weight:700;color:var(--navy)}}.profile-summary-group--first-xv .summary-result{{color:#fff}}
.profile-detail-list{{display:flex;gap:16px;flex-wrap:wrap;color:#34405a}}.profile-detail-list p{{margin:0}}
.record-chip-group{{display:inline-flex;gap:3px;margin-left:3px;vertical-align:middle}}.record-chip{{display:inline-flex;padding:2px 6px;border-radius:99px;font-size:12px;font-weight:700;line-height:1.1}}.record-chip--win{{background:#d4edda;color:#146f14}}.record-chip--loss{{background:#f8d7da;color:#991515}}.record-chip--draw{{background:#fff3cd;color:#856404}}.result-badge{{display:inline-block;padding:.1em .45em;border-radius:.25rem;font-weight:600;font-size:.85em;white-space:nowrap}}.result-badge--win{{background:#d4edda;color:#146f14}}.result-badge--loss{{background:#f8d7da;color:#991515}}.result-badge--draw{{background:#fff3cd;color:#856404}}.profile-last-ten-line{{display:flex;align-items:center;gap:5px;flex-wrap:wrap}}.last-ten-results-strip{{display:inline-flex;gap:3px}}.last-ten-result{{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;font-size:11px;font-weight:700}}.last-ten-result--win{{background:#d4edda;color:#146f14}}.last-ten-result--loss{{background:#f8d7da;color:#991515}}.last-ten-result--draw{{background:#fff3cd;color:#856404}}
.teammate-layout{{display:flex;flex-flow:row nowrap;gap:12px;overflow-x:auto;padding-bottom:6px}}.teammate-card{{flex:0 0 260px;min-width:0;padding:10px;background:#fff;border:1px solid #d8e2f3;border-radius:4px}}.teammate-card h3{{margin:0 0 7px;color:var(--navy);font-size:16px}}
.table-wrap{{overflow-x:auto;margin:6px 0 12px}}table{{border-collapse:collapse;width:100%;font-size:14px;page-break-inside:auto;table-layout:auto}}
table.database-data-table{{background:#fff;border:1px solid #d9e0f0}}.database-data-table thead th{{background:var(--navy);color:#fff;text-align:left;font-weight:700;white-space:nowrap}}.database-data-table tbody tr:nth-child(odd){{background:#fff}}.database-data-table tbody tr:nth-child(even){{background:#f2f1f4}}.database-data-table tbody tr:hover{{background:rgba(125,150,232,.12)}}
thead{{display:table-header-group}}th{{background:var(--navy);color:#fff;text-align:left;font-weight:700;white-space:nowrap}}
th,td{{padding:5px 7px;border:1px solid #d9dce2;vertical-align:middle}}tbody tr{{page-break-inside:avoid}}
.group-header th{{background:#404b68;color:#fff;text-align:center;border-color:#fff}}th.group-1st-xv{{background:#202946}}th.group-2nd-xv{{background:#7d96e8;color:#15213e}}th.group-overall{{background:#45484e}}
table.season-summary thead .group-header th.group-1st-xv{{background:#202946;color:#fff;border-right:3px solid #7d96e8}}table.season-summary thead .group-header th.group-2nd-xv{{background:#7d96e8;color:#15213e;border-right:3px solid #62666e}}table.season-summary thead .group-header th.group-overall{{background:#45484e;color:#fff}}
table.season-summary td.group-1st-xv,table.scoring-table td.group-1st-xv{{background-color:#eef1f7}}table.season-summary td.group-2nd-xv,table.scoring-table td.group-2nd-xv{{background-color:#eaf1ff}}table.season-summary td.group-overall,table.scoring-table td.group-overall{{background-color:#f0f1f2}}
table.season-summary .group-1st-xv.group-start,table.scoring-table .group-1st-xv.group-start{{border-left:3px solid #202946!important}}table.season-summary .group-1st-xv.group-end,table.scoring-table .group-1st-xv.group-end{{border-right:3px solid #202946!important}}
table.season-summary .group-2nd-xv.group-start,table.scoring-table .group-2nd-xv.group-start{{border-left:3px solid #7d96e8!important}}table.season-summary .group-2nd-xv.group-end,table.scoring-table .group-2nd-xv.group-end{{border-right:3px solid #7d96e8!important}}
table.season-summary .group-overall.group-start,table.scoring-table .group-overall.group-start{{border-left:3px solid #62666e!important}}table.season-summary .group-overall.group-end,table.scoring-table .group-overall.group-end{{border-right:3px solid #62666e!important}}
.categorical{{text-align:center;font-weight:700;white-space:nowrap}}.checkmark{{color:#146f14;font-size:16px}}.squad-pill{{display:inline-block;padding:2px 9px;border-radius:20px;white-space:nowrap;font-weight:700}}.squad-1st .squad-pill{{background:#202946;color:#fff}}.squad-2nd .squad-pill{{background:#7d96e8;color:#202946}}
.appearance-table .column-captain,.appearance-table .column-motm,.appearance-table .column-number,.appearance-table .column-h-a,.appearance-table .column-google,.appearance-table .column-pitchero,.appearance-table .column-rfu{{width:1%;text-align:center;white-space:nowrap}}.appearance-table .column-scores{{white-space:nowrap;text-align:center}}.appearance-table .column-date{{min-width:92px}}.appearance-table .column-opposition{{min-width:120px}}.appearance-table .column-result{{min-width:90px;white-space:nowrap}}
.appearance-table .column-date{{width:14ch;min-width:14ch;max-width:14ch;font-variant-numeric:tabular-nums}}
.position-appearance-wrap{{overflow-x:auto;margin:8px 0 18px}}.position-appearance-wrap h3{{margin-bottom:6px}}.position-appearance-bar{{display:flex;gap:3px;width:100%;min-width:max-content;min-height:60px}}.position-bar-segment{{display:flex;flex:var(--segment-count) 1 0;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-width:max-content;padding:4px 10px;background:var(--segment-color);color:var(--segment-text);border-radius:7px;font-size:16px;font-weight:700;line-height:1.15;text-align:center;white-space:nowrap}}.position-bar-segment span{{font-size:13px;font-weight:400}}
.score-marker{{display:inline-block;color:#991515;font-weight:900;margin-right:5px;white-space:nowrap}}.captain-marker{{color:#7d96e8;font-weight:900}}.motm-marker{{color:#c6894a;font-size:16px}}.source-flag{{color:#146f14;font-weight:900}}
.season-summary th{{white-space:normal;text-align:center}}.season-summary td{{text-align:center;font-variant-numeric:tabular-nums}}.season-summary td:first-child{{text-align:left;font-weight:700}}
.data-bar{{display:block;padding:1px 6px;border-radius:4px;font-weight:700;font-variant-numeric:tabular-nums;background:linear-gradient(90deg,var(--bar) var(--pct),transparent var(--pct))}}.data-bar--high{{--bar:#cfe8d5;color:#146f14}}.data-bar--mid{{--bar:#dde4fa;color:#202946}}.data-bar--low{{--bar:#f6d4d7;color:#991515}}.data-bar--count{{--bar:rgba(125,150,232,.4);color:#202946}}
.data-bar--score{{--bar:#aab5d8;color:#202946}}.scoring-table td.group-2nd-xv .data-bar--score{{--bar:rgba(125,150,232,.5)}}.scoring-table td.group-overall .data-bar--score{{--bar:#d2d4d8}}.zero-value{{color:#a0a6b1}}
.lineout-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;align-items:start}}.lineout-grid .table-wrap{{margin:0}}.lineout-table{{width:100%}}.lineout-table th,.lineout-table td{{padding:4px 8px!important}}.lineout-table td:not(:first-child),.lineout-table th:not(:first-child){{text-align:center}}
.season-summary,.scoring-table,.teammate-card table,.lineout-table{{font-size:12px}}.season-summary th,.season-summary td,.scoring-table th,.scoring-table td,.teammate-card th,.teammate-card td{{padding:3px 5px}}
.scoring-table{{width:auto;max-width:100%;table-layout:auto}}.scoring-table th,.scoring-table td{{width:20ch;min-width:20ch;max-width:20ch;text-align:center;overflow:hidden;text-overflow:ellipsis}}.scoring-table th:first-child,.scoring-table td:first-child{{width:24ch;min-width:24ch;max-width:24ch;text-align:left}}.scoring-table thead th{{text-align:center}}.scoring-table thead tr:last-child th:first-child{{text-align:left}}
.career-chart,.league-chart{{width:100%;overflow-x:auto;background:#fff;border:1px solid #e0e3e9;padding:14px 12px}}.career-chart>svg,.league-chart>svg{{display:block;width:max(100%,1100px);max-width:none;height:auto}}.chart-legend{{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0;color:#535b69;font-size:12px}}.legend-dot{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}}.league-chart-title{{margin:0;color:var(--navy);font-size:20px;font-weight:900}}.league-chart-subtitle{{margin:0 0 8px;color:#59616e;font-size:12px}}.timeline-legend{{display:grid;gap:6px;margin-top:8px;color:#535b69;font-size:12px}}.timeline-legend-group{{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px}}.timeline-legend-group strong{{min-width:145px;color:var(--navy)}}.timeline-scope-label{{font-size:11px;color:#59616e}}.timeline-pair{{display:inline-flex;align-items:center;gap:3px}}.milestone-dot{{display:inline-flex;width:22px;height:22px;align-items:center;justify-content:center;border-radius:50%;font-style:normal;font-size:9px;font-weight:800}}.milestone-dot--club{{background:#fff;border:1px solid #202946;color:#202946}}.milestone-dot--xv{{background:#202946;border:1px solid #7d96e8;color:#fff}}.milestone-dot--latest{{background:#fff;border:2px solid #202946}}.timeline-event{{font-weight:900;font-size:15px}}.timeline-event em{{font-style:normal;font-size:12px;font-weight:400;color:#535b69}}.timeline-event--try{{color:#991515}}.timeline-event--captain{{color:#7d96e8}}.timeline-event--motm{{color:#c6894a}}
.full-profile-timeline-legend-block{{width:100%;border:1px solid #dbe2f4;border-radius:6px;background:#f2f1f4;padding:8px 12px}}.full-profile-timeline-legend-groups{{display:flex;flex-wrap:nowrap;gap:34px}}.full-profile-timeline-legend-group{{min-width:0}}.match-team-sheet-legend-title{{margin:0 0 4px;color:#4e5a7a;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}.match-team-sheet-legend-row{{display:flex;flex-wrap:wrap;gap:4px 11px;align-items:flex-start}}.match-team-sheet-legend-item{{display:inline-flex;flex-direction:column-reverse;align-items:center;gap:2px;color:#2f3a58;font-size:11px;line-height:1.2}}.match-team-sheet-legend-scopes{{color:#1f2a4a;font-size:11px;line-height:1;min-width:42px;margin-top:auto;text-align:right}}.match-team-sheet-legend-pair{{position:relative;display:inline-flex;align-items:center;width:31px;height:27px}}.match-team-sheet-legend-pair-icon{{position:absolute;display:inline-flex}}.match-team-sheet-legend-pair-icon--club{{left:0;top:0;z-index:1}}.match-team-sheet-legend-pair-icon--first-xv{{left:9px;top:8px;z-index:2}}.match-team-sheet-legend-text{{font-weight:700;color:#2f3a58;line-height:1}}.match-team-sheet-milestone{{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;border-radius:50%;flex:0 0 auto;background:#fff;color:#202946;border:2px solid #202946;box-shadow:0 1px 2px rgba(0,0,0,.18);line-height:1}}.match-team-sheet-milestone-core{{display:inline-flex;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%}}.match-team-sheet-milestone-text{{font-size:9px;font-weight:900;line-height:1}}.match-team-sheet-milestone--scope-club{{background:#fff;color:#202946;border:1px solid #111}}.match-team-sheet-milestone--scope-first-xv{{background:#202946;color:#fff;border:2px solid #7d96e8}}.match-team-sheet-milestone--25{{background:linear-gradient(135deg,#eed2ac 0%,#c6894a 100%);color:#3d230f;border-color:#9f6b37}}.match-team-sheet-milestone--50{{background:linear-gradient(135deg,#f5f7fa 0%,#b9c2cf 100%);color:#1f2833;border-color:#8e98a8}}.match-team-sheet-milestone--100{{background:linear-gradient(135deg,#fff3ad 0%,#f0b90b 100%);color:#4a3500;border-color:#d39d00}}.match-team-sheet-milestone--last{{background:#fff;color:#000;border:2px solid #000}}.full-profile-timeline-event-glyph{{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;font-size:18px;font-weight:900;font-family:"PT Sans Narrow",sans-serif;line-height:1;flex:0 0 auto}}.full-profile-timeline-event-glyph--star{{color:#c6894a;font-size:19px;text-shadow:0 0 0 #d39d00}}
.league-history-legend{{display:flex;flex-wrap:wrap;gap:5px 14px;align-items:center;margin-top:12px;padding:7px 10px;border:1px solid #cfd7eb;background:#fff;width:fit-content;max-width:100%}}.league-history-legend .performance-set-piece-legend-item{{display:inline-flex;align-items:center;gap:6px;color:#2f3a58;font-size:13px;line-height:1.1}}.league-history-legend-symbol{{display:inline-flex;width:18px;height:18px;align-items:center;justify-content:center;flex:0 0 auto}}.league-history-legend-symbol svg{{display:block;width:18px;height:18px}}.league-history-legend-position-text{{font-family:"PT Sans Narrow",sans-serif;font-size:12px;font-weight:700}}
@page{{size:A4 portrait;margin:10mm}}@media print{{body{{background-color:#fff;font-size:8.5pt}}main{{max-width:none;margin:0;padding:0;box-shadow:none}}.hero{{break-inside:avoid;margin:0 0 14px;padding:0 14px;min-height:150px;height:150px;background-size:cover!important;background-position:center 25%!important}}.hero-club{{top:10px;left:14px;width:70px;height:70px}}.hero-image{{width:140px;height:150px;margin-left:54px}}.brand-avatar{{width:58px;height:58px}}.brand-url{{font-size:15px}}.career-summary-grid{{break-inside:avoid}}h2,h3{{break-after:avoid}}.table-wrap{{overflow:visible;margin:4px 0 8px}}table{{font-size:7.2pt;table-layout:auto}}th,td{{padding:2.5px 3px}}.appearance-table th,.appearance-table td{{white-space:nowrap}}.appearance-table .column-scores{{text-align:center}}.appearance-table .column-h-a,.appearance-table .column-number,.appearance-table .column-captain,.appearance-table .column-motm,.appearance-table .column-google,.appearance-table .column-pitchero,.appearance-table .column-rfu{{text-align:center}}.teammate-layout{{overflow:visible;flex-wrap:nowrap}}.teammate-card{{flex:1 1 0;min-width:0}}.career-chart{{overflow:hidden}}.career-chart>svg{{width:100%!important;max-width:100%;height:auto}}.league-chart{{overflow:visible}}.league-chart>svg{{width:auto!important;max-width:none!important;height:auto}}footer{{break-inside:avoid}}}}
@media(max-width:700px){{main{{margin:0;padding:0 16px 24px}}.hero{{margin:0 -16px 20px;padding:8px 12px 0;gap:8px;min-height:118px}}.hero-club{{top:8px;left:12px;width:52px;height:52px}}.hero-image{{width:90px;height:123px;margin-left:42px}}.brand{{gap:2px}}.brand-avatar{{width:40px;height:40px}}.brand-url{{font-size:13px}}.career-summary-grid{{grid-template-columns:1fr}}.teammate-layout{{max-width:100%}}h1{{font-size:24px}}.table-wrap{{margin:5px 0 9px}}table{{font-size:13.5px}}th,td{{padding:4px 5px}}}}
</style><style>@page{{size:A4 portrait;margin:6mm}}@media print{{.playing-record-heading{{break-before:page}}.career-chart,.league-chart{{display:flex;align-items:flex-start;gap:8px}}.career-chart>svg,.league-chart>svg{{order:2;flex:1 1 auto;height:auto!important;width:calc(100% - 150px)!important;max-width:none!important}}.full-profile-timeline-legend-block,.league-history-legend{{order:1;flex:0 0 142px;width:142px;margin:0;padding:4px 6px}}.full-profile-timeline-legend-groups{{display:block}}.full-profile-timeline-legend-group{{margin-bottom:6px}}.full-profile-timeline-legend-group:last-child{{margin-bottom:0}}.full-profile-timeline-legend-group .match-team-sheet-legend-row{{gap:3px 6px}}.league-history-legend{{display:flex;flex-wrap:wrap;align-content:flex-start;gap:4px 6px}}.position-appearance-wrap{{margin:4px 0 8px}}h2{{margin:14px 0 5px}}h3{{margin:8px 0 4px}}}}</style></head><body><main><header class="hero">{club_image}{hero_image}<div class="hero-copy"><h1>{html.escape(entity)}</h1>{f'<p class="hero-subtitle">{custom_sections["HEADER_POSITION"]}</p>' if custom_sections and custom_sections.get("HEADER_POSITION") else ''}</div>{brand_header}</header>{rendered}<footer>{avatar}<span>eg-stats.uk</span></footer></main></body></html>'''


def _chrome_executable():
    configured = os.environ.get("CHROME_BIN")
    candidates = [
        configured,
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def _export_pdf(html_path, pdf_path):
    browser = _chrome_executable()
    if not browser:
        raise RuntimeError("Automatic PDF export requires Google Chrome or Chromium. Set CHROME_BIN to its executable; HTML is available beside the requested PDF path.")
    with tempfile.TemporaryDirectory(prefix="egrfc-report-chrome-") as profile_dir:
        log_path = Path(profile_dir) / "chrome.log"
        generated_pdf = Path(profile_dir) / "report.pdf"
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={profile_dir}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={generated_pdf}",
            Path(html_path).resolve().as_uri(),
        ]
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log_file)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if generated_pdf.is_file() and generated_pdf.stat().st_size > 5 and generated_pdf.read_bytes()[:5] == b"%PDF-":
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.2)
            else:
                process.kill()
                process.wait()
                raise RuntimeError(f"Chrome PDF export timed out: {log_path.read_text(encoding='utf-8', errors='replace')[-2000:]}")
        if process.returncode not in (0, -15, -9) and not (generated_pdf.is_file() and generated_pdf.stat().st_size > 5):
            raise RuntimeError(f"Chrome PDF export failed: {log_path.read_text(encoding='utf-8', errors='replace')[-2000:]}")
        if not generated_pdf.is_file() or generated_pdf.stat().st_size < 5 or generated_pdf.read_bytes()[:5] != b"%PDF-":
            raise RuntimeError("Chrome produced an invalid PDF output.")
        os.replace(generated_pdf, pdf_path)


class ReportGenerator:
    """Read the canonical database and render entity reports."""

    def __init__(self, db_path):
        path = Path(db_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Backend database not found: {path}")
        self.con = duckdb.connect(str(path), read_only=True)
        self.con.create_function("report_player_key", _player_name_key, [str], str)
        self.con.create_function("report_scorer_key", _report_scorer_player_key, [str, str], str)

    def close(self):
        self.con.close()

    def _rows(self, query, params=None):
        cursor = self.con.execute(query, params or [])
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _pitchero_alias_names(player_name):
        return [
            alias
            for alias, canonical in IN_GAME_PLAYER_ALIAS_CANONICAL.items()
            if _player_name_key(canonical) == _player_name_key(player_name)
        ]

    def _pitchero_alias_game_keys(self, player_name):
        aliases = self._pitchero_alias_names(player_name)
        if not aliases:
            return set()
        placeholders = ", ".join("?" for _ in aliases)
        rows = self._rows(
            f"""SELECT DISTINCT p.game_id, p.date, p.squad
                FROM player_appearances_stage_pitchero p
                JOIN player_appearances_stage_google g
                  ON g.game_id = p.game_id
                 AND g.date = p.date
                 AND g.squad = p.squad
                WHERE p.player IN ({placeholders})
                  AND report_player_key(g.player) = report_player_key(?)""",
            [*aliases, player_name],
        )
        return {(row["game_id"], row["date"], row["squad"]) for row in rows}

    def _pitchero_scorer_game_keys(self, player_name):
        rows = self._rows(
            """SELECT DISTINCT game_id, date, squad
               FROM scorers_stage_pitchero
               WHERE report_scorer_key(player, season) = report_player_key(?)""",
            [player_name],
        )
        return {(row["game_id"], row["date"], row["squad"]) for row in rows}

    def _lineout_role_match_sql(self, role, player_name):
        aliases = self._pitchero_alias_names(player_name) if role == "jumper" else []
        clause = f"report_player_key(lo.{role}) = report_player_key(?)"
        params = [player_name]
        if aliases:
            placeholders = ", ".join("?" for _ in aliases)
            clause = (
                f"({clause} OR EXISTS ("
                "SELECT 1 FROM player_appearances_stage_pitchero p "
                "JOIN player_appearances_stage_google g "
                "ON g.game_id = p.game_id AND g.date = p.date AND g.squad = p.squad "
                f"WHERE p.player IN ({placeholders}) "
                "AND report_player_key(g.player) = report_player_key(?) "
                "AND p.game_id = lo.game_id AND p.date = lo.date AND p.squad = lo.squad))"
            )
            params.extend(aliases)
            params.append(player_name)
        return clause, params

    @staticmethod
    def _pitchero_alias_names(player_name):
        return [
            alias
            for alias, canonical in IN_GAME_PLAYER_ALIAS_CANONICAL.items()
            if _player_name_key(canonical) == _player_name_key(player_name)
        ]

    def _pitchero_alias_game_keys(self, player_name):
        aliases = self._pitchero_alias_names(player_name)
        if not aliases:
            return set()
        placeholders = ", ".join("?" for _ in aliases)
        rows = self._rows(
            f"""SELECT DISTINCT p.game_id, p.date, p.squad
                FROM player_appearances_stage_pitchero p
                JOIN player_appearances_stage_google g
                  ON g.game_id = p.game_id
                 AND g.date = p.date
                 AND g.squad = p.squad
                WHERE p.player IN ({placeholders})
                  AND report_player_key(g.player) = report_player_key(?)""",
            [*aliases, player_name],
        )
        return {(row["game_id"], row["date"], row["squad"]) for row in rows}

    def _lineout_role_match_sql(self, role, player_name):
        aliases = self._pitchero_alias_names(player_name) if role == "jumper" else []
        clause = f"report_player_key(lo.{role}) = report_player_key(?)"
        params = [player_name]
        if aliases:
            placeholders = ", ".join("?" for _ in aliases)
            clause = (
                f"({clause} OR EXISTS ("
                "SELECT 1 FROM player_appearances_stage_pitchero p "
                "JOIN player_appearances_stage_google g "
                "ON g.game_id = p.game_id AND g.date = p.date AND g.squad = p.squad "
                f"WHERE p.player IN ({placeholders}) "
                "AND report_player_key(g.player) = report_player_key(?) "
                "AND p.game_id = lo.game_id AND p.date = lo.date AND p.squad = lo.squad))"
            )
            params.extend(aliases)
            params.append(player_name)
        return clause, params

    def _started_set_piece_success(self, player_name):
        return self._rows(
            """SELECT sp.season, sp.squad,
                      SUM(COALESCE(sp.scrums_won, 0)) AS scrums_won,
                      SUM(COALESCE(sp.scrums_total, 0)) AS scrums_total,
                      SUM(COALESCE(sp.lineouts_won, 0)) AS lineouts_won,
                      SUM(COALESCE(sp.lineouts_total, 0)) AS lineouts_total
               FROM set_piece sp
               WHERE sp.team = 'EGRFC'
                 AND EXISTS (
                     SELECT 1
                     FROM player_appearances a
                     WHERE a.game_id = sp.game_id
                       AND a.squad = sp.squad
                       AND a.is_starter = TRUE
                       AND report_player_key(a.player) = report_player_key(?)
                 )
               GROUP BY sp.season, sp.squad
               ORDER BY sp.season, sp.squad""",
            [player_name],
        )

    def _resolve_name(self, table, column, requested):
        rows = self._rows(
            f"SELECT DISTINCT {column} AS name FROM {table} "
            f"WHERE {column} IS NOT NULL ORDER BY {column}"
        )
        values = [str(row["name"]).strip() for row in rows if str(row["name"]).strip()]
        exact = [value for value in values if value.casefold() == requested.casefold()]
        matches = exact or [value for value in values if requested.casefold() in value.casefold()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"No {table} match found for {requested!r}.")
        raise ValueError("Ambiguous match. Use one of: " + ", ".join(matches[:20]))

    @staticmethod
    def _player_image(profile):
        relative_path = str(profile.get("photo_url") or "").strip()
        image_path = (PROJECT_ROOT / relative_path).resolve() if relative_path else None
        if image_path and image_path.is_relative_to(PROJECT_ROOT):
            return _embedded_image(image_path)
        return ""

    @staticmethod
    def _opposition_image(name):
        manifest_path = PROJECT_ROOT / "data" / "logos.json"
        if not manifest_path.exists():
            return ""
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        match = manifest.get(key)
        if not match:
            matches = [filename for logo_key, filename in manifest.items() if key.startswith(logo_key) or logo_key.startswith(key)]
            match = matches[0] if len(matches) == 1 else None
        return _embedded_image(PROJECT_ROOT / "img" / "logos" / match) if match else ""

    def player_markdown(self, requested, top_n=5):
        name = self._resolve_name("player_appearances", "player", requested)
        profile_rows = self._rows("SELECT * FROM player_profiles_canonical WHERE name = ?", [name])
        profile = profile_rows[0] if profile_rows else {}
        appearances = self._rows(
            """
                 SELECT a.season, a.date, a.squad, a.game_id, a.number,
                   COALESCE(g.game_type, a.game_type) AS game_type, g.competition,
                   g.opposition, g.home_away, g.score_for, g.score_against, a.position, a.is_starter,
                   a.is_captain, g.motm,
                   sc.tries, sc.conversions, sc.penalties, sc.drop_goals, sc.points,
                   EXISTS (SELECT 1 FROM player_appearances_stage_google s
                       WHERE report_player_key(s.player) = report_player_key(a.player) AND (s.game_id = a.game_id OR (s.date = a.date AND s.squad = a.squad))) AS google_source,
                   EXISTS (SELECT 1 FROM player_appearances_stage_pitchero s
                       WHERE report_player_key(s.player) = report_player_key(a.player) AND (s.game_id = a.game_id OR (s.date = a.date AND s.squad = a.squad))) AS pitchero_source,
                   EXISTS (SELECT 1 FROM player_appearances_stage_rfu s
                       WHERE report_player_key(s.player) = report_player_key(a.player) AND (s.game_id = a.game_id OR (s.date = a.date AND s.squad = a.squad))) AS rfu_source,
                   g.result
            FROM player_appearances a
            LEFT JOIN games g ON g.game_id = a.game_id
                 LEFT JOIN LATERAL (
                  SELECT resolved.tries, resolved.conversions, resolved.penalties,
                      resolved.drop_goals, resolved.points
                  FROM (
                      SELECT game_id, date, squad, player,
                          arg_max(tries, source_priority) AS tries,
                          arg_max(conversions, source_priority) AS conversions,
                          arg_max(penalties, source_priority) AS penalties,
                          arg_max(drop_goals, source_priority) AS drop_goals,
                          arg_max(points, source_priority) AS points
                      FROM (
                       SELECT game_id, date, squad, player,
                           SUM(COALESCE(tries, 0)) AS tries,
                           SUM(COALESCE(conversions, 0)) AS conversions,
                           SUM(COALESCE(penalties, 0)) AS penalties,
                           SUM(COALESCE(drop_goals, 0)) AS drop_goals,
                           SUM(COALESCE(points, 0)) AS points, 3 AS source_priority
                       FROM scorers_stage_google GROUP BY game_id, date, squad, player
                       UNION ALL
                       SELECT game_id, date, squad, player,
                           SUM(COALESCE(tries, 0)), SUM(COALESCE(conversions, 0)),
                           SUM(COALESCE(penalties, 0)), SUM(COALESCE(drop_goals, 0)),
                           SUM(COALESCE(points, 0)), 2
                       FROM scorers_stage_pitchero GROUP BY game_id, date, squad, player
                       UNION ALL
                       SELECT game_id, date, squad, player,
                           SUM(COALESCE(tries, 0)), SUM(COALESCE(conversions, 0)),
                           SUM(COALESCE(penalties, 0)), SUM(COALESCE(drop_goals, 0)),
                           SUM(COALESCE(points, 0)), 1
                       FROM scorers_stage_rfu GROUP BY game_id, date, squad, player
                      ) source_scores
                      GROUP BY game_id, date, squad, player
                  ) resolved
                     WHERE (report_player_key(resolved.player) = report_player_key(a.player)
                         OR report_scorer_key(resolved.player, a.season) = report_player_key(a.player))
                        AND (resolved.game_id = a.game_id OR (resolved.date = a.date AND resolved.squad = a.squad))
                  ORDER BY CASE WHEN resolved.game_id = a.game_id THEN 0 ELSE 1 END
                  LIMIT 1
                 ) sc ON TRUE
            WHERE a.player = ?
            ORDER BY a.date, a.squad
            """,
            [name],
        )
        pitchero_source_game_keys = (
            self._pitchero_alias_game_keys(name)
            | self._pitchero_scorer_game_keys(name)
        )
        for row in appearances:
            appearance_key = (row["game_id"], row["date"], row["squad"])
            if appearance_key in pitchero_source_game_keys:
                row["pitchero_source"] = True
        positions = {}
        seasons = {}
        for row in appearances:
            row["is_motm"] = _matches_motm(row["motm"], name)
            if row["is_starter"] and row["position"] and row["position"].lower() != "bench":
                positions[row["position"]] = positions.get(row["position"], 0) + 1
            season = row["season"] or "Unknown"
            squad = str(row["squad"] or "")
            squad_scope = "1st XV" if squad == "1st" else "2nd XV" if squad == "2nd" else squad
            scopes = [squad_scope, "Overall"]
            for scope in scopes:
                item = seasons.setdefault((season, scope, "Total"), {"apps": 0, "starts": 0, "wins": 0, "draws": 0, "losses": 0, "tries": 0, "points": 0})
                item["apps"] += 1
                item["starts"] += int(bool(row["is_starter"]))
                item["tries"] += row["tries"] or 0
                item["points"] += row["points"] or 0
                result = str(row["result"] or "").upper()
                if result in {"W", "D", "L"}:
                    item[{"W": "wins", "D": "draws", "L": "losses"}[result]] += 1
                if str(row["game_type"] or "").casefold() == "league":
                    league_item = seasons.setdefault((season, scope, "League"), {"apps": 0, "starts": 0, "wins": 0, "draws": 0, "losses": 0, "tries": 0, "points": 0})
                    for key in ("apps", "starts", "tries", "points"):
                        league_item[key] += int(bool(row["is_starter"])) if key == "starts" else (row["tries"] or 0 if key == "tries" else row["points"] or 0 if key == "points" else 1)
                    if result in {"W", "D", "L"}:
                        league_item[{"W": "wins", "D": "draws", "L": "losses"}[result]] += 1
        include_scrum_success = _has_majority_tight5_starts(appearances)
        jumper_match_sql, jumper_match_params = self._lineout_role_match_sql("jumper", name)
        jumper_attempt_rows = self._rows(
            f"SELECT COUNT(*) AS attempts FROM lineouts lo WHERE lo.jumper IS NOT NULL AND {jumper_match_sql}",
            jumper_match_params,
        )
        total_jump_attempts = int(jumper_attempt_rows[0]["attempts"] or 0) if jumper_attempt_rows else 0
        include_lineout_success = _meets_jumper_attempt_threshold(total_jump_attempts)
        started_set_piece = self._started_set_piece_success(name) if include_scrum_success or include_lineout_success else []
        main_position = sorted(positions.items(), key=lambda pair: (-pair[1], pair[0]))
        scoring = {
            "tries": sum(row["tries"] or 0 for row in appearances),
            "conversions": sum(row["conversions"] or 0 for row in appearances),
            "penalties": sum(row["penalties"] or 0 for row in appearances),
            "drop_goals": sum(row["drop_goals"] or 0 for row in appearances),
            "points": sum(row["points"] or 0 for row in appearances),
        }
        first_game = appearances[0] if appearances else {}
        latest_game = appearances[-1] if appearances else {}
        def career_summary(scope):
            selected = [row for row in appearances if scope == "Overall" or row["squad"] == "1st"]
            first = selected[0] if selected else None
            latest = selected[-1] if selected else None
            wins = sum(str(row["result"] or "").upper() == "W" for row in selected)
            losses = sum(str(row["result"] or "").upper() == "L" for row in selected)
            draws = sum(str(row["result"] or "").upper() == "D" for row in selected)
            summary_scoring = {key: sum(row[key] or 0 for row in selected) for key in ("tries", "conversions", "penalties", "drop_goals", "points")}
            scoring_detail = [
                f"{summary_scoring[key]} {label if summary_scoring[key] == 1 else 'tries' if label == 'try' else f'{label}s'}"
                for key, label in (("tries", "try"), ("conversions", "conversion"), ("penalties", "penalty"), ("drop_goals", "drop goal"))
                if summary_scoring[key]
            ]
            points_text = str(summary_scoring["points"])
            if scoring_detail:
                points_text += f" ({', '.join(scoring_detail)})"
            def fixture(row):
                if not row:
                    return "-"
                result = f"{row['result']} {row['score_for']}-{row['score_against']}" if row["score_for"] and row["score_against"] is not None else str(row["result"] or "")
                result_code = str(row["result"] or "").upper()
                result_class = "win" if result_code == "W" else "loss" if result_code == "L" else "draw" if result_code == "D" else ""
                return f'{_date(row["date"])} vs {html.escape(str(row["opposition"] or "Unknown"))} ({html.escape(str(row["home_away"] or "?"))}) <span class="fixture-result-separator">&bull;</span> <span class="result-badge result-badge--{result_class}">{html.escape(result)}</span>'
            group_class = "first-xv" if scope == "1st XV" else "overall"
            return f'''<section class="profile-summary-group profile-summary-group--{group_class}">
              <h3>{html.escape(scope)}</h3>
              <div class="profile-summary-lines">
                <p><strong>Appearances:</strong> {len(selected)} ({sum(bool(row["is_starter"]) for row in selected)} starts)</p>
                <p><strong>Points:</strong> {html.escape(points_text)}</p>
                <p><strong>Debut:</strong> {fixture(first)}</p>
                <p><strong>Latest appearance:</strong> {fixture(latest)}</p>
                <p><strong>Win record:</strong> <span class="record-chip-group"><span class="record-chip record-chip--win">W {wins}</span><span class="record-chip record-chip--loss">L {losses}</span>{f'<span class="record-chip record-chip--draw">D {draws}</span>' if draws else ''}</span></p>
              </div>
            </section>'''
        primary_position = main_position[0][0] if main_position else profile.get("position", "Unknown")
        secondary_ratio = main_position[1][1] / main_position[0][1] if len(main_position) > 1 and main_position[0][1] else 0
        secondary_position = main_position[1][0] if len(main_position) > 1 and secondary_ratio > 0.3 else "-"
        season_tables = {}
        for row in appearances:
            season_tables.setdefault(row["season"] or "Unknown", []).append(row)
        self.last_player_html_sections = {
            "CAREER_TIMELINE": _profile_timeline_chart(name),
            "CAREER_SUMMARY": f'<div class="career-summary-grid" style="margin-bottom:0">{career_summary("1st XV")}{career_summary("Overall")}</div>',
            "POSITION_BAR": _position_appearance_bar(appearances),
            "LEAGUE_HISTORY": _profile_league_history_chart(appearances),
            "TIMELINE_TITLE": '<h3>Timeline</h3>',
            "LEAGUE_HISTORY_TITLE": '<h3>League History</h3>',
            "HEADER_POSITION": html.escape(primary_position),
        }
        lines = [
            f"# {name}",
            "",
            "## Career Summary",
            "",
            "@@CAREER_SUMMARY@@",
            "",
            "@@POSITION_BAR@@",
            "",
            "@@TIMELINE_TITLE@@",
            "",
            "@@CAREER_TIMELINE@@",
            "",
            "@@LEAGUE_HISTORY_TITLE@@",
            "",
            "@@LEAGUE_HISTORY@@",
            "",
            "## Playing Record",
            "",
        ]
        for season, season_appearances in sorted(season_tables.items()):
            lines.extend([
                f"### {season} ({len(season_appearances)} appearances)",
                "",
                _table(
                    [
                        "Game detail::Date", "Game detail::Competition", "Game detail::Squad",
                        "Game detail::Opposition", "Game detail::H/A", "Game detail::Result",
                        "Player detail::Position", "Player detail::Number", "Player detail::Captain",
                        "Player detail::Scores", "Player detail::MOTM", "Data Source::Google",
                        "Data Source::Pitchero", "Data Source::RFU",
                    ],
                    [
                        (
                            _date(row["date"]), row["competition"] or row["game_type"], row["squad"],
                            row["opposition"], row["home_away"],
                            f"{row['result']} {row['score_for']}-{row['score_against']}" if row["score_for"] is not None and row["score_against"] is not None else "-",
                            row["position"] if row["is_starter"] else "Bench", row["number"] or "",
                            "C" if row["is_captain"] else "", _score_markers(row),
                            "★" if row["is_motm"] else "", _check(row["google_source"]),
                            _check(row["pitchero_source"]), _check(row["rfu_source"]),
                        )
                        for row in season_appearances
                    ],
                ),
                "",
            ])
        season_headers = ["Season::Season"]
        for squad in ("1st XV", "2nd XV", "Overall"):
            season_headers.extend([f"{squad}::Apps", f"{squad}::Starts", f"{squad}::Results"])
        season_rows = []
        for season in sorted(season_tables):
            values = [season]
            for squad in ("1st XV", "2nd XV", "Overall"):
                stats = seasons.get((season, squad, "Total"), {"apps": 0, "starts": 0, "wins": 0, "draws": 0, "losses": 0})
                record = f"W {stats['wins']} L {stats['losses']}"
                if stats["draws"]:
                    record += f" D {stats['draws']}"
                values.extend([stats["apps"], stats["starts"], record])
            season_rows.append(values)
        score_seasons = self._rows(
            """SELECT season, squad, SUM(COALESCE(tries, 0)) AS tries,
                      SUM(COALESCE(conversions, 0)) AS conversions,
                      SUM(COALESCE(penalties, 0)) AS penalties,
                      SUM(COALESCE(drop_goals, 0)) AS drop_goals,
                      SUM(COALESCE(points, 0)) AS points
               FROM season_scorers WHERE player = ?
               GROUP BY season, squad ORDER BY season, squad""",
            [name],
        )
        score_rows = []
        scored_squads = {
            str(row["squad"])
            for row in score_seasons
            if any(row[key] for key in ("tries", "conversions", "penalties", "drop_goals", "points"))
        }
        scoring_squads = [squad for squad in ("1st", "2nd") if squad in scored_squads]
        if {"1st", "2nd"}.issubset(scored_squads):
            scoring_squads.append("Overall")
        scoring_metrics = [
            (key, label)
            for key, label in (("tries", "Tries"), ("conversions", "Conversions"), ("penalties", "Penalties"), ("drop_goals", "Drop goals"), ("points", "Points"))
            if key != "points" and any(row[key] for row in score_seasons)
        ]
        if any(row[key] for row in score_seasons for key in ("conversions", "penalties", "drop_goals")):
            scoring_metrics.append(("points", "Points"))
        squad_scopes = {"1st": "1st XV", "2nd": "2nd XV", "Overall": "Overall"}
        for season in sorted(season_tables):
            values = [season]
            season_score_rows = [row for row in score_seasons if row["season"] == season]
            for squad in scoring_squads:
                selected = season_score_rows if squad == "Overall" else [row for row in season_score_rows if row["squad"] == squad]
                totals = {key: sum(row[key] or 0 for row in selected) for key, _ in scoring_metrics}
                played = seasons.get((season, squad_scopes[squad], "Total"), {}).get("apps", 0) > 0
                values.extend(totals[key] if played else "" for key, _ in scoring_metrics)
            score_rows.append(values)
        lines.extend([
            "",
            "## Season Summaries",
            "",
            _table(season_headers, season_rows),
            "",
        ])
        success_headers = ["Season::Season"]
        for squad_label in ("1st XV", "2nd XV", "Overall"):
            success_headers.extend(
                f"{squad_label}::{column}"
                for column in ("Won", "Total", "Success")
            )
        if score_rows and scoring_metrics:
            score_headers = ["Season::Season"]
            squad_labels = {"1st": "1st XV", "2nd": "2nd XV", "Overall": "Overall"}
            for squad in scoring_squads:
                score_headers.extend(f"{squad_labels[squad]}::{label}" for _, label in scoring_metrics)
            lines.extend(["", "## Scoring Record", "", _table(score_headers, score_rows)])
        lines.extend(["", "## Most Common Teammates", "", "### Overall", ""])
        overall_teammates = self._rows(
            """SELECT other.player, COUNT(DISTINCT mine.game_id) AS games
               FROM player_appearances mine
               JOIN player_appearances other ON other.game_id = mine.game_id AND other.player <> mine.player
               WHERE mine.player = ?
               GROUP BY other.player ORDER BY games DESC, other.player LIMIT ?""",
            [name, top_n],
        )
        lines.append(_table(["Player", "Games"], [(row["player"], row["games"]) for row in overall_teammates] or [("No shared appearance data", "-")]))
        position_teammates = self._rows(
            """SELECT mine.position, other.player, COUNT(DISTINCT mine.game_id) AS games
               FROM player_appearances mine
               JOIN player_appearances other
                 ON other.game_id = mine.game_id AND other.player <> mine.player
                AND other.position = mine.position
               WHERE mine.player = ? AND mine.position IS NOT NULL
                 AND mine.position <> 'Bench' AND mine.game_id IS NOT NULL
               GROUP BY mine.position, other.player
               ORDER BY mine.position, games DESC, other.player""",
            [name],
        )
        positions_seen = sorted({row["position"] for row in position_teammates})
        for position in positions_seen:
            lines.extend(["", f"### {position} Partners", "", _table(
                ["Player", "Games"],
                [(row["player"], row["games"]) for row in [r for r in position_teammates if r["position"] == position][:top_n]],
            )])
        def lineout_breakdown(role, group_column, limit=None, order="attempts DESC, label"):
            role_match_sql, role_match_params = self._lineout_role_match_sql(role, name)
            return self._rows(
                f"""SELECT COALESCE(CAST(lo.{group_column} AS VARCHAR), 'Unspecified') AS label,
                          COUNT(*) AS attempts, SUM(CASE WHEN won THEN 1 ELSE 0 END) AS won
                   FROM lineouts lo WHERE {role_match_sql}
                   GROUP BY label ORDER BY {order}
                   {'LIMIT ' + str(int(limit)) if limit else ''}""",
                role_match_params,
            )

        def lineout_table(heading, rows):
            return _table(
                [heading, "Attempts", "Won", "Success"],
                [(row["label"], row["attempts"], row["won"], f"{100 * row['won'] / row['attempts']:.1f}%" if row["attempts"] else "-") for row in rows],
            )

        def lineout_grid(key, *tables):
            self.last_player_html_sections[key] = f'<div class="lineout-grid">{_markdown_html(chr(10).join(table + chr(10) for table in tables))}</div>'
            return f"@@{key}@@"

        jumping_areas = lineout_breakdown("jumper", "area") if include_lineout_success else []
        jumping_throwers = lineout_breakdown("jumper", "thrower", limit=5) if include_lineout_success else []
        jumping_seasons = lineout_breakdown("jumper", "season", order="label") if include_lineout_success else []
        throwing_areas = lineout_breakdown("thrower", "area")
        throwing_jumpers = lineout_breakdown("thrower", "jumper", limit=5)
        throwing_seasons = lineout_breakdown("thrower", "season", order="label")
        has_scrum_success = include_scrum_success and any(row["scrums_total"] for row in started_set_piece)
        has_lineout_success = include_lineout_success and any(row["lineouts_total"] for row in started_set_piece)
        if has_scrum_success or has_lineout_success or jumping_areas or throwing_areas:
            lines.extend(["", "## Set Piece Record", ""])
        if has_scrum_success:
            lines.extend([
                "### Team Scrum Success",
                "",
                "Team scrums in games the player started; shown because more than half of their career starts were in the tight five.",
                "",
                _table(
                    success_headers,
                    _started_set_piece_summary_rows(started_set_piece, "scrums_won", "scrums_total"),
                ),
                "",
            ])
        if has_lineout_success:
            lines.extend([
                "### Team Lineout Success",
                "",
                "Team lineouts in games the player started; shown because they have at least 10 career lineout jump attempts.",
                "",
                _table(
                    success_headers,
                    _started_set_piece_summary_rows(started_set_piece, "lineouts_won", "lineouts_total"),
                ),
                "",
            ])
        if jumping_areas:
            lines.extend(["### Jumping", "", lineout_grid("LINEOUT_JUMPING", lineout_table("Season", jumping_seasons), lineout_table("Area", jumping_areas), lineout_table("Thrower", jumping_throwers)), ""])
        if throwing_areas:
            lines.extend(["### Throwing", "", lineout_grid("LINEOUT_THROWING", lineout_table("Season", throwing_seasons), lineout_table("Area", throwing_areas), lineout_table("Jumper", throwing_jumpers)), ""])
        return "\n".join(lines).rstrip() + "\n"

    def player_image(self, requested):
        name = self._resolve_name("player_appearances", "player", requested)
        rows = self._rows("SELECT photo_url FROM player_profiles_canonical WHERE name = ?", [name])
        return self._player_image(rows[0] if rows else {})

    def opposition_markdown(self, requested):
        name = self._resolve_name("games", "opposition_club", requested)
        games = self._rows(
            """SELECT game_id, season, date, squad, opposition, home_away, score_for, score_against, result
               FROM games WHERE opposition_club = ? ORDER BY date, squad""",
            [name],
        )
        summaries = {}
        for game in games:
            season = game["season"] or "Unknown"
            squad = str(game["squad"] or "")
            result = str(game["result"] or "").upper()
            for scope in (squad, "Overall"):
                values = summaries.setdefault((season, scope), {"games": 0, "wins": 0, "draws": 0, "losses": 0, "pf": 0, "pa": 0})
                values["games"] += 1
                values["pf"] += game["score_for"] or 0
                values["pa"] += game["score_against"] or 0
                if result in {"W", "D", "L"}:
                    values[{"W": "wins", "D": "draws", "L": "losses"}[result]] += 1
        set_piece = self._rows(
            """SELECT g.season, g.date, g.squad, g.opposition, s.team, s.lineouts_won,
                      s.lineouts_total, s.scrums_won, s.scrums_total
               FROM set_piece s JOIN games g ON g.game_id = s.game_id
               WHERE g.opposition_club = ? ORDER BY g.date, g.squad, s.team""",
            [name],
        )
        rfu_players = self._rows(
            """SELECT pa.season, pa.player, COUNT(DISTINCT pa.match_id) AS appearances
               FROM player_appearances_rfu pa
               JOIN games g ON g.date = pa.date AND g.squad = pa.tracked_squad
               WHERE g.opposition_club = ?
                 AND lower(pa.team) NOT LIKE '%grinstead%'
                 AND lower(pa.opposition) LIKE '%grinstead%'
               GROUP BY pa.season, pa.player
               ORDER BY pa.season, appearances DESC, pa.player""",
            [name],
        )
        summary_headers = ["Season::Season"]
        for squad in ("1st XV", "2nd XV", "Overall"):
            summary_headers.extend([f"{squad}::Matches", f"{squad}::W-D-L", f"{squad}::Points For", f"{squad}::Points Against"])
        summary_rows = []
        seasons_present = sorted({game["season"] or "Unknown" for game in games})
        for season in seasons_present:
            values = [season]
            for scope in ("1st", "2nd", "Overall"):
                label = "1st XV" if scope == "1st" else "2nd XV" if scope == "2nd" else scope
                stats = summaries.get((season, label), {"games": 0, "wins": 0, "draws": 0, "losses": 0, "pf": 0, "pa": 0})
                values.extend([stats["games"], f"{stats['wins']}-{stats['draws']}-{stats['losses']}", stats["pf"], stats["pa"]])
            summary_rows.append(values)
        lines = [
            f"# {name}",
            "",
            "## Historical Record",
            "",
            f"Overall: {len(games)} matches, {sum(str(g['result'] or '').upper() == 'W' for g in games)} wins, {sum(str(g['result'] or '').upper() == 'D' for g in games)} draws, {sum(str(g['result'] or '').upper() == 'L' for g in games)} losses; points for/against {sum(g['score_for'] or 0 for g in games)}-{sum(g['score_against'] or 0 for g in games)}.",
            "",
            _table(summary_headers, summary_rows),
            "",
            "## Match Record",
            "",
        ]
        for season in seasons_present:
            season_games = [game for game in games if (game["season"] or "Unknown") == season]
            lines.extend([
                f"### {season} ({len(season_games)} matches)",
                "",
                _table(
                    ["Game detail::Date", "Game detail::H/A", "Game detail::Score", "Result detail::Result", "Team detail::Squad", "Team detail::Fixture"],
                    [(_date(g["date"]), g["home_away"], f"{g['score_for']}-{g['score_against']}" if g["score_for"] is not None and g["score_against"] is not None else "-", g["result"], g["squad"], g["opposition"]) for g in season_games],
                ),
                "",
            ])
        lines.extend([
            "## Set Piece Results",
            "",
        ])
        if set_piece:
            lines.append(_table(
                ["Match detail::Season", "Match detail::Date", "Match detail::Squad", "Set piece detail::Team", "Set piece detail::Lineouts won/total", "Set piece detail::Scrums won/total"],
                [(r["season"], _date(r["date"]), r["squad"], r["team"], f"{r['lineouts_won'] or 0}/{r['lineouts_total'] or 0}", f"{r['scrums_won'] or 0}/{r['scrums_total'] or 0}") for r in set_piece],
            ))
        else:
            lines.append("No set-piece records are available for these matches.")
        lines.extend(["", "## Opposition Player Appearances by Season (RFU)", ""])
        if rfu_players:
            for season in sorted({row["season"] for row in rfu_players}):
                season_rows = [row for row in rfu_players if row["season"] == season]
                lines.extend([f"### {season}", "", _table(["Player detail::Player", "Player detail::Games"], [(r["player"], r["appearances"]) for r in season_rows]), ""])
        else:
            lines.append("No RFU opponent lineup data is available for these matches.")
        return "\n".join(lines).rstrip() + "\n"

    def opposition_image(self, requested):
        name = self._resolve_name("games", "opposition_club", requested)
        return self._opposition_image(name)


def _write_report(kind, entity, content, output, report_format, image_data="", custom_sections=None, background_data=""):
    extension = "html" if report_format == "html" else "pdf"
    path = Path(output) if output else DEFAULT_REPORT_DIR / kind / f"{_slug(entity)}.{extension}"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.with_suffix(f".{extension}")
    path.parent.mkdir(parents=True, exist_ok=True)
    avatar_data = _embedded_image(PROJECT_ROOT / "img" / "SLM_Avatar.png")
    content = _html_document(content, entity, image_data, "Player headshot" if kind == "player" else "Opposition logo", avatar_data, custom_sections, background_data)
    if report_format == "html":
        path.write_text(content, encoding="utf-8")
    else:
        html_path = path.with_suffix(".html")
        html_path.write_text(content, encoding="utf-8")
        _export_pdf(html_path, path)
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate branded PDF summaries from the canonical EGRFC database.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Canonical DuckDB path (relative to the project root unless absolute).")
    subparsers = parser.add_subparsers(dest="report_type", required=True)
    player_parser = subparsers.add_parser("player", help="Generate a player profile and playing-history report.")
    player_parser.add_argument("name", nargs="+", help="Player name (exact match preferred; unique partial matches are accepted).")
    player_parser.add_argument("--top-n", type=int, default=5, help="Number of teammates to include per ranking (default: 5).")
    player_parser.add_argument("--format", choices=("html", "pdf"), default="pdf", help="Generate PDF by default with an HTML source copy.")
    player_parser.add_argument("--output", help="Output path; defaults under reports/generated/player/.")
    opposition_parser = subparsers.add_parser("opposition", help="Generate an opposition history and trends report.")
    opposition_parser.add_argument("name", nargs="+", help="Opposition club name (exact match preferred; unique partial matches are accepted).")
    opposition_parser.add_argument("--format", choices=("html", "pdf"), default="pdf", help="Generate PDF by default with an HTML source copy.")
    opposition_parser.add_argument("--output", help="Output path; defaults under reports/generated/opposition/.")
    args = parser.parse_args()
    if args.report_type == "player" and args.top_n < 1:
        parser.error("--top-n must be at least 1")
    generator = ReportGenerator(args.db_path)
    try:
        requested = " ".join(args.name).strip()
        if args.report_type == "player":
            content = generator.player_markdown(requested, args.top_n)
            image_data = generator.player_image(requested)
            background_data = _embedded_image(PROJECT_ROOT / "img" / "EGRFC Background.png")
            custom_sections = generator.last_player_html_sections
        else:
            content = generator.opposition_markdown(requested)
            image_data = generator.opposition_image(requested)
            background_data = ""
            custom_sections = None
        output = _write_report(args.report_type, requested, content, args.output, args.format, image_data, custom_sections, background_data)
        print(output)
    finally:
        generator.close()


if __name__ == "__main__":
    main()
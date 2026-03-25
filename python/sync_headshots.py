from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from python.process_headshots import process_image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEADSHOTS_DIR = PROJECT_ROOT / "img" / "headshots"
TARGET_FILES = [
    PROJECT_ROOT / "data" / "backend" / "players.json",
    PROJECT_ROOT / "data" / "backend" / "v_player_profiles.json",
]
HEADSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg"}
RECROP_TOLERANCE_PX = 2

RECROP_OPTIONS: dict[str, Any] = {
    "use_face_crop": False,
    "alpha_threshold": 8,
    "blank_threshold": 245,
    "side_margin": 12,
    "top_margin": 0,
    "face_crop_scale": 2.15,
    "face_top_padding_ratio": 0.22,
}


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _iter_headshot_files(headshots_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in headshots_dir.glob("*.*")
        if path.is_file() and path.suffix.lower() in HEADSHOT_EXTENSIONS
    )


def _load_headshots_map(headshots_dir: Path) -> dict[str, str]:
    if not headshots_dir.exists():
        return {}

    headshots: dict[str, str] = {}
    for photo_file in _iter_headshot_files(headshots_dir):
        key = _normalise_key(photo_file.stem)
        if key:
            headshots[key] = photo_file.name
    return headshots


@dataclass
class FileUpdateResult:
    path: Path
    rows: int
    updated_rows: int


@dataclass
class RecropResult:
    checked: int
    needs_recrop: int
    recropped: int


def _headshot_needs_recrop(image_path: Path) -> bool:
    with Image.open(image_path) as image:
        width, height = image.size
    return abs(width - height) > RECROP_TOLERANCE_PX


def _check_and_recrop_headshots(headshots_dir: Path, write: bool) -> RecropResult:
    files = _iter_headshot_files(headshots_dir)
    needs_recrop = 0
    recropped = 0

    for input_path in files:
        if not _headshot_needs_recrop(input_path):
            continue

        needs_recrop += 1
        if not write:
            continue

        output_path = input_path if input_path.suffix.lower() == ".png" else input_path.with_suffix(".png")
        process_image(input_path=input_path, output_path=output_path, **RECROP_OPTIONS)
        if output_path != input_path and input_path.exists():
            input_path.unlink()
        recropped += 1

    return RecropResult(checked=len(files), needs_recrop=needs_recrop, recropped=recropped)


def _sync_file(path: Path, headshots: dict[str, str], write: bool) -> FileUpdateResult:
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    updates = 0

    for row in rows:
        name = str(row.get("name") or "").strip()
        key = _normalise_key(name)
        expected = f"img/headshots/{headshots[key]}" if key in headshots else None
        if row.get("photo_url") != expected:
            row["photo_url"] = expected
            updates += 1

    if write and updates > 0:
        output = json.dumps(rows, indent=4).replace("/", "\\/") + "\n"
        path.write_text(output)

    return FileUpdateResult(path=path, rows=len(rows), updated_rows=updates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync player photo_url fields with files available in img/headshots."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply updates to JSON files. Without this flag, runs in check mode.",
    )
    parser.add_argument(
        "--headshots-dir",
        type=Path,
        default=HEADSHOTS_DIR,
        help="Directory containing headshot image files.",
    )
    parser.add_argument(
        "--target",
        action="append",
        type=Path,
        default=None,
        help="Target JSON file to sync. Can be supplied multiple times.",
    )
    return parser.parse_args()


def run_sync(write: bool, headshots_dir: Path, targets: list[Path]) -> tuple[RecropResult, list[FileUpdateResult], int]:
    if not headshots_dir.exists():
        raise FileNotFoundError(f"Headshots directory does not exist: {headshots_dir}")

    missing_targets = [target for target in targets if not target.exists()]
    if missing_targets:
        missing = "\n".join(str(path) for path in missing_targets)
        raise FileNotFoundError(f"Target file(s) do not exist:\n{missing}")

    recrop_result = _check_and_recrop_headshots(headshots_dir=headshots_dir, write=write)
    headshots = _load_headshots_map(headshots_dir)

    if not headshots:
        print(f"No headshot files found in {headshots_dir}")

    results = [_sync_file(path=target, headshots=headshots, write=write) for target in targets]
    total_updates = sum(result.updated_rows for result in results)
    return recrop_result, results, total_updates


def main() -> None:
    args = parse_args()
    headshots_dir = args.headshots_dir.resolve()
    targets = [target.resolve() for target in args.target] if args.target else TARGET_FILES

    recrop_result, results, total_updates = run_sync(
        write=args.write,
        headshots_dir=headshots_dir,
        targets=targets,
    )
    mode = "WRITE" if args.write else "CHECK"
    print(f"Mode: {mode}")
    print(
        "Headshots: "
        f"checked={recrop_result.checked}, "
        f"needs_recrop={recrop_result.needs_recrop}, "
        f"recropped={recrop_result.recropped}"
    )
    for result in results:
        print(
            f"{result.path.relative_to(PROJECT_ROOT)}: rows={result.rows}, updates={result.updated_rows}"
        )
    print(f"Total updates: {total_updates}")

    if not args.write and (total_updates > 0 or recrop_result.needs_recrop > 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

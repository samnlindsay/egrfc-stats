"""Resize web images to appropriate dimensions for the EGRFC stats site.

Run from the project root:
    env/bin/python python/resize_images.py [--dry-run]

Targets:
  img/headshots/*.png  → max 300×300 px  (displayed as ≤150 px circles; 2× retina)
  img/logos/*.png      → max 200 px on longest side
  img/EGRFC Background*.png → max 900 px wide  (CSS banner backgrounds)
  img/SLM_Avatar.png   → max 300×300 px

All files are rewritten in-place as PNG.  Files already within the target
dimensions are left untouched (but are still reported).
"""

import argparse
import sys
from pathlib import Path

from PIL import Image


def resize_image(path: Path, max_w: int, max_h: int, dry_run: bool = False) -> tuple[bool, int, int]:
    """Resize *path* so it fits within max_w × max_h, preserving aspect ratio.

    Returns (was_resized, old_kb, new_kb).
    """
    try:
        img = Image.open(path)
    except Exception as e:
        print(f"  SKIP    {path.name}: cannot open ({e})")
        return False, 0, 0
    orig_w, orig_h = img.size
    old_kb = path.stat().st_size // 1024

    # Nothing to do if already small enough.
    if orig_w <= max_w and orig_h <= max_h:
        return False, old_kb, old_kb

    img.thumbnail((max_w, max_h), Image.LANCZOS)
    new_w, new_h = img.size

    if not dry_run:
        img.save(path, format="PNG", optimize=True)
        new_kb = path.stat().st_size // 1024
    else:
        new_kb = old_kb  # Can't know without saving

    print(
        f"  {'[DRY]' if dry_run else 'RESIZED'} {path.name}: "
        f"{orig_w}×{orig_h} → {new_w}×{new_h}  ({old_kb}KB → {new_kb}KB)"
    )
    return True, old_kb, new_kb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing files")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    img_dir = project_root / "img"
    dry_run = args.dry_run

    tasks = [
        # (glob_pattern, max_width, max_height, label)
        (list((img_dir / "headshots").glob("*.png")), 300, 300, "Headshots"),
        (list((img_dir / "logos").glob("*.png")), 200, 200, "Logos"),
        (list(img_dir.glob("EGRFC Background*.png")), 900, 1200, "Backgrounds"),
        ([img_dir / "SLM_Avatar.png"], 300, 300, "SLM Avatar"),
    ]

    total_old_kb = total_new_kb = 0
    total_resized = 0

    for files, max_w, max_h, label in tasks:
        files = [f for f in files if f.exists()]
        if not files:
            continue
        print(f"\n{label} (target: {max_w}×{max_h}px):")
        for path in sorted(files):
            resized, old_kb, new_kb = resize_image(path, max_w, max_h, dry_run=dry_run)
            total_old_kb += old_kb
            total_new_kb += new_kb
            if resized:
                total_resized += 1
            elif not dry_run:
                print(f"  OK      {path.name}: {old_kb}KB (already ≤{max_w}×{max_h})")

    saved_kb = total_old_kb - total_new_kb
    print(f"\nDone — {total_resized} image(s) resized, ~{saved_kb}KB saved "
          f"({total_old_kb}KB → {total_new_kb}KB total)")


if __name__ == "__main__":
    main()

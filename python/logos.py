"""Generate a manifest of available club logos for the frontend."""

import json
import os
from pathlib import Path


def normalize_logo_key(filename: str) -> str:
    """Convert a logo filename to its normalized lookup key.
    
    E.g., 'BarnsGreen.png' -> 'barnsgreen'
          'BrightonSM.png' -> 'brightonsm'
    """
    # Remove .png extension and convert to lowercase
    name = Path(filename).stem.lower()
    return name


def build_logos_manifest(logos_dir: Path) -> dict[str, str]:
    """Build a manifest mapping normalized names to logo filenames.
    
    Returns a dict like:
        {
            'barnsgreen': 'BarnsGreen.png',
            'brighton': 'Brighton.png',
            ...
        }
    """
    manifest = {}
    
    if not logos_dir.exists():
        return manifest
    
    # Find all PNG files
    for png_file in sorted(logos_dir.glob('*.png')):
        if png_file.name.startswith('.'):
            continue
        
        key = normalize_logo_key(png_file.name)
        manifest[key] = png_file.name
    
    return manifest


def export_logos_manifest(output_path: Path, logos_dir: Path | None = None) -> None:
    """Generate and write the logos manifest JSON file.
    
    Args:
        output_path: Path to write the JSON manifest (e.g., 'data/logos.json')
        logos_dir: Path to the logos directory (defaults to 'img/logos')
    """
    if logos_dir is None:
        logos_dir = Path(__file__).parent.parent / 'img' / 'logos'
    
    manifest = build_logos_manifest(logos_dir)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Generated logos manifest: {output_path} ({len(manifest)} logos)")


if __name__ == '__main__':
    output = Path(__file__).parent.parent / 'data' / 'logos.json'
    export_logos_manifest(output)

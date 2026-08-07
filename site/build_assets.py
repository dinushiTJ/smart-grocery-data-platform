#!/usr/bin/env python3
"""Generate the web copies of the screenshots that section 08 displays.

The page used to point straight at ``../docs/screenshots/*.png``. That path leaves the
``site/`` directory, and a browser opening ``index.html`` over ``file://`` may refuse to
read a parent directory at all -- Safari does, Chrome does not -- so every image came up
broken for anyone who simply double-clicked the file. Nothing the page references may sit
outside ``site/``.

So the originals stay in ``docs/screenshots/`` (full resolution, for the README and for
download) and this script derives display copies into ``site/assets/``:

    python3 site/build_assets.py            # (re)generate any stale or missing asset
    python3 site/build_assets.py --check    # exit 1 if an asset is missing or out of date

The page renders these about 450px wide, so ``MAX_WIDTH`` is generous. They are JPEG
because re-encoding these screenshots as PNG at any useful size comes out *larger* than
the originals; JPEG at this quality holds the UI text legibly at a third of the weight.
Uses ``sips``, which ships with macOS, so there is no new dependency.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "docs" / "screenshots"
TARGET = REPO / "site" / "assets"

MAX_WIDTH = 1600
QUALITY = 90


def sources() -> list[Path]:
    return sorted(SOURCE.glob("*.png"))


def target_for(source: Path) -> Path:
    return TARGET / (source.stem + ".jpg")


def is_stale(source: Path, target: Path) -> bool:
    return not target.exists() or target.stat().st_mtime < source.stat().st_mtime


def build(source: Path, target: Path) -> None:
    """Downscale and re-encode one capture, via sips."""
    subprocess.run(
        ["sips", "--resampleWidth", str(MAX_WIDTH),
         "-s", "format", "jpeg",
         "-s", "formatOptions", str(QUALITY),
         str(source), "--out", str(target)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report stale or missing assets and exit 1 without writing")
    args = parser.parse_args()

    found = sources()
    if not found:
        raise SystemExit(f"no source screenshots in {SOURCE}")

    stale = [s for s in found if is_stale(s, target_for(s))]

    if args.check:
        if stale:
            names = ", ".join(s.name for s in stale)
            print(f"{len(stale)} asset(s) missing or out of date: {names}")
            sys.exit(1)
        print(f"every asset is current ({len(found)} files)")
        return

    if not stale:
        print(f"nothing to do, every asset is current ({len(found)} files)")
        return

    TARGET.mkdir(parents=True, exist_ok=True)
    for source in stale:
        build(source, target_for(source))
    print(f"built {len(stale)} asset(s): {', '.join(s.stem for s in stale)}")


if __name__ == "__main__":
    main()

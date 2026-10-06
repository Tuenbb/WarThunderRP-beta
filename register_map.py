import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from user_map_registry import register_map, registry_path

MAX_LEVEL_CANDIDATES = 100
MAX_LEVEL_DIRECTORY_ENTRIES = 10_000


def read_active_map_fingerprint() -> tuple[str, tuple[int, int]]:
    from map_image import read_map_image_hash

    return read_map_image_hash()


def _suggest_label(level_id: str) -> str:
    return " ".join(level_id.replace("_", " ").replace("-", " ").split()).title()


def print_level_candidates(levels_dir: Path, output: TextIO = sys.stdout) -> None:
    if not levels_dir.is_dir():
        raise ValueError("The supplied levels directory does not exist")

    print(
        "Candidate .bin files only; none is verified as the active map:",
        file=output,
    )
    shown = 0
    inspected = 0
    for candidate in levels_dir.iterdir():
        inspected += 1
        if candidate.suffix.casefold() != ".bin" or not candidate.is_file():
            if inspected >= MAX_LEVEL_DIRECTORY_ENTRIES:
                break
            continue
        level_id = candidate.stem
        print(
            "  "
            f"{json.dumps(level_id, ensure_ascii=True)} -> "
            f"suggested label {json.dumps(_suggest_label(level_id), ensure_ascii=True)}",
            file=output,
        )
        shown += 1
        if shown >= MAX_LEVEL_CANDIDATES:
            print("  ... candidate listing limit reached", file=output)
            break
        if inspected >= MAX_LEVEL_DIRECTORY_ENTRIES:
            break
    if inspected >= MAX_LEVEL_DIRECTORY_ENTRIES and shown < MAX_LEVEL_CANDIDATES:
        print("  ... directory scan limit reached", file=output)
    if shown == 0:
        print("  (no .bin files found)", file=output)


def register_current_map(
    name: str,
    level_id: str | None = None,
    levels_dir: Path | None = None,
    output: TextIO = sys.stdout,
) -> str:
    print(
        "Reading the active local map; ensure the desired map is currently loaded.",
        file=output,
    )
    if levels_dir is not None:
        print_level_candidates(levels_dir, output)

    fingerprint, dimensions = read_active_map_fingerprint()
    register_map(fingerprint, name, level_id)
    print(f"Registered map fingerprint: {fingerprint}", file=output)
    print(f"Display name: {name.strip()}", file=output)
    if level_id is not None:
        print(f"User-chosen level ID: {level_id}", file=output)
    print(f"Saved registry: {registry_path()}", file=output)
    print(f"Map image dimensions: {dimensions[0]} x {dimensions[1]}", file=output)
    return fingerprint


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register the fingerprint of the map currently served by War Thunder."
        ),
        epilog=(
            "Run while the desired map is active. Any optional .bin file stem "
            "is only a candidate; the game API does not confirm that it matches "
            "the active map."
        ),
    )
    parser.add_argument("display_name", help="confirmed in-game map display name")
    parser.add_argument(
        "--level-id",
        help="optional level ID chosen by you; stored as an annotation only",
    )
    parser.add_argument(
        "--levels-dir",
        type=Path,
        help="optional directory to list .bin filename candidates (not read)",
    )
    args = parser.parse_args(argv)

    try:
        register_current_map(
            args.display_name,
            args.level_id,
            args.levels_dir,
        )
    except (OSError, TimeoutError, ValueError) as error:
        print(f"Registration failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

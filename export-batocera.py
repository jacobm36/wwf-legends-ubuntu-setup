#!/usr/bin/env python3
"""Export an installed Ubuntu game as a self-contained Batocera folder."""

import argparse
import os
from pathlib import Path
import shutil
import sys

from legends_runtime import project64_files, soundtrack_files


SOURCE = Path(__file__).resolve().parent
GAME_FOLDER = "Ch64 - Public"
GAME_PATH = Path("prefix/drive_c") / GAME_FOLDER


def export(prefix, output, runner):
    prefix = prefix.expanduser().resolve()
    output = output.expanduser()
    if output.is_symlink():
        raise RuntimeError(f"Refusing to overwrite an export symlink: {output}")
    output = output.resolve()
    if runner not in ("wine-proton", "wine-tkg"):
        raise RuntimeError(f"Unsupported Batocera Wine runner: {runner}")
    project64 = prefix / "drive_c" / GAME_FOLDER / "Project64"
    if output == Path("/") or output == Path.home().resolve():
        raise RuntimeError("Choose a dedicated export folder, not / or your home folder.")
    if output.is_relative_to(SOURCE) or output.is_relative_to(prefix):
        raise RuntimeError("The export folder must be outside this repository and source prefix.")
    if not (prefix / "system.reg").is_file():
        raise RuntimeError(f"An installed Ubuntu Wine prefix is required: {prefix}")
    for path in project64_files(project64):
        if not path.is_file():
            raise FileNotFoundError(f"Required installed game component is missing: {path}")
    music = project64 / "Music Tool/Music"
    if not soundtrack_files(project64):
        raise RuntimeError(f"The required MP3 soundtrack is missing: {music}")
    for path in (project64, *project64.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Game symlinks cannot be exported; supply regular files: {path}")
    config = project64 / "Config/Project64.cfg"
    try:
        text = config.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"Project64 config must be UTF-8: {config}") from error
    if "E:\\Project64\\" in text:
        raise RuntimeError("Run setup-ubuntu.py first; Project64 still has its original E: paths.")
    for name in ("launch-batocera.py", "legends_runtime.py", "install-batocera.py"):
        if not (SOURCE / name).is_file():
            raise FileNotFoundError(f"Export support file is missing: {SOURCE / name}")

    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing export or saves: {output}")
    try:
        output.mkdir(parents=True, exist_ok=False)
        game = output / GAME_PATH
        shutil.copytree(project64, game / "Project64",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
        for name in ("launch-batocera.py", "legends_runtime.py"):
            shutil.copy2(SOURCE / name, game / name)
        installer = output / "install-batocera.py"
        shutil.copy2(SOURCE / installer.name, installer)
        (output / "runner.txt").write_text(runner + "\n", encoding="utf-8")
    except (OSError, shutil.Error) as error:
        raise RuntimeError(
            f"Export failed: {error}. Partial files may remain in {output}; "
            "inspect them before retrying."
        ) from error
    return game, installer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    parser.add_argument("--prefix", type=Path,
                        default=xdg_data / "wineprefixes/wwf-legends",
                        help="installed Ubuntu prefix (default: the setup helper's prefix)")
    parser.add_argument("--output", type=Path, required=True,
                        help="new export folder to copy directly into Batocera /userdata")
    parser.add_argument("--runner", choices=("wine-proton", "wine-tkg"),
                        default="wine-proton", help="Batocera Wine runner (default: wine-proton)")
    args = parser.parse_args()
    try:
        game, installer = export(args.prefix, args.output, args.runner)
    except (OSError, RuntimeError, shutil.Error) as error:
        print(f"Batocera export failed: {error}", file=sys.stderr)
        return 1
    print(f"Export complete: {args.output.expanduser().resolve()}")
    print(f"One-time installer: {installer}")
    print("Copy the whole export folder into Batocera /userdata, then run its installer.")
    print(f"Copied game and soundtrack: {game / 'Project64'}")
    print("A fresh Wine prefix will be initialized on Batocera at first launch.")
    print("Run the target --check command in SETUP.md before playing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

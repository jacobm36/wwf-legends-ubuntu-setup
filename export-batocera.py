#!/usr/bin/env python3
"""Export an installed Ubuntu game as a Batocera userdata overlay."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

from legends_runtime import project64_files, soundtrack_files


SOURCE = Path(__file__).resolve().parent
GAME_FOLDER = "Ch64 - Public"
PORT_NAME = "WWF Legends - Challenge 64.sh"
GAME_PATH = Path("system/wwf-legends/prefix/drive_c") / GAME_FOLDER


def export(prefix, output, runner):
    prefix = prefix.expanduser().resolve()
    output = output.expanduser().resolve()
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
    for name in ("launch-batocera.py", "legends_runtime.py"):
        if not (SOURCE / name).is_file():
            raise FileNotFoundError(f"Export support file is missing: {SOURCE / name}")

    state = output / "system/wwf-legends"
    port = output / "roms/ports" / PORT_NAME
    keys = port.with_name(port.name + ".keys")
    for path in (state, port, keys):
        if not path.resolve().is_relative_to(output):
            raise RuntimeError(f"Export path points outside the output folder: {path}")
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"Refusing to overwrite existing Batocera files or saves: {path}")
        if prefix.is_relative_to(path.resolve()) or SOURCE.is_relative_to(path.resolve()):
            raise RuntimeError(f"Export path overlaps the source: {path}")

    state.mkdir(parents=True, exist_ok=False)
    try:
        game = output / GAME_PATH
        shutil.copytree(project64, game / "Project64",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
        for name in ("launch-batocera.py", "legends_runtime.py"):
            shutil.copy2(SOURCE / name, game / name)
        launcher = Path("/userdata") / GAME_PATH / "launch-batocera.py"
        port.parent.mkdir(parents=True, exist_ok=True)
        with keys.open("x", encoding="utf-8") as handle:
            json.dump({"actions_player1": [{
                "trigger": ["hotkey", "start"], "type": "key",
                "target": ["KEY_LEFTALT", "KEY_F4"],
            }]}, handle, indent=2)
            handle.write("\n")
        with port.open("x", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\nset -eu\n"
                "mkdir -p /userdata/system/logs\n"
                "log=/userdata/system/logs/wwf-legends.log\n"
                'if [ -f "$log" ]; then cp "$log" "${log%.log}.previous.log"; fi\n'
                f"exec /usr/bin/python3 {shlex.quote(str(launcher))} "
                f'--runner {shlex.quote(runner)} >"$log" 2>&1\n'
            )
        port.chmod(0o755)
    except (OSError, shutil.Error) as error:
        raise RuntimeError(
            f"Export failed: {error}. Partial files may remain in {state} "
            f"and {port.parent}; inspect them before retrying."
        ) from error
    return game, port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    parser.add_argument("--prefix", type=Path,
                        default=xdg_data / "wineprefixes/wwf-legends",
                        help="installed Ubuntu prefix (default: the setup helper's prefix)")
    parser.add_argument("--output", type=Path, required=True,
                        help="export folder whose contents will be copied into Batocera /userdata")
    parser.add_argument("--runner", choices=("wine-proton", "wine-tkg"),
                        default="wine-proton", help="Batocera Wine runner (default: wine-proton)")
    args = parser.parse_args()
    try:
        game, port = export(args.prefix, args.output, args.runner)
    except (OSError, RuntimeError, shutil.Error) as error:
        print(f"Batocera export failed: {error}", file=sys.stderr)
        return 1
    print(f"Export complete: {args.output.expanduser().resolve()}")
    print(f"Ports launcher: {port}")
    print("Copy roms/ and system/ into Batocera /userdata, without replacing existing exports.")
    print("Refresh the game list, then launch WWF Legends - Challenge 64 from Ports.")
    print(f"Copied game and soundtrack: {game / 'Project64'}")
    print("A fresh Wine prefix will be initialized on Batocera at first launch.")
    print("Run the target --check command in SETUP.md before playing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

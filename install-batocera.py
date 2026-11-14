#!/usr/bin/env python3
"""Register a copied WWF Legends export in Batocera's Ports menu."""

import json
from pathlib import Path
import shlex
import sys


PORT_NAME = "WWF Legends - Challenge 64.sh"
GAME_PATH = Path("prefix/drive_c/Ch64 - Public")
USERDATA = Path("/userdata")


def install(root, userdata):
    root = root.resolve()
    userdata = userdata.resolve()
    if root.parent != userdata:
        raise RuntimeError(f"Copy the whole export folder directly into {userdata} first.")
    launcher = root / GAME_PATH / "launch-batocera.py"
    if not launcher.is_file():
        raise FileNotFoundError(f"Export launcher is missing: {launcher}")
    runner_file = root / "runner.txt"
    runner = runner_file.read_text(encoding="utf-8").strip()
    if runner not in ("wine-proton", "wine-tkg"):
        raise RuntimeError(f"Invalid Wine runner in {runner_file}: {runner!r}")

    ports = userdata / "roms/ports"
    if not ports.resolve().is_relative_to(userdata):
        raise RuntimeError(f"Ports directory points outside {userdata}: {ports}")
    port = ports / PORT_NAME
    keys = ports / (PORT_NAME + ".keys")
    for path in (port, keys):
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"Refusing to overwrite existing Ports entry: {path}")
    ports.mkdir(parents=True, exist_ok=True)
    try:
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
    except OSError as error:
        raise RuntimeError(
            f"Could not register the Ports entry: {error}. Partial files may "
            f"remain at {port} or {keys}; inspect them before retrying."
        ) from error
    return port


def main():
    try:
        port = install(Path(__file__).resolve().parent, USERDATA)
    except (OSError, RuntimeError) as error:
        print(f"Batocera installation failed: {error}", file=sys.stderr)
        return 1
    print(f"Ports entry installed: {port}")
    print("Update game lists, then launch WWF Legends - Challenge 64 from Ports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

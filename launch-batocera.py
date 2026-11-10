#!/usr/bin/env python3
"""Run an exported Challenge 64 installation from Batocera's Ports menu."""

import argparse
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

from legends_runtime import (
    LOG, MusicPlayer, entrypoint, project64_files, run, soundtrack_files, wine_environment,
)


ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.parent.parent
STATE = PREFIX.parent
VERSION = Path("/usr/share/batocera/batocera.version")


def runner_environment(wine):
    base = wine.parent.parent
    lib64 = base / ("lib64/wine" if (base / "lib64/wine").is_dir() else "lib/wine")
    lib32 = base / ("lib32/wine" if (base / "lib32/wine").is_dir() else "lib/wine")
    libraries = f"/lib32:{lib32}/i386-unix:/lib:/usr/lib:{lib64}/x86_64-unix"
    if (base / "lib/x86_64-linux-gnu").is_dir():
        libraries += f":{base}/lib/x86_64-linux-gnu:{base}/lib/i386-linux-gnu"
    env = wine_environment(PREFIX)
    env.update({
        "WINEARCH": "win64",
        "LD_LIBRARY_PATH": libraries,
        "WINEDLLPATH": f"{lib32}/i386-windows:{lib64}/x86_64-windows",
        "GST_PLUGIN_SYSTEM_PATH_1_0": "/usr/lib/gstreamer-1.0:/lib32/gstreamer-1.0",
        "LIBGL_DRIVERS_PATH": "/lib32/dri:/usr/lib/dri",
        "SPA_PLUGIN_DIR": "/usr/lib/spa-0.2:/lib32/spa-0.2",
        "PIPEWIRE_MODULE_DIR": "/usr/lib/pipewire-0.3:/lib32/pipewire-0.3",
    })
    return env


def check_requirements(wine):
    if not VERSION.is_file() or platform.machine() != "x86_64":
        raise RuntimeError("This export requires Batocera 43 or newer on an x86-64 PC.")
    version = VERSION.read_text().strip()
    major = re.match(r"(\d+)", version)
    if major is None or int(major.group(1)) < 43:
        raise RuntimeError(f"This export requires Batocera 43 or newer; found {version!r}.")
    for path in (wine, wine.with_name("wineserver")):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"Batocera Wine runner is missing or not executable: {path}")
    for path in project64_files(ROOT / "Project64"):
        if not path.is_file():
            raise FileNotFoundError(f"Required game component is missing: {path}")
    music = ROOT / "Project64/Music Tool/Music"
    tracks = sorted(
        soundtrack_files(ROOT / "Project64"),
        key=lambda path: path.name,
    )
    if not tracks:
        raise RuntimeError(f"The required MP3 soundtrack is missing: {music}")
    player = MusicPlayer()
    try:
        # Decode a real supplied track through the target's audio sink, muted.
        player.player.set_property("volume", 0.0)
        player.play(tracks[0])
        result, _, _ = player.player.get_state(10 * player.gst.SECOND)
        player.poll()
        if result != player.gst.StateChangeReturn.SUCCESS:
            raise RuntimeError("GStreamer could not start MP3 playback within 10 seconds.")
    finally:
        player.close()
    LOG.info("Batocera version: %s", version)
    LOG.info("Wine runner and MP3 decoding/audio sink check passed.")
    LOG.info("Game RAM access and controller settings still require an in-game test.")


def prepare_prefix(wine, env):
    marker = PREFIX / ".wwf-legends-ready"
    if marker.is_file() and (PREFIX / "system.reg").is_file():
        if marker.read_text().strip() != str(wine):
            raise RuntimeError(
                "This prefix was initialized with another Wine runner. Back up "
                "your saves and use a separate export to test a different runner."
            )
        return
    LOG.info("Initializing Batocera Wine prefix (first launch can take several minutes).")
    boot_env = dict(env, WINEARCH="win64")
    boot_env["WINEDLLOVERRIDES"] += ";mscoree,mshtml=;winegstreamer="
    try:
        subprocess.run([str(wine), "wineboot", "-u"], env=boot_env,
                       cwd=ROOT, check=True, timeout=180)
        subprocess.run([str(wine.with_name("wineserver")), "-w"], env=boot_env,
                       cwd=ROOT, check=True, timeout=180)
    except (subprocess.SubprocessError, OSError):
        # Stop only the server for this game's prefix, not other Wine games.
        try:
            stopped = subprocess.run(
                [str(wine.with_name("wineserver")), "-k"], env=boot_env,
                check=False, timeout=30)
            if stopped.returncode:
                LOG.error("Prefix cleanup exited with status %d", stopped.returncode)
        except (subprocess.SubprocessError, OSError):
            LOG.exception("Could not stop this game's Wine server after initialization failed.")
        raise
    if not (PREFIX / "system.reg").is_file():
        raise RuntimeError(f"Wine did not create its registry at {PREFIX}")
    marker.write_text(str(wine) + "\n", encoding="utf-8")


def start():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", choices=("wine-proton", "wine-tkg"),
                        default="wine-proton")
    parser.add_argument("--check", action="store_true",
                        help="check target dependencies without initializing Wine or launching the game")
    args = parser.parse_args()
    wine = Path("/usr/wine") / args.runner / "bin/wine"
    check_requirements(wine)
    if args.check:
        return 0
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("No graphical display. Launch from Ports or set DISPLAY=:0 over SSH.")
    env = runner_environment(wine)
    return run(ROOT, PREFIX, wine, env, STATE / "launch.lock",
               prepare=lambda: prepare_prefix(wine, env))


if __name__ == "__main__":
    sys.exit(entrypoint(start, "/userdata/system/logs/wwf-legends.log"))

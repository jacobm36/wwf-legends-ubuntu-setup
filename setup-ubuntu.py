#!/usr/bin/env python3
"""Install this extracted game folder into a dedicated Ubuntu Wine prefix."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from legends_runtime import project64_files, soundtrack_files


SOURCE = Path(__file__).resolve().parent
GAME_FOLDER = "Ch64 - Public"


def required_source_paths():
    return project64_files(SOURCE / "Project64") + (
        SOURCE / "launch-ubuntu.py",
        SOURCE / "legends_runtime.py",
        SOURCE / "enable-fullscreen.py",
        SOURCE / "borderless.py",
        SOURCE / "borderless.exe",
    )


def source_music_files():
    return soundtrack_files(SOURCE / "Project64")


def dependency_problems():
    problems = [
        command for command in (
            "/usr/bin/wine",
            "/usr/bin/wineboot",
            "/usr/bin/zenity",
            "/usr/bin/python3",
        )
        if not Path(command).is_file()
    ]
    if not Path("/usr/share/winebundle/lib/graphics.py").is_file():
        problems.append("Winebundle (GPU helper at /usr/share/winebundle/lib/graphics.py)")
    result = subprocess.run(
        [
            "/usr/bin/python3", "-c",
            "import gi; gi.require_version('Gst', '1.0'); "
            "from gi.repository import Gst; Gst.init(None); "
            "assert Gst.ElementFactory.make('playbin', 'check') is not None",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        problems.append("Python GStreamer bindings (python3-gi and gir1.2-gstreamer-1.0)")
    return problems


def rewrite_project64_config(config):
    try:
        original = config.read_bytes()
        text = original.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RuntimeError(f"Cannot read Project64 config {config}: {error}") from error

    updated = text.replace(
        "E:\\Project64\\Roms\\",
        "C:\\Ch64 - Public\\Project64\\Roms\\",
    ).replace(
        "E:\\Project64\\Save",
        "C:\\Ch64 - Public\\Project64\\Save",
    ).replace(
        r"GFX\RiceVideo.dll",
        "RiceVideo.dll",
    )
    if "E:\\Project64\\" in updated:
        raise RuntimeError(
            f"Project64 config contains an unrecognized E:\\Project64 path: {config}"
        )
    lines = updated.splitlines(keepends=True)
    cheat_section = "[4E4B0640-1B49BCFB-C:45]"
    sections = [
        index for index, line in enumerate(lines)
        if line.strip() == cheat_section
    ]
    if len(sections) != 1:
        raise RuntimeError(
            f"Expected one {cheat_section} cheat section in {config}; found {len(sections)}."
        )
    section_start = sections[0]
    section_end = next(
        (
            index for index in range(section_start + 1, len(lines))
            if lines[index].strip().startswith("[")
            and lines[index].strip().endswith("]")
        ),
        len(lines),
    )
    cheat_2147 = [
        index for index in range(section_start + 1, section_end)
        if lines[index].partition("=")[0].strip() == "Cheat2147"
        and "=" in lines[index]
    ]
    if len(cheat_2147) > 1:
        raise RuntimeError(f"Duplicate Cheat2147 entries in {config}.")
    newline = next(
        (
            ending for line in lines
            for ending in ("\r\n", "\n", "\r")
            if line.endswith(ending)
        ),
        "\n",
    )
    if cheat_2147:
        index = cheat_2147[0]
        if lines[index].partition("=")[2].strip() != "1":
            lines[index] = f"Cheat2147=1{newline}"
    else:
        cheat_2146 = next(
            (
                index for index in range(section_start + 1, section_end)
                if lines[index].partition("=")[0].strip() == "Cheat2146"
                and lines[index].partition("=")[2].strip() == "1"
            ),
            None,
        )
        if cheat_2146 is None:
            raise RuntimeError(f"Cheat2146=1 was not found in {cheat_section}.")
        lines.insert(cheat_2146 + 1, f"Cheat2147=1{newline}")
    updated = "".join(lines)
    if updated != text:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = config.with_name(f"{config.name}.before-ubuntu-setup-{stamp}")
        try:
            shutil.copy2(config, backup)
            config.write_bytes(updated.encode("utf-8"))
        except OSError as error:
            raise RuntimeError(f"Could not update {config}: {error}") from error
        print(f"Project64 config backup: {backup}")


def create_menu_launcher(game_dir):
    home = Path.home()
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    wrapper = home / ".local" / "bin" / "wwf-legends"
    desktop = xdg_data / "applications" / "wwf-legends.desktop"
    for path in (wrapper, desktop):
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite existing launcher file: {path}")

    wrapper.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'state="${XDG_STATE_HOME:-$HOME/.local/state}/wwf-legends"\n'
        'mkdir -p "$state"\n'
        'if [ -f "$state/launch.log" ]; then\n'
        '    cp "$state/launch.log" "$state/launch.previous.log"\n'
        "fi\n"
        f"exec /usr/bin/python3 {shlex.quote(str(game_dir / 'launch-ubuntu.py'))} "
        '>"$state/launch.log" 2>&1\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    desktop_exec = str(wrapper).replace("\\", "\\\\").replace('"', '\\"')
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=WWF Legends - Challenge 64\n"
        "Comment=Play Challenge 64 with native music and Winebundle GPU selection\n"
        f'Exec="{desktop_exec}"\n'
        "Icon=applications-games\n"
        "Terminal=false\n"
        "Categories=Game;Emulator;\n"
        "StartupNotify=false\n"
        "StartupWMClass=project64.exe\n",
        encoding="utf-8",
    )
    print(f"Application menu entry created: {desktop}")


def main():
    parser = argparse.ArgumentParser(
        description="Set up the extracted WWF Legends game in a separate Wine prefix."
    )
    parser.add_argument(
        "--prefix",
        type=Path,
        help="empty Wine-prefix location (default: ~/.local/share/wineprefixes/wwf-legends)",
    )
    args = parser.parse_args()

    missing = [path for path in required_source_paths() if not path.is_file()]
    if missing:
        print("This does not look like the extracted game folder. Missing:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    music_files = source_music_files()
    if not music_files:
        print(
            "The mod's required music files are missing. Obtain the soundtrack "
            "pack from a source authorized to distribute it, then extract its "
            "MP3 files into Project64/Music Tool/Music before running setup.",
            file=sys.stderr,
        )
        return 1

    problems = dependency_problems()
    if problems:
        print("Install or repair these requirements before continuing:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nUbuntu packages: wine python3-gi gir1.2-gstreamer-1.0 "
            "gstreamer1.0-plugins-base gstreamer1.0-plugins-good "
            "gstreamer1.0-plugins-ugly zenity",
            file=sys.stderr,
        )
        print(
            "Install Winebundle separately; its GPU helper is required by this launcher.",
            file=sys.stderr,
        )
        return 1

    xdg_data = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    prefix = (args.prefix or xdg_data / "wineprefixes" / "wwf-legends").expanduser()
    prefix = prefix.resolve()
    game_dir = prefix / "drive_c" / GAME_FOLDER
    if (
        prefix == Path("/")
        or SOURCE == prefix
        or SOURCE.is_relative_to(prefix)
        or prefix.is_relative_to(SOURCE)
    ):
        print(f"Unsafe prefix location: {prefix}", file=sys.stderr)
        return 1
    if prefix.exists() and any(prefix.iterdir()):
        print(
            f"Prefix already exists and is not empty: {prefix}\n"
            "Choose a new, empty location with --prefix. Existing game data was not changed.",
            file=sys.stderr,
        )
        return 1

    home = Path.home()
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    if (home / ".local" / "bin" / "wwf-legends").exists() \
            or (xdg_data / "applications" / "wwf-legends.desktop").exists():
        print(
            "A WWF Legends menu launcher already exists. It was not overwritten.",
            file=sys.stderr,
        )
        return 1

    try:
        env = dict(os.environ, WINEPREFIX=str(prefix), WINEARCH="win64")
        subprocess.run(["/usr/bin/wineboot", "-u"], env=env, check=True)
        registry = prefix / "system.reg"
        deadline = time.monotonic() + 30
        while not registry.is_file() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not registry.is_file():
            raise RuntimeError(f"Wine did not create a prefix at {prefix}")

        game_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            SOURCE,
            game_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
        )
        rewrite_project64_config(game_dir / "Project64" / "Config" / "Project64.cfg")
        subprocess.run(
            ["/usr/bin/python3", str(game_dir / "enable-fullscreen.py"), "--disable"],
            check=True,
        )
        create_menu_launcher(game_dir)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        print(f"Review the new prefix before retrying: {prefix}", file=sys.stderr)
        return 1

    print("\nSetup complete.")
    print(f"Game folder: {game_dir}")
    print("Launch WWF Legends - Challenge 64 from the application menu.")
    print(f"Found {len(music_files)} required MP3 music files.")
    print("Music filenames are matched case-insensitively, for example 0x1A.mp3.")
    print("The initial texture scan may take 1-2 minutes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

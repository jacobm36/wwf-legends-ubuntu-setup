#!/usr/bin/env python3
"""Enable or disable Project64's native automatic full-screen preference."""

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "Project64" / "Config" / "Project64.cfg"
SETTING = "Auto Full Screen"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disable", action="store_true",
                        help="disable native fullscreen for the borderless launcher")
    args = parser.parse_args()
    value = "0" if args.disable else "1"
    state = "disabled" if args.disable else "enabled"
    if not CONFIG.is_file():
        print(f"Project64 config not found: {CONFIG}", file=sys.stderr)
        return 1

    try:
        content = CONFIG.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"Cannot read Project64 config: {error}", file=sys.stderr)
        return 1

    lines = content.splitlines(keepends=True)
    default_sections = [
        index for index, line in enumerate(lines)
        if line.strip().casefold() == "[default]"
    ]
    if len(default_sections) != 1:
        print(
            f"Expected one [default] section in {CONFIG}; found "
            f"{len(default_sections)}.",
            file=sys.stderr,
        )
        return 1

    section_start = default_sections[0]
    section_end = next(
        (
            index for index in range(section_start + 1, len(lines))
            if lines[index].strip().startswith("[")
            and lines[index].strip().endswith("]")
        ),
        len(lines),
    )
    setting_lines = [
        index for index in range(section_start + 1, section_end)
        if lines[index].partition("=")[0].strip().casefold() == SETTING.casefold()
        and "=" in lines[index]
    ]
    if len(setting_lines) > 1:
        print(f"Found duplicate {SETTING} entries in {CONFIG}.", file=sys.stderr)
        return 1

    newline = next(
        (
            ending for line in lines
            for ending in ("\r\n", "\n", "\r")
            if line.endswith(ending)
        ),
        "\n",
    )
    if setting_lines:
        index = setting_lines[0]
        key, _, current = lines[index].partition("=")
        if current.strip() == value:
            print(f"Project64 automatic full screen is already {state}.")
            return 0
        lines[index] = f"{key}={value}{newline}"
    else:
        if not lines[section_start].endswith(("\r", "\n")):
            lines[section_start] += newline
        lines.insert(section_start + 1, f"{SETTING}={value}{newline}")

    backup = CONFIG.with_name(
        f"{CONFIG.name}.before-fullscreen-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    )
    try:
        shutil.copy2(CONFIG, backup)
        CONFIG.write_bytes("".join(lines).encode("utf-8"))
    except OSError as error:
        print(f"Could not update Project64 config: {error}", file=sys.stderr)
        return 1

    print(f"Project64 automatic full screen is {state}.")
    print(f"Original config backed up to: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

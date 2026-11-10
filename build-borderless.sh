#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
compiler="${MINGW_CC:-i686-w64-mingw32-gcc}"
if ! command -v "$compiler" >/dev/null 2>&1; then
    printf 'Missing Windows cross compiler: %s\nInstall it with: sudo apt install gcc-mingw-w64-i686\n' "$compiler" >&2
    exit 1
fi
"$compiler" -Wall -Wextra -Werror -O2 -static-libgcc \
    "$root/borderless.c" -o "$root/borderless.exe" -luser32 -ladvapi32
printf 'Built %s/borderless.exe\n' "$root"

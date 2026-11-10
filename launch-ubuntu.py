#!/usr/bin/python3
"""Launch Challenge 64 with native MP3 playback and Winebundle GPU selection."""

from pathlib import Path
import sys

import borderless
from legends_runtime import LOG, entrypoint, run, wine_environment


ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.parent.parent


def environment():
    sys.path.insert(0, "/usr/share/winebundle/lib")
    try:
        from graphics import discrete_gpu
    except ImportError as error:
        raise RuntimeError("Winebundle's installed GPU helper is missing.") from error

    env = wine_environment(PREFIX)
    card = discrete_gpu()
    if card:
        env.update(card["env"])
        LOG.info("Winebundle graphics selection: %s", card["name"])
    else:
        LOG.info("Winebundle graphics selection: default GPU")
    return env


def start():
    wine = Path("/usr/bin/wine")
    env = environment()
    return run(
        ROOT, PREFIX, wine, env, Path.home() / ".cache" / "wwf-legends.lock",
        prepare=lambda: borderless.configure(ROOT, wine, env),
        ready=lambda: borderless.enter(ROOT, wine, env),
    )


if __name__ == "__main__":
    sys.exit(entrypoint(start, "~/.local/state/wwf-legends/launch.log"))

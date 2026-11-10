"""Configure Rice's render size and enter borderless mode through Wine."""

import logging
import subprocess


LOG = logging.getLogger("wwf-legends")


def helper(root, wine, env, *arguments):
    executable = root / "borderless.exe"
    if not executable.is_file():
        raise RuntimeError(
            f"Missing borderless helper: {executable}. Run build-borderless.sh first."
        )
    try:
        result = subprocess.run(
            [str(wine), str(executable), *arguments],
            env=env, capture_output=True, text=True, timeout=75, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("The Wine borderless helper timed out after 75 seconds.") from error
    if result.returncode:
        raise RuntimeError(
            f"Borderless fullscreen failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    LOG.info("%s", result.stdout.strip())


def configure(root, wine, env):
    windowed = env.get("WWF_LEGENDS_WINDOWED") == "1"
    helper(root, wine, env, "--windowed" if windowed else "--configure")
    try:
        result = subprocess.run(
            ["/usr/bin/python3", str(root / "enable-fullscreen.py"), "--disable"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Disabling native auto-fullscreen timed out.") from error
    if result.returncode:
        raise RuntimeError(
            "Cannot disable conflicting native auto-fullscreen: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    LOG.info("%s", result.stdout.strip())


def enter(root, wine, env):
    if env.get("WWF_LEGENDS_WINDOWED") != "1":
        helper(root, wine, env)

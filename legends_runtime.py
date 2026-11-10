#!/usr/bin/python3
"""Shared Project64 launch and native soundtrack support."""

import fcntl
import logging
import os
from pathlib import Path
import signal
import shutil
import struct
import subprocess
import time

LOG = logging.getLogger("wwf-legends")
ROM = "WWF Legends - Challenge 64.z64"


def project64_files(project64):
    return tuple(project64 / relative for relative in (
        "Project64.exe", "Config/Project64.cfg", f"Roms/{ROM}",
        "Plugin/RiceVideo.dll", "msvcr71.dll", "msvcp71.dll",
    ))


def soundtrack_files(project64):
    music = project64 / "Music Tool/Music"
    if not music.is_dir():
        return []
    return [
        path for path in music.iterdir()
        if path.is_file() and path.suffix.casefold() == ".mp3"
    ]


def read_short(memory, address):
    data = os.pread(memory, 2, address)
    if len(data) != 2:
        raise OSError(f"Cannot read game memory at {address:#x}")
    return struct.unpack("<H", data)[0]


def write_short(memory, address, value):
    if os.pwrite(memory, struct.pack("<H", value), address) != 2:
        raise OSError(f"Cannot write game memory at {address:#x}")


def music_track(music, command):
    name = f"{command:#x}.mp3"
    exact = music / name
    if exact.is_file():
        return exact
    folded_name = name.casefold()
    return next(
        (
            track for track in music.iterdir()
            if track.is_file() and track.name.casefold() == folded_name
        ),
        None,
    )


def find_ram(pid, memory):
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        fields = line.split()
        start, end = (int(value, 16) for value in fields[0].split("-"))
        if not fields[1].startswith("rw") or start >= 2**32 or end - start < 0x800000:
            continue
        for base in range(start, end - 0x800000 + 1, 0x10000):
            if (read_short(memory, base + 0x159AD4) == 0x71F3
                    and read_short(memory, base + 0x702) == 0x8FB4):
                return base
    return None


def gstreamer():
    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
    except (ImportError, ValueError) as error:
        raise RuntimeError(
            "Native soundtrack playback requires Python PyGObject and "
            "the GStreamer Gst 1.0 typelib."
        ) from error
    Gst.init(None)
    return Gst


class MusicPlayer:
    def __init__(self):
        Gst = gstreamer()
        self.gst = Gst
        self.player = Gst.ElementFactory.make("playbin", "music")
        if self.player is None:
            raise RuntimeError("GStreamer playbin is missing")
        self.bus = self.player.get_bus()
        self.track = None

    def play(self, track):
        Gst = self.gst
        self.close()
        self.player.set_property("uri", track.as_uri())
        if self.player.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError(f"Cannot play {track.name}")
        self.track = track
        LOG.info("Music: %s", track.name)

    def poll(self):
        Gst = self.gst
        message = self.bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if message is None:
            return
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            raise RuntimeError(f"Music playback failed: {error.message}; {debug}")
        if not self.player.seek_simple(
                Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0):
            raise RuntimeError(f"Cannot loop {self.track}")

    def close(self):
        Gst = self.gst
        self.player.set_state(Gst.State.NULL)
        self.player.get_state(5 * Gst.SECOND)
        while self.bus.pop() is not None:
            pass
        self.track = None


def wine_environment(prefix):
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG="-all,err+all")
    overrides = env.get("WINEDLLOVERRIDES", "")
    env["WINEDLLOVERRIDES"] = (
        (overrides + ";" if overrides else "") + "msvcr71,msvcp71=n,b")
    return env


def run(root, prefix, wine, env, lock_path, prepare=None, ready=None):
    emulator = root / "Project64"
    music = emulator / "Music Tool" / "Music"
    for path in (emulator / "Project64.exe", emulator / "Roms" / ROM, music):
        if not path.exists():
            raise FileNotFoundError(f"Required game component is missing: {path}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("WWF Legends is already running") from None
        if prepare is not None:
            prepare()
        if not (prefix / "system.reg").is_file():
            raise FileNotFoundError(f"Wine prefix is missing: {prefix}")
        player = MusicPlayer()
        process = None
        memory = None
        try:
            process = subprocess.Popen(
                [str(wine), str(emulator / "Project64.exe"),
                 r"C:\Ch64 - Public\Project64\Roms\WWF Legends - Challenge 64.z64"],
                cwd=emulator, env=env)
            LOG.info("Project64 PID: %d; texture scanning can take 1-2 minutes", process.pid)
            deadline = time.monotonic() + 180
            base = None
            last_track = None
            while process.poll() is None:
                if base is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Game RAM was not ready after 3 minutes")
                    if memory is None:
                        memory = os.open(f"/proc/{process.pid}/mem", os.O_RDWR)
                    base = find_ram(process.pid, memory)
                    if base is None:
                        os.close(memory)
                        memory = None
                        time.sleep(0.5)
                        continue
                    LOG.info("Validated game RAM: %#x; native music enabled", base)
                    if ready is not None:
                        ready()
                signature = os.pread(memory, 2, base + 0x702)
                if signature != b"\xb4\x8f":
                    LOG.info("Emulation stopped or reset; stopping music")
                    player.close()
                    os.close(memory)
                    memory = None
                    base = None
                    last_track = None
                    deadline = time.monotonic() + 180
                    continue
                # Match the supplied music tool's address translation.
                write_short(memory, base + 0x1502C4, 0x0200)
                command = read_short(memory, base + 0x485A6)
                if command not in (0, 0x44, 0xFFFF) and command != last_track:
                    track = music_track(music, command)
                    if track is not None:
                        player.play(track)
                    else:
                        player.close()
                        LOG.warning("No custom track for music command %#x", command)
                    last_track = command
                if player.track is not None:
                    write_short(memory, base + 0x485A6, 0x44)
                player.poll()
                time.sleep(0.015)
            code = process.wait()
            LOG.info("Project64 exited with status %d", code)
            return code
        finally:
            player.close()
            if memory is not None:
                os.close(memory)
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def interrupted(signum, frame):
    raise KeyboardInterrupt


def entrypoint(start, log_path):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        return start()
    except KeyboardInterrupt:
        LOG.info("Launcher stopped")
        return 130
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        LOG.exception("WWF Legends failed")
        zenity = shutil.which("zenity")
        if zenity:
            result = subprocess.run(
                [zenity, "--error", "--title=WWF Legends",
                 f"--text={error}\n\nDetails: {log_path}"],
                check=False)
            if result.returncode:
                LOG.error("Error dialog exited with status %d", result.returncode)
        return 1

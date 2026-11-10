import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import legends_runtime as runtime


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), REPO / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter = load_script("export-batocera")
batocera = load_script("launch-batocera")
ubuntu = load_script("launch-ubuntu")
setup = load_script("setup-ubuntu")


class GameFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wwf-export-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / "ubuntu prefix"
        self.game = self.prefix / "drive_c/Ch64 - Public"
        self.project64 = self.game / "Project64"
        for path in runtime.project64_files(self.project64):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic fixture", encoding="utf-8")
        (self.prefix / "system.reg").write_text("Ubuntu registry fixture")
        (self.prefix / "user.reg").write_text("Ubuntu user registry fixture")
        self.config = self.project64 / "Config/Project64.cfg"
        self.config.write_bytes(
            b"[default]\r\nAuto Full Screen=1\r\n"
            b"Rom Directory=C:\\Ch64 - Public\\Project64\\Roms\\\r\n"
            b"Save Directory=C:\\Ch64 - Public\\Project64\\Save\r\n"
            b"[4E4B0640-1B49BCFB-C:45]\r\nCheat2146=1\r\nCheat2147=1\r\n"
        )
        self.music = self.project64 / "Music Tool/Music"
        self.music.mkdir(parents=True)
        (self.music / "0x1A.MP3").write_bytes(b"synthetic music fixture")
        self.save = self.project64 / "Save/test.fla"
        self.save.parent.mkdir()
        self.save.write_bytes(b"synthetic save")
        self.output = self.root / "batocera export"


class ExportTests(GameFixture):
    def test_complete_overlay_preserves_assets_and_source(self):
        original = self.config.read_bytes()
        game, port = exporter.export(self.prefix, self.output, "wine-proton")
        self.assertEqual(game, self.output / exporter.GAME_PATH)
        self.assertEqual((game / "Project64/Config/Project64.cfg").read_bytes(), original)
        self.assertEqual((game / "Project64/Save/test.fla").read_bytes(), self.save.read_bytes())
        self.assertTrue((game / "Project64/Music Tool/Music/0x1A.MP3").is_file())
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual((self.prefix / "system.reg").read_text(), "Ubuntu registry fixture")
        target_prefix = game.parent.parent
        self.assertFalse((target_prefix / "system.reg").exists())
        self.assertFalse((target_prefix / "user.reg").exists())
        for name in ("launch-batocera.py", "legends_runtime.py"):
            self.assertEqual((game / name).read_bytes(), (REPO / name).read_bytes())
        self.assertFalse((game / "launch-ubuntu.py").exists())
        self.assertTrue(os.access(port, os.X_OK))
        text = port.read_text()
        self.assertIn("'/userdata/system/wwf-legends/prefix/drive_c/Ch64 - Public/launch-batocera.py'", text)
        self.assertNotIn(str(self.prefix), text)
        self.assertIn("--runner wine-proton", text)
        subprocess.run(["sh", "-n", str(port)], check=True)
        keys = json.loads(port.with_name(port.name + ".keys").read_text())
        self.assertEqual(keys["actions_player1"][0]["target"], ["KEY_LEFTALT", "KEY_F4"])

    def test_tkg_runner(self):
        _, port = exporter.export(self.prefix, self.output, "wine-tkg")
        self.assertIn("--runner wine-tkg", port.read_text())

    def test_refuses_second_export_without_modifying_saves(self):
        game, _ = exporter.export(self.prefix, self.output, "wine-proton")
        saved = game / "Project64/Save/test.fla"
        saved.write_bytes(b"target progress")
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertEqual(saved.read_bytes(), b"target progress")

    def test_each_required_asset_is_checked_before_writing(self):
        for path in runtime.project64_files(self.project64):
            with self.subTest(path=path):
                content = path.read_bytes()
                path.unlink()
                with self.assertRaises(FileNotFoundError):
                    exporter.export(self.prefix, self.output, "wine-proton")
                self.assertFalse(self.output.exists())
                path.write_bytes(content)

    def test_soundtrack_required(self):
        (self.music / "0x1A.MP3").unlink()
        with self.assertRaisesRegex(RuntimeError, "MP3 soundtrack"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertFalse(self.output.exists())

    def test_requires_installed_prefix(self):
        (self.prefix / "system.reg").unlink()
        with self.assertRaisesRegex(RuntimeError, "installed Ubuntu Wine prefix"):
            exporter.export(self.prefix, self.output, "wine-proton")

    def test_rejects_original_windows_paths(self):
        self.config.write_text("Rom Directory=E:\\Project64\\Roms\\")
        with self.assertRaisesRegex(RuntimeError, "original E: paths"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertFalse(self.output.exists())

    def test_rejects_game_symlinks(self):
        (self.project64 / "external").symlink_to(self.root / "private")
        with self.assertRaisesRegex(RuntimeError, "symlinks cannot be exported"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertFalse(self.output.exists())

    def test_rejects_unsafe_outputs(self):
        for output in (Path("/"), Path.home(), self.prefix / "export", REPO / "export"):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                exporter.export(self.prefix, output, "wine-proton")

    def test_existing_ports_entry_and_broken_link_are_preserved(self):
        port = self.output / "roms/ports" / exporter.PORT_NAME
        port.parent.mkdir(parents=True)
        port.write_text("existing launcher")
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertEqual(port.read_text(), "existing launcher")
        port.unlink()
        port.symlink_to(port.parent / "missing")
        with self.assertRaises(RuntimeError):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertTrue(port.is_symlink())
        self.assertFalse((self.output / "system/wwf-legends").exists())

    def test_rejects_output_parent_symlink_outside_overlay(self):
        self.output.mkdir()
        (self.output / "system").symlink_to(self.root)
        with self.assertRaisesRegex(RuntimeError, "outside the output folder"):
            exporter.export(self.prefix, self.output, "wine-proton")
        self.assertFalse((self.root / "wwf-legends").exists())

    def test_copy_failure_reports_partial_paths(self):
        with patch.object(exporter.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "Partial files may remain"):
                exporter.export(self.prefix, self.output, "wine-proton")
        self.assertFalse((self.output / "roms/ports" / exporter.PORT_NAME).exists())

    def test_cli_success_and_error_codes(self):
        result = subprocess.run(
            [sys.executable, str(REPO / "export-batocera.py"),
             "--prefix", str(self.prefix), "--output", str(self.output)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Export complete", result.stdout)
        result = subprocess.run(
            [sys.executable, str(REPO / "export-batocera.py"),
             "--prefix", str(self.prefix), "--output", str(self.output)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Refusing to overwrite", result.stderr)


class BatoceraLaunchTests(GameFixture):
    def setUp(self):
        super().setUp()
        self.version = self.root / "batocera.version"
        self.version.write_text("43.1")
        self.wine = self.root / "wine-proton/bin/wine"
        self.wine.parent.mkdir(parents=True)
        for path in (self.wine, self.wine.with_name("wineserver")):
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.env = {"WINEPREFIX": str(self.prefix), "WINEDLLOVERRIDES": "msvcr71,msvcp71=n,b"}
        self.player = Mock()
        self.player.gst.SECOND = 1
        self.player.gst.StateChangeReturn.SUCCESS = "success"
        self.player.player.get_state.return_value = ("success", None, None)
        for name, value in (
            ("ROOT", self.game), ("PREFIX", self.prefix), ("VERSION", self.version),
        ):
            patcher = patch.object(batocera, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_dependency_check_decodes_real_track_muted(self):
        with patch.object(batocera.platform, "machine", return_value="x86_64"), \
                patch.object(batocera, "MusicPlayer", return_value=self.player):
            batocera.check_requirements(self.wine)
        self.player.player.set_property.assert_called_once_with("volume", 0.0)
        self.player.play.assert_called_once_with(self.music / "0x1A.MP3")
        self.player.poll.assert_called_once()
        self.player.close.assert_called_once()

    def test_old_version_and_arm_are_rejected(self):
        for version, machine in (("42", "x86_64"), ("43", "aarch64"), ("invalid", "x86_64")):
            with self.subTest(version=version, machine=machine):
                self.version.write_text(version)
                with patch.object(batocera.platform, "machine", return_value=machine):
                    with self.assertRaisesRegex(RuntimeError, "requires Batocera"):
                        batocera.check_requirements(self.wine)

    def test_audio_error_and_timeout_are_not_silenced(self):
        with patch.object(batocera.platform, "machine", return_value="x86_64"), \
                patch.object(batocera, "MusicPlayer", return_value=self.player):
            self.player.poll.side_effect = RuntimeError("MP3 decoder missing")
            with self.assertRaisesRegex(RuntimeError, "MP3 decoder missing"):
                batocera.check_requirements(self.wine)
            self.player.close.assert_called_once()
            self.player.poll.side_effect = None
            self.player.player.get_state.return_value = ("async", None, None)
            with self.assertRaisesRegex(RuntimeError, "within 10 seconds"):
                batocera.check_requirements(self.wine)

    def test_environment_contains_runner_libraries_and_native_dlls(self):
        with patch.dict(os.environ, {"WINEDLLOVERRIDES": "existing=n"}, clear=True):
            env = batocera.runner_environment(self.wine)
        self.assertEqual(env["WINEPREFIX"], str(self.prefix))
        self.assertEqual(env["WINEARCH"], "win64")
        self.assertEqual(env["WINEDLLOVERRIDES"], "existing=n;msvcr71,msvcp71=n,b")
        self.assertIn(str(self.wine.parent.parent / "lib/wine/x86_64-unix"), env["LD_LIBRARY_PATH"])
        (self.wine.parent.parent / "lib64/wine").mkdir(parents=True)
        (self.wine.parent.parent / "lib32/wine").mkdir(parents=True)
        (self.wine.parent.parent / "lib/x86_64-linux-gnu").mkdir(parents=True)
        env = batocera.runner_environment(self.wine)
        self.assertIn("/lib64/wine/x86_64-unix", env["LD_LIBRARY_PATH"])
        self.assertIn("/lib32/wine/i386-windows", env["WINEDLLPATH"])
        self.assertIn("/lib/x86_64-linux-gnu", env["LD_LIBRARY_PATH"])

    def test_prefix_initialized_once_and_runner_changes_rejected(self):
        with patch.object(batocera.subprocess, "run") as execute:
            batocera.prepare_prefix(self.wine, self.env)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(execute.call_args_list[0].args[0], [str(self.wine), "wineboot", "-u"])
            self.assertEqual(execute.call_args_list[1].args[0], [str(self.wine.with_name("wineserver")), "-w"])
            self.assertEqual(execute.call_args_list[0].kwargs["env"]["WINEARCH"], "win64")
            batocera.prepare_prefix(self.wine, self.env)
            self.assertEqual(execute.call_count, 2)
            with self.assertRaisesRegex(RuntimeError, "another Wine runner"):
                batocera.prepare_prefix(self.root / "wine-tkg/bin/wine", self.env)

    def test_failed_initialization_has_no_ready_marker_and_stops_only_its_server(self):
        failed = subprocess.CalledProcessError(1, "wineboot")
        with patch.object(batocera.subprocess, "run", side_effect=[failed, Mock(returncode=0)]) as execute:
            with self.assertRaises(subprocess.CalledProcessError):
                batocera.prepare_prefix(self.wine, self.env)
        self.assertFalse((self.prefix / ".wwf-legends-ready").exists())
        self.assertEqual(execute.call_args_list[1].args[0], [str(self.wine.with_name("wineserver")), "-k"])
        self.assertEqual(execute.call_args_list[1].kwargs["env"]["WINEPREFIX"], str(self.prefix))

    def test_registry_must_exist_after_initialization(self):
        (self.prefix / "system.reg").unlink()
        with patch.object(batocera.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "did not create"):
                batocera.prepare_prefix(self.wine, self.env)
        self.assertFalse((self.prefix / ".wwf-legends-ready").exists())

    def test_check_mode_never_initializes_or_launches_wine(self):
        with patch.object(sys, "argv", ["launch-batocera.py", "--check"]), \
                patch.object(batocera, "check_requirements") as check, \
                patch.object(batocera, "prepare_prefix") as prepare, \
                patch.object(batocera, "run") as launch:
            self.assertEqual(batocera.start(), 0)
        check.assert_called_once_with(Path("/usr/wine/wine-proton/bin/wine"))
        prepare.assert_not_called()
        launch.assert_not_called()

    def test_tkg_launch_uses_selected_runner_and_prepare_hook(self):
        with patch.object(sys, "argv", ["launch-batocera.py", "--runner", "wine-tkg"]), \
                patch.dict(os.environ, {"DISPLAY": ":0"}), \
                patch.object(batocera, "check_requirements"), \
                patch.object(batocera, "run", return_value=0) as launch, \
                patch.object(batocera, "prepare_prefix") as prepare:
            self.assertEqual(batocera.start(), 0)
            self.assertEqual(launch.call_args.args[2], Path("/usr/wine/wine-tkg/bin/wine"))
            launch.call_args.kwargs["prepare"]()
            prepare.assert_called_once()


class RuntimeTests(GameFixture):
    def test_ubuntu_paths_gpu_selection_and_required_shared_module(self):
        graphics = Mock()
        graphics.discrete_gpu.return_value = {"name": "test GPU", "env": {"DRI_PRIME": "1"}}
        with patch.dict(sys.modules, {"graphics": graphics}):
            env = ubuntu.environment()
        self.assertEqual(env["DRI_PRIME"], "1")
        self.assertEqual(env["WINEPREFIX"], str(ubuntu.PREFIX))
        with patch.object(ubuntu, "run", return_value=0) as launch, \
                patch.object(ubuntu.borderless, "configure") as configure, \
                patch.object(ubuntu.borderless, "enter") as enter:
            with patch.dict(sys.modules, {"graphics": graphics}):
                self.assertEqual(ubuntu.start(), 0)
            launch.call_args.kwargs["prepare"]()
            launch.call_args.kwargs["ready"]()
            arguments = (ubuntu.ROOT, Path("/usr/bin/wine"), launch.call_args.args[3])
            configure.assert_called_once_with(*arguments)
            enter.assert_called_once_with(*arguments)
        self.assertEqual(launch.call_args.args[2], Path("/usr/bin/wine"))
        self.assertIn(REPO / "legends_runtime.py", setup.required_source_paths())

    def test_music_matching_ignores_case(self):
        self.assertEqual(runtime.music_track(self.music, 0x1A), self.music / "0x1A.MP3")
        self.assertIsNone(runtime.music_track(self.music, 0x2))

    def test_soundtrack_command_memory_writes_and_clean_exit(self):
        memory_path = self.root / "memory"
        with memory_path.open("w+b") as memory:
            memory.truncate(0x800000)
            runtime.write_short(memory.fileno(), 0x702, 0x8FB4)
            runtime.write_short(memory.fileno(), 0x485A6, 0x1A)
            process = Mock(pid=123, poll=Mock(side_effect=[None, None, 0, 0]))
            process.wait.return_value = 0
            player = Mock(track=None)
            player.play.side_effect = lambda track: setattr(player, "track", track)
            ready = Mock()
            fd = os.open(memory_path, os.O_RDWR)
            with patch.object(runtime, "MusicPlayer", return_value=player), \
                    patch.object(runtime.subprocess, "Popen", return_value=process) as launch, \
                    patch.object(runtime.os, "open", side_effect=[os.dup(fd), fd]), \
                    patch.object(runtime, "find_ram", side_effect=[None, 0]) as find_ram, \
                    patch.object(runtime.time, "sleep"):
                ready.side_effect = lambda: self.assertEqual(find_ram.call_count, 2)
                code = runtime.run(self.game, self.prefix, Path("/test/wine"), {},
                                   self.root / "launch.lock", ready=ready)
            self.assertEqual(code, 0)
            ready.assert_called_once_with()
            self.assertEqual(runtime.read_short(memory.fileno(), 0x1502C4), 0x0200)
            self.assertEqual(runtime.read_short(memory.fileno(), 0x485A6), 0x44)
            player.play.assert_called_once_with(self.music / "0x1A.MP3")
            player.close.assert_called_once()
            self.assertEqual(launch.call_args.args[0][0], "/test/wine")
            self.assertEqual(launch.call_args.kwargs["cwd"], self.project64)
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_music_player_closed_if_wine_cannot_start(self):
        player = Mock()
        with patch.object(runtime, "MusicPlayer", return_value=player), \
                patch.object(runtime.subprocess, "Popen", side_effect=OSError("Wine failed")):
            with self.assertRaisesRegex(OSError, "Wine failed"):
                runtime.run(self.game, self.prefix, Path("/test/wine"), {},
                            self.root / "launch.lock")
        player.close.assert_called_once()

    @unittest.skipUnless(platform.machine() == "x86_64", "requires Linux MAP_32BIT")
    def test_real_child_memory_detection_and_soundtrack_handshake(self):
        wine = self.root / "synthetic-wine"
        wine.write_text(
            f"#!{sys.executable}\n"
            "import ctypes, mmap, time\n"
            "libc = ctypes.CDLL(None)\n"
            "libc.mmap.restype = ctypes.c_void_p\n"
            "base = libc.mmap(None, 0x800000, 3,\n"
            "                 mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS | 0x40, -1, 0)\n"
            "if base is None or base >= 2**32: raise SystemExit(3)\n"
            "ctypes.c_uint16.from_address(base + 0x159AD4).value = 0x71F3\n"
            "ctypes.c_uint16.from_address(base + 0x702).value = 0x8FB4\n"
            "command = ctypes.c_uint16.from_address(base + 0x485A6)\n"
            "command.value = 0x1A\n"
            "deadline = time.monotonic() + 10\n"
            "while time.monotonic() < deadline:\n"
            "    if command.value == 0x44:\n"
            "        enabled = ctypes.c_uint16.from_address(base + 0x1502C4).value\n"
            "        raise SystemExit(0 if enabled == 0x0200 else 4)\n"
            "    time.sleep(0.01)\n"
            "raise SystemExit(5)\n",
            encoding="utf-8",
        )
        wine.chmod(0o755)
        player = Mock(track=None)
        player.play.side_effect = lambda track: setattr(player, "track", track)
        with patch.object(runtime, "MusicPlayer", return_value=player):
            self.assertEqual(runtime.run(
                self.game, self.prefix, wine, dict(os.environ), self.root / "launch.lock"
            ), 0)
        player.play.assert_called_once_with(self.music / "0x1A.MP3")
        player.close.assert_called_once()

    def test_gstreamer_looping_and_playback_errors(self):
        gst = Mock()
        gst.SECOND = 1
        gst.MessageType.ERROR = 1
        gst.MessageType.EOS = 2
        gst.SeekFlags.FLUSH = 1
        gst.SeekFlags.KEY_UNIT = 2
        playbin = gst.ElementFactory.make.return_value
        bus = playbin.get_bus.return_value
        bus.pop.return_value = None
        playbin.set_state.return_value = gst.StateChangeReturn.SUCCESS
        with patch.object(runtime, "gstreamer", return_value=gst):
            player = runtime.MusicPlayer()
            player.play(self.music / "0x1A.MP3")
            playbin.set_property.assert_called_with("uri", (self.music / "0x1A.MP3").as_uri())
            bus.pop_filtered.return_value = Mock(type=gst.MessageType.EOS)
            playbin.seek_simple.return_value = True
            player.poll()
            playbin.seek_simple.assert_called_once_with(
                gst.Format.TIME, gst.SeekFlags.FLUSH | gst.SeekFlags.KEY_UNIT, 0
            )
            error = Mock(type=gst.MessageType.ERROR)
            error.parse_error.return_value = (Mock(message="decoder error"), "details")
            bus.pop_filtered.return_value = error
            with self.assertRaisesRegex(RuntimeError, "decoder error"):
                player.poll()
            playbin.set_state.return_value = gst.StateChangeReturn.FAILURE
            with self.assertRaisesRegex(RuntimeError, "Cannot play"):
                player.play(self.music / "0x1A.MP3")

    def test_lock_prevents_prefix_initialization_and_launch(self):
        import fcntl
        lock_path = self.root / "launch.lock"
        prepare = Mock()
        with lock_path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "already running"):
                runtime.run(self.game, self.prefix, Path("/test/wine"), {},
                            lock_path, prepare=prepare)
        prepare.assert_not_called()

    def test_ubuntu_config_rewriter_remains_compatible(self):
        self.config.write_bytes(self.config.read_bytes().replace(
            b"C:\\Ch64 - Public\\Project64\\", b"E:\\Project64\\"
        ).replace(b"Cheat2147=1\r\n", b""))
        setup.rewrite_project64_config(self.config)
        text = self.config.read_bytes()
        self.assertIn(b"C:\\Ch64 - Public\\Project64\\Roms\\", text)
        self.assertIn(b"Cheat2147=1\r\n", text)
        self.assertTrue(list(self.config.parent.glob("*.before-ubuntu-setup-*")))


if __name__ == "__main__":
    unittest.main()

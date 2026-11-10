import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "borderless", Path(__file__).resolve().parents[1] / "borderless.py"
)
borderless = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(borderless)


class BorderlessTests(unittest.TestCase):
    def test_configure_and_enter(self):
        for env, argument in (({}, "--configure"),
                              ({"WWF_LEGENDS_WINDOWED": "1"}, "--windowed")):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "borderless.exe").touch()
                with patch.object(borderless.subprocess, "run") as run:
                    run.return_value = subprocess.CompletedProcess([], 0, "configured", "")
                    borderless.configure(root, Path("/usr/bin/wine"), env)
                    self.assertEqual(run.call_args_list[0].args[0][-1], argument)
                    self.assertEqual(run.call_args_list[1].args[0], [
                        "/usr/bin/python3", str(root / "enable-fullscreen.py"), "--disable",
                    ])
                    run.reset_mock()
                    borderless.enter(root, Path("/usr/bin/wine"), env)
                    self.assertEqual(run.call_count, 0 if argument == "--windowed" else 1)

    def test_missing_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "build-borderless.sh"):
                borderless.configure(Path(tmp), Path("/usr/bin/wine"), {})

    def test_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "borderless.exe").touch()
            with patch.object(borderless.subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess([], 1, "", "No game window")
                with self.assertRaisesRegex(RuntimeError, "No game window"):
                    borderless.enter(root, Path("/usr/bin/wine"), {})
                run.side_effect = subprocess.TimeoutExpired("wine", 30)
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    borderless.enter(root, Path("/usr/bin/wine"), {})

    def test_native_setting_failure_aborts_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "borderless.exe").touch()
            for failure, message in (
                (subprocess.CompletedProcess([], 1, "", "Cannot read config"),
                 "Cannot read config"),
                (subprocess.TimeoutExpired("python3", 30), "timed out"),
            ):
                with self.subTest(message=message):
                    with patch.object(borderless.subprocess, "run") as run:
                        run.side_effect = [
                            subprocess.CompletedProcess([], 0, "configured", ""),
                            failure,
                        ]
                        with self.assertRaisesRegex(RuntimeError, message):
                            borderless.configure(root, Path("/usr/bin/wine"), {})

    def test_native_setting_disable_preserves_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "enable-fullscreen.py"
            script.write_bytes(
                (Path(__file__).resolve().parents[1] / script.name).read_bytes()
            )
            config = root / "Project64" / "Config" / "Project64.cfg"
            config.parent.mkdir(parents=True)
            original = b"[default]\r\nAuto Full Screen=1\r\n[Settings]\r\nOther=1\r\n"
            config.write_bytes(original)
            for attempt in range(2):
                result = subprocess.run(
                    ["/usr/bin/python3", str(script), "--disable"],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(config.read_bytes(), original.replace(
                    b"Auto Full Screen=1", b"Auto Full Screen=0",
                ))
                backups = list(config.parent.glob("*.before-fullscreen-*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), original)
                if attempt:
                    self.assertIn("already disabled", result.stdout)


if __name__ == "__main__":
    unittest.main()

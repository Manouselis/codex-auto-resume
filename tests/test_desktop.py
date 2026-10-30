import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from auto_resume.desktop import ensure_background
from auto_resume.power import AwakeLease
from auto_resume.store import Store


class DesktopTests(unittest.TestCase):
    def test_existing_background_service_is_reused(self):
        with patch("auto_resume.desktop.sys.platform", "linux"), patch("auto_resume.desktop.shutil.which", return_value="/usr/bin/systemctl"), patch("auto_resume.desktop.subprocess.run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(ensure_background(Path("state.sqlite3")))
            self.assertEqual(run.call_count, 1)

    def test_installed_app_starts_service_without_a_window_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / "app.pyz"
            app.write_bytes(b"fixture")
            with patch("auto_resume.desktop.sys.platform", "linux"), patch("auto_resume.desktop.sys.argv", [str(app)]), patch("auto_resume.desktop.shutil.which", return_value="/usr/bin/systemctl"), patch("auto_resume.desktop.subprocess.run", side_effect=[SimpleNamespace(returncode=3), SimpleNamespace(returncode=0)]) as run:
                self.assertTrue(ensure_background(Path(folder) / "state.sqlite3"))
                self.assertEqual(run.call_args.args[0], ["systemctl", "--user", "start", "codex-auto-resume.service"])

    def test_no_user_bus_falls_back_without_claiming_background_operation(self):
        with patch("auto_resume.desktop.sys.platform", "linux"), patch("auto_resume.desktop.shutil.which", return_value="/usr/bin/systemctl"), patch("auto_resume.desktop.subprocess.run", side_effect=OSError("No user bus")):
            self.assertFalse(ensure_background(Path("state.sqlite3")))

    def test_legacy_global_index_migrates_to_one_reservation_per_chat(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.sqlite3"
            store = Store(path)
            store.db.execute("DROP INDEX one_execution_per_thread")
            store.db.execute("CREATE UNIQUE INDEX one_execution ON submissions((1)) WHERE status IN ('reserved','running','uncertain')")
            store.close()
            store = Store(path)
            try:
                store.db.execute("INSERT INTO submissions VALUES('a','first','running','turn-a',1)")
                store.db.execute("INSERT INTO submissions VALUES('b','second','uncertain',NULL,1)")
                import sqlite3
                with self.assertRaises(sqlite3.IntegrityError):
                    store.db.execute("INSERT INTO submissions VALUES('c','first','reserved',NULL,1)")
                self.assertEqual(store.db.execute("SELECT count(*) FROM submissions").fetchone()[0], 2)
            finally:
                store.close()


class PowerTests(unittest.TestCase):
    def test_armed_lease_inhibits_sleep_and_releases_when_unarmed(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.BytesIO(b"ready\n")
        process.stdin = io.BytesIO()
        with patch("auto_resume.power.sys.platform", "linux"), patch("auto_resume.power.shutil.which", return_value="/usr/bin/systemd-inhibit"), patch("auto_resume.power.subprocess.Popen", return_value=process) as start, patch("auto_resume.power.select.select", return_value=([process.stdout], [], [])):
            lease = AwakeLease()
            lease.update(True)
            self.assertIn("sleep prevented", lease.status)
            command = start.call_args.args[0]
            self.assertIn("--what=sleep", command)
            self.assertNotIn("--no-ask-password", command)  # Unsupported by Ubuntu 22.04's systemd.
            self.assertFalse(any("idle" in arg or "shutdown" in arg for arg in command))
            lease.update(True)
            self.assertEqual(start.call_count, 1)
            lease.update(False)
            self.assertTrue(process.stdin.closed)
            self.assertIsNone(lease.process)

    def test_missing_inhibitor_reports_the_limitation(self):
        with patch("auto_resume.power.sys.platform", "linux"), patch("auto_resume.power.shutil.which", return_value=None):
            lease = AwakeLease()
            lease.update(True)
            self.assertIn("unavailable", lease.status)
            self.assertIsNone(lease.process)

    def test_inactive_or_non_linux_controller_never_takes_an_inhibitor(self):
        with patch("auto_resume.power.sys.platform", "win32"), patch("auto_resume.power.subprocess.Popen") as start:
            AwakeLease().update(True)
            AwakeLease(enabled=False).update(True)
            self.assertFalse(start.called)

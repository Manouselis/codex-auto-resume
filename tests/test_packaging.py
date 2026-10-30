import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from auto_resume.store import Store

ROOT = Path(__file__).resolve().parent.parent


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prefix = Path(self.tmp.name) / "private prefix"

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, *args, check=True):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *map(str, args)],
                              capture_output=True, text=True, check=check)

    def test_isolated_install_update_launch_and_uninstall_preserves_unrelated(self):
        sentinel = self.prefix / "unrelated.txt"
        sentinel.parent.mkdir()
        sentinel.write_text("preserve me")
        self.run_script("install.py", "--prefix", self.prefix)
        app = self.prefix / "share/codex-auto-resume/codex-auto-resume.pyz"
        metadata = json.loads((app.parent / "installation.json").read_text())
        expected = ["share/codex-auto-resume/codex-auto-resume.pyz",
                    "bin/codex-auto-resume.cmd" if os.name == "nt" else "bin/codex-auto-resume",
                    "share/codex-auto-resume/icon.png"]
        if os.name != "nt":
            expected.append("share/applications/codex-auto-resume.desktop")
        if sys.platform.startswith("linux"):
            expected.append("share/systemd/user/codex-auto-resume.service")
        self.assertEqual(metadata["files"], expected)
        self.assertTrue((app.parent / "icon.png").read_bytes().startswith(b'\x89PNG'))
        result = subprocess.run([sys.executable, str(app), "demo"], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["automatic_continuations"], 1)
        self.run_script("install.py", "--prefix", self.prefix)
        self.run_script("uninstall.py", "--prefix", self.prefix)
        self.assertEqual(sentinel.read_text(), "preserve me")
        self.assertFalse(app.exists())

    def test_refuse_overwrite_without_ownership_marker(self):
        path = self.prefix / "share/codex-auto-resume/codex-auto-resume.pyz"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"unrelated file")
        result = self.run_script("install.py", "--prefix", self.prefix, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_bytes(), b"unrelated file")

    def test_uninstaller_rejects_path_escape_manifest(self):
        self.run_script("install.py", "--prefix", self.prefix)
        marker = self.prefix / "share/codex-auto-resume/installation.json"
        data = json.loads(marker.read_text())
        data["files"].append("../../do-not-delete")
        marker.write_text(json.dumps(data))
        result = self.run_script("uninstall.py", "--prefix", self.prefix, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.prefix / "share/codex-auto-resume/codex-auto-resume.pyz").exists())

    def test_reproducible_zipapp(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from build import build_app
            first, second = build_app(ROOT), build_app(ROOT)
            self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())
            self.assertLess(len(first), 100000)
        finally:
            sys.path.pop(0)

    def test_source_archive_excludes_credentials_and_runtime_state(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from build import source_files
            root = Path(self.tmp.name) / "source"
            (root / "auto_resume").mkdir(parents=True)
            for name in ("normal.py", "auth.json", "config.toml", "private.sqlite3", ".env", "core.dump"):
                (root / "auto_resume" / name).write_text("invented fixture")
            names = {p.name for p in source_files(root)}
            self.assertEqual(names, {"normal.py"})
        finally:
            sys.path.pop(0)

    def test_refuse_unrelated_state_database_without_modification(self):
        path = Path(self.tmp.name) / "other.sqlite3"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE unrelated(value TEXT)")
        db.commit()
        db.close()
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            Store(path)
        self.assertEqual(path.read_bytes(), before)

    @unittest.skipIf(os.name == "nt", "Symlink creation depends on Windows privileges")
    def test_refuse_symlink_state_destination(self):
        path, link = Path(self.tmp.name) / "actual.sqlite3", Path(self.tmp.name) / "link.sqlite3"
        path.write_text("preserve this file")
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            Store(link)
        self.assertEqual(path.read_text(), "preserve this file")

    @unittest.skipIf(os.name == "nt", "POSIX desktop installer test")
    def test_installer_refuses_parent_symlink_escape(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.prefix / "share").mkdir(parents=True)
        (self.prefix / "share/applications").symlink_to(outside, target_is_directory=True)
        result = self.run_script("install.py", "--prefix", self.prefix, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

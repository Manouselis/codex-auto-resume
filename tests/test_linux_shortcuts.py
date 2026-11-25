import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_resume import linux_shortcuts as shortcuts


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux desktop entries")
class LinuxShortcutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.prefix = Path(temporary.name) / "prefix with spaces"
        self.data_home = self.prefix / "share"
        self.entry = self.data_home / "applications" / shortcuts.DESKTOP_NAME
        self.entry.parent.mkdir(parents=True)
        self.original = shortcuts.source_entry("/usr/bin/python3", self.prefix)
        self.entry.write_text(self.original, encoding="utf-8")

    def test_migration_reveals_system_launcher_and_keeps_exact_backup(self):
        system = self.prefix / "system"
        system.write_text("package launcher")
        system.chmod(0o755)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.data_home)}), \
                patch.object(shortcuts, "SYSTEM_ENTRY", system), \
                patch.object(shortcuts, "SYSTEM_LAUNCHER", system):
            backup = shortcuts.migrate_shortcut()
            self.assertFalse(self.entry.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), self.original)
            self.assertEqual(backup.stat().st_uid, os.getuid())
            self.assertIsNone(shortcuts.migrate_shortcut())
        self.assertEqual(list(self.entry.parent.iterdir()), [backup])

    def test_custom_entry_is_preserved(self):
        custom = self.original.replace("Terminal=false", "Terminal=true")
        self.entry.write_text(custom, encoding="utf-8")
        self.assertIsNone(shortcuts._archive_override(self.entry, self.data_home))
        self.assertEqual(self.entry.read_text(encoding="utf-8"), custom)

    def test_legacy_refresh_icon_is_recognized_but_symlink_is_not(self):
        legacy = self.original.replace(str(self.data_home / "codex-auto-resume/icon.png"), "view-refresh")
        target = self.prefix / "other.desktop"
        target.write_text(legacy, encoding="utf-8")
        self.entry.unlink()
        self.entry.symlink_to(target)
        self.assertIsNone(shortcuts._archive_override(self.entry, self.data_home))
        self.assertTrue(self.entry.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), legacy)
        self.entry.unlink()
        self.entry.write_text(legacy, encoding="utf-8")
        self.assertEqual(shortcuts._archive_override(self.entry, self.data_home).read_text(encoding="utf-8"), legacy)

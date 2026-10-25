import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_resume.native_schedule import schedule_status


class NativeScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict("os.environ", {"CODEX_HOME": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = Path(self.tmp.name) / "automations/native-test/automation.toml"
        self.path.parent.mkdir(parents=True)

    def write(self, **changes):
        fields = {"id": "native-test", "kind": "heartbeat", "status": "ACTIVE", "target_thread_id": "test-thread"}
        fields.update(changes)
        self.path.write_text("\n".join(k + " = " + json.dumps(v) for k, v in fields.items()))

    def test_real_metadata_fields_distinguish_active_paused_and_missing(self):
        self.assertEqual(schedule_status("native-test", "test-thread")[0], "MISSING")
        self.write()
        self.assertEqual(schedule_status("native-test", "test-thread")[0], "ACTIVE")
        self.write(status="PAUSED")
        self.assertEqual(schedule_status("native-test", "test-thread")[0], "PAUSED")

    def test_wrong_conversation_or_kind_cannot_authorize_native_work(self):
        for changes in ({"target_thread_id": "other"}, {"kind": "cron"}, {"id": "other"}):
            self.write(**changes)
            self.assertEqual(schedule_status("native-test", "test-thread")[0], "INVALID")

    def test_invalid_or_duplicate_metadata_is_refused(self):
        self.write()
        self.path.write_text(self.path.read_text() + '\nstatus = "PAUSED"')
        self.assertEqual(schedule_status("native-test", "test-thread")[0], "INVALID")
        self.assertEqual(schedule_status("../other", "test-thread")[0], "INVALID")

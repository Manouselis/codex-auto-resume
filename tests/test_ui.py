import os
import tempfile
import time
import unittest
from pathlib import Path

from auto_resume.adapters import SimulationAdapter
from auto_resume.engine import Engine
from auto_resume.store import Store


@unittest.skipUnless(os.environ.get("AUTO_RESUME_GUI_TEST") == "1", "Needs an explicit GUI test session")
class UiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "ui.sqlite3")
        self.adapter = SimulationAdapter()
        self.engine = Engine(self.store, self.adapter)
        self.root = tk.Tk()
        self.window = ControlWindow(self.root, self.engine, simulation=True)
        self.root.update()

    def tearDown(self):
        import gc
        self.window.close()
        self.store.close()
        self.tmp.cleanup()
        del self.window, self.root
        # Tk interpreters and callback cycles must be collected on the GUI thread.
        gc.collect()

    def pump(self):
        deadline = time.monotonic() + 3
        while self.window.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()

    def test_one_click_toggle_and_close_disables(self):
        self.assertTrue(self.store.enabled)
        self.assertIn("selected", self.window.toggle.state())
        self.window.toggle.invoke()
        self.assertFalse(self.store.enabled)
        self.window.toggle.invoke()
        self.assertTrue(self.store.enabled)
        self.window.close()
        self.assertFalse(self.store.enabled)

    def test_keyboard_entry_arm_and_disarm(self):
        self.window.arm()
        self.pump()
        self.assertTrue(self.store.get("demo-task")["eligible"])
        # Pump the scheduled refresh instead of creating a second timer chain.
        deadline = time.monotonic() + 1
        while not self.window.tasks.exists("demo-task") and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.window.tasks.selection_set("demo-task")
        self.window.disarm()
        self.assertFalse(self.store.get("demo-task")["eligible"])

    def test_usage_check_and_themes(self):
        self.window.check_usage()
        self.pump()
        self.assertIn("5h: 100% used", self.window.usage_text.get())
        for dark in (False, True):
            self.window.dark.set(dark)
            self.window.theme()
            self.root.update()
        self.assertFalse(self.adapter.requests)

    def test_background_controller_can_keep_control_window(self):
        from auto_resume.ui import ControlWindow
        import tkinter as tk
        second_root = tk.Toplevel(self.root)
        second = ControlWindow(second_root, self.engine, simulation=True)
        self.root.update()
        try:
            self.assertFalse(second.scheduler.thread.is_alive())
            self.assertTrue(self.window.scheduler.thread.is_alive())
        finally:
            second.close()

    def test_closing_service_control_window_keeps_armed_work_enabled(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        self.store.set_enabled(True, time.time())
        self.engine.register("demo-task")
        second = ControlWindow(tk.Toplevel(self.root), self.engine, simulation=True)
        try:
            self.assertFalse(second.owns_controller)
            second.close()
            self.assertTrue(self.store.enabled)
            self.assertTrue(self.store.get("demo-task")["eligible"])
            self.assertTrue(self.window.scheduler.thread.is_alive())
        finally:
            second.close()

    def test_render_own_window(self):
        output = os.environ.get("AUTO_RESUME_SCREENSHOTS")
        if not output:
            self.skipTest("Screenshot capture not requested")
        from PIL import ImageGrab
        self.root.lift()
        for dark, name in ((True, "ui-dark.png"), (False, "ui-light.png")):
            self.window.dark.set(dark)
            self.window.theme()
            self.root.update()
            time.sleep(0.2)
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            box = (x, y, x + self.root.winfo_width(), y + self.root.winfo_height())
            ImageGrab.grab(bbox=box).save(Path(output) / name)

    def test_controls_fit_at_minimum_size(self):
        self.root.geometry("720x720")
        self.root.update()
        bottom = self.root.winfo_rooty() + self.root.winfo_height()
        self.assertTrue(self.window.footer.winfo_ismapped())
        def check(widget):
            for child in widget.winfo_children():
                if child.winfo_ismapped():
                    self.assertLessEqual(child.winfo_rooty() + child.winfo_height(), bottom)
                    check(child)
        check(self.root)

    def test_arm_and_disarm_are_adjacent_on_the_same_row(self):
        arm, disarm = self.window.arm_button, self.window.disarm_button
        self.assertIs(arm.master, disarm.master)
        self.assertEqual(arm.winfo_rooty(), disarm.winfo_rooty())
        self.assertGreater(disarm.winfo_rootx(), arm.winfo_rootx())
        self.assertLessEqual(disarm.winfo_rootx() - (arm.winfo_rootx() + arm.winfo_width()), 12)

    def test_disarm_also_uses_the_chosen_conversation_without_table_selection(self):
        self.window.arm()
        self.pump()
        self.window.tasks.selection_remove(*self.window.tasks.selection())
        self.window.disarm_button.invoke()
        self.assertFalse(self.store.get("demo-task")["eligible"])

    def test_real_control_panel_fits_and_renders(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        from auto_resume.live import LiveAdapter
        from test_live import Backend
        store = Store(Path(self.tmp.name) / "real-panel.sqlite3")
        window_root = tk.Toplevel(self.root)
        window = ControlWindow(window_root, Engine(store, LiveAdapter(Backend(self.tmp.name))), simulation=False)
        try:
            window_root.geometry("720x720")
            self.root.update()
            bottom = window_root.winfo_rooty() + window_root.winfo_height()
            for child in window_root.winfo_children()[0].winfo_children():
                if child.winfo_ismapped():
                    self.assertLessEqual(child.winfo_rooty() + child.winfo_height(), bottom)
            output = os.environ.get("AUTO_RESUME_SCREENSHOTS")
            if output:
                from PIL import ImageGrab
                window_root.geometry("760x760")
                window_root.lift()
                self.root.update()
                time.sleep(0.2)
                x, y = window_root.winfo_rootx(), window_root.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + window_root.winfo_width(), y + window_root.winfo_height())).save(
                    Path(output) / "ui-live.png")
        finally:
            window.close()
            store.close()

    def test_arm_external_open_turn_through_real_control_panel(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        from auto_resume.live import LiveAdapter
        from test_live import Backend
        backend = Backend(self.tmp.name)
        backend.latest.update(status="interrupted", completedAt=None, error=None)
        store = Store(Path(self.tmp.name) / "external-panel.sqlite3")
        store.set_enabled(True, time.time())
        window = ControlWindow(tk.Toplevel(self.root), Engine(store, LiveAdapter(backend)), simulation=False)
        try:
            window.thread_id.insert(0, "live-test")
            window.arm()
            deadline = time.monotonic() + 3
            while window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.root.update()
            self.assertTrue(store.get("live-test")["eligible"])
            self.assertIn("armed", window.notice.get())
            self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in backend.calls))
        finally:
            window.close()
            store.close()

    def test_context_checkpoint_recovery_can_be_explicitly_armed_in_ui(self):
        import json
        import tkinter as tk
        from auto_resume.checkpoints import CHECKPOINT_MARKER
        from auto_resume.ui import ControlWindow
        from auto_resume.live import LiveAdapter
        from test_live import Backend
        backend = Backend(self.tmp.name)
        backend.latest.update(status="completed", completedAt=int(time.time()), error=None,
                              items=[{"type": "agentMessage", "phase": "final_answer",
                                      "text": "Saved next action.\n" + CHECKPOINT_MARKER}])
        store = Store(Path(self.tmp.name) / "context-panel.sqlite3")
        store.set_enabled(True, time.time())
        window = ControlWindow(tk.Toplevel(self.root), Engine(store, LiveAdapter(backend)), simulation=False)
        try:
            window.thread_id.insert(0, "live-test")
            window.recover_context.set(True)
            window.arm()
            deadline = time.monotonic() + 3
            while window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.root.update()
            self.assertTrue(json.loads(store.get("live-test")["context"])["recover_context"])
            self.assertIn("context-budget recovery", window.notice.get())
        finally:
            window.close()
            store.close()

    def prepare_saved_native_task(self):
        self.store.set_enabled(True, time.time())
        self.engine.register("demo-task", recover_context=True, native_heartbeat="saved-native")
        self.window.refresh()
        self.window.thread_id.delete(0, "end")
        self.window.recover_context.set(False)

    def test_clicking_saved_row_loads_id_and_mode_then_arm_succeeds(self):
        import json
        self.prepare_saved_native_task()
        self.window.tasks.selection_set("demo-task")
        self.root.update()
        self.assertEqual(self.window.thread_id.get(), "demo-task")
        self.assertTrue(self.window.recover_context.get())
        self.window.arm()
        self.pump()
        context = json.loads(self.store.get("demo-task")["context"])
        self.assertEqual(context["native_heartbeat"], "saved-native")
        self.assertIn("Native recovery armed", self.window.notice.get())
        self.assertFalse(self.adapter.requests)

    def test_chooser_restores_existing_native_settings_before_arm(self):
        import tkinter as tk
        import json
        self.prepare_saved_native_task()
        self.window.show_picker([{"id": "demo-task", "name": "Saved conversation"}])
        picker = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        listing = next(w for w in picker.winfo_children() if isinstance(w, tk.Listbox))
        listing.selection_set(0)
        next(w for w in picker.winfo_children() if w.winfo_class() == "TButton").invoke()
        self.assertEqual(self.window.thread_id.get(), "demo-task")
        self.assertTrue(self.window.recover_context.get())
        self.window.arm()
        self.pump()
        self.assertEqual(json.loads(self.store.get("demo-task")["context"])["native_heartbeat"], "saved-native")
        self.assertFalse(self.adapter.requests)

    def test_arm_uses_selected_row_when_entry_is_empty(self):
        self.prepare_saved_native_task()
        self.window.tasks.selection_set("demo-task")
        self.root.update()
        self.window.thread_id.delete(0, "end")
        self.window.arm()
        self.pump()
        self.assertEqual(self.window.thread_id.get(), "demo-task")
        self.assertTrue(self.store.get("demo-task")["eligible"])
        self.assertFalse(self.adapter.requests)

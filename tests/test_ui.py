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
        self.assertFalse(self.store.enabled)
        self.window.toggle.invoke()
        self.assertTrue(self.store.enabled)
        self.window.close()
        self.assertFalse(self.store.enabled)

    def test_keyboard_entry_arm_and_disarm(self):
        self.window.toggle.invoke()
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
        def check(widget):
            for child in widget.winfo_children():
                if child.winfo_ismapped():
                    self.assertLessEqual(child.winfo_rooty() + child.winfo_height(), bottom)
                    check(child)
        check(self.root)

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

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
        from unittest.mock import patch
        launcher = patch("auto_resume.ui.open_conversation")
        self.open_desktop = launcher.start()
        self.addCleanup(launcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "ui.sqlite3")
        self.adapter = SimulationAdapter()
        self.engine = Engine(self.store, self.adapter)
        self.root = tk.Tk()
        self.window = ControlWindow(self.root, self.engine, simulation=True)
        self.root.update()
        self.pump()

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

    def test_opening_window_enables_monitoring_without_rearming_old_tasks(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        self.engine.register("demo-task")
        self.store.set_enabled(False, time.time())
        window = ControlWindow(tk.Toplevel(self.root), self.engine, simulation=True)
        try:
            self.assertTrue(self.store.enabled)
            self.assertIn("selected", window.toggle.state())
            self.assertFalse(self.store.get("demo-task")["eligible"])
            self.assertIsNotNone(window.icon)
        finally:
            window.close()

    def test_single_selection_arms_immediately_then_disarm_removes_the_row(self):
        import tkinter as tk
        self.window.add_button.invoke()
        picker = self.window.picker
        self.root.update()
        self.assertIsNotNone(picker)
        listing = next(w for w in picker.winfo_children() if isinstance(w, tk.Listbox))
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
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
        self.assertFalse(self.window.tasks.exists("demo-task"))
        self.window.refresh()
        self.assertFalse(self.window.tasks.get_children())
        self.assertTrue(self.store.history())

    def test_add_conversation_arms_an_idle_desktop_chat_without_sending(self):
        import json
        import tkinter as tk
        from unittest.mock import patch
        from auto_resume.live import LiveAdapter
        from auto_resume.ui import ControlWindow
        from test_live import Backend

        backend = Backend(self.tmp.name)
        backend.latest.update(status="completed", error=None)
        adapter = LiveAdapter(backend)
        store = Store(Path(self.tmp.name) / "arm-ahead.sqlite3")
        window = ControlWindow(tk.Toplevel(self.root), Engine(store, adapter), background=True)
        try:
            with patch.object(adapter, "recent_threads", return_value=[{"id": "live-test", "name": "Idle chat"}]):
                window.add_button.invoke()
                deadline = time.monotonic() + 3
                while window.picker is None and time.monotonic() < deadline:
                    self.root.update()
                    time.sleep(0.01)
                self.assertIsNotNone(window.picker)
                listing = next(w for w in window.picker.winfo_children() if isinstance(w, tk.Listbox))
                listing.selection_set(0)
                listing.event_generate("<<ListboxSelect>>")
                while not window.tasks.exists("live-test") and time.monotonic() < deadline:
                    self.root.update()
                    time.sleep(0.01)
            self.assertEqual(window.tasks.item("live-test", "values")[0], "Armed ahead")
            task = store.get("live-test")
            self.assertTrue(task["eligible"])
            self.assertTrue(json.loads(task["context"])["wait_for_limit"])
            self.assertFalse(any(method in ("thread/queue/add", "turn/start") for method, _ in backend.calls))
        finally:
            window.close()
            store.close()

    def test_adding_a_second_chat_keeps_the_first_armed(self):
        import tkinter as tk
        from dataclasses import replace

        idle = replace(self.adapter.observations["demo-task"], turn_status="completed",
                       error_code=None, incomplete=False)
        self.adapter.observations["demo-task"] = idle
        self.adapter.observations["second-chat"] = replace(idle, thread_id="second-chat")
        for index, thread_id in enumerate(("demo-task", "second-chat")):
            self.window.add_button.invoke()
            self.root.update()
            listing = next(w for w in self.window.picker.winfo_children() if isinstance(w, tk.Listbox))
            listing.selection_set(index)
            listing.event_generate("<<ListboxSelect>>")
            self.pump()
            task = self.store.get(thread_id)
            self.assertIsNotNone(task, self.window.notice.get())
            self.assertTrue(task["eligible"])
        self.assertEqual({task["thread_id"] for task in self.store.tasks() if task["eligible"]},
                         {"demo-task", "second-chat"})
        self.assertFalse(self.adapter.requests)

    def test_recovery_message_editor_saves_and_clears_selected_chat(self):
        import tkinter as tk

        self.engine.register("demo-task")
        self.window.refresh()
        self.window.tasks.selection_set("demo-task")
        self.window.show_reason()
        for value in ("Finish the report.\nRun checks.", ""):
            self.window.message_button.invoke()
            dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
            body = dialog.winfo_children()[0]
            editor = next(child for child in body.winfo_children() if isinstance(child, tk.Text))
            editor.delete("1.0", "end")
            editor.insert("1.0", value)
            buttons = body.winfo_children()[-1]
            save = next(button for button in buttons.winfo_children() if button.cget("text") == "Save")
            save.invoke()
            self.assertEqual(self.store.recovery_message("demo-task"), value)
            self.assertFalse(dialog.winfo_exists())
        self.assertFalse(self.adapter.requests)

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

    def test_add_and_disarm_are_adjacent_on_the_same_row(self):
        arm, disarm = self.window.add_button, self.window.disarm_button
        self.assertIs(arm.master, disarm.master)
        self.assertEqual(arm.winfo_rooty(), disarm.winfo_rooty())
        self.assertGreater(disarm.winfo_rootx(), arm.winfo_rootx())
        self.assertLessEqual(disarm.winfo_rootx() - (arm.winfo_rootx() + arm.winfo_width()), 12)

    def test_installed_app_shows_version_and_prompts_automatically(self):
        import io
        import tkinter as tk
        from unittest.mock import patch
        from auto_resume import __version__, update
        from auto_resume.ui import ControlWindow
        from test_update import atom_feed

        def wait_until(condition):
            deadline = time.monotonic() + 5
            while not condition() and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.assertTrue(condition())

        name = "codex-auto-resume-1.0.0-linux-x64.deb"
        assets = f"{update.RELEASE_PAGE}/download/v1.0.0"
        release = update.Release("1.0.0", name, f"{assets}/{name}", "a" * 64, None)
        installer = Path(self.tmp.name) / release.name

        def read(request, timeout):
            return io.BytesIO({
                f"{update.RELEASE_PAGE}.atom": atom_feed("1.0.0"),
                f"{assets}/SHA256SUMS": f"{release.digest}  {name}\n".encode(),
            }[request.full_url])

        with (patch.object(update, "installed_target", return_value="linux-x64.deb"),
              patch.object(update, "_cache_dir", return_value=Path(self.tmp.name)),
              patch.object(update, "_open_url", side_effect=read),
              patch.object(update, "check_for_update", wraps=update.check_for_update) as check,
              patch("tkinter.messagebox.askyesno", side_effect=[False, True]) as confirm,
              patch.object(update, "download_update", return_value=installer) as download,
              patch.object(update, "install_update", return_value=True) as install):
            window = ControlWindow(tk.Toplevel(self.root), self.engine, background=True)
            try:
                self.assertIn(f"Version {__version__}", [child.cget("text") for child in window.footer.winfo_children()])
                wait_until(lambda: confirm.call_count == 1)
                self.assertEqual(window.update_button.cget("text"), "Update to 1.0.0")
                download.assert_not_called()
                window.check_update(automatic=True)
                wait_until(lambda: check.call_count == 2 and not window.update_button.instate(["disabled"]))
                confirm.assert_called_once()
                window.update_button.invoke()
                wait_until(lambda: window.closed)
                download.assert_called_once_with(release)
                install.assert_called_once_with(installer, release)
                self.assertTrue(window.relaunch_after_update)
            finally:
                window.close(for_update=True)

    def test_disarm_also_uses_the_chosen_conversation_without_table_selection(self):
        self.window.arm()
        self.pump()
        self.window.tasks.selection_remove(*self.window.tasks.selection())
        self.window.disarm()
        self.assertFalse(self.store.get("demo-task")["eligible"])

    def test_real_control_panel_fits_and_renders(self):
        import tkinter as tk
        from auto_resume.ui import ControlWindow
        from auto_resume.live import LiveAdapter
        from test_live import Backend
        store = Store(Path(self.tmp.name) / "real-panel.sqlite3")
        window_root = tk.Toplevel(self.root)
        window = ControlWindow(window_root, Engine(store, LiveAdapter(Backend(self.tmp.name))), simulation=False, background=True)
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
        backend.queue_auto_start = True
        backend.latest.update(status="interrupted", completedAt=None, error=None)
        store = Store(Path(self.tmp.name) / "external-panel.sqlite3")
        store.set_enabled(True, time.time())
        window = ControlWindow(tk.Toplevel(self.root), Engine(store, LiveAdapter(backend)), simulation=False, background=True)
        try:
            window.selected_thread_id.set("live-test")
            window.arm()
            deadline = time.monotonic() + 3
            while window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.root.update()
            self.assertTrue(store.get("live-test")["eligible"])
            self.assertIn("armed", window.notice.get().lower())
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
        backend.queue_auto_start = True
        backend.latest.update(status="completed", completedAt=int(time.time()), error=None,
                              items=[{"type": "agentMessage", "phase": "final_answer",
                                      "text": "Saved next action.\n" + CHECKPOINT_MARKER}])
        store = Store(Path(self.tmp.name) / "context-panel.sqlite3")
        store.set_enabled(True, time.time())
        window = ControlWindow(tk.Toplevel(self.root), Engine(store, LiveAdapter(backend)), simulation=False, background=True)
        try:
            window.selected_thread_id.set("live-test")
            window.recover_context.set(True)
            window.arm()
            deadline = time.monotonic() + 3
            while window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.root.update()
            self.assertTrue(json.loads(store.get("live-test")["context"])["recover_context"])
            self.assertTrue(store.get("live-test")["eligible"])
        finally:
            window.close()
            store.close()

    def prepare_saved_native_task(self):
        self.store.set_enabled(True, time.time())
        self.engine.register("demo-task", recover_context=True, native_heartbeat="saved-native")
        self.window.refresh()
        self.window.selected_thread_id.set("")
        self.window.recover_context.set(False)

    def test_clicking_saved_row_preserves_native_settings(self):
        import json
        self.prepare_saved_native_task()
        self.window.tasks.selection_set("demo-task")
        self.root.update()
        self.assertEqual(self.window.selected_thread_id.get(), "demo-task")
        self.assertTrue(self.window.recover_context.get())
        self.window.arm()
        self.pump()
        context = json.loads(self.store.get("demo-task")["context"])
        self.assertEqual(context["native_heartbeat"], "saved-native")
        self.assertIn("armed", self.window.notice.get().lower())
        self.assertFalse(self.adapter.requests)

    def test_picker_immediately_arms_and_restores_existing_native_settings(self):
        import tkinter as tk
        import json
        self.prepare_saved_native_task()
        self.engine.disarm("demo-task")
        self.window.show_picker([{"id": "demo-task", "name": "Saved conversation"}])
        picker = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        self.root.update()
        listing = next(w for w in picker.winfo_children() if isinstance(w, tk.Listbox))
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        self.root.update()
        self.assertEqual(self.window.selected_thread_id.get(), "demo-task")
        self.assertTrue(self.window.recover_context.get())
        self.pump()
        self.assertTrue(self.store.get("demo-task")["eligible"])
        self.assertEqual(json.loads(self.store.get("demo-task")["context"])["native_heartbeat"], "saved-native")
        self.assertFalse(self.adapter.requests)

    def test_ineligible_conversations_are_hidden_without_erasing_their_state(self):
        self.engine.register("demo-task")
        self.window.refresh()
        self.assertTrue(self.window.tasks.exists("demo-task"))
        self.store.set_enabled(False, time.time())
        self.window.refresh()
        self.assertFalse(self.window.tasks.get_children())
        self.assertIsNotNone(self.store.get("demo-task"))
        self.root.update()
        self.assertTrue(self.window.empty_state.winfo_ismapped())

    def test_allowance_timer_repeats_every_minute_without_a_refresh_button(self):
        from unittest.mock import patch
        self.pump()
        if self.window.initial_check_id:
            self.root.after_cancel(self.window.initial_check_id)
            self.window.initial_check_id = None
        with patch.object(self.window, "check_usage") as check, patch.object(self.root, "after", wraps=self.root.after) as after:
            self.window.auto_refresh_allowance()
            check.assert_called_once_with(quiet=True)
            self.assertEqual(after.call_args.args[0], 60000)
            self.root.after_cancel(self.window.allowance_timer_id)
            self.window.auto_refresh_allowance()
            self.assertEqual(check.call_count, 2)
            self.assertEqual(after.call_args.args[0], 60000)
        self.assertFalse(hasattr(self.window, "check"))

    def test_selection_is_not_lost_when_an_allowance_check_is_in_progress(self):
        import threading
        import tkinter as tk
        gate = threading.Event()
        def allowance():
            gate.wait(3)
            return {"summary": "5h: 5% used", "remaining": [95, 80], "checked": "Last checked now"}
        self.window.work(allowance, self.window.show_usage, quiet=True)
        self.window.add_button.invoke()
        self.root.update()
        listing = next(w for w in self.window.picker.winfo_children() if isinstance(w, tk.Listbox))
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        self.assertTrue(self.window.pending_actions)
        gate.set()
        self.pump()
        self.assertTrue(self.store.get("demo-task")["eligible"])
        self.assertFalse(self.adapter.requests)

    def test_arm_uses_selected_row_when_no_id_is_selected(self):
        self.prepare_saved_native_task()
        self.window.tasks.selection_set("demo-task")
        self.root.update()
        self.window.selected_thread_id.set("")
        self.window.arm()
        self.pump()
        self.assertEqual(self.window.selected_thread_id.get(), "demo-task")
        self.assertTrue(self.store.get("demo-task")["eligible"])
        self.assertFalse(self.adapter.requests)

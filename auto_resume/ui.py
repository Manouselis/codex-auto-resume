"""Accessible, native Tk control window. GUI never runs network I/O on its event thread."""
import queue
import json
import threading
import base64
import subprocess
import time
from collections import deque
from importlib import resources
from datetime import datetime
from tkinter.font import nametofont

from .engine import Scheduler
from . import __version__
from .domain import DEFAULT_RECOVERY_MESSAGE, UnsafeError
from .desktop import open_conversation
from . import update


class ControlWindow:
    def __init__(self, root, engine, simulation=False, *, background=False):
        import tkinter as tk
        from tkinter import ttk

        self.root, self.engine, self.simulation = root, engine, simulation
        self.results = queue.Queue()
        self.busy = False
        self.closed = False
        self.refresh_id = None
        self.worker = None
        self.initial_check_id = None
        self.allowance_timer_id = None
        self.update_timer_id = None
        self.update_results = queue.Queue()
        self.offered_update = None
        self.installing_update = False
        self.relaunch_after_update = False
        self.pending_actions = deque()
        self.picker = None
        self.pending_selection = None
        self.empty_visible = None
        self.scheduler = Scheduler(engine)
        self.owns_controller = False
        # Opening the app is the user's explicit request to enable monitoring.
        # Previously disarmed conversations still require their own Arm action.
        if not engine.store.enabled:
            engine.store.set_enabled(True, engine.clock())

        root.title("Codex Auto-Resume" + (" · Demo" if simulation else ""))
        root.geometry("920x800")
        root.minsize(760, 760)
        try:
            self.icon = tk.PhotoImage(data=base64.b64encode(resources.files("auto_resume").joinpath("assets/icon.png").read_bytes()))
            root.iconphoto(True, self.icon)
        except (OSError, tk.TclError):
            self.icon = None
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.font_family = nametofont("TkDefaultFont", root=root).actual("family")
        self.dark = tk.BooleanVar(value=True)
        self.enabled = tk.BooleanVar(value=engine.store.enabled)
        self.recover_context = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="●  Recovery on" if self.enabled.get() else "●  Paused")
        self.detail_title = tk.StringVar(value="Conversation details")
        self.detail_text = tk.StringVar(value="Select an armed conversation to see its recovery status.")
        self.usage_text = tk.StringVar(value="Usage has not been checked")
        self.quota_updated = tk.StringVar(value="Checking allowance automatically…")
        self.notice = tk.StringVar(value="Click Add conversation to start automatic recovery.")
        self.selected_thread_id = tk.StringVar(value="demo-task" if simulation else "")
        self.queue_title = tk.StringVar(value="Armed conversations · 0")
        self.power_status = tk.StringVar(value="Keep Codex open; screen locking is allowed.")
        self.names = {"demo-task": "Demo research conversation"} if simulation else {}
        self.remaining = [tk.StringVar(value="Not checked"), tk.StringVar(value="Not checked")]
        self.progress = [tk.DoubleVar(value=0), tk.DoubleVar(value=0)]
        self.bars = []
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 18))
        if self.icon:
            self.brand_icon = self.icon.subsample(4, 4)
            ttk.Label(header, image=self.brand_icon).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, text="Auto-Resume", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Codex desktop companion", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        setting = ttk.Frame(frame, style="Card.TFrame", padding=(18, 14))
        setting.pack(fill="x", pady=(0, 18))
        self.toggle = ttk.Checkbutton(setting, text="Continue automatically when the 5h limit resets",
                                      variable=self.enabled, command=self.toggle_enabled,
                                      style="Card.TCheckbutton", takefocus=True)
        self.toggle.pack(side="left")
        self.status_badge = ttk.Label(setting, textvariable=self.status, style="Status.TLabel")
        self.status_badge.pack(side="right", padx=(12, 0))
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(0, 14))
        self.add_button = ttk.Button(controls, text="+ Add conversation", command=self.choose, style="Primary.TButton")
        self.add_button.pack(side="left")
        self.disarm_button = ttk.Button(controls, text="Disarm", command=self.disarm, state="disabled")
        self.disarm_button.pack(side="left", padx=(8, 0))
        self.message_button = ttk.Button(controls, text="Recovery message", command=self.edit_recovery_message,
                                         state="disabled")
        self.message_button.pack(side="left", padx=(8, 0))
        ttk.Checkbutton(controls, text="Recover context checkpoints", variable=self.recover_context).pack(side="right")
        quota_head = ttk.Frame(frame)
        quota_head.pack(fill="x", pady=(0, 10))
        ttk.Label(quota_head, text="Included allowance", style="Section.TLabel").pack(side="left")
        ttk.Label(quota_head, text="Updates every minute", style="Muted.TLabel").pack(side="right")
        quotas = ttk.Frame(frame)
        quotas.pack(fill="x")
        quotas.columnconfigure((0, 1), weight=1, uniform="quota")
        for i, label in enumerate(("5-hour window", "Weekly window")):
            card = ttk.Frame(quotas, style="Card.TFrame", padding=(18, 13))
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 7) if i == 0 else (7, 0))
            ttk.Label(card, text=label, style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=self.remaining[i], style="Metric.TLabel").pack(anchor="w", pady=(5, 10))
            bar = tk.Canvas(card, height=6, borderwidth=0, highlightthickness=0)
            bar.pack(fill="x")
            bar.bind("<Configure>", lambda _: self.draw_quotas())
            self.bars.append(bar)
        ttk.Label(frame, textvariable=self.quota_updated, style="Muted.TLabel").pack(anchor="w", pady=(7, 17))
        ttk.Label(frame, textvariable=self.queue_title, style="Section.TLabel").pack(anchor="w", pady=(0, 9))
        table = ttk.Frame(frame, style="Card.TFrame", padding=1)
        table.pack(fill="both", expand=True)
        self.tasks = ttk.Treeview(table, columns=("state", "reset", "reason"), show="tree headings", height=2, selectmode="browse")
        self.tasks.heading("#0", text="Conversation", anchor="w")
        self.tasks.heading("state", text="Recovery", anchor="w")
        self.tasks.heading("reset", text="Next check", anchor="w")
        self.tasks.heading("reason", text="Details", anchor="w")
        self.tasks.column("#0", width=260, minwidth=210)
        self.tasks.column("state", width=150, minwidth=130)
        self.tasks.column("reset", width=150, minwidth=125)
        self.tasks.column("reason", width=270, minwidth=160)
        self.tasks.configure(displaycolumns=("state", "reset"))
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tasks.yview)
        self.tasks.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tasks.pack(fill="both", expand=True)
        self.tasks.bind("<<TreeviewSelect>>", self.show_reason)
        self.empty_state = ttk.Label(table, text="No conversations armed yet\nClick Add conversation to get started.",
                                     justify="center", style="CardMuted.TLabel")
        details = ttk.Frame(frame, style="Card.TFrame", padding=(16, 10))
        details.pack(fill="x", pady=(10, 0))
        ttk.Label(details, textvariable=self.detail_title, style="CardTitle.TLabel",
                  wraplength=640).pack(anchor="w")
        ttk.Label(details, textvariable=self.detail_text, style="CardMuted.TLabel",
                  wraplength=640).pack(anchor="w", pady=(4, 0))
        ttk.Label(frame, textvariable=self.notice, wraplength=690, style="Muted.TLabel").pack(anchor="w", fill="x", pady=(8, 8))
        if simulation:
            sims = ttk.Frame(frame)
            sims.pack(fill="x", pady=(0, 8))
            ttk.Button(sims, text="Simulate reset", command=lambda: self.reset_simulation(30)).pack(side="left")
            ttk.Button(sims, text="Weekly limit", command=lambda: self.reset_simulation(100)).pack(side="left", padx=8)
            ttk.Button(sims, text="Complete task", command=self.complete_simulation).pack(side="left")
        footer = self.footer = ttk.Frame(frame)
        footer.pack(fill="x")
        ttk.Button(footer, text="Activity log", command=self.history).pack(side="left")
        ttk.Label(footer, text=f"Version {__version__}", style="Muted.TLabel").pack(side="left", padx=12)
        ttk.Checkbutton(footer, text="Dark mode", variable=self.dark, command=self.theme).pack(side="right")
        if not simulation and update.installed_target() is not None:
            self.update_button = ttk.Button(footer, text="Check for updates", command=self.check_update)
            self.update_button.pack(side="right", padx=12)
            self.update_timer_id = root.after(1000, lambda: self.check_update(automatic=True))
        elif simulation:
            ttk.Label(footer, text="Demo data · no model requests", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Label(frame, textvariable=self.power_status, style="Muted.TLabel").pack(anchor="w", pady=(7, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-q>", lambda _: self.close())
        self.theme()
        if background:
            self.notice.set("Background controller connected. Closing this panel keeps recovery enabled.")
        else:
            try:
                self.scheduler.start()
                self.owns_controller = True
            except UnsafeError:
                self.notice.set("Background controller connected. Closing this panel keeps recovery enabled.")
        self.refresh()
        self.initial_check_id = root.after(250, self.initial_check)

    def initial_check(self):
        self.initial_check_id = None
        self.auto_refresh_allowance()

    def auto_refresh_allowance(self):
        self.allowance_timer_id = None
        if self.closed:
            return
        if self.busy or self.pending_actions:
            self.allowance_timer_id = self.root.after(1000, self.auto_refresh_allowance)
            return
        self.check_usage(quiet=True)
        self.allowance_timer_id = self.root.after(60000, self.auto_refresh_allowance)

    def update_work(self, action, on_success, on_error=None):
        self.update_button.state(["disabled"])
        results = self.update_results

        def finished(outcome):
            self.update_button.state(["!disabled"])
            callback, result = outcome
            if callback is not None:
                callback(result)

        def run():
            try:
                result = action()
            except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
                results.put((finished, (on_error, None)))
            else:
                results.put((finished, (on_success, result)))

        threading.Thread(target=run, daemon=True).start()

    def check_update(self, *, automatic=False):
        if self.update_timer_id is not None:
            self.root.after_cancel(self.update_timer_id)
        self.update_timer_id = self.root.after(6 * 60 * 60 * 1000, lambda: self.check_update(automatic=True))
        if self.update_button.instate(["disabled"]):
            return

        def checked(release):
            if release:
                self.update_button.configure(text=f"Update to {release.version}", command=lambda: self.install_update(release))
                if self.offered_update != release.version:
                    self.offered_update = release.version
                    self.install_update(release)
            elif not automatic:
                self.notice.set("Auto-Resume is up to date.")

        if not automatic:
            self.notice.set("Checking for updates…")
        self.update_work(update.check_for_update, checked,
                         None if automatic else lambda _: self.notice.set(
                             "Could not reach GitHub releases. Try again or download the update from the project website."))

    def install_update(self, release):
        from tkinter import messagebox

        if self.installing_update:
            return
        if not messagebox.askyesno("Update Auto-Resume", f"Download and install Auto-Resume {release.version}? "
                                   "Auto-Resume will reopen after installation.", parent=self.root):
            return

        def failed(message):
            self.installing_update = False
            self.notice.set(message)

        def installed(relaunch):
            self.relaunch_after_update = relaunch
            self.close(for_update=True)

        def downloaded(installer):
            self.notice.set("Installing the update. Your system may ask for permission.")
            self.update_work(lambda: update.install_update(installer, release), installed,
                             lambda _: failed("The update could not be installed. Try again."))

        self.installing_update = True
        self.notice.set(f"Downloading Auto-Resume {release.version}…")
        self.update_work(lambda: update.download_update(release), downloaded,
                         lambda _: failed("The update could not be downloaded or verified. Try again."))

    def theme(self):
        if self.dark.get():
            bg, fg, muted, panel, border, accent = "#10151e", "#edf3fb", "#9baac0", "#1a2331", "#2d3a4e", "#73a9ff"
            selection, success = "#233e61", "#65dbc3"
        else:
            bg, fg, muted, panel, border, accent = "#f1f5fa", "#172b45", "#586c84", "#ffffff", "#d6e0ed", "#2563eb"
            selection, success = "#dce9ff", "#087b64"
        self.root.configure(background=bg)
        self.style.configure(".", background=bg, foreground=fg, fieldbackground=panel, font=(self.font_family, 10))
        self.style.configure("TFrame", background=bg)
        self.style.configure("Card.TFrame", background=panel)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Title.TLabel", font=(self.font_family, 25, "bold"))
        self.style.configure("Section.TLabel", font=(self.font_family, 11, "bold"))
        self.style.configure("Muted.TLabel", foreground=muted, font=(self.font_family, 9))
        self.style.configure("CardTitle.TLabel", background=panel, font=(self.font_family, 10, "bold"))
        self.style.configure("CardMuted.TLabel", background=panel, foreground=muted, font=(self.font_family, 9))
        self.style.configure("Metric.TLabel", background=panel, font=(self.font_family, 19, "bold"))
        self.style.configure("Paused.TLabel", background=panel, foreground=muted, font=(self.font_family, 9, "bold"))
        self.style.configure("Status.TLabel", background=panel, foreground=success, font=(self.font_family, 9, "bold"))
        self.style.configure("TButton", background=panel, foreground=fg, bordercolor=border, lightcolor=panel,
                             darkcolor=panel, borderwidth=1, padding=(13, 8), focuscolor=accent)
        self.style.map("TButton", background=[("active", border)], foreground=[("active", fg)])
        self.style.configure("Primary.TButton", background=accent, foreground="#101b2d", bordercolor=accent,
                             font=(self.font_family, 10, "bold"))
        self.style.map("Primary.TButton", background=[("active", "#91bdff")], foreground=[("active", "#101b2d")])
        if not self.dark.get():
            self.style.configure("Primary.TButton", foreground="#ffffff")
            self.style.map("Primary.TButton", foreground=[("active", "#ffffff")], background=[("active", "#1d4ed8")])
        self.style.configure("TCheckbutton", background=bg, foreground=fg, indicatorbackground=panel, indicatorforeground=accent)
        self.style.map("TCheckbutton", background=[("active", bg)])
        self.style.configure("Card.TCheckbutton", background=panel)
        self.style.map("Card.TCheckbutton", background=[("active", panel)])
        self.style.configure("TEntry", fieldbackground=panel, foreground=fg, bordercolor=border,
                             lightcolor=border, darkcolor=border, padding=5, insertcolor=fg)
        self.style.map("TEntry", bordercolor=[("focus", accent)], lightcolor=[("focus", accent)])
        self.style.configure("Treeview", background=panel, fieldbackground=panel, foreground=fg,
                             rowheight=40, borderwidth=0, relief="flat", bordercolor=border, lightcolor=panel, darkcolor=panel)
        self.style.configure("Treeview.Heading", background=panel, foreground=muted, relief="flat",
                             borderwidth=0, font=(self.font_family, 9, "bold"), padding=(12, 11))
        self.style.map("Treeview", background=[("selected", selection)], foreground=[("selected", fg)])
        self.style.map("Treeview.Heading", background=[("active", panel)])
        self.bar_colors = (border, accent, success)
        self.draw_quotas()

    def draw_quotas(self):
        if not hasattr(self, "bar_colors"):
            return
        trough, first, second = self.bar_colors
        for i, bar in enumerate(self.bars):
            bar.configure(background=trough)
            bar.delete("all")
            width = int(bar.winfo_width() * self.progress[i].get() / 100)
            if width:
                bar.create_rectangle(0, 0, width, 6, fill=(first, second)[i], width=0)

    def toggle_enabled(self):
        self.engine.store.set_enabled(self.enabled.get(), self.engine.clock())
        self.status.set("Enabled" if self.enabled.get() else "Paused")
        self.scheduler.wake.set()
        if self.enabled.get() and not self.simulation:
            self.work(self.engine.adapter.ensure_daemon)

    def work(self, action, callback=None, *, quiet=False):
        if self.busy:
            if not quiet:
                self.pending_actions.append((action, callback))
                self.notice.set("Finishing the current check…")
            return
        self.busy = True
        if not quiet:
            self.notice.set("Checking…")
        results = self.results
        def run():
            try:
                results.put((True, action(), callback, quiet))
            except Exception as exc:
                # UI exceptions are short local diagnostics; raw protocol errors are never passed through.
                results.put((False, str(exc)[:180], None, quiet))
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()
        if self.refresh_id is not None:
            self.root.after_cancel(self.refresh_id)
            self.refresh_id = self.root.after(50, self.refresh)

    def check_usage(self, *, quiet=False):
        engine = self.engine
        def check():
            usage = engine.adapter.usage()
            engine.usage_changed(usage)
            bucket = usage.payload.get("rateLimits", {})
            windows = {w.get("windowDurationMins"): w for key in ("primary", "secondary")
                       if isinstance((w := bucket.get(key)), dict)}
            values, remaining = [], []
            for duration, label in ((300, "5h"), (10080, "Weekly")):
                w = windows.get(duration)
                if w and type(w.get("usedPercent")) in (int, float) and 0 <= w["usedPercent"] <= 100:
                    used = w["usedPercent"]
                    values.append(f"{label}: {used:g}% used")
                    remaining.append(100 - used)
                else:
                    values.append(f"{label}: unavailable")
                    remaining.append(None)
            return {"summary": " · ".join(values), "remaining": remaining,
                    "checked": "Last checked " + datetime.now().strftime("%H:%M")}
        self.work(check, self.show_usage, quiet=quiet)

    def show_usage(self, result):
        self.usage_text.set(result["summary"])
        for i, value in enumerate(result["remaining"]):
            self.remaining[i].set(f"{value:g}% remaining" if value is not None else "Unavailable")
            self.progress[i].set(value or 0)
        self.draw_quotas()
        self.quota_updated.set(result["checked"] + " · refreshes every minute")

    def arm(self):
        tid = self.selected_thread_id.get().strip()
        if not tid and self.tasks.selection():
            tid = self.tasks.selection()[0]
            self.select_conversation(tid)
        recover_context = self.recover_context.get()
        engine, wake = self.engine, self.scheduler.wake
        def arm():
            if not self.simulation:
                open_conversation(tid)
            previous = engine.store.get(tid)
            native = previous and json.loads(previous["context"]).get("native_heartbeat")
            task = engine.register(tid, recover_context=recover_context, wait_for_limit=not native,
                                   desktop_queue=not self.simulation)
            if not self.simulation and self.owns_controller:
                task = engine.start_selected(tid)
            wake.set()
            if not task["eligible"]:
                if task["state"] == "COMPLETED":
                    return "The selected chat has finished its turn"
                raise UnsafeError(task["reason"])
            if task["state"] == "WAITING_FOR_GOAL":
                return task["reason"]
            context = json.loads(task["context"])
            if context.get("wait_for_limit"):
                return task["reason"]
            if task["state"] == "RUNNING":
                return "Conversation armed · continue sent" if context.get("user_start_pending") else "Conversation armed · already working"
            if context.get("user_start_pending") and not task["ack_turn"]:
                return "Conversation armed · continue will start when included usage is available"
            if context.get("native_heartbeat"):
                if task["state"] == "WAITING_FOR_SCHEDULE":
                    return "Native schedule is paused; activate it in Codex to enable recovery"
                return "Native recovery armed; existing running work is preserved"
            return ("Conversation armed for usage-limit and context-budget recovery" if recover_context
                    else "Conversation explicitly armed")
        def armed(message):
            self.notice.set(message)
            self.pending_selection = tid
        self.work(arm, armed)

    def edit_recovery_message(self):
        import tkinter as tk
        from tkinter import ttk

        selected = self.tasks.selection()
        if not selected:
            return
        thread_id = selected[0]
        store = self.engine.store
        task = store.get(thread_id)
        if not task or not task["eligible"]:
            return
        context = json.loads(task["context"])
        if context.get("native_heartbeat"):
            self.notice.set("Set the recovery message in this chat’s Codex schedule.")
            return

        window = tk.Toplevel(self.root)
        window.title("Recovery message")
        window.transient(self.root)
        window.configure(background=self.style.lookup("TFrame", "background"))
        window.minsize(510, 410)
        body = ttk.Frame(window, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Recovery message", style="Section.TLabel").pack(anchor="w")
        title = self.names.get(thread_id) or context.get("name") or thread_id
        ttk.Label(body, text=title, style="Muted.TLabel", wraplength=465).pack(anchor="w", pady=(4, 14))
        ttk.Label(body, text="Codex receives this message when automatic recovery starts. Leave it blank to use the default.",
                  wraplength=465).pack(anchor="w", pady=(0, 10))
        foreground = self.style.lookup("TLabel", "foreground")
        editor = tk.Text(body, width=52, height=6, wrap="word", undo=True, relief="flat", padx=10, pady=10,
                         background=self.style.lookup("Card.TFrame", "background"),
                         foreground=foreground, insertbackground=foreground)
        editor.pack(fill="both", expand=True)
        editor.insert("1.0", store.recovery_message(thread_id))
        ttk.Label(body, text="Default message", style="Section.TLabel").pack(anchor="w", pady=(14, 4))
        ttk.Label(body, text=DEFAULT_RECOVERY_MESSAGE, wraplength=465,
                  style="Muted.TLabel").pack(anchor="w")
        feedback = tk.StringVar()
        ttk.Label(body, textvariable=feedback, wraplength=465).pack(anchor="w", pady=(8, 0))
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(10, 0))

        def save():
            try:
                store.set_recovery_message(thread_id, editor.get("1.0", "end-1c"), self.engine.clock())
            except ValueError as exc:
                feedback.set(str(exc))
                return
            self.notice.set("Custom recovery message saved." if store.recovery_message(thread_id)
                            else "Default recovery message restored.")
            self.show_reason()
            window.destroy()

        ttk.Button(buttons, text="Use default", command=lambda: editor.delete("1.0", "end")).pack(side="left")
        ttk.Button(buttons, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right", padx=(0, 8))
        window.bind("<Escape>", lambda _: window.destroy())
        window.bind("<Control-Return>", lambda _: save())
        window.grab_set()
        editor.focus_set()

    def disarm(self):
        chosen = self.tasks.selection()
        if not chosen:
            tid = self.selected_thread_id.get().strip()
            chosen = (tid,) if self.engine.store.get(tid) else ()
        if not chosen:
            self.notice.set("Choose a conversation to disarm.")
            return
        for tid in chosen:
            self.engine.disarm(tid)
            if self.tasks.exists(tid):
                self.tasks.delete(tid)
        self.selected_thread_id.set("")
        self.disarm_button.state(["disabled"])
        self.message_button.state(["disabled"])
        self.scheduler.wake.set()
        self.notice.set("Conversation disarmed and removed from the queue.")

    def choose(self):
        if self.picker is not None and self.picker.winfo_exists():
            self.picker.lift()
            return
        if self.simulation:
            self.show_picker([{"id": tid, "name": self.names.get(tid, tid)} for tid in self.engine.adapter.observations])
        else:
            self.work(self.engine.adapter.recent_threads, self.show_picker)

    def show_picker(self, conversations):
        import tkinter as tk
        from tkinter import ttk
        self.names.update({item["id"]: item["name"] for item in conversations})
        window = tk.Toplevel(self.root)
        self.picker = window
        window.title("Add a conversation")
        window.geometry("660x400")
        window.transient(self.root)
        window.configure(background=self.style.lookup("TFrame", "background"))
        ttk.Label(window, text="Select a conversation to arm it", style="Section.TLabel").pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Label(window, text="Codex opens when you choose. Start or keep working in Codex whenever you’re ready.",
                  style="Muted.TLabel", wraplength=600).pack(anchor="w", padx=16)
        query = tk.StringVar()
        ttk.Label(window, text="Find by title or ID", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(14, 4))
        search = ttk.Entry(window, textvariable=query)
        search.pack(fill="x", padx=16)
        listing = tk.Listbox(window, font=(self.font_family, 11), exportselection=False, relief="flat",
                             background=self.style.lookup("Card.TFrame", "background"),
                             foreground=self.style.lookup("TLabel", "foreground"))
        listing.pack(fill="both", expand=True, padx=16, pady=12)
        matches = tk.StringVar()
        ttk.Label(window, textvariable=matches, style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 12))
        filtered = []

        def filter_list(*_):
            words = query.get().casefold().split()
            filtered[:] = [item for item in conversations
                           if all(word in (item["name"] + " " + item["id"]).casefold() for word in words)]
            listing.delete(0, "end")
            for item in filtered:
                listing.insert("end", item["name"] + " · " + item["id"][-8:])
            matches.set(f"{len(filtered)} conversations" if filtered else
                        ("No matches. Try another title or ID." if conversations else
                         "No conversations found. Open a chat in Codex, then try again."))

        query.trace_add("write", filter_list)
        filter_list()
        accepted = False
        def select(*_):
            nonlocal accepted
            selected = listing.curselection()
            if selected and not accepted:
                accepted = True
                self.select_conversation(filtered[selected[0]]["id"])
                window.destroy()
                self.picker = None
                self.arm()
        listing.bind("<<ListboxSelect>>", select)
        listing.bind("<Return>", select)
        def select_first(_):
            if filtered:
                listing.selection_set(0)
                select()

        search.bind("<Return>", select_first)
        window.bind("<Escape>", lambda _: window.destroy())
        search.focus_set()

    def show_reason(self, *_):
        chosen = self.tasks.selection()
        task = self.engine.store.get(chosen[0]) if chosen else None
        self.update_details(task)
        if task:
            self.select_conversation(chosen[0])

    def update_details(self, task):
        available = bool(task and task["eligible"])
        self.set_button_enabled(self.disarm_button, available)
        if not available:
            self.set_button_enabled(self.message_button, False)
            self.set_if_changed(self.detail_title, "Conversation details")
            self.set_if_changed(self.detail_text, "Select an armed conversation to see its recovery status.")
            return
        thread_id = task["thread_id"]
        context = json.loads(task["context"])
        native = bool(context.get("native_heartbeat"))
        self.set_button_enabled(self.message_button, not native)
        if native:
            mode = "Message managed by the Codex schedule"
        elif self.engine.store.recovery_message(thread_id):
            mode = "Custom recovery message"
        else:
            mode = "Default recovery message"
        name = self.names.get(thread_id) or context.get("name") or thread_id
        self.set_if_changed(self.detail_title, name)
        self.set_if_changed(self.detail_text, task["reason"] + "\n" + mode)

    def select_conversation(self, thread_id):
        self.selected_thread_id.set(thread_id)
        task = self.engine.store.get(thread_id)
        if task:
            self.recover_context.set(json.loads(task["context"]).get("recover_context", False))

    def history(self):
        import tkinter as tk
        from tkinter import ttk
        window = tk.Toplevel(self.root)
        window.title("Auto-Resume activity")
        text = tk.Text(window, width=90, height=22, wrap="word")
        text.pack(fill="both", expand=True, padx=12, pady=12)
        for event in self.engine.store.history():
            text.insert("end", f"{datetime.fromtimestamp(event['at']):%d %b %H:%M} · {event['state']}\n{event['reason']}\n\n")
        text.configure(state="disabled")
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=8)

    def reset_simulation(self, weekly):
        self.engine.adapter.reset(weekly=weekly)
        self.engine.usage_changed(self.engine.adapter.usage())
        with self.engine.store.transaction():
            self.engine.store.db.execute("UPDATE tasks SET next_check=? WHERE eligible=1", (self.engine.clock(),))
        self.scheduler.wake.set()

    def complete_simulation(self):
        self.engine.adapter.complete()
        with self.engine.store.transaction():
            self.engine.store.db.execute("UPDATE tasks SET next_check=? WHERE eligible=1", (self.engine.clock(),))
        self.scheduler.wake.set()

    @staticmethod
    def set_if_changed(variable, value):
        if variable.get() != value:
            variable.set(value)

    @staticmethod
    def set_button_enabled(button, enabled):
        if button.instate(["disabled"]) == enabled:
            button.state(["!disabled" if enabled else "disabled"])

    def refresh(self):
        if self.closed:
            return
        if self.refresh_id is not None:
            self.root.after_cancel(self.refresh_id)
            self.refresh_id = None
        while not self.update_results.empty():
            callback, value = self.update_results.get_nowait()
            callback(value)
            if self.closed:
                return
        while not self.results.empty():
            ok, message, callback, quiet = self.results.get_nowait()
            self.busy = False
            if ok and callback is not None:
                callback(message)
                continue
            if quiet:
                self.quota_updated.set(message)
            else:
                self.notice.set(message)
            if ok and "% used" in message:
                self.usage_text.set(message)
        if not self.busy and self.pending_actions:
            self.work(*self.pending_actions.popleft())
        enabled = self.engine.store.enabled
        self.set_if_changed(self.enabled, enabled)
        self.set_if_changed(self.status, "●  Recovery on" if enabled else "●  Paused")
        badge_style = "Status.TLabel" if enabled else "Paused.TLabel"
        if self.status_badge.cget("style") != badge_style:
            self.status_badge.configure(style=badge_style)
        power = self.engine.store.value("power_status")
        alive = time.time() - float(self.engine.store.value("controller_heartbeat")) < 20
        controller = "Window controller" if self.owns_controller else ("Background controller active" if alive else "Background controller starting")
        if alive and not self.owns_controller and self.engine.store.value("controller_version") != __version__:
            controller = "Older background controller active. Restart it after upgrading."
        self.set_if_changed(self.power_status, controller + " · " + (power if power != "Not requested" else "No armed work needs sleep protection."))
        saved_tasks = self.engine.store.tasks()
        saved_by_id = {task["thread_id"]: task for task in saved_tasks}
        active = [task for task in saved_tasks if task["eligible"]]
        visible = {task["thread_id"] for task in active}
        for tid in self.tasks.get_children():
            if tid not in visible:
                if tid in saved_by_id:
                    task = saved_by_id[tid]
                    name = self.names.get(tid) or json.loads(task["context"]).get("name") or "Conversation"
                    self.notice.set(name + ": " + task["reason"])
                self.tasks.delete(tid)
        self.set_if_changed(self.queue_title, f"Armed conversations · {len(active)}")
        empty = not active
        if empty != self.empty_visible:
            self.empty_visible = empty
            if empty:
                self.empty_state.place(relx=.5, rely=.55, anchor="center")
            else:
                self.empty_state.place_forget()
        for task in active:
            reset = datetime.fromtimestamp(task["next_check"]).strftime("%d %b %H:%M") if task["next_check"] else "—"
            context = json.loads(task["context"])
            if context.get("native_heartbeat"):
                reset = "Activate in Codex" if task["state"] == "WAITING_FOR_SCHEDULE" else "Native schedule"
            label = {"WAITING_FOR_SCHEDULE": "Schedule paused", "PAUSED_FOR_USER": "Needs attention",
                     "WAITING_FOR_GOAL": "Goal recovery",
                     "WAITING_FOR_RESET": "Waiting for reset"}.get(task["state"], task["state"].replace("_", " ").capitalize())
            if context.get("wait_for_limit") and task["state"] == "ARMED":
                label = "Armed ahead"
            if task["state"] == "WAITING_FOR_RESET" and task["reason"].startswith("Connection unavailable"):
                label = "Retrying connection"
            values = (label, reset, task["reason"])
            tid = task["thread_id"]
            name = self.names.get(tid) or context.get("name") or tid
            if self.tasks.exists(tid):
                row = self.tasks.item(tid)
                if row["text"] != name or tuple(row["values"]) != values:
                    self.tasks.item(tid, text=name, values=values)
            else:
                self.tasks.insert("", "end", iid=tid, text=name, values=values)
        if self.pending_selection and self.tasks.exists(self.pending_selection):
            self.tasks.selection_set(self.pending_selection)
            self.tasks.focus(self.pending_selection)
            self.pending_selection = None
        selected = self.tasks.selection()
        self.update_details(saved_by_id.get(selected[0]) if selected else None)
        if self.scheduler.last_error:
            self.notice.set(self.scheduler.last_error)
        active_work = self.busy or self.pending_actions or self.installing_update
        self.refresh_id = self.root.after(200 if active_work else 1000, self.refresh)

    def close(self, *, for_update=False):
        if self.closed:
            return
        if self.installing_update and not for_update:
            self.notice.set("Wait for the update to finish before closing Auto-Resume.")
            return
        self.closed = True
        if self.initial_check_id is not None:
            self.root.after_cancel(self.initial_check_id)
            self.initial_check_id = None
        if self.allowance_timer_id is not None:
            self.root.after_cancel(self.allowance_timer_id)
            self.allowance_timer_id = None
        if self.update_timer_id is not None:
            self.root.after_cancel(self.update_timer_id)
            self.update_timer_id = None
        self.pending_actions.clear()
        if self.refresh_id is not None:
            self.root.after_cancel(self.refresh_id)
            self.refresh_id = None
        if self.owns_controller and not for_update:
            self.engine.store.set_enabled(False, self.engine.clock())
        self.engine.adapter.close()
        self.scheduler.stop()
        if self.worker is not None and self.worker.is_alive():
            self.worker.join(timeout=3)
        self.root.destroy()


def launch(engine, simulation=False, *, background=False):
    try:
        import tkinter as tk
        root = tk.Tk(className="CodexAutoResume")
    except Exception as exc:
        raise ValueError("Desktop UI is unavailable. On Ubuntu install python3-tk and use a desktop session.") from exc
    window = ControlWindow(root, engine, simulation, background=background)
    root.mainloop()
    return window.relaunch_after_update

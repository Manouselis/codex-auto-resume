"""Accessible, native Tk control window. GUI never runs network I/O on its event thread."""
import queue
import json
import threading
import base64
import time
from importlib import resources
from datetime import datetime

from .engine import Scheduler
from .domain import UnsafeError


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
        self.dark = tk.BooleanVar(value=True)
        self.enabled = tk.BooleanVar(value=engine.store.enabled)
        self.recover_context = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Enabled" if self.enabled.get() else "Paused")
        self.usage_text = tk.StringVar(value="Usage has not been checked")
        self.quota_updated = tk.StringVar(value="Refresh to check your included allowance")
        self.notice = tk.StringVar(value="Select a conversation to see recovery details.")
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
        ttk.Label(titles, text="Keep your work moving in the same conversation.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        setting = ttk.Frame(frame, style="Card.TFrame", padding=(18, 14))
        setting.pack(fill="x", pady=(0, 18))
        self.toggle = ttk.Checkbutton(setting, text="Continue automatically when the 5h limit resets",
                                      variable=self.enabled, command=self.toggle_enabled,
                                      style="Card.TCheckbutton", takefocus=True)
        self.toggle.pack(side="left")
        ttk.Label(setting, textvariable=self.status, style="Status.TLabel").pack(side="right", padx=(12, 0))
        quota_head = ttk.Frame(frame)
        quota_head.pack(fill="x", pady=(0, 10))
        ttk.Label(quota_head, text="Included allowance", style="Section.TLabel").pack(side="left")
        self.check = ttk.Button(quota_head, text="Refresh allowance", command=self.check_usage)
        self.check.pack(side="right")
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
        ttk.Label(frame, text="Conversations", style="Section.TLabel").pack(anchor="w", pady=(0, 9))
        entryrow = ttk.Frame(frame)
        entryrow.pack(fill="x", pady=(0, 10))
        self.thread_id = ttk.Entry(entryrow)
        self.thread_id.pack(side="left", fill="x", expand=True, ipady=6)
        self.thread_id.insert(0, "demo-task" if simulation else "")
        self.thread_id.bind("<Return>", lambda _: self.arm())
        if not simulation:
            ttk.Button(entryrow, text="Choose…", command=self.choose).pack(side="left", padx=(10, 0))
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(0, 12))
        self.arm_button = ttk.Button(controls, text="Arm conversation", command=self.arm, style="Primary.TButton")
        self.arm_button.pack(side="left")
        self.disarm_button = ttk.Button(controls, text="Disarm", command=self.disarm)
        self.disarm_button.pack(side="left", padx=(8, 0))
        ttk.Checkbutton(controls, text="Recover context checkpoints", variable=self.recover_context).pack(side="right")
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
        self.tasks.pack(fill="both", expand=True)
        self.tasks.bind("<<TreeviewSelect>>", self.show_reason)
        ttk.Label(frame, textvariable=self.notice, wraplength=700, style="Muted.TLabel").pack(anchor="w", fill="x", pady=(10, 10))
        if simulation:
            sims = ttk.Frame(frame)
            sims.pack(fill="x", pady=(0, 8))
            ttk.Button(sims, text="Simulate reset", command=lambda: self.reset_simulation(30)).pack(side="left")
            ttk.Button(sims, text="Weekly limit", command=lambda: self.reset_simulation(100)).pack(side="left", padx=8)
            ttk.Button(sims, text="Complete task", command=self.complete_simulation).pack(side="left")
        footer = self.footer = ttk.Frame(frame)
        footer.pack(fill="x")
        ttk.Button(footer, text="Activity log", command=self.history).pack(side="left")
        ttk.Label(footer, text="Demo data · no model requests" if simulation else "Keep Codex open · screen locking is allowed.", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Checkbutton(footer, text="Dark mode", variable=self.dark, command=self.theme).pack(side="right")
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
        if not simulation:
            self.initial_check_id = root.after(250, self.initial_check)

    def initial_check(self):
        self.initial_check_id = None
        if not self.closed and not self.busy:
            self.check_usage()

    def theme(self):
        if self.dark.get():
            bg, fg, muted, panel, border, accent = "#10151e", "#edf3fb", "#9baac0", "#1a2331", "#2d3a4e", "#73a9ff"
            selection, success = "#233e61", "#65dbc3"
        else:
            bg, fg, muted, panel, border, accent = "#f1f5fa", "#172b45", "#586c84", "#ffffff", "#d6e0ed", "#2563eb"
            selection, success = "#dce9ff", "#087b64"
        self.root.configure(background=bg)
        self.style.configure(".", background=bg, foreground=fg, fieldbackground=panel, font=("DejaVu Sans", 10))
        self.style.configure("TFrame", background=bg)
        self.style.configure("Card.TFrame", background=panel)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Title.TLabel", font=("DejaVu Sans", 25, "bold"))
        self.style.configure("Section.TLabel", font=("DejaVu Sans", 11, "bold"))
        self.style.configure("Muted.TLabel", foreground=muted, font=("DejaVu Sans", 9))
        self.style.configure("CardMuted.TLabel", background=panel, foreground=muted, font=("DejaVu Sans", 9))
        self.style.configure("Metric.TLabel", background=panel, font=("DejaVu Sans", 19, "bold"))
        self.style.configure("Status.TLabel", background=panel, foreground=success, font=("DejaVu Sans", 9, "bold"))
        self.style.configure("TButton", background=panel, foreground=fg, bordercolor=border, lightcolor=panel,
                             darkcolor=panel, borderwidth=1, padding=(13, 8), focuscolor=accent)
        self.style.map("TButton", background=[("active", border)], foreground=[("active", fg)])
        self.style.configure("Primary.TButton", background=accent, foreground="#101b2d", bordercolor=accent,
                             font=("DejaVu Sans", 10, "bold"))
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
                             borderwidth=0, font=("DejaVu Sans", 9, "bold"), padding=(12, 11))
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

    def work(self, action, callback=None):
        if self.busy:
            self.notice.set("A check is already running")
            return
        self.busy = True
        self.notice.set("Checking…")
        results = self.results
        def run():
            try:
                results.put((True, action(), callback))
            except Exception as exc:
                # UI exceptions are short local diagnostics; raw protocol errors are never passed through.
                results.put((False, str(exc)[:180], None))
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def check_usage(self):
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
        self.work(check, self.show_usage)

    def show_usage(self, result):
        self.usage_text.set(result["summary"])
        for i, value in enumerate(result["remaining"]):
            self.remaining[i].set(f"{value:g}% remaining" if value is not None else "Unavailable")
            self.progress[i].set(value or 0)
        self.draw_quotas()
        self.quota_updated.set(result["checked"])
        self.notice.set("Included allowance refreshed.")

    def arm(self):
        tid = self.thread_id.get().strip()
        if not tid and self.tasks.selection():
            tid = self.tasks.selection()[0]
            self.select_conversation(tid)
        recover_context = self.recover_context.get()
        engine, wake = self.engine, self.scheduler.wake
        def arm():
            task = engine.register(tid, recover_context=recover_context)
            wake.set()
            if json.loads(task["context"]).get("native_heartbeat"):
                if task["state"] == "WAITING_FOR_SCHEDULE":
                    return "Native schedule is paused; activate it in Codex to enable recovery"
                return "Native recovery armed; existing running work is preserved"
            return ("Conversation armed for usage-limit and context-budget recovery" if recover_context
                    else "Conversation explicitly armed")
        self.work(arm)

    def disarm(self):
        chosen = self.tasks.selection()
        if not chosen:
            tid = self.thread_id.get().strip()
            chosen = (tid,) if self.engine.store.get(tid) else ()
        if not chosen:
            self.notice.set("Choose a conversation to disarm.")
            return
        for tid in chosen:
            self.engine.disarm(tid)
        self.scheduler.wake.set()
        self.notice.set("Selected conversation disarmed")

    def choose(self):
        self.work(self.engine.adapter.recent_threads, self.show_picker)

    def show_picker(self, conversations):
        import tkinter as tk
        from tkinter import ttk
        self.names.update({item["id"]: item["name"] for item in conversations})
        window = tk.Toplevel(self.root)
        window.title("Choose a conversation")
        window.geometry("660x360")
        listing = tk.Listbox(window, font=("sans-serif", 11), exportselection=False)
        listing.pack(fill="both", expand=True, padx=16, pady=16)
        for item in conversations:
            listing.insert("end", item["name"] + " · " + item["id"][-8:])
        def select(*_):
            selected = listing.curselection()
            if selected:
                self.select_conversation(conversations[selected[0]]["id"])
                window.destroy()
        listing.bind("<Return>", select)
        listing.bind("<Double-Button-1>", select)
        ttk.Button(window, text="Use this conversation", command=select).pack(pady=(0, 16))

    def show_reason(self, *_):
        chosen = self.tasks.selection()
        if chosen:
            task = self.engine.store.get(chosen[0])
            if task:
                self.select_conversation(chosen[0])
                self.notice.set(task["reason"])

    def select_conversation(self, thread_id):
        self.thread_id.delete(0, "end")
        self.thread_id.insert(0, thread_id)
        task = self.engine.store.get(thread_id)
        self.recover_context.set(json.loads(task["context"]).get("recover_context", False) if task else False)

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

    def refresh(self):
        if self.closed:
            return
        while not self.results.empty():
            ok, message, callback = self.results.get_nowait()
            self.busy = False
            if ok and callback is not None:
                callback(message)
                if isinstance(message, list):
                    self.notice.set("Choose a conversation, then click Arm conversation.")
                continue
            self.notice.set(message)
            if ok and "% used" in message:
                self.usage_text.set(message)
        enabled = self.engine.store.enabled
        self.enabled.set(enabled)
        self.status.set("Enabled" if enabled else "Paused")
        power = self.engine.store.value("power_status")
        alive = time.time() - float(self.engine.store.value("controller_heartbeat")) < 20
        controller = "Window controller" if self.owns_controller else ("Background controller active" if alive else "Background controller starting")
        self.power_status.set(controller + " · " + (power if power != "Not requested" else "No armed work needs sleep protection."))
        for task in self.engine.store.tasks():
            reset = datetime.fromtimestamp(task["next_check"]).strftime("%d %b %H:%M") if task["next_check"] else "—"
            context = json.loads(task["context"])
            if context.get("native_heartbeat"):
                reset = "Activate in Codex" if task["state"] == "WAITING_FOR_SCHEDULE" else "Native schedule"
            label = {"WAITING_FOR_SCHEDULE": "Schedule paused", "PAUSED_FOR_USER": "Needs attention",
                     "WAITING_FOR_RESET": "Waiting for reset"}.get(task["state"], task["state"].replace("_", " ").capitalize())
            if task["state"] == "WAITING_FOR_RESET" and task["reason"].startswith("Connection unavailable"):
                label = "Retrying connection"
            values = (label, reset, task["reason"])
            tid = task["thread_id"]
            name = self.names.get(tid) or context.get("name") or tid
            if self.tasks.exists(tid):
                self.tasks.item(tid, text=name, values=values)
            else:
                self.tasks.insert("", "end", iid=tid, text=name, values=values)
        if self.scheduler.last_error:
            self.notice.set(self.scheduler.last_error)
        self.refresh_id = self.root.after(500, self.refresh)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.initial_check_id is not None:
            self.root.after_cancel(self.initial_check_id)
            self.initial_check_id = None
        if self.refresh_id is not None:
            self.root.after_cancel(self.refresh_id)
            self.refresh_id = None
        if self.owns_controller:
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
    ControlWindow(root, engine, simulation, background=background)
    root.mainloop()

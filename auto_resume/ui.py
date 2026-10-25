"""Accessible, native Tk control window. GUI never runs network I/O on its event thread."""
import queue
import json
import threading
from datetime import datetime

from .engine import Scheduler
from .domain import UnsafeError


class ControlWindow:
    def __init__(self, root, engine, simulation=False):
        import tkinter as tk
        from tkinter import ttk

        self.root, self.engine, self.simulation = root, engine, simulation
        self.results = queue.Queue()
        self.busy = False
        self.closed = False
        self.refresh_id = None
        self.worker = None
        self.scheduler = Scheduler(engine)
        self.owns_controller = False

        root.title("Codex Auto-Resume" + (" · Simulation" if simulation else ""))
        root.geometry("760x760")
        root.minsize(720, 720)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.dark = tk.BooleanVar(value=True)
        self.enabled = tk.BooleanVar(value=engine.store.enabled)
        self.recover_context = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Auto-Resume enabled" if self.enabled.get() else "Auto-Resume disabled")
        self.usage_text = tk.StringVar(value="Usage has not been checked")
        self.notice = tk.StringVar(value="")
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Auto-Resume", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Local companion · independent community project", style="Muted.TLabel").pack(anchor="w", pady=(2, 18))
        self.toggle = ttk.Checkbutton(frame, text="Continue automatically when the 5h limit resets",
                                      variable=self.enabled, command=self.toggle_enabled, takefocus=True)
        self.toggle.pack(anchor="w", pady=8)
        ttk.Label(frame, textvariable=self.status, style="Status.TLabel").pack(anchor="w", pady=(0, 14))
        banner = ("SIMULATION · Invented tasks and usage. No model requests are sent." if simulation else
                  "Armed conversations recover usage-limit stops and optional context checkpoints.\nWeekly exhaustion, paid credits, unknown usage or changed work pauses automation.\nKeep the background controller running while waiting.")
        ttk.Label(frame, text=banner, wraplength=650, style="Notice.TLabel", padding=12).pack(fill="x", pady=(0, 16))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, text="Included usage", style="Section.TLabel").pack(side="left")
        self.check = ttk.Button(row, text="Check usage", command=self.check_usage)
        self.check.pack(side="right")
        ttk.Label(frame, textvariable=self.usage_text, wraplength=650).pack(anchor="w", pady=(8, 18))
        ttk.Label(frame, text="Eligible conversations", style="Section.TLabel").pack(anchor="w")
        armrow = ttk.Frame(frame)
        armrow.pack(fill="x", pady=8)
        self.thread_id = ttk.Entry(armrow)
        self.thread_id.pack(side="left", fill="x", expand=True)
        self.thread_id.insert(0, "demo-task" if simulation else "")
        self.thread_id.bind("<Return>", lambda _: self.arm())
        if not simulation:
            ttk.Button(armrow, text="Choose…", command=self.choose).pack(side="left", padx=(8, 0))
        ttk.Button(armrow, text="Arm conversation", command=self.arm).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(frame, text="Also recover context-budget checkpoints for this arming",
                        variable=self.recover_context).pack(anchor="w", pady=(0, 8))
        self.tasks = ttk.Treeview(frame, columns=("state", "reset"), show="tree headings", height=4, selectmode="browse")
        self.tasks.heading("#0", text="Conversation ID")
        self.tasks.heading("state", text="Status")
        self.tasks.heading("reset", text="Next check · local time")
        self.tasks.column("#0", width=190)
        self.tasks.column("state", width=180)
        self.tasks.column("reset", width=150)
        self.tasks.pack(fill="both", expand=True)
        self.tasks.bind("<<TreeviewSelect>>", self.show_reason)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Disarm selected", command=self.disarm).pack(side="left")
        ttk.Button(actions, text="Activity history", command=self.history).pack(side="left", padx=8)
        ttk.Checkbutton(actions, text="Dark theme", variable=self.dark, command=self.theme).pack(side="right")
        if simulation:
            sims = ttk.Frame(frame)
            sims.pack(fill="x", pady=4)
            ttk.Button(sims, text="Simulate 5h reset", command=lambda: self.reset_simulation(30)).pack(side="left")
            ttk.Button(sims, text="Simulate weekly limit", command=lambda: self.reset_simulation(100)).pack(side="left", padx=8)
            ttk.Button(sims, text="Complete task", command=self.complete_simulation).pack(side="left")
        ttk.Label(frame, textvariable=self.notice, wraplength=650).pack(anchor="w", pady=8)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-q>", lambda _: self.close())
        self.theme()
        try:
            self.scheduler.start()
            self.owns_controller = True
        except UnsafeError:
            # A user service may own scheduling. The window still controls the
            # same database; opening it must never recover a healthy controller.
            self.notice.set("Background controller connected. Closing this window keeps armed tasks active. Use OFF to stop.")
        self.refresh()

    def theme(self):
        bg, fg, muted, panel = ("#17191c", "#f1f3f5", "#b8c0c8", "#272d34") if self.dark.get() else (
            "#f6f7f8", "#17212b", "#475569", "#e4e9ee")
        self.root.configure(background=bg)
        self.style.configure(".", background=bg, foreground=fg, fieldbackground=panel, font=("sans-serif", 10))
        self.style.configure("TButton", padding=7)
        self.style.map("TButton", background=[("active", panel)], foreground=[("active", fg)])
        self.style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", fg)])
        self.style.configure("Title.TLabel", font=("sans-serif", 23, "bold"))
        self.style.configure("Section.TLabel", font=("sans-serif", 11, "bold"))
        self.style.configure("Muted.TLabel", foreground=muted)
        self.style.configure("Notice.TLabel", background=panel)
        self.style.configure("Status.TLabel", foreground="#69d6b2" if self.dark.get() else "#00654b")
        self.style.configure("Treeview", background=panel, fieldbackground=panel, rowheight=28)
        self.style.map("Treeview", background=[("selected", "#225b69")], foreground=[("selected", "#ffffff")])

    def toggle_enabled(self):
        self.engine.store.set_enabled(self.enabled.get(), self.engine.clock())
        self.status.set("Auto-Resume enabled" if self.enabled.get() else "Auto-Resume disabled")
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
            values = []
            for duration, label in ((300, "5h"), (10080, "Weekly")):
                w = windows.get(duration)
                if w and type(w.get("usedPercent")) is int:
                    values.append(f"{label}: {w['usedPercent']}% used")
                else:
                    values.append(f"{label}: unavailable")
            return " · ".join(values) + " · checked " + datetime.now().strftime("%H:%M")
        self.work(check)

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
                return "Native recovery armed; existing running work is preserved"
            return ("Conversation armed for usage-limit and context-budget recovery" if recover_context
                    else "Conversation explicitly armed")
        self.work(arm)

    def disarm(self):
        for tid in self.tasks.selection():
            self.engine.disarm(tid)
        self.notice.set("Selected conversation disarmed")

    def choose(self):
        self.work(self.engine.adapter.recent_threads, self.show_picker)

    def show_picker(self, conversations):
        import tkinter as tk
        from tkinter import ttk
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
                self.notice.set("Choose the original task, then explicitly arm it")
                continue
            self.notice.set(message)
            if ok and "% used" in message:
                self.usage_text.set(message)
        enabled = self.engine.store.enabled
        self.enabled.set(enabled)
        self.status.set("Auto-Resume enabled" if enabled else "Auto-Resume disabled")
        for task in self.engine.store.tasks():
            reset = datetime.fromtimestamp(task["next_check"]).strftime("%d %b %H:%M") if task["next_check"] else "—"
            values = (task["state"].replace("_", " ").capitalize(), reset)
            tid = task["thread_id"]
            if self.tasks.exists(tid):
                self.tasks.item(tid, values=values)
            else:
                self.tasks.insert("", "end", iid=tid, text=tid, values=values)
        if self.scheduler.last_error:
            self.notice.set(self.scheduler.last_error)
        self.refresh_id = self.root.after(500, self.refresh)

    def close(self):
        if self.closed:
            return
        self.closed = True
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


def launch(engine, simulation=False):
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception as exc:
        raise ValueError("Desktop UI is unavailable. On Ubuntu install python3-tk and use a desktop session.") from exc
    ControlWindow(root, engine, simulation)
    root.mainloop()

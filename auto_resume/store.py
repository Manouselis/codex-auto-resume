"""Private SQLite state with durable reservations and cross-process serialization."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from .domain import Observation, State, transition_allowed


class Store:
    def __init__(self, path: Path | str):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError("State file must not be a symlink")
        application_id = 0x43524152
        if path.exists() and path.stat().st_size:
            try:
                check = sqlite3.connect("file:" + quote(str(path.resolve())) + "?mode=ro", uri=True)
                try:
                    owned = check.execute("PRAGMA application_id").fetchone()[0] == application_id
                finally:
                    check.close()
            except sqlite3.DatabaseError as exc:
                raise ValueError("State destination is not an Auto-Resume database") from exc
            if not owned:
                raise ValueError("Refusing an unrelated database; choose a new Auto-Resume state file")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self.path = path
        self.db = sqlite3.connect(path, timeout=5, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(f"PRAGMA application_id={application_id}")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO meta VALUES('schema_version','1');
            INSERT OR IGNORE INTO meta VALUES('enabled','1');
            INSERT OR IGNORE INTO meta VALUES('generation','0');
            CREATE TABLE IF NOT EXISTS tasks(
                thread_id TEXT PRIMARY KEY, context TEXT NOT NULL, state TEXT NOT NULL,
                eligible INTEGER NOT NULL, next_check REAL, retries INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0, continuation_id TEXT, ack_turn TEXT,
                reason TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS submissions(
                id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, status TEXT NOT NULL,
                turn_id TEXT, created_at REAL NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_execution ON submissions((1))
                WHERE status IN ('reserved','running','uncertain');
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY, at REAL NOT NULL, thread_id TEXT,
                state TEXT NOT NULL, reason TEXT NOT NULL);
        """)
        if self.value("schema_version") != "1":
            self.close()
            raise ValueError("Unsupported state schema; preserve this file and upgrade the application")

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def value(self, key):
        with self.lock:
            return self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]

    @property
    def enabled(self):
        return self.value("enabled") == "1"

    @property
    def generation(self):
        return int(self.value("generation"))

    def set_enabled(self, enabled: bool, now: float):
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        with self.transaction():
            self.db.execute("UPDATE meta SET value=? WHERE key='enabled'", (str(int(enabled)),))
            self.db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
            if not enabled:
                for t in self.tasks():
                    if t["eligible"]:
                        self.update(t["thread_id"], State.DISABLED, "Auto-Resume disabled", now, eligible=False)

    def register(self, obs: Observation, now: float, *, recover_context=False,
                 native_heartbeat=None, native_max_attempts=10, finished_submissions=(), expected_generation=None):
        with self.transaction():
            if not self.enabled:
                raise ValueError("Enable Auto-Resume before arming a task")
            if expected_generation is not None and self.generation != expected_generation:
                raise ValueError("Arming changed during inspection; select the conversation and try again")
            old = self.get(obs.thread_id)
            old_context = json.loads(old["context"]) if old else {}
            for submission_id, turn_id in finished_submissions:
                if not old or (submission_id, turn_id) != (old["continuation_id"], old["ack_turn"]):
                    raise ValueError("Reserved turn changed during inspection")
                changed = self.db.execute("UPDATE submissions SET status='finished' WHERE id=? AND thread_id=? AND turn_id=? AND status IN ('running','uncertain')",
                    (submission_id, obs.thread_id, turn_id)).rowcount
                if changed:
                    self.log(obs.thread_id, State(old["state"]), "Acknowledged reserved turn confirmed ended; reservation finished without a retry", now)
            same_settings = (old and old_context.get("recover_context", False) == recover_context
                and old_context.get("native_heartbeat") == native_heartbeat
                and old_context.get("native_max_attempts", 10) == native_max_attempts
                and tuple(old_context.get("bucket_ids", ())) == obs.bucket_ids
                and all(old_context.get(k) == getattr(obs, k) for k in ("thread_id", "account_id", "model", "cwd", "config_hash")))
            same_turn = old and obs.turn_id == (old["ack_turn"] or old_context["turn_id"])
            outstanding = self.db.execute("SELECT * FROM submissions WHERE thread_id=? AND status IN ('reserved','running','uncertain')",
                (obs.thread_id,)).fetchone()
            known_running = (outstanding and old and outstanding["status"] == "running"
                and outstanding["id"] == old["continuation_id"] and outstanding["turn_id"] == old["ack_turn"])
            if same_settings and same_turn and old["eligible"] and not finished_submissions and (not outstanding or known_running):
                return old  # Repeated Arm does not reset attempts or dispatch again.
            if same_settings and same_turn and native_heartbeat and obs.turn_status in ("inProgress", "unresolved"):
                running = self.db.execute("SELECT 1 FROM submissions WHERE id=? AND thread_id=? AND turn_id=? AND status='running'",
                    (old["continuation_id"], obs.thread_id, obs.turn_id)).fetchone()
                if running and old["continuation_id"] == "native-" + obs.turn_id:
                    self.db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
                    self.update(obs.thread_id, State.ARMED, "Existing native turn is still running; recovery rearmed", now, eligible=True, next_check=None)
                    self.update(obs.thread_id, State.RUNNING, "Existing native turn is still running; recovery rearmed", now)
                    return self.get(obs.thread_id)
            if old and old["state"] == State.COMPLETED:
                same_turn = obs.turn_id == (old["ack_turn"] or old_context["turn_id"])
                if same_turn and not (recover_context and obs.stop_reason == "context_budget"):
                    raise ValueError("This Codex turn ended; only a new turn or an explicitly enabled context checkpoint can be armed")
            if self.db.execute("SELECT 1 FROM submissions WHERE thread_id=? AND status IN ('reserved','running','uncertain')",
                               (obs.thread_id,)).fetchone():
                raise ValueError("Execution is outstanding or uncertain; inspect the original conversation")
            context = dict(obs.__dict__)
            context["recover_context"] = recover_context
            context["native_heartbeat"] = native_heartbeat
            context["native_max_attempts"] = native_max_attempts
            reason = ("Task armed for usage-limit and context-budget recovery" if recover_context
                      else "Task explicitly armed")
            if native_heartbeat:
                reason = "Native scheduled recovery armed; waiting for a native wake-up"
            self.db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
            self.db.execute("""INSERT INTO tasks(thread_id,context,state,eligible,reason)
                VALUES(?,?,?,1,?) ON CONFLICT(thread_id) DO UPDATE SET context=excluded.context,
                state=excluded.state,eligible=1,next_check=NULL,retries=0,attempts=0,
                continuation_id=NULL,ack_turn=NULL,reason=excluded.reason""",
                (obs.thread_id, json.dumps(context), State.ARMED.value, reason))
            self.log(obs.thread_id, State.ARMED, reason, now)
            return self.get(obs.thread_id)

    def get(self, thread_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM tasks WHERE thread_id=?", (thread_id,)).fetchone()
            return dict(row) if row else None

    def tasks(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM tasks ORDER BY thread_id")]

    def update(self, thread_id, state: State, reason: str, now: float, **changes):
        # Caller owns transaction. Columns are allowlisted, values always bound.
        old = self.get(thread_id)
        if old is None or not transition_allowed(State(old["state"]), state):
            raise ValueError(f"Invalid state transition to {state}")
        allowed = {"eligible", "next_check", "retries", "attempts", "continuation_id", "ack_turn"}
        if not changes.keys() <= allowed:
            raise ValueError("Invalid state update")
        values = {"state": state.value, "reason": reason, **changes}
        self.db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in values) + " WHERE thread_id=?",
                        (*values.values(), thread_id))
        if old["state"] != state or old["reason"] != reason:
            self.log(thread_id, state, reason, now)

    def log(self, thread_id, state, reason, now):
        self.db.execute("INSERT INTO history(at,thread_id,state,reason) VALUES(?,?,?,?)",
                        (now, thread_id, str(state.value), reason))
        self.db.execute("DELETE FROM history WHERE id <= (SELECT COALESCE(MAX(id),0)-1000 FROM history)")

    def history(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM history ORDER BY id DESC LIMIT 100")]

    def recover(self, now: float):
        # Never repeat a request whose transmission/acknowledgement is uncertain.
        with self.transaction():
            rows = self.db.execute("SELECT * FROM submissions WHERE status IN ('reserved','running')").fetchall()
            for r in rows:
                t = self.get(r["thread_id"])
                # The companion did not dispatch a native turn. Leave its
                # acknowledged slot for the native guard's terminal-history
                # check; the external scheduler always skips native bindings.
                if (t and r["status"] == "running" and r["id"] == "native-" + (r["turn_id"] or "")
                        and t["ack_turn"] == r["turn_id"] and json.loads(t["context"]).get("native_heartbeat")):
                    continue
                if t and t["state"] != State.COMPLETED:
                    self.update(r["thread_id"], State.PAUSED_FOR_USER,
                                "Previous continuation may have been sent. Inspect the conversation; no retry.",
                                now, eligible=False, next_check=None)
                self.db.execute("UPDATE submissions SET status='uncertain' WHERE id=?", (r["id"],))
            for t in self.tasks():
                if t["state"] == State.VERIFYING_ALLOWANCE:
                    self.update(t["thread_id"], State.WAITING_FOR_RESET, "Rechecking after restart", now, next_check=now)

    def close(self):
        with self.lock:
            self.db.close()

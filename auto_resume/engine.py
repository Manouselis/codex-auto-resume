"""Deterministic continuation controller with fresh included-usage preflight."""
import json
import threading
import time
import uuid

from .domain import Adapter, Observation, Request, State, TransientError, UnsafeError
from .policy import evaluate
from .store import Store
from .lifecycle import ControllerLock


class Engine:
    def __init__(self, store: Store, adapter: Adapter, clock=time.time, *, reserve=5,
                 verification_delay=5, max_attempts=3, max_retries=3):
        if not (type(verification_delay) is int and 1 <= verification_delay <= 300
                and type(max_attempts) is int and 1 <= max_attempts <= 10
                and type(max_retries) is int and 0 <= max_retries <= 5
                and type(reserve) is int and 0 <= reserve <= 99):
            raise ValueError("Invalid safety settings")
        self.store, self.adapter, self.clock = store, adapter, clock
        self.reserve, self.delay = reserve, verification_delay
        self.max_attempts, self.max_retries = max_attempts, max_retries
        self.lock = threading.Lock()
        self.last_quota_audit = 0

    def register(self, thread_id: str):
        # No context or private messages are copied from the original conversation.
        if not isinstance(thread_id, str) or not 1 <= len(thread_id) <= 128 or any(
                not (c.isalnum() or c in "-_") for c in thread_id):
            raise ValueError("Invalid conversation ID")
        obs = self.adapter.observe(thread_id)
        reason = self._valid_observation(obs)
        if reason:
            raise UnsafeError(reason)
        if obs.turn_status not in ("inProgress", "failed") or (
                obs.turn_status == "failed" and obs.error_code != "usageLimitExceeded"):
            raise UnsafeError("Only running tasks or structured usage-limit failures can be armed")
        self.store.register(obs, self.clock())

    def disarm(self, thread_id, reason="Task disarmed by user"):
        with self.store.transaction():
            t = self.store.get(thread_id)
            if t and t["state"] != State.COMPLETED:
                self.store.db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
                self.store.update(thread_id, State.PAUSED_FOR_USER, reason, self.clock(),
                                  eligible=False, next_check=None)

    def _valid_observation(self, obs: Observation):
        if not 0 <= self.clock() - obs.observed_at <= 30:
            return "Conversation state is stale or clock changed"
        if not obs.thread_id or not obs.turn_id or not obs.revision or not obs.config_hash:
            return "Conversation context is unavailable"
        if not obs.account_id or not obs.model:
            return "Account or model identity is unavailable"
        if not obs.history_available or not obs.project_exists:
            return "Original conversation history or project is unavailable"
        if obs.cancelled or obs.turn_status == "interrupted":
            return "Task was cancelled or interrupted by the user"
        if obs.approval_pending or obs.user_work_active:
            return "Waiting for user input, approval, or other user work"
        return None

    def _change(self, thread_id, state, reason, **values):
        with self.store.transaction():
            t = self.store.get(thread_id)
            if t and t["eligible"] and self.store.enabled:
                self.store.update(thread_id, state, reason, self.clock(), **values)

    def _pause(self, thread_id, reason, state=State.PAUSED_FOR_USER):
        self._change(thread_id, state, reason, eligible=False, next_check=None)

    def usage_changed(self, usage):
        """Accept only a complete authoritative snapshot from the adapter, not a sparse UI event."""
        for t in self.store.tasks():
            if not t["eligible"]:
                continue
            c = json.loads(t["context"])
            d = evaluate(usage, c["account_id"], tuple(c["bucket_ids"]), self.clock(), reserve=self.reserve)
            if d.kind == "weekly":
                self._pause(t["thread_id"], d.reason, State.WEEKLY_LIMIT_REACHED)

    def tick(self):
        # A second event is redundant. SQLite reservations also protect separate processes.
        if not self.lock.acquire(blocking=False):
            return
        try:
            if not self.store.enabled:
                return
            if (getattr(self.adapter, "live_execution", False)
                    and self.clock() - self.last_quota_audit >= 300
                    and any(t["eligible"] for t in self.store.tasks())):
                try:
                    self.usage_changed(self.adapter.usage())
                    self.last_quota_audit = self.clock()
                except (TransientError, UnsafeError):
                    pass
            for task in self.store.tasks():
                if not self.store.enabled:
                    return
                if task["eligible"]:
                    self._tick_task(task)
        finally:
            self.lock.release()

    def _tick_task(self, task):
        tid, now = task["thread_id"], self.clock()
        if task["next_check"] is not None and now < task["next_check"]:
            return
        generation = self.store.generation
        state = State(task["state"])
        if state not in (State.ARMED, State.RUNNING, State.WAITING_FOR_RESET):
            return
        try:
            obs = self.adapter.observe(tid)
            if self.store.generation != generation:
                return
            reason = self._valid_observation(obs)
            if reason:
                self._pause(tid, reason)
                return
            context = json.loads(task["context"])
            keys = ("thread_id", "account_id", "model", "cwd", "config_hash")
            if any(getattr(obs, key) != context[key] for key in keys) or tuple(context["bucket_ids"]) != obs.bucket_ids:
                self._pause(tid, "Conversation, account, model, project, or permissions changed")
                return
            expected_turn = task["ack_turn"] or context["turn_id"]
            if obs.turn_id != expected_turn:
                self._pause(tid, "A different turn started; the task may have been superseded")
                return
            if obs.turn_status == "completed" or obs.incomplete is False:
                self._change(tid, State.COMPLETED, "Task completed", eligible=False, next_check=None)
                self._finish_reservation(task)
                return
            if obs.incomplete is not True:
                self._pause(tid, "Unable to verify that the task remains unfinished")
                return
            if obs.turn_status == "inProgress":
                if state == State.WAITING_FOR_RESET:
                    self._pause(tid, "Codex is already working; automatic continuation cancelled")
                else:
                    self._change(tid, State.RUNNING, "Codex working", next_check=now + 30)
                return
            if obs.turn_status != "failed" or obs.error_code != "usageLimitExceeded":
                self._pause(tid, "The interruption is not a structured included usage-limit failure")
                return
            if state == State.WAITING_FOR_RESET and obs.revision != context["revision"]:
                self._pause(tid, "Conversation changed while waiting; rearm after inspection")
                return
            usage = self.adapter.usage()
            if self.store.generation != generation:
                return
            decision = evaluate(usage, context["account_id"], tuple(context["bucket_ids"]),
                                self.clock(), reserve=self.reserve, for_resume=state == State.WAITING_FOR_RESET)
            if decision.kind == "weekly":
                self._pause(tid, decision.reason, State.WEEKLY_LIMIT_REACHED)
                self._finish_reservation(task)
                return
            if decision.kind == "pause":
                if state == State.WAITING_FOR_RESET and decision.reason.startswith((
                        "Usage still reports exhaustion after reset", "Quota windows have expired",
                        "Unable to verify usage: ordinary included usage")):
                    self._retry(task)
                    return
                self._pause(tid, decision.reason)
                self._finish_reservation(task)
                return
            if state != State.WAITING_FOR_RESET:
                if decision.kind != "wait":
                    self._pause(tid, "No confirmed 5h interruption to recover")
                    return
                self._finish_reservation(task)
                with self.store.transaction():
                    current = self.store.get(tid)
                    if not current["eligible"] or not self.store.enabled or self.store.generation != generation:
                        return
                    self.store.db.execute("UPDATE tasks SET context=?,ack_turn=NULL WHERE thread_id=?",
                                          (json.dumps(obs.__dict__), tid))
                    self.store.update(tid, State.FIVE_HOUR_LIMIT_REACHED, decision.reason, now)
                    self.store.update(tid, State.WAITING_FOR_RESET, decision.reason, now,
                                      next_check=decision.reset_at + self.delay, retries=0)
                return
            self._change(tid, State.VERIFYING_ALLOWANCE, "Checking available usage")
            if decision.kind == "wait":
                self._change(tid, State.WAITING_FOR_RESET, decision.reason,
                             next_check=decision.reset_at + self.delay, retries=0)
                return
            if not (self.adapter.capabilities.safe or getattr(self.adapter, "live_execution", False)):
                self._pause(tid, "This adapter does not support continuation execution")
                return
            if task["attempts"] >= self.max_attempts:
                self._pause(tid, "Maximum automatic continuations reached")
                return
            self._submit(task, obs, generation)
        except TransientError:
            self._retry(task)
        except (UnsafeError, ValueError, KeyError, TypeError):
            self._pause(tid, "Unable to verify usage or conversation safely; inspect diagnostics")

    def _finish_reservation(self, task):
        if task["continuation_id"]:
            with self.store.transaction():
                self.store.db.execute("UPDATE submissions SET status='finished' WHERE id=? AND status='running'",
                                      (task["continuation_id"],))

    def _retry(self, task):
        n = task["retries"] + 1
        if n > self.max_retries:
            self._pause(task["thread_id"], "Unable to verify usage — paused after bounded retries")
            return
        state = State(self.store.get(task["thread_id"])["state"])
        if state == State.VERIFYING_ALLOWANCE:
            state = State.WAITING_FOR_RESET
        self._change(task["thread_id"], state, "Connection unavailable; scheduled a limited retry",
                     next_check=self.clock() + min(300, 15 * 2 ** (n - 1)), retries=n)

    def _submit(self, task, obs, generation):
        tid, now = task["thread_id"], self.clock()
        cid = str(uuid.uuid4())
        with self.store.transaction():
            current = self.store.get(tid)
            if not self.store.enabled or self.store.generation != generation or not current["eligible"]:
                return
            if current["state"] != State.VERIFYING_ALLOWANCE:
                return
            if self.store.db.execute("SELECT 1 FROM submissions WHERE status IN ('reserved','running','uncertain')").fetchone():
                self.store.update(tid, State.WAITING_FOR_RESET, "Another automatic task is working", now, next_check=now + 30)
                return
            self.store.db.execute("INSERT INTO submissions VALUES(?,?,?,NULL,?)", (cid, tid, "reserved", now))
            self.store.update(tid, State.RESUMING, "Resuming previous task", now,
                              continuation_id=cid, attempts=current["attempts"] + 1, next_check=None)
        # The durable reservation precedes the only submission. No automatic retries,
        # even if the process crashes before the call, or acknowledgement is lost.
        request = Request(cid, tid, obs.revision, obs.account_id, obs.model, obs.config_hash, obs.bucket_ids)
        try:
            if not self.store.enabled or not self.store.get(tid)["eligible"] or self.store.generation != generation:
                raise UnsafeError("Disarmed before dispatch")
            if getattr(self.adapter, "live_execution", False):
                self.adapter.check_enabled = lambda: (
                    self.store.enabled and self.store.generation == generation
                    and bool(self.store.get(tid)["eligible"])
                    and self.store.get(tid)["continuation_id"] == cid)
            turn_id = self.adapter.submit(request)
            if not isinstance(turn_id, str) or not turn_id:
                raise UnsafeError("Missing continuation acknowledgement")
        except Exception:
            with self.store.transaction():
                self.store.db.execute("UPDATE submissions SET status='uncertain' WHERE id=?", (cid,))
                current = self.store.get(tid)
                if current["state"] != State.COMPLETED:
                    self.store.update(tid, State.PAUSED_FOR_USER,
                                      "Continuation outcome uncertain; inspect the original conversation. No automatic retry.",
                                      self.clock(), eligible=False, next_check=None)
            return
        with self.store.transaction():
            self.store.db.execute("UPDATE submissions SET status='running',turn_id=? WHERE id=?", (turn_id, cid))
            current = self.store.get(tid)
            if current["eligible"] and self.store.enabled:
                self.store.update(tid, State.RUNNING, "Codex working", self.clock(), ack_turn=turn_id,
                                  retries=0, next_check=self.clock() + 30)


class Scheduler:
    """One idle thread. Re-evaluate wall time every 30s to tolerate sleep and clock changes."""
    def __init__(self, engine: Engine):
        self.engine = engine
        self.wake = threading.Event()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name="auto-resume-scheduler", daemon=True)
        self.last_error = None
        self.controller_lock = ControllerLock(engine.store.path)

    def start(self):
        self.controller_lock.acquire()
        self.engine.store.recover(self.engine.clock())
        self.thread.start()

    def _run(self):
        while not self.stopped.is_set():
            try:
                self.engine.tick()
            except Exception:
                # Unexpected failures stop scheduling, but leave Codex itself alone.
                self.last_error = "Background controller stopped after an unexpected error"
                self.engine.store.set_enabled(False, self.engine.clock())
                self.stopped.set()
            self.wake.wait(30)
            self.wake.clear()

    def stop(self):
        self.stopped.set()
        self.wake.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
        if not self.thread.is_alive():
            self.controller_lock.release()

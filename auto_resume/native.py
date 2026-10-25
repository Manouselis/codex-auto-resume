"""Fresh admission guards for turns started by Codex's native heartbeat scheduler.

This module never starts a model turn. The native scheduler owns the writer;
the guard grants or refuses substantive work inside that already admitted turn.
"""
import json
import time

from .checkpoints import context_checkpoint
from .domain import State, UnsafeError
from .policy import evaluate
from .native_schedule import schedule_status


class NativeController:
    def __init__(self, store, adapter, clock=time.time, *, native_schedule_check=schedule_status):
        self.store, self.adapter, self.clock = store, adapter, clock
        self.native_schedule_check = native_schedule_check

    def _paused(self, task, reason, state=State.PAUSED_FOR_USER):
        with self.store.transaction():
            current = self.store.get(task["thread_id"])
            if current and current["eligible"] and current["state"] != State.COMPLETED:
                self.store.update(task["thread_id"], state, reason, self.clock(), eligible=False, next_check=None)
        return {"action": "pause", "reason": reason}

    def _is_native_wake(self, thread_id, turn_id, automation_id):
        page = self.adapter.rpc.call("thread/items/list", {"threadId": thread_id,
            "turnId": turn_id, "sortDirection": "asc", "limit": 10})
        marker = "[codex-auto-resume:native-heartbeat=" + automation_id + "]"
        for entry in page.get("data", []):
            item = entry.get("item") or {}
            if item.get("type") != "userMessage":
                continue
            text = item.get("text")
            if not isinstance(text, str):
                content = item.get("content") or []
                text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
            if marker in text.splitlines():
                return True
        return False

    def _tracked_stop(self, thread_id, turn_id, *, automation_id=None, current_turn_id=None, authorized_baseline=None):
        cursor = None
        turn = None
        intervening = []
        baseline_seen = authorized_baseline is None
        for _ in range(20):
            params = {"threadId": thread_id, "sortDirection": "desc", "limit": 100, "itemsView": "notLoaded"}
            if cursor:
                params["cursor"] = cursor
            page = self.adapter.rpc.call("thread/turns/list", params)
            data = page.get("data")
            if not isinstance(data, list):
                raise UnsafeError("Prior native turn metadata is unavailable")
            for item in data:
                if item.get("id") == authorized_baseline:
                    baseline_seen = True
                if item.get("id") == turn_id:
                    turn = item
                    break
                if item.get("id") != current_turn_id and (authorized_baseline is None or not baseline_seen):
                    intervening.append(item.get("id"))
            if turn:
                break
            cursor = page.get("nextCursor")
            if not cursor:
                break
        if not turn or not baseline_seen:
            raise UnsafeError("The tracked native turn is unavailable")
        if automation_id and any(not self._is_native_wake(thread_id, other, automation_id) for other in intervening):
            return False
        status = turn.get("status")
        error = turn.get("error") or {}
        if status == "failed" and isinstance(error, dict) and error.get("codexErrorInfo") in (
                "usageLimitExceeded", "contextWindowExceeded"):
            return True
        if status != "completed":
            return False
        page = self.adapter.rpc.call("thread/items/list", {"threadId": thread_id,
            "turnId": turn_id, "sortDirection": "desc", "limit": 10})
        entries = page.get("data")
        if not isinstance(entries, list):
            raise UnsafeError("Prior native checkpoint is unavailable")
        turn = {**turn, "items": [entry["item"] for entry in reversed(entries)
                                  if isinstance(entry, dict) and isinstance(entry.get("item"), dict)]}
        return context_checkpoint(turn)

    def claim(self, thread_id, automation_id):
        task = self.store.get(thread_id)
        if not self.store.enabled:
            return {"action": "pause", "reason": "Auto-Resume is OFF"}
        if not task:
            return {"action": "pause", "reason": "This conversation has not been armed in Auto-Resume"}
        if not task["eligible"]:
            return {"action": "pause", "reason": "This task is disarmed: " + task["reason"]}
        context = json.loads(task["context"])
        if not automation_id or context.get("native_heartbeat") != automation_id:
            return {"action": "pause", "reason": "Native heartbeat identity does not match the arming"}
        status, reason = self.native_schedule_check(automation_id, thread_id)
        if status == "PAUSED":
            return {"action": "wait", "reason": reason}
        if status != "ACTIVE":
            return self._paused(task, reason)
        arming = {"registered_at": context.get("armed_at"), "monitored_turn": context["turn_id"],
                  "scope": "This explicit arming supersedes earlier schedule cancellations; newer user activity still blocks admission"}
        generation = self.store.generation
        obs = self.adapter.observe(thread_id)
        if (not 0 <= self.clock() - obs.observed_at <= 30 or not obs.history_available
                or not obs.project_exists or obs.cancelled or obs.approval_pending or obs.user_work_active):
            return self._paused(task, "Native conversation is unavailable, cancelled or waiting for user action")
        if any(getattr(obs, key) != context[key] for key in ("thread_id", "account_id", "model", "cwd", "config_hash")) or tuple(context["bucket_ids"]) != obs.bucket_ids:
            return self._paused(task, "Native account, model, project or original configuration changed")
        if not self.adapter.goal_allows_continuation(thread_id):
            return self._paused(task, "Native goal is paused, terminal or its configured budget is unavailable/exhausted")
        if obs.turn_status not in ("inProgress", "unresolved"):
            return {"action": "wait", "reason": "The guard must run inside a new native heartbeat turn"}
        native_id = "native-" + obs.turn_id
        previous = self.store.db.execute("SELECT status FROM submissions WHERE id=?", (native_id,)).fetchone()
        if previous and previous["status"] != "running":
            return {"action": "pause", "reason": "This native work turn has already finished its guard lifecycle"}
        tracked_turn = task["ack_turn"] or context["turn_id"]
        if obs.turn_id == tracked_turn and not previous:
            return {"action": "wait", "reason": "No new native heartbeat turn has started"}
        if not self._is_native_wake(thread_id, obs.turn_id, automation_id):
            return self._paused(task, "The current turn is not the configured native heartbeat")
        saved_checkpoint = context.get("native_checkpoint_turn") if not task["ack_turn"] else None
        if not previous and not self._tracked_stop(thread_id, saved_checkpoint or tracked_turn,
                automation_id=automation_id, current_turn_id=obs.turn_id,
                authorized_baseline=context["turn_id"] if saved_checkpoint else None):
            return self._paused(task, "The tracked turn ended without a recognized checkpoint or usage-limit failure")
        decision = evaluate(self.adapter.usage(), context["account_id"], tuple(context["bucket_ids"]), self.clock())
        if decision.kind == "weekly":
            return self._paused(task, decision.reason, State.WEEKLY_LIMIT_REACHED)
        if decision.kind == "wait":
            return {"action": "wait", "reason": decision.reason, "reset_at": decision.reset_at}
        if decision.kind != "ready":
            return self._paused(task, decision.reason)
        self.adapter._financial_config(obs.cwd)
        with self.store.transaction():
            current = self.store.get(thread_id)
            if not self.store.enabled or not current["eligible"] or self.store.generation != generation:
                return {"action": "pause", "reason": "Arming changed during native preflight"}
            if previous:
                return {"action": "continue", "reason": "Fresh guards passed for the reserved native work turn",
                        "attempt": current["attempts"], "arming": arming}
            maximum = context.get("native_max_attempts", 10)
            if type(maximum) is not int or not 1 <= maximum <= 10 or current["attempts"] >= maximum:
                self.store.update(thread_id, State.PAUSED_FOR_USER, "Native work-turn limit reached", self.clock(), eligible=False, next_check=None)
                return {"action": "pause", "reason": "Native work-turn limit reached"}
            # A prior admitted native turn is known terminal before its slot is
            # released. Unknown external dispatch outcomes continue to block.
            self.store.db.execute("UPDATE submissions SET status='finished' WHERE thread_id=? AND turn_id=? AND id LIKE 'native-%' AND status='running'", (thread_id, tracked_turn))
            if self.store.db.execute("SELECT 1 FROM submissions WHERE status IN ('reserved','running','uncertain')").fetchone():
                return {"action": "wait", "reason": "Another automatic submission is outstanding or uncertain"}
            self.store.db.execute("INSERT INTO submissions VALUES(?,?,?,?,?)", (native_id, thread_id, "running", obs.turn_id, self.clock()))
            self.store.update(thread_id, State.VERIFYING_ALLOWANCE, "Native included-usage guard passed", self.clock())
            self.store.update(thread_id, State.RESUMING, "Admitting the existing native heartbeat work turn", self.clock())
            self.store.update(thread_id, State.RUNNING, "Native research turn admitted", self.clock(),
                              continuation_id=native_id, ack_turn=obs.turn_id,
                              attempts=current["attempts"] + 1, next_check=None)
            return {"action": "continue", "reason": "Fresh included usage and native checkpoint guard passed",
                    "attempt": current["attempts"] + 1, "maximum": maximum, "arming": arming}

    def finish(self, thread_id, automation_id, outcome):
        if outcome not in ("checkpoint", "complete", "blocked"):
            raise ValueError("Unsupported native outcome")
        task = self.store.get(thread_id)
        if not task or json.loads(task["context"]).get("native_heartbeat") != automation_id:
            raise UnsafeError("Native heartbeat identity does not match")
        obs = self.adapter.observe(thread_id)
        if obs.turn_id != task["ack_turn"] or task["continuation_id"] != "native-" + obs.turn_id:
            raise UnsafeError("The native work reservation does not match this turn")
        with self.store.transaction():
            self.store.db.execute("UPDATE submissions SET status='finished' WHERE id=? AND status='running'", (task["continuation_id"],))
            current = self.store.get(thread_id)
            if not self.store.enabled or not current["eligible"]:
                return {"outcome": outcome, "armed": False}
            if outcome == "checkpoint":
                status, reason = self.native_schedule_check(automation_id, thread_id)
                if status not in ("ACTIVE", "PAUSED"):
                    self.store.update(thread_id, State.PAUSED_FOR_USER, reason, self.clock(), eligible=False, next_check=None)
                    return {"outcome": outcome, "armed": False}
                state = State.ARMED if status == "ACTIVE" else State.WAITING_FOR_SCHEDULE
                self.store.update(thread_id, state, "Native checkpoint saved; waiting for the next native wake-up" if status == "ACTIVE" else reason, self.clock(), next_check=None)
            else:
                state = State.COMPLETED if outcome == "complete" else State.PAUSED_FOR_USER
                self.store.update(thread_id, state, "Native objective completion reported" if outcome == "complete" else "Native work needs user input or approval", self.clock(), eligible=False, next_check=None)
        return {"outcome": outcome, "armed": outcome == "checkpoint"}

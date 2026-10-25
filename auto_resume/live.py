"""Real same-thread continuation through the official persistent App Server.

Safety is enforced by fresh preflight checks and the service's own quota limits.
It is not a claim of atomic billing reservation or remote exactly-once execution.
"""
import hashlib
import json
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .domain import Capabilities, NotSentError, Observation, Request, UnsafeError, Usage, WriterConflictError
from .policy import evaluate
from .protocol import READ_METHODS
from .protocol import find_codex
from .websocket import DaemonRpc
from .checkpoints import context_checkpoint, final_text


LIVE_METHODS = READ_METHODS | {"config/read", "thread/list", "thread/loaded/list", "thread/goal/get", "thread/resume", "turn/start",
                             "thread/items/list"}


class LiveRpc(DaemonRpc):
    """Disconnecting never terminates the daemon's running Codex turn."""
    methods = LIVE_METHODS


class LiveAdapter:
    live_execution = True
    # These old fields describe atomic guarantees the protocol does not provide.
    # Engine dispatch instead requires this adapter's live preflight, not invented guarantees.
    capabilities = Capabilities()

    def __init__(self, rpc=None, clock=time.time):
        self.rpc = rpc or LiveRpc()
        self.clock = clock
        self.guard = threading.RLock()
        self.pending = {}
        self.subscribed = set()
        self.check_enabled = lambda: False  # Bound by Engine; fail closed before binding.
        self.on_dispatch_stage = lambda stage: None

    def _events(self):
        events = getattr(self.rpc, "events", None)
        if events is None:
            return
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                return
            params = event.get("params") or {}
            if "id" in event:
                self.pending[event["id"]] = params.get("threadId")
            elif event.get("method") == "serverRequest/resolved":
                self.pending.pop(params.get("requestId"), None)

    def usage(self):
        account = self.rpc.call("account/read", {"refreshToken": False}).get("account")
        if not isinstance(account, dict) or account.get("type") != "chatgpt" or account.get("planType") != "plus":
            raise UnsafeError("Included ChatGPT Plus authentication is required; API authentication is refused")
        payload = self.rpc.call("account/rateLimits/read")
        if not isinstance(payload.get("accountId"), str) or not payload["accountId"]:
            raise UnsafeError("The backend did not validate the current account identity")
        return Usage(payload, self.clock(), "chatgpt")

    def ensure_daemon(self):
        try:
            subprocess.run([find_codex(), "app-server", "daemon", "start"], capture_output=True,
                           timeout=30, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise UnsafeError("Unable to start the official local Codex App Server") from exc
        self.usage()
        return "Codex connected. Choose the original conversation and arm it."

    @staticmethod
    def bucket_ids(usage):
        buckets = usage.payload.get("rateLimitsByLimitId")
        if not isinstance(buckets, dict) or not buckets:
            raise UnsafeError("Authoritative quota buckets are unavailable")
        # Check EVERY reported bucket. This is deliberately stricter than guessing
        # which normal model or alias applies to a single 'primary' quota.
        return tuple(sorted(buckets))

    def _read(self, thread_id):
        thread = self.rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False}).get("thread")
        if not isinstance(thread, dict) or thread.get("id") != thread_id:
            raise UnsafeError("Original conversation is unavailable")
        if thread.get("historyMode") == "paginated":
            page = self.rpc.call("thread/turns/list", {"threadId": thread_id, "sortDirection": "desc",
                                                       "limit": 1, "itemsView": "full"})
            turns = page.get("data")
            latest = turns[0] if isinstance(turns, list) and turns else None
        else:
            thread = self.rpc.call("thread/read", {"threadId": thread_id, "includeTurns": True}).get("thread")
            turns = thread.get("turns") if isinstance(thread, dict) else None
            latest = turns[-1] if isinstance(turns, list) and turns else None
        if not isinstance(latest, dict) or not latest.get("id"):
            raise UnsafeError("Original turn history is unavailable")
        return thread, latest

    @staticmethod
    def _config(thread):
        # The saved configuration is restored by thread/resume without overrides.
        # This fingerprint pins available metadata, not an invented permission API.
        values = {k: thread.get(k) for k in ("id", "model", "modelProvider", "cwd", "reasoningEffort")}
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def confirmed_terminal_turn(self, thread_id, turn_id):
        """Prove an acknowledged turn ended; an external open marker is not proof."""
        cursor = None
        for _ in range(20):
            params = {"threadId": thread_id, "sortDirection": "desc", "limit": 100, "itemsView": "notLoaded"}
            if cursor:
                params["cursor"] = cursor
            page = self.rpc.call("thread/turns/list", params)
            turns = page.get("data")
            if not isinstance(turns, list):
                raise UnsafeError("Cannot verify the reserved turn history")
            for turn in turns:
                if turn.get("id") == turn_id:
                    ended = turn.get("completedAt")
                    return (turn.get("status") in ("completed", "failed", "interrupted")
                            and type(ended) in (int, float) and 0 < ended <= self.clock())
            cursor = page.get("nextCursor")
            if not cursor:
                break
        return False

    def goal_allows_continuation(self, thread_id):
        response = self.rpc.call("thread/goal/get", {"threadId": thread_id})
        if not isinstance(response, dict) or "goal" not in response:
            raise UnsafeError("Cannot verify the conversation goal state")
        goal = response["goal"]
        if goal is None:
            return True
        if not isinstance(goal, dict):
            raise UnsafeError("Cannot verify the conversation goal state")
        budget, spent = goal.get("tokenBudget"), goal.get("tokensUsed")
        return goal.get("status") == "active" and (budget is None or (
            type(budget) is int and budget > 0 and type(spent) is int and 0 <= spent < budget))

    def observe(self, thread_id):
        with self.guard:
            self._events()
            usage = self.usage()
            thread, latest = self._read(thread_id)
            status = thread.get("status") or {}
            model = thread.get("model")
            cwd = thread.get("cwd")
            if not model or thread.get("modelProvider") != "openai":
                raise UnsafeError("Only the original OpenAI model with included ChatGPT authentication is supported")
            error = latest.get("error") or {}
            if not isinstance(error, dict):
                raise UnsafeError("Original turn error metadata is invalid")
            checkpoint = context_checkpoint(latest)
            goal_blocked = False
            if checkpoint:
                goal_blocked = not self.goal_allows_continuation(thread_id)
            revision_data = {k: latest.get(k) for k in ("id", "status", "error", "completedAt")}
            if checkpoint:
                revision_data["checkpoint"] = hashlib.sha256(final_text(latest).encode()).hexdigest()
            revision = hashlib.sha256(json.dumps(revision_data, sort_keys=True).encode()).hexdigest()
            # notLoaded describes this reader's runtime, not the desktop's.
            # Its stored-history reconstruction can label an open external turn
            # interrupted, even while the desktop is still executing it.
            unresolved = (status.get("type") == "notLoaded"
                          and latest.get("status") in ("interrupted", "inProgress")
                          and latest.get("completedAt") is None
                          and latest.get("error") is None)
            return Observation(thread_id, usage.payload["accountId"], model, self.bucket_ids(usage), cwd or "",
                               self._config(thread), latest["id"],
                               "unresolved" if unresolved else latest.get("status", "unknown"),
                               error.get("codexErrorInfo"), revision, self.clock(),
                               project_exists=bool(cwd and Path(cwd).is_dir()),
                               approval_pending=bool(status.get("activeFlags")) or thread_id in self.pending.values(),
                               user_work_active=goal_blocked,
                               cancelled=latest.get("status") == "interrupted" and not unresolved,
                               incomplete=None if unresolved else latest.get("status") in ("inProgress", "failed"),
                               external_unresolved=unresolved,
                               stop_reason="context_budget" if checkpoint else None,
                               name=thread.get("name") or "")

    def _financial_config(self, cwd):
        config = self.rpc.call("config/read", {"cwd": cwd, "includeLayers": False}).get("config")
        if not isinstance(config, dict):
            raise UnsafeError("Cannot verify provider configuration")
        if config.get("model_provider") not in (None, "openai"):
            raise UnsafeError("Custom or API model providers are refused")
        if config.get("service_tier") not in (None, "default"):
            raise UnsafeError("A non-default speed/billing tier is configured")
        chatgpt_url = config.get("chatgpt_base_url")
        if config.get("openai_base_url") or chatgpt_url not in (
                None, "https://chatgpt.com/backend-api/", "https://chatgpt.com/backend-api"):
            raise UnsafeError("Custom inference endpoints are refused")
        providers = config.get("model_providers") or {}
        if not isinstance(providers, dict) or providers.get("openai"):
            raise UnsafeError("An OpenAI provider override prevents included-usage verification")

    def _preflight(self, request, *, automatic=True):
        if request.included_only is not True:
            raise UnsafeError("Only included-usage continuation requests are permitted")
        if automatic and not self.check_enabled():
            raise UnsafeError("Auto-Resume was disabled or this task was disarmed")
        obs = self.observe(request.thread_id)
        expected = (request.expected_revision, request.expected_account_id, request.expected_model,
                    request.expected_config_hash, request.bucket_ids)
        actual = (obs.revision, obs.account_id, obs.model, obs.config_hash, obs.bucket_ids)
        if obs.external_unresolved:
            raise UnsafeError("The current turn has no confirmed result; no continuation will be sent")
        if expected != actual or obs.approval_pending or obs.user_work_active or not obs.project_exists or obs.cancelled:
            raise UnsafeError("The account, model, task, project, or original context changed")
        if obs.turn_status == "inProgress":
            raise UnsafeError("Another turn is active; no continuation will be sent")
        if automatic:
            if request.trigger == "usage_limit":
                if obs.turn_status != "failed" or obs.error_code != "usageLimitExceeded":
                    raise UnsafeError("Only a structured usage-limit interruption may automatically continue")
            elif request.trigger == "context_budget":
                if obs.stop_reason != "context_budget" or obs.turn_status not in ("completed", "failed"):
                    raise UnsafeError("The context-budget checkpoint is no longer confirmed")
            else:
                raise UnsafeError("Unsupported continuation trigger")
        usage = self.usage()
        decision = evaluate(usage, request.expected_account_id, request.bucket_ids, self.clock())
        if decision.kind != "ready":
            raise UnsafeError(decision.reason)
        self._financial_config(obs.cwd)
        return obs

    def _dispatch(self, request, *, automatic=True):
        """One real request; no replay of the original prompt and no submission retry."""
        with self.guard:
            self.on_dispatch_stage("Checking continuation preflight")
            try:
                obs = self._preflight(request, automatic=automatic)
            except Exception as exc:
                reason = str(exc) if isinstance(exc, UnsafeError) else "Continuation preflight failed; no model request was sent"
                raise NotSentError(reason) from exc
            self.on_dispatch_stage("Restoring the original conversation")
            try:
                resumed = self.rpc.call("thread/resume", {"threadId": request.thread_id, "excludeTurns": True})
            except WriterConflictError as exc:
                raise NotSentError("The desktop owns this conversation. Use native scheduled recovery; no model request was sent") from exc
            except Exception as exc:
                raise NotSentError("Conversation restoration failed; no model request was sent") from exc
            if (resumed.get("model"), resumed.get("modelProvider"), resumed.get("cwd")) != (
                    obs.model, "openai", obs.cwd):
                raise NotSentError("Restored conversation identity/configuration changed; no model request was sent")
            if resumed.get("serviceTier") not in (None, "default"):
                raise NotSentError("The original conversation uses a non-default billing/speed tier")
            if not isinstance(resumed.get("sandbox"), dict) or "approvalPolicy" not in resumed:
                raise NotSentError("Cannot verify the restored sandbox and approval policy")
            self.subscribed.add(request.thread_id)
            # Re-read after loading. No model, sandbox or approval override is sent.
            try:
                self._preflight(request, automatic=automatic)
            except Exception as exc:
                raise NotSentError("Restored preflight failed; no model request was sent") from exc
            if automatic and not self.check_enabled():
                raise NotSentError("Disarmed immediately before dispatch")
            self.on_dispatch_stage("Sending one continuation")
            result = self.rpc.call("turn/start", {
                "threadId": request.thread_id, "clientUserMessageId": request.continuation_id,
                "input": [{"type": "text", "text": request.text}],
                "turnTrigger": "codex-auto-resume" if automatic else "codex-auto-resume-live-verification"
            })
            turn_id = (result.get("turn") or {}).get("id")
            if not turn_id:
                raise UnsafeError("Continuation acknowledgement is unavailable; do not retry")
            return turn_id

    def submit(self, request):
        return self._dispatch(request)

    def recent_threads(self):
        page = self.rpc.call("thread/list", {"limit": 30, "sortKey": "updated_at", "sourceKinds": [],
                                              "modelProviders": ["openai"]})
        return [{"id": t["id"], "name": t.get("name") or "Untitled conversation"}
                for t in page.get("data", []) if t.get("id")]

    def close(self):
        # Only the proxy connection closes. The persistent daemon retains live work.
        self.rpc.close()


def manual_request(obs, text):
    """Explicit verification/manual continuation; never called by the automatic scheduler."""
    return Request(str(uuid.uuid4()), obs.thread_id, obs.revision, obs.account_id, obs.model,
                   obs.config_hash, obs.bucket_ids, text=text)

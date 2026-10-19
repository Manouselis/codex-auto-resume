"""Optional read-only observer and isolated test simulator. See live.py for real continuation."""
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

from .domain import Capabilities, Observation, Request, UnsafeError, Usage
from .policy import evaluate
from .protocol import ReadOnlyRpc


class CodexObserver:
    capabilities = Capabilities()  # No setting, CLI flag, or manifest may enable live execution.

    def __init__(self, rpc=None, clock=time.time):
        self.rpc, self.clock = rpc or ReadOnlyRpc(), clock

    def usage(self):
        a = self.rpc.call("account/read", {"refreshToken": False}).get("account")
        if not isinstance(a, dict) or a.get("type") != "chatgpt" or a.get("planType") != "plus":
            raise UnsafeError("A signed-in ChatGPT Plus account is required")
        p = self.rpc.call("account/rateLimits/read")
        # Arrival time applies only to this request; sparse notifications are not reused.
        return Usage(p, self.clock(), a["type"])

    def observe(self, thread_id):
        u = self.usage()
        response = self.rpc.call("thread/read", {"threadId": thread_id, "includeTurns": True})
        thread = response.get("thread")
        if not isinstance(thread, dict) or thread.get("id") != thread_id:
            raise UnsafeError("Original conversation is unavailable")
        turns = thread.get("turns")
        if not isinstance(turns, list) or not turns:
            raise UnsafeError("Conversation history is unavailable; cannot recover context")
        latest = turns[-1]
        if not isinstance(latest, dict):
            raise UnsafeError("Unsupported turn history")
        status = thread.get("status") or {}
        model = thread.get("model") or ""
        buckets = u.payload.get("rateLimitsByLimitId") or {}
        # Do not guess that every model uses 'codex'. Absence means unverifiable.
        binding = tuple(sorted(key for key, b in buckets.items() if isinstance(b, dict)
                               and b.get("normalModelSlug") == model and model))
        digest = hashlib.sha256(json.dumps(thread, sort_keys=True).encode()).hexdigest()
        error = latest.get("error") or {}
        cwd = thread.get("cwd") or ""
        return Observation(thread_id, u.payload.get("accountId") or "", model, binding, cwd,
                           "unverified-permissions:" + digest, latest.get("id") or "",
                           latest.get("status") or "unknown", error.get("codexErrorInfo"), digest,
                           self.clock(), history_available=thread.get("historyMode", "legacy") == "legacy",
                           project_exists=bool(cwd and Path(cwd).is_dir()),
                           approval_pending=bool(status.get("activeFlags")),
                           user_work_active=status.get("type") == "notLoaded",
                           cancelled=latest.get("status") == "interrupted",
                           incomplete=latest.get("status") in ("inProgress", "failed"))

    def submit(self, request: Request):
        raise UnsafeError("This observer is read-only; use LiveAdapter for real continuation")

    def close(self):
        self.rpc.close()


def fake_payload(now, *, five=100, weekly=30, ordinary=False):
    """Invented account ID and model binding, never imported from the user's account."""
    b = {"limitId": "codex", "planType": "plus", "normalModelSlug": "simulation-model",
         "primary": {"windowDurationMins": 300, "usedPercent": five,
                     "resetsAt": int(now + (20 if five >= 100 else 18000))},
         "secondary": {"windowDurationMins": 10080, "usedPercent": weekly, "resetsAt": int(now + 86400)},
         "credits": {"hasCredits": False, "unlimited": False, "balance": "0"},
         "spendControlReached": False, "individualLimit": None,
         "rateLimitReachedType": "rate_limit_reached" if five >= 100 else None}
    return {"ordinaryUsageAllowed": ordinary, "accountId": "simulation-account",
            "rateLimits": b, "rateLimitsByLimitId": {"codex": b},
            "rateLimitResetCredits": {"availableCount": 1, "credits": None}}


class SimulationAdapter:
    """All execution is in memory. This cannot create a Codex process or send a model request."""
    capabilities = Capabilities(True, True, True, True)

    def __init__(self, clock=time.time, cwd=None):
        self.clock = clock
        self.payload = fake_payload(clock())
        self.observations = {"demo-task": Observation(
            "demo-task", "simulation-account", "simulation-model", ("codex",),
            str(Path(cwd or ".").resolve()), "simulation-permissions", "demo-failed-turn", "failed",
            "usageLimitExceeded", "demo-revision", clock())}
        self.requests = []
        self.acks = {}

    def observe(self, thread_id):
        if thread_id not in self.observations:
            raise UnsafeError("Simulation conversation does not exist")
        return replace(self.observations[thread_id], observed_at=self.clock())

    def usage(self):
        return Usage(self.payload, self.clock(), "chatgpt")

    def reset(self, *, weekly=30):
        self.payload = fake_payload(self.clock(), five=5, weekly=weekly, ordinary=weekly < 100)

    def submit(self, request):
        if request.continuation_id in self.acks:
            return self.acks[request.continuation_id]
        obs = self.observe(request.thread_id)
        if not request.included_only or (
                obs.revision, obs.account_id, obs.model, obs.config_hash, obs.bucket_ids) != (
                request.expected_revision, request.expected_account_id, request.expected_model,
                request.expected_config_hash, request.bucket_ids):
            raise UnsafeError("Simulated atomic precondition rejected")
        if obs.turn_status != "failed" or obs.cancelled or obs.approval_pending or obs.user_work_active:
            raise UnsafeError("Simulated turn is no longer eligible")
        decision = evaluate(self.usage(), obs.account_id, obs.bucket_ids, self.clock(), reserve=0)
        if decision.kind != "ready":
            raise UnsafeError("Simulated backend rejected included-only execution")
        self.requests.append(request)
        turn = "simulation-turn-" + str(len(self.requests))
        self.acks[request.continuation_id] = turn
        self.observations[request.thread_id] = replace(obs, turn_id=turn, turn_status="inProgress",
                                                    error_code=None, revision=turn)
        return turn

    def complete(self, thread_id="demo-task"):
        self.observations[thread_id] = replace(self.observe(thread_id), turn_status="completed", incomplete=False)

    def close(self):
        pass

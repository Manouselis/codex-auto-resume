"""Strict interpretation of authoritative snapshots. Timestamps never authorize execution."""
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .domain import Usage


@dataclass(frozen=True)
class Decision:
    kind: str  # ready, wait, weekly, pause
    reason: str
    reset_at: int | None = None


def number(value, low, high) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def evaluate(usage: Usage, account_id: str, bucket_ids: tuple[str, ...], now: float,
             *, reserve: int = 5, max_age: int = 30, for_resume: bool = True) -> Decision:
    """Require an explicit model/bucket binding supplied by a trusted adapter.

    This intentionally accepts fewer accounts than Codex: Plus, exactly the two
    documented windows, no credit balance, no unknown spend control. An adapter
    must additionally revalidate the actual execution route before submission.
    """
    pause = lambda message: Decision("pause", message)
    if not number(reserve, 0, 99) or not number(max_age, 1, 300):
        return pause("Invalid safety settings.")
    if not number(usage.fetched_at, 0, now) or now - usage.fetched_at > max_age:
        return pause("Unable to verify usage: snapshot is stale or clock changed.")
    if usage.auth_mode != "chatgpt":
        return pause("Included ChatGPT authentication is required.")
    p = usage.payload
    if not isinstance(p, dict) or not account_id or p.get("accountId") != account_id:
        return pause("Unable to verify usage: account identity changed or is missing.")
    buckets = p.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict) or not bucket_ids or len(set(bucket_ids)) != len(bucket_ids):
        return pause("Unable to verify the selected model's quota buckets.")
    windows = []
    financial_problem = None
    for key in bucket_ids:
        b = buckets.get(key)
        if not isinstance(b, dict) or b.get("limitId") != key or b.get("planType") != "plus":
            return pause("Quota identity or supported plan changed.")
        pair = {}
        for name in ("primary", "secondary"):
            w = b.get(name)
            if not isinstance(w, dict):
                return pause("Both the 5h and weekly windows must be available.")
            duration = w.get("windowDurationMins")
            if type(duration) is not int or duration not in (300, 10080) or duration in pair:
                return pause("Unsupported or ambiguous quota windows.")
            if not number(w.get("usedPercent"), 0, 100):
                return pause("Invalid usage percentage.")
            reset = w.get("resetsAt")
            if type(reset) is not int or not 0 < reset <= now + 366 * 86400:
                return pause("Missing or invalid official reset time.")
            pair[duration] = w
        windows.append(pair)
        credits = b.get("credits")
        try:
            balance = Decimal(credits["balance"]) if isinstance(credits, dict) and isinstance(credits.get("balance"), str) else None
            credit_safe = (isinstance(credits, dict) and credits.get("hasCredits") is False
                           and credits.get("unlimited") is False and balance is not None
                           and balance.is_finite() and balance == 0)
        except (InvalidOperation, ValueError):
            credit_safe = False
        if not credit_safe:
            financial_problem = "Unable to exclude paid credits: balance is nonzero or unknown."
        if b.get("spendControlReached") is not False or b.get("individualLimit") is not None:
            financial_problem = "Unable to verify spend controls."
        if b.get("rateLimitReachedType") not in (None, "rate_limit_reached"):
            financial_problem = "Unsupported credit or workspace limit."
    # Weekly exhaustion is a sticky hard stop even if ordinaryUsageAllowed is false.
    if any(w[10080]["usedPercent"] >= 100 for w in windows):
        return Decision("weekly", "Weekly limit reached. Rearm this task manually after recovery.")
    if any(100 - w[10080]["usedPercent"] <= reserve for w in windows):
        return pause("Weekly usage is below the configured reserve.")
    if financial_problem:
        return pause(financial_problem)
    exhausted = [w[300] for w in windows if w[300]["usedPercent"] >= 100]
    if exhausted:
        reset = max(w["resetsAt"] for w in exhausted)
        if reset <= now:
            return pause("Usage still reports exhaustion after reset; fresh authorization is required.")
        return Decision("wait", "5h limit reached — waiting for reset", reset)
    if any(w[d]["resetsAt"] <= now for w in windows for d in (300, 10080)):
        return pause("Quota windows have expired; unable to verify current allowance.")
    if p.get("ordinaryUsageAllowed") is not True:
        return pause("Unable to verify usage: ordinary included usage is not authorized.")
    if for_resume and any(buckets[k].get("rateLimitReachedType") is not None for k in bucket_ids):
        return pause("Backend still reports a limit interruption.")
    return Decision("ready", "Included allowance is available; execution safeguards must also pass.")

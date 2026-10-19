#!/usr/bin/env python3
"""Explicit two-turn real-backend check. Never exhausts quota or fakes a reset.

Run with --run only when genuine included model usage for verification is wanted.
It creates one dedicated harmless thread and verifies continuation of its context.
"""
import argparse
import json
import queue
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto_resume.live import LiveAdapter, LiveRpc, manual_request
from auto_resume.domain import UnsafeError
from auto_resume.policy import evaluate


class VerificationRpc(LiveRpc):
    def call(self, method, params=None):
        if method == "thread/start":
            with self.lock:
                if self.connection is None:
                    self._start()
                return self._call(method, params or {})
        return super().call(method, params)


def wait_for_completion(rpc, thread_id, turn_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            event = rpc.events.get(timeout=min(30, max(0.01, deadline - time.monotonic())))
        except queue.Empty:
            continue
        params = event.get("params") or {}
        if "id" in event:
            raise UnsafeError("Verification requested approval; no approval was given")
        turn = params.get("turn") or {}
        if event.get("method") == "turn/completed" and params.get("threadId") == thread_id and turn.get("id") == turn_id:
            if turn.get("status") != "completed":
                raise UnsafeError("The real verification turn did not complete successfully")
            return turn
    raise UnsafeError("Verification timed out; no request will be retried")


def verify():
    adapter = LiveAdapter(VerificationRpc())
    try:
        usage = adapter.usage()
        ids = adapter.bucket_ids(usage)
        decision = evaluate(usage, usage.payload["accountId"], ids, time.time())
        if decision.kind != "ready":
            raise UnsafeError(decision.reason)
        token = "CONTEXT_" + uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix="codex-auto-resume-live-check-") as folder:
            adapter._financial_config(folder)
            created = adapter.rpc.call("thread/start", {"cwd": folder, "modelProvider": "openai",
                                                        "sandbox": "read-only", "approvalPolicy": "on-request"})
            thread_id = created["thread"]["id"]
            first = adapter.rpc.call("turn/start", {"threadId": thread_id,
                "input": [{"type": "text", "text": "This is part one of a two-part context-continuation test. "
                           f"Remember this exact token: {token}. Reply with READY only. Do not use tools."}]})
            wait_for_completion(adapter.rpc, thread_id, first["turn"]["id"])
            observation = adapter.observe(thread_id)
            request = manual_request(observation,
                "Continue part two of the context-continuation test. Reply only with the exact token "
                "you were asked to remember in the previous turn. Do not use tools.")
            second_id = adapter._dispatch(request, automatic=False)
            second = wait_for_completion(adapter.rpc, thread_id, second_id)
            messages = [item.get("text", "") for item in second.get("items", []) if item.get("type") == "agentMessage"]
            if not messages:
                _, latest = adapter._read(thread_id)
                messages = [item.get("text", "") for item in latest.get("items", []) if item.get("type") == "agentMessage"]
            if not any(message.strip() == token for message in messages):
                raise UnsafeError("The real model did not confirm the original thread's context token")
            return {"status": "PASS", "backend": "real authenticated Codex App Server",
                    "model_turns": 2, "same_thread": True, "original_context_preserved": True,
                    "ordinary_usage_authorized": True, "paid_credits_available": False,
                    "automatic_quota_reset_test": "NOT TESTED: no real quota was exhausted",
                    "thread_id": thread_id}
    finally:
        adapter.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Authorize two tiny genuine included-usage turns")
    parser.add_argument("--report", type=Path, help="Write a redacted verification result")
    args = parser.parse_args()
    if not args.run:
        parser.error("Pass --run for the real backend check; this is not a simulation")
    result = verify()
    print(json.dumps(result, indent=2))
    if args.report:
        public = {k: v for k, v in result.items() if k != "thread_id"}
        args.report.write_text(json.dumps(public, indent=2) + "\n")


if __name__ == "__main__":
    main()

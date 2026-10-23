"""Real usage-limit continuation with explicit task arming."""
import argparse
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from . import __version__
from .adapters import SimulationAdapter
from .domain import TransientError, UnsafeError
from .engine import Engine, Scheduler
from .protocol import find_codex
from .store import Store
from .live import LiveAdapter


def state_path(simulation=False):
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "codex-auto-resume" / ("simulation.sqlite3" if simulation else "state.sqlite3")


def doctor(connect=False):
    result = {"version": __version__, "live_execution": True,
              "reason": "Same-thread continuation with fresh backend usage and context checks",
              "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown")}
    try:
        binary = find_codex()
        v = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, check=True)
        result["runtime"] = v.stdout.strip()
        with tempfile.TemporaryDirectory(prefix="auto-resume-schema-") as folder:
            subprocess.run([binary, "app-server", "generate-json-schema", "--experimental", "--out", folder],
                           capture_output=True, timeout=20, check=True)
            p = json.loads((Path(folder) / "v2/TurnStartParams.json").read_text())
            q = json.loads((Path(folder) / "v2/GetAccountRateLimitsResponse.json").read_text())
            result["turn_start_fields"] = sorted(p.get("properties", {}))
            result["usage_permission_field"] = "ordinaryUsageAllowed" in q.get("properties", {})
        if connect:
            observer = LiveAdapter()
            try:
                usage = observer.usage()
                result["read_only_connection"] = "PASS"
                result["ordinary_usage_allowed"] = usage.payload.get("ordinaryUsageAllowed")
                result["account_identity_available"] = bool(usage.payload.get("accountId"))
                result["bucket_count"] = len(usage.payload.get("rateLimitsByLimitId") or {})
            finally:
                observer.close()
    except (UnsafeError, TransientError, OSError, subprocess.SubprocessError, ValueError):
        result["read_only_connection"] = "UNAVAILABLE"
        result["diagnostic"] = "Check Codex installation, authentication, permissions and schema compatibility"
    return result


def demo(folder):
    now = [1_800_000_000.0]
    clock = lambda: now[0]
    store = Store(Path(folder) / "demo.sqlite3")
    adapter = SimulationAdapter(clock)
    engine = Engine(store, adapter, clock)
    try:
        store.set_enabled(True, clock())
        engine.register("demo-task")
        engine.tick()
        waiting = store.get("demo-task")["state"]
        now[0] += 26
        adapter.reset()
        engine.tick()
        engine.tick()
        adapter.complete()
        now[0] += 31
        engine.tick()
        return {"mode": "SIMULATION — no model requests", "waiting": waiting,
                "automatic_continuations": len(adapter.requests), "final": store.get("demo-task")["state"]}
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Codex Auto-Resume: continue armed tasks after included-usage reset")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--state", type=Path, help="Private application state file (never a Codex file)")
    parser.add_argument("--simulation", action="store_true", help="Use invented tasks and quotas; no Codex connection")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ui", help="Open the companion control window")
    sub.add_parser("run", help="Run the local continuation controller")
    sub.add_parser("threads", help="List recent local conversations for explicit arming")
    sub.add_parser("status", help="Show local registered tasks")
    sub.add_parser("enable", help="Enable Auto-Resume; individual tasks still require explicit arming")
    sub.add_parser("disable", help="Cancel scheduled continuations without interrupting Codex")
    sub.add_parser("toggle", help="Toggle Auto-Resume on/off")
    arm = sub.add_parser("arm", help="Explicitly register an eligible conversation")
    arm.add_argument("thread_id")
    arm.add_argument("--recover-context", action="store_true",
                     help="Also recover confirmed context-budget checkpoints for this conversation")
    arm.add_argument("--native-heartbeat", help="Bind this arming to an existing native Codex heartbeat ID")
    arm.add_argument("--native-max-attempts", type=int, default=10,
                     help="Maximum admitted native work turns, from 1 to 10 (default: 10)")
    claim = sub.add_parser("native-claim", help="Check and durably admit work inside a native heartbeat turn")
    claim.add_argument("thread_id")
    claim.add_argument("--automation-id", required=True)
    finish = sub.add_parser("native-finish", help="Record a native checkpoint, completion or user-input block")
    finish.add_argument("thread_id")
    finish.add_argument("outcome", choices=("checkpoint", "complete", "blocked"))
    finish.add_argument("--automation-id", required=True)
    native_prompt = sub.add_parser("native-prompt", help="Print the guarded native heartbeat instruction")
    native_prompt.add_argument("thread_id")
    native_prompt.add_argument("--automation-id", required=True)
    disarm = sub.add_parser("disarm", help="Disarm one registered conversation")
    disarm.add_argument("thread_id")
    doc = sub.add_parser("doctor", help="Inspect installed schema without inference")
    doc.add_argument("--connect", action="store_true", help="Also read account and quota via App Server")
    sub.add_parser("demo", help="Run a finite isolated simulation with a fake clock")
    args = parser.parse_args(argv)
    if args.command == "native-prompt":
        from .native_prompt import prompt
        print(prompt(args.thread_id, args.automation_id))
        return 0
    if args.command == "doctor":
        print(json.dumps(doctor(args.connect), indent=2))
        return 0
    if args.command == "demo":
        with tempfile.TemporaryDirectory(prefix="auto-resume-demo-") as folder:
            print(json.dumps(demo(folder), indent=2))
        return 0
    store = Store(args.state or state_path(args.simulation))
    adapter = SimulationAdapter() if args.simulation else LiveAdapter()
    engine = Engine(store, adapter)
    try:
        if args.command == "threads":
            print(json.dumps(adapter.recent_threads(), indent=2))
            return 0
        elif args.command == "enable":
            if not args.simulation:
                adapter.ensure_daemon()
            store.set_enabled(True, time.time())
        elif args.command == "disable":
            store.set_enabled(False, time.time())
        elif args.command == "toggle":
            store.set_enabled(not store.enabled, time.time())
        elif args.command == "arm":
            engine.register(args.thread_id, recover_context=args.recover_context,
                            native_heartbeat=args.native_heartbeat, native_max_attempts=args.native_max_attempts)
        elif args.command in ("native-claim", "native-finish"):
            from .native import NativeController
            native = NativeController(store, adapter)
            result = (native.claim(args.thread_id, args.automation_id) if args.command == "native-claim"
                      else native.finish(args.thread_id, args.automation_id, args.outcome))
            print(json.dumps(result, indent=2))
            return 0
        elif args.command == "disarm":
            engine.disarm(args.thread_id)
        elif args.command == "ui":
            from .ui import launch
            launch(engine, args.simulation)
        elif args.command == "run":
            if not args.simulation:
                adapter.ensure_daemon()
            scheduler = Scheduler(engine)
            stop = threading.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: stop.set())
            scheduler.start()
            stop.wait()
            scheduler.stop()
            # An explicit process stop requires a fresh opt-in. A crash uses recovery.
            store.set_enabled(False, time.time())
        print(json.dumps({"enabled": store.enabled, "live_execution": not args.simulation,
                          "tasks": [{**{k: t[k] for k in ("thread_id", "state", "reason", "next_check", "attempts")},
                                     **{k: json.loads(t["context"]).get(k) for k in
                                        ("recover_context", "native_heartbeat", "native_max_attempts")}}
                                    for t in store.tasks()]}, indent=2))
        return 0
    except (UnsafeError, TransientError, ValueError) as exc:
        print(str(exc))
        return 2
    finally:
        adapter.close()
        store.close()

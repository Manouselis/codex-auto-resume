# Release history

[Documentation index](README.md) · [Verification report](TESTING.md)

## 0.3.1 — 25 October 2026

- Fixed choosing-and-arming and clicking-and-arming saved conversations. Both restore the chat ID and context-recovery setting; native heartbeat bindings are preserved.
- Explicit rearming now reconciles a stale acknowledged reservation only when read-only history proves that its exact turn ended. Unknown deliveries and unfinished external markers still block retries.
- Repeated Arm on a running native turn is idempotent and preserves its attempt count. A disabled but still running native turn can be rearmed without starting another turn.
- Added eight controller and three real Tk regressions. The full local suite passed 178 tests, including thirteen GUI checks.

## 0.3.0 — 23 October 2026

- Added explicit per-arming recovery for context-budget checkpoints and structured context-window failures, with fresh included-usage checks and the existing three-attempt limit.
- Added the GUI opt-in and CLI `arm THREAD_ID --recover-context`. Ordinary completion is still a stop condition.
- Corrected the misleading **Task completed** reason: a completed turn does not prove the wider objective is finished.
- Goal state and configured token budgets are checked without modifying them. Checkpoint text is pinned across dispatch preflight.
- Closing a service-owned control panel now keeps armed background work active; OFF still disarms.
- Added an experimental admission guard and prompt for native scheduled desktop recovery. External restoration and queue start cannot bypass the desktop writer; this now reports `not_sent` and pauses. The first real native scheduled wake-up passed on Ubuntu on 23 October: fresh guards admitted work in the original chat, which resumed saved research. Repeated checkpoint cycles and natural quota-reset recovery remain unverified.
- Native mode admits at most ten work turns, checks prior checkpoints and fresh usage, and is skipped by the external scheduler. Each native wake-up is a normal model turn.
- The local suite passes 167 tests, including ten native GUI checks. See [Recovery modes](RECOVERY.md) for recognition boundaries.

## 0.2.1 — 22 October 2026

- Fixed false cancellation when arming a conversation still running in another Codex runtime. An open external-history marker is monitored as unresolved; it cannot authorize a continuation.
- Kept confirmed cancellation, completion, superseding turns, approvals and dispatch preflight safeguards in place.
- Added 12 adapter/controller regressions and one native control-panel regression. The local GUI-inclusive suite records 120 passing tests.
- Verified the arming fix against an active desktop conversation using read-only metadata and isolated state, without inference or thread mutations.
- Fixed Windows test cleanup so SQLite handles close before temporary directories are removed. Installation manifests now use portable relative paths on every platform.
- Passed all four hosted Ubuntu/Windows and Python 3.10/3.13 CI jobs. This verifies the core and packaging, not live Windows Codex integration.

## 0.2.0 — 19 October 2026

- Implemented real same-thread continuation through the official persistent App Server, replacing the observation-only execution path.
- Added local WebSocket transport, fresh account/quota/configuration checks, explicit task selection and durable submission reservations.
- Verified the continuation path with two real authenticated model turns that preserved the original context. The local suite recorded 107 passing tests at that release.

## 0.1.0 — historical prototype

The initial prototype could observe state and exercise the scheduler with fixtures, but refused real continuation. Its results do not describe the current adapter's execution capability.

## Still awaiting live validation

A natural five-hour exhaustion/reset sequence, real Windows desktop continuation, cross-client approval routing, Wayland and actual suspend/reboot recovery remain unverified. Controlled reset tests and real same-thread execution are separate pieces of evidence; see [Testing](TESTING.md).

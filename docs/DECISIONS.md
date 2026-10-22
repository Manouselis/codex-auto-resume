# Decisions and engineering review

## 0.2.1: monitoring work owned by another runtime

The desktop can report a turn as active while a separate App Server reader reports `notLoaded` and reconstructs the same unfinished turn as `interrupted`, with no error or completion time. Treating that stored marker as an explicit user cancellation prevented arming a normally running conversation.

The adapter now marks precisely this open external-history case as unresolved. Explicit arming permits monitoring it without loading the thread or sending a model request. The engine waits for a confirmed result for that same turn. Only a later structured usage-limit failure can enter reset recovery; unresolved history cannot replace a previously confirmed failure or pass dispatch preflight. Completed cancellations and interruptions observed in the loaded runtime still stop automation. Identity changes, approvals and superseding turns retain their existing safeguards.

Regression coverage includes the real control-panel arm action, unresolved monitoring with zero mutations, rejection of automatic and manual dispatch, subsequent completion/cancellation/supersession, and a later confirmed five-hour failure followed by one continuation. Diagnosis used read-only metadata against a running desktop conversation; no model request or interruption was sent to it.

The first hosted Windows run caught open SQLite handles being cleaned up after their temporary directories, and platform-specific backslashes in the installation manifest conflicting with the uninstaller's portable path allowlist. Test cleanup now closes handles first; installation records POSIX-relative paths on every platform. These changes do not alter the running controller or its continuation policy.

## 0.2.0 correction

The 0.1.0 prototype interpreted the financial invariant as requiring a new atomic backend operation and therefore never executed. That was overly restrictive for the brief's requirement to verify included, non-chargeable usage before intentionally continuing. The current adapter performs those checks and submits a real same-thread continuation, while explicitly documenting the remaining external-change/concurrency race.

No safety preference simply bypasses the policy. Live execution requires authoritative ordinary permission, both available windows, Plus authentication, matching account/thread/model, zero/known credits, a standard provider/tier and unchanged failed work. Banked resets and paid paths remain forbidden.

## Integration cycle

Re-inspected installed runtime 0.163.0-alpha.10.2 and current official docs. A stale socket was diagnosed and the official local daemon started through its supported CLI. Initial proxy-based JSON-lines initialization failed because the socket transport is WebSocket. Replaced it with a masked RFC6455 client over the local socket. Metadata reads then passed. The backend's official `https://chatgpt.com/backend-api/` configuration was distinguished from custom endpoints rather than incorrectly rejecting a default URL.

## Genuine model verification

Ran two tiny real included-usage turns in one dedicated non-destructive thread. The second request used the production same-thread dispatch path with an explicit manual-test trigger and correctly recalled the first turn's context token. No backend quota was mocked. No live quota was exhausted. The automatic failure/reset trigger is separately covered by controlled tests; this distinction is preserved in the report.

## Safety and regression cycle

Added live protocol-level regressions for ordinary permission false/null, weekly exhaustion, paid balances, API auth, provider/endpoint/tier changes, account changes, task changes after resume, disabled state, pending approvals and all reported model buckets. Added WebSocket framing/fragmentation/ping, size-limit and no-retry tests. Delayed backend recovery after reset receives bounded read-only retries.

The production transport disconnects without killing daemon work. Default operation now uses the real adapter; the simulator is retained only for normal testing. Added a native conversation chooser, current documentation and a versioned 0.2.0 distribution. Tests, real evidence and release hashes are recorded separately.

## Unchanged principles

Explicit per-thread arming; global OFF disarms; weekly exhaustion requires fresh user action; no prompt replay; durable reservation before dispatch; uncertainty pauses; no automatic approvals; no private app patches; no automatic GitHub publication. SQLite/runtime credentials remain separate. MIT license and reproducible packaging remain in place.

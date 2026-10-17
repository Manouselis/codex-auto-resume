# Engineering decisions and review cycles

## Decisions

1. **Fail closed before convenience.** `ordinaryUsageAllowed` and percentages are necessary read-time signals, not an atomic billing reservation. The shipped live adapter cannot execute.
2. **Standalone companion, no cosmetic plugin.** A plugin manifest would not add the missing execution contract or persistent host toggle. Do not imply this is an official native feature.
3. **Python standard library and native Tk.** Available on Ubuntu 22.04, small dependency surface, testable core, no web server, browser extension, cloud account or model API key. Windows code remains unverified.
4. **Separate observation from execution.** Protocol reads are allowlisted. The simulator implements stronger hypothetical backend guarantees; its capability flags are not evidence that Codex provides them.
5. **Conservative quota interpretation.** Require explicit account/model/bucket identity, both window durations, no paid credits, fresh ordinary permission and a weekly reserve. Do not infer recovery from time.
6. **Durable at-most-once dispatch.** Commit a reservation before transmission; never retry an ambiguous send. Ambiguity blocks the automatic queue. Some safe opportunities can be missed after a crash.
7. **Explicit task arming.** Global OFF disarms tasks; ON does not sweep conversations or rearm weekly exhaustion. Registration changes invalidate stale work by a generation number.
8. **User interruption takes precedence.** Normal window/process close disarms automation; no forced interruption of ordinary Codex work. Normal shutdown may therefore need manual opt-in afterward.
9. **No installation side effects on Codex.** Installer owns a separate prefix and manifest. Startup is manual opt-in. GitHub publication is deferred until the owner requests it.

## Review cycle 1 — finance, persistence and concurrency

Reviewed policy and initial 54 tests. Hardened global serialization to include uncertain submissions, added OS controller locking, moved recovery after lock acquisition, and invalidated prior observations when a task is rearmed. Added regressions for concurrent controllers, disarming/rearming during reads, no polling during idle waits, attempt limits and uncertainty blocking other tasks.

A new test exposed an unrealistic simulator reset: recovered five-hour windows expired after 20 seconds. The fixture now reports a future five-hour window after recovery while retaining a short initial demonstration wait. This was a simulator defect, not a live backend result.

## Review cycle 2 — real protocol boundary and crash behavior

Added a subprocess-based mock App Server and tested initialization, reconnects, timeout, malformed data, unexpected approval requests, sensitive backend error redaction, forbidden execution/billing/auth methods, and OS lock release after process death. Re-ran all tests. The installed bundled runtime then passed the real account/quota read-only probe. No model turn or billing request was submitted.

## Review cycle 3 — UI and distribution

Ran the native control-window tests on Ubuntu X11 and inspected dark/light screenshots. Visual inspection found clipped lower controls despite passing interaction tests. Increased minimum/default window dimensions, reduced initial table height, and added a widget-bounds regression. Added isolated installation/update/uninstallation and reproducible-build checks. A control window can now share state with an existing background controller without running crash recovery against a healthy process. Removed unused imports found by pyflakes.

Final results and remaining untested items are recorded in [TESTING.md](TESTING.md). No review cycle is a claim that live continuation works.

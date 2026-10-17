# Limitations and blocked acceptance criteria

Version 0.1.0 is not ready to provide unattended real-task continuation. It is an executable, tested companion and policy engine with live read-only integration.

| Requested behavior | Status |
| --- | --- |
| Default-OFF one-click desktop control | Implemented; Ubuntu GUI tested |
| Native Codex Settings/task toggle | BLOCKED: no supported persistent host-control extension established |
| Live quota inspection | PASS against installed bundled App Server |
| 5h reset scheduling and exact task identity | PASS in simulated structured events and persisted state |
| Zero continuation when weekly usage is exhausted | PASS in automated simulation; live adapter always sends zero |
| Real included-only, unchanged-thread continuation | BLOCKED: required atomic backend operation absent from inspected schemas |
| Real exactly-once submission/ack reconciliation | BLOCKED: no verified remote idempotency contract |
| Completion/cancellation/approval protection | PASS in simulation; live metadata cannot prove original active runtime ownership |
| Immediate live weekly/cancel event detection | BLOCKED: no connection to desktop lifecycle stream |
| Working while the desktop app is closed | Metadata reads only; no real continuation |
| Crash/reconnect recovery | PASS for local state and mocked transport; ambiguous requests pause |
| Normal reboot automatically restores eligibility | Unsupported: normal stop/shutdown disarms conservatively |
| Ubuntu user installation and removal | Tested in an isolated user prefix |
| Windows support | Code paths provided; NOT TESTED on Windows |
| Wayland | NOT TESTED; no OS input automation dependency |
| System tray, notifications, auto-start UI preferences | Not implemented; manual systemd template supplied |
| Public GitHub repository or release | Not created or published |

Only ChatGPT Plus snapshots with both reported quota windows are accepted. Unknown, partial, stale or model-specific quota semantics pause eligibility. The live response inspected on this account did not establish a model binding (`normalModelSlug` was null); no general-bucket assumption is made.

The state machine cannot infer whether a failed task is semantically unfinished from a conversation summary. It requires trusted structured observation and does not reconstruct missing history. Paginated live history is rejected in this release.

## Work needed before enabling live execution

1. Obtain a documented backend operation that atomically enforces included-only, non-chargeable execution and rejects account/model/quota changes for the continuation's lifetime.
2. Bind the request to the original runtime, permissions and latest thread revision, rejecting active user work and outstanding approvals.
3. Verify durable remote idempotency and reconciliation after lost acknowledgements.
4. Implement a new audited adapter with real lifecycle subscriptions and explicit model/quota bindings.
5. Test the complete flow in an isolated non-destructive real conversation, including billing rejection and concurrent user input. Do not exhaust the user's live quota for routine tests.
6. Verify Windows, Wayland and normal reboot behavior on appropriate hosts before claiming those capabilities.

A configuration flag, credit balance check, UI automation, private app-bundle patch or repeated Continue prompt does not resolve these blockers.

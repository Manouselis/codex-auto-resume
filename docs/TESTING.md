# Testing — 0.8.0

Local Ubuntu 22.04/X11, Python 3.10.12: **241 tests, 240 passed, one Windows-only API test skipped; all 19 GUI tests passed**. [Current report](evidence/test-results.json). Tests send zero live model requests.

## Native installers and compatibility

The [desktop workflow](../.github/workflows/desktop.yml) builds native installers and runs real bundled Tk windows, not just import/syntax checks. Each smoke report records the exact OS/architecture, GUI/icon/default-enabled checks, private SQLite/recovery simulation and total launch/test duration. Linux/Windows install and uninstall the final artifact; macOS mounts the DMG, copies its app and launches that copy.

| Target | Automated check | Live Codex integration |
| --- | --- | --- |
| Ubuntu 22.04 x64 | Native DEB build/install/bundled GUI/uninstall | Previously verified on this local X11 host, runtime 0.166 |
| Ubuntu 24.04 and 26.04 x64 | Install/run/uninstall the **same 22.04-built DEB** | Not verified |
| Windows Server 2025 x64 | NSIS build/install/bundled GUI/uninstall; full GUI suite | Not verified |
| Windows 11 ARM | Same x64 installer under x64 emulation; GUI/core tests and native power API | Not verified; not a native ARM build or an Intel Windows 11 hardware test |
| macOS 14 ARM / macOS 15 Intel | Native DMG build/mount/copy/bundled GUI; full GUI suite | Not verified |

CI results and uploaded JSON reports are the evidence for each configured row; a configured job is not a passing result. Release publication requires all platform checks to pass. [View actual runs](https://github.com/Manouselis/codex-auto-resume/actions/workflows/desktop.yml). The release bundles its platform smoke reports alongside installer checksums.

Package smoke mode uses invented data. It verifies bundled runtime/install behavior without a signed-in Codex account. It does not establish live continuation, natural quota reset, private-socket ownership/ACL enforcement on every OS, downloaded-app SmartScreen/Gatekeeper prompts, physical locking, forced sleep or reboot behavior. CI hosts may have development tools installed; smoke tests launch the frozen executable, not system Python, but are not minimal clean consumer machines.

## Real continuation evidence

- [0.7.0 harmless chat](evidence/startup-0.7.0.json): actual picker → native queue → one acknowledged `continue` → `CONTINUED`, followed by normal completion/removal. Existing working chats were not closed.
- [Genuine daemon-owned continuation](evidence/live-continuation.json): two authenticated included-usage turns preserved context.
- [Native scheduled recovery](evidence/native-scheduled-recovery.json) and [one post-reset restart](evidence/limit-reset-recovery-0.4.0.json): actual scheduled work resumed. Repeated unattended exhaustion/wait/reset cycles remain unverified.
- [Sleep/controller evidence](evidence/desktop-0.5.0.json): Ubuntu inhibitor acquired/released; controller persisted after panels closed. A physical locked-session continuation was not observed.

## Historical verification (0.7.0 and earlier)

# Testing and real verification — 0.7.0

The 0.7.0 suite adds 15 selection/dispatch regressions, three desktop-launch tests and two native-guard tests. They cover literal `continue`, no extra message for active work, repeated selections, normal completion, exhausted usage, weekly and goal stops, approvals, uncertain delivery, existing user queues, changed chat state, preserved queue transport after a later quota reset, and exact native message identity. A user-authorized harmless chat also resumed through the real native queue and replied `CONTINUED`. No working user chat was closed for testing.

The 0.6.0 UI regressions exercise a real picker-selection event that arms without a second button, saved native settings, queue removal without state deletion, a repeating 60-second timer, and a selection queued during an in-flight allowance check. GUI layout checks cover the visible Add/Disarm controls, the empty queue and both themes. These UI tests use controlled backend data and send no real model requests.

Version 0.5.0 adds regressions for migration from the global reservation index, concurrent admitted chats, isolation of uncertain work, exact terminal-reservation cleanup, automatic daemon bootstrap, service reuse/start, a fresh ON window, icon packaging and the scoped sleep-inhibitor lifecycle. The actual Ubuntu inhibitor was acquired, listed through logind and released. The live stale reservation was verified terminal and retired with zero model requests. The sludge chat subsequently reported completion of its newer turn. Actual physical locking and a new uninterrupted quota-reset cycle have not been tested.

Automated regression checks: Ubuntu 22.04.5 LTS, X11, Python 3.10.12, 30 October 2026. The daemon-owned model execution evidence is from 19 October 2026. The first native scheduled desktop continuation passed on 23 October 2026.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Full automated suite, including native GUI | PASS — 233 tests, zero failures/errors/skips | [0.7.0 recorded results](evidence/test-results-0.7.0.json) |
| Hosted Ubuntu/Windows core and packaging CI, Python 3.10/3.13 | PASS — all four jobs at code commit `701b654`; exact pass/skip counts below | [Recorded CI evidence](evidence/ci-0.3.0.json), [GitHub run](https://github.com/Manouselis/codex-auto-resume/actions/runs/39905443617) |
| Open turn owned by another runtime can be armed | PASS — monitors without loading the thread or sending inference; controlled later failure/reset submits once on a resumable daemon-owned fixture | 12 live-adapter regressions and one native control-panel regression |
| Read-only reproduction against an active desktop conversation | PASS — external open turn arms and remains monitored, with zero thread mutations | [Sanitized arming probe](evidence/external-arm.json) |
| Genuine same-thread continuation in a daemon-owned chat | PASS — two real authenticated model turns; original context token recalled | [Redacted real-backend result](evidence/live-continuation.json) |
| Real desktop writer ownership | Reproduced refusal; external restoration and queue start cannot take over the writer | [Redacted refusal](evidence/desktop-writer-conflict.json) |
| Native scheduled desktop recovery | PASS for one real wake-up — native guard admitted work, durable reservation matched, saved checkpoint read and research resumed | [Redacted live evidence](evidence/native-scheduled-recovery.json) |
| Real daemon account/quota connection | PASS — ordinary usage authorized; both quota windows; no paid balance | [Metadata probe](evidence/live-probe.json) |
| Quota interruption → wait → fresh read → one real-protocol submission | PASS with controlled backend responses | `tests/test_live.py` |
| Weekly exhausted after 5h reset | PASS — zero continuation requests | Engine, policy and live-adapter tests |
| Native restart after a genuine usage-limit failure | PASS — fresh included permission, scheduled native wake-up, first-action guard, matching reservation and preserved interrupted work | [25 October live evidence](evidence/limit-reset-recovery-0.4.0.json) |
| Entire unattended exhaustion/wait/reset cycle and repeated resets | NOT VERIFIED — the observed chat was repaired after its failure and quota reset | One post-reset continuation does not establish repeated unattended reliability |
| Actual task picker / live control-panel layout | PASS — real read-only list call and GUI layout test | `live.py`, `tests/test_ui.py` |
| Dark/light and real-panel visual QA | PASS | [Real panel](evidence/ui-live.png), dark/light screenshots |
| WebSocket framing, masking, fragmentation, ping/pong, size checks | PASS | `tests/test_websocket.py`; real daemon handshake also passed |
| Crash, duplicate events, lost acknowledgements and cross-process reservation | PASS in controlled tests | Safety/protocol suites |
| Isolated installation, update and uninstall | PASS locally on Ubuntu and in hosted Ubuntu/Windows CI; unrelated files preserved | Packaging suite and CI evidence |
| Static name/import checks and compilation | PASS | `pyflakes`, `compileall` |
| Reproducible application and source package | PASS | Two builds produced identical SHA-256 values |
| Live Windows Codex integration, Wayland, OS suspend/reboot, user-service autostart | NOT TESTED in these scenarios | Hosted core/packaging CI does not validate live desktop integration |

The normal automated suite makes zero live model requests. The separately invoked live check made two genuine included-usage turns, in a dedicated harmless conversation, through the same production `_dispatch` method with an explicit manual-test trigger. It did not inject a fake quota or pretend that the real service had exhausted/reset. This confirms daemon-owned execution and context preservation. It did not test taking over the desktop writer, native scheduled recovery or a natural quota reset.

The final full run includes nineteen GUI tests; headless runs intentionally skip them. The 2500-case randomized quota check is counted as one test. Earlier 0.1.0 results remain in Git history and do not describe this release's execution capability.

## Recorded 0.3.0 hosted CI results

The [23 October 2026 run](https://github.com/Manouselis/codex-auto-resume/actions/runs/39905443617) verified code commit `701b654`. Each job discovered 167 tests. Build and packaged simulation steps passed in all four jobs.

| Runner | Python | Passed | Skipped |
| --- | --- | --- | --- |
| Ubuntu | 3.10 | 157 | 10 |
| Ubuntu | 3.13 | 157 | 10 |
| Windows | 3.10 | 154 | 13 |
| Windows | 3.13 | 154 | 13 |

Headless jobs skip the ten GUI tests; Windows also skips three POSIX-specific cases. See [recorded evidence](evidence/ci-0.3.0.json). This does not verify live Windows desktop recovery.

## Recorded 0.2.1 hosted CI results

The [22 October 2026 run](https://github.com/Manouselis/codex-auto-resume/actions/runs/39858070583) verified code commit `8fe287e` after the Windows cleanup and manifest-path fixes. Each job discovers 120 tests; the total includes skipped tests.

| Runner | Python | Passed | Skipped | Build and simulation |
| --- | --- | --- | --- | --- |
| Ubuntu | 3.10 | 112 | 8 | PASS |
| Ubuntu | 3.13 | 112 | 8 | PASS |
| Windows | 3.10 | 109 | 11 | PASS |
| Windows | 3.13 | 109 | 11 | PASS |

Ubuntu skips the eight opt-in native GUI tests in headless CI. Windows also skips the state-file symlink test, the POSIX installer symlink-escape test and the POSIX state-file mode test. Windows packaging is exercised on a real hosted Windows runner; real Codex authentication, desktop interaction and continuation are not. The local GUI run and hosted CI have separate evidence records.

## Context recovery regressions

The 0.3.0 suite adds context-marker recognition, rejection of explanations/quoted examples/tool output, per-arming opt-in, immediate recovery with fresh usage, waiting through exhausted quota, persistence of the mode across quota recovery, ordinary completion, goal pause/budget limits, credit/permission guards, checkpoint changes during restoration, durable reservation turnover and the three-attempt cap. Native GUI tests cover the opt-in control and closing a service-owned panel without disabling work. The real read-only [context preflight](evidence/context-preflight.json) confirms recognition of the observed stopped conversation without model requests. The separate [native history-read probe](evidence/native-guard-readonly.json) also recognized its saved checkpoint through the native guard’s actual pagination APIs, with zero model requests or thread mutations.

## Native guard regressions

Forty-one tests cover external-scheduler exclusion, native heartbeat and thread identity, fresh allowance on repeated claims, idempotent reservation, checkpoint turnover, terminal-history reconciliation after companion restart, ordinary completion, cancellation, OFF, paid balances, weekly reserve, goal budgets, unknown external submissions, the native cap and intervening manual turns. They use controlled metadata. Separately, the [23 October live check](evidence/native-scheduled-recovery.json) observed the actual scheduled heartbeat, its successful guard command, a matching reservation and subsequent research commands in the original desktop chat. The turn was still running when recorded. The [25 October post-reset restart](evidence/limit-reset-recovery-0.4.0.json) separately passed after a genuine persisted usage-limit failure. Repeated checkpoint recoveries and uninterrupted unattended reset cycles remain unverified.

## Rearming regressions in 0.3.1

Eight new controller tests cover a confirmed terminal native reservation, acknowledged-but-uncertain terminal history, refusal of unresolved or unknown delivery, idempotent Arm while running, rearming a disabled but running native turn, transactional rollback when arming changes, and a later checkpoint after explicit manual rearming. Three real Tk regressions cover clicking the saved row, choosing it in the picker, and arming from a selected row with an empty entry. These make zero model requests. The separate [real UI check](evidence/rearming-0.3.1.json) also exercised both paths against the already armed research chat with server mutations forbidden, confirming the task and attempt count stayed unchanged.

The engine preserves a saved native binding and per-task settings when options are omitted. It reads bounded paginated metadata to confirm the exact acknowledged turn ended; an `interrupted` marker without `completedAt` is insufficient. Reconciliation and rearming commit atomically, and a concurrent change rolls them back.

## Required scenario coverage

PASS below means the corresponding local/mock scenario passed. It does not mean a real Codex model executed.

| Specification scenario | Result and coverage |
| --- | --- |
| 1 default ON (updated by user request) | PASS — fresh setting is checked; explicitly switching OFF still blocks arming |
| 2–9 enable, limit, wait, authorize, resume once, complete, stop | PASS — normal-flow engine test and finite CLI demo |
| 10 both windows exhausted | PASS — weekly decision wins |
| 11 weekly exhaustion during wait | PASS — complete usage-event snapshot disarms immediately |
| 12 nearly exhausted weekly quota | PASS — reserve boundary |
| 13 missing weekly data | PASS — pause |
| 14 stale weekly snapshot | PASS — snapshot freshness rejection |
| 15 5h reset with exhausted weekly | PASS — zero submissions; primary acceptance test |
| 16 later weekly reset after disarm | PASS — no implicit rearming |
| 17 paid credits with included exhaustion | PASS — paid balance rejected |
| 18 unknown balance | PASS — pause |
| 19 paid fallback not excluded | PASS — missing adapter enforcement capability blocks |
| 20 API-key authentication | PASS — rejected |
| 21 banked reset available | PASS — never treated as authorization; consume method forbidden |
| 22–23 ordinary permission false/null | PASS — false/null/missing/nonboolean rejected |
| 24 account/model identity changes | PASS — account/bucket/config changes pause |
| 25 disabled while waiting | PASS — task disarmed and cannot revive on re-enable |
| 26 manual cancellation | PASS — interrupted/cancelled task paused |
| 27 completion during wait | PASS — completed with zero new requests |
| 28 another turn starts | PASS — superseded thread paused |
| 29 duplicate reset events | PASS — 20 concurrent ticks and separate controllers submit once at most |
| 30 restart during continuation | PASS — durable reservation becomes uncertain; no retry |
| 31 dropped acknowledgement | PASS — one simulated remote send, no retransmission |
| 32 missing history | PASS — pause |
| 33 missing project | PASS — pause |
| 34 outstanding approval | PASS — pause; transport never answers interactive requests |
| 35 multiple waiting tasks | PASS — independent per-chat reservations, fresh quota checks and uncertainty isolated to its chat |
| 36 network unavailable | PASS — bounded retry and transport disconnect tests |
| 37 expired authentication | PASS — pause |
| 38 temporary App Server failure | PASS — read reconnect and retry bounds |
| 39 suspend through reset | PASS in fake-clock simulation; real OS suspend NOT TESTED |
| 40 clock changes | PASS — backwards/future-snapshot rejection and safe delay |
| 41 daylight saving | PASS for epoch-based core scheduling; real timezone transition NOT TESTED |
| 42 restart | PASS for persisted wait and OS lock release; actual reboot NOT TESTED |
| 43 unsupported protocol | PASS — unsupported execution adapter, no submission |
| 44 changed format | PASS — malformed/partial data rejected |
| 45 weekly-only bucket | PASS — insufficient window information rejected |
| 46 reversed windows | PASS — durations determine meaning |
| 47 model-specific buckets | PASS — every explicitly bound bucket checked |
| 48 repeated temporary errors | PASS — bounded retries end in paused state |

Additional tests cover permissions changes, disabling/rearming during reads, no reads during idle waits, limits on continuation count, credential-free error messages, state ownership, symlink escapes, archive credential exclusions and safe installation paths.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify.py --gui
python3 -m pyflakes auto_resume scripts tests
python3 -m compileall -q auto_resume scripts tests
python3 scripts/build.py
```

For an explicitly authorized real check using two tiny included-usage turns:

```sh
python3 scripts/live_check.py --run
```

GUI tests require Tk and a graphical session; screenshot capture uses Pillow only during tests. Application runtime remains standard-library only. The legacy core CI runs Python 3.10/3.13 on Ubuntu, Windows and macOS. Native package/GUI coverage is described above; no automated check here establishes live Windows Codex continuation.

## Native recovery health and UI redesign in 0.4.0

The controller now checks the saved native schedule identity, target chat and ACTIVE/PAUSED status using read-only metadata. Missing or invalid schedules disarm with a reason; paused schedules use `WAITING_FOR_SCHEDULE`, then return to `ARMED` after activation. Tests cover deletion, mismatched metadata, activation, zero-work paused admission, renewed arming timestamps, a quota failure followed by fresh permission, and checkpoint completion after schedule deletion. UI checks cover adjacent Arm/Disarm controls, disarming a chosen chat without a table selection, both themes and minimum-size visibility.

The recovery prompt requires the guard as its first action, including before deciding whether an older cancellation applies. Successful admission reports the fresh arming time and monitored turn. This instruction is model-mediated; schedule health prevents silent false-ARMED status if an automation disappears. A new human cancellation still stops admission.

## Observed post-reset continuation on 25 October

The old heartbeat had deleted itself in response to an earlier cancellation, while the local row incorrectly remained ARMED. The repaired version recorded a fresh arming and a new schedule identity. At 15:13:51 CET its native scheduled turn ran `native-claim` as its first action; the guard returned `continue` with the current arming timestamp. The same original chat then read its interrupted working tree and saved next steps. The schedule remained ACTIVE and SQLite recorded the matching RUNNING reservation. No manual continuation or alternate external dispatch was sent.

This verifies one scheduled continuation after a genuine persisted usage-limit failure and renewed included allowance. It does not verify an uninterrupted unattended exhaustion/wait/reset cycle or multiple resets. See [redacted evidence](evidence/limit-reset-recovery-0.4.0.json).

## Heartbeat XML checkpoint repair in 0.4.1

The observed research turn saved its next action and called `native-finish checkpoint`, then placed the required checkpoint marker inside its XML heartbeat message. Version 0.4.0 looked only at the final line of the entire response and disarmed the next wake-up. The global switch stayed ON. The repaired parser extracts only the plain-text message of a complete, unambiguous heartbeat envelope. Four parser regressions cover the observed format, terminal state requirements, conflicting outcome markers, malformed/nested XML and quoted examples. Five native regressions cover three successive guarded checkpoint wake-ups, accurate disarm diagnostics, explicit rearming after diagnostic replies, newer-message rejection and ordinary-completion rejection. These repeat-wake tests use controlled metadata; they do not claim repeated live quota resets.

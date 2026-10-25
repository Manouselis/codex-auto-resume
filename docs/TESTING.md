# Testing and real verification — 0.3.1

Automated regression checks: Ubuntu 22.04.5 LTS, X11, Python 3.10.12, 25 October 2026. The daemon-owned model execution evidence is from 19 October 2026. The first native scheduled desktop continuation passed on 23 October 2026.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Full automated suite, including native GUI | PASS — 178 tests, zero failures/errors/skips | [Recorded results](evidence/test-results.json) |
| Hosted Ubuntu/Windows core and packaging CI, Python 3.10/3.13 | PASS — all four jobs at code commit `701b654`; exact pass/skip counts below | [Recorded CI evidence](evidence/ci-0.3.0.json), [GitHub run](https://github.com/Manouselis/codex-auto-resume/actions/runs/39905443617) |
| Open turn owned by another runtime can be armed | PASS — monitors without loading the thread or sending inference; controlled later failure/reset submits once on a resumable daemon-owned fixture | 12 live-adapter regressions and one native control-panel regression |
| Read-only reproduction against an active desktop conversation | PASS — external open turn arms and remains monitored, with zero thread mutations | [Sanitized arming probe](evidence/external-arm.json) |
| Genuine same-thread continuation in a daemon-owned chat | PASS — two real authenticated model turns; original context token recalled | [Redacted real-backend result](evidence/live-continuation.json) |
| Real desktop writer ownership | Reproduced refusal; external restoration and queue start cannot take over the writer | [Redacted refusal](evidence/desktop-writer-conflict.json) |
| Native scheduled desktop recovery | PASS for one real wake-up — native guard admitted work, durable reservation matched, saved checkpoint read and research resumed | [Redacted live evidence](evidence/native-scheduled-recovery.json) |
| Real daemon account/quota connection | PASS — ordinary usage authorized; both quota windows; no paid balance | [Metadata probe](evidence/live-probe.json) |
| Quota interruption → wait → fresh read → one real-protocol submission | PASS with controlled backend responses | `tests/test_live.py` |
| Weekly exhausted after 5h reset | PASS — zero continuation requests | Engine, policy and live-adapter tests |
| Real natural five-hour exhaustion/reset | NOT TESTED — no live quota was deliberately exhausted | Separate from real context/dispatch verification |
| Actual task picker / live control-panel layout | PASS — real read-only list call and GUI layout test | `live.py`, `tests/test_ui.py` |
| Dark/light and real-panel visual QA | PASS | [Real panel](evidence/ui-live.png), dark/light screenshots |
| WebSocket framing, masking, fragmentation, ping/pong, size checks | PASS | `tests/test_websocket.py`; real daemon handshake also passed |
| Crash, duplicate events, lost acknowledgements and cross-process reservation | PASS in controlled tests | Safety/protocol suites |
| Isolated installation, update and uninstall | PASS locally on Ubuntu and in hosted Ubuntu/Windows CI; unrelated files preserved | Packaging suite and CI evidence |
| Static name/import checks and compilation | PASS | `pyflakes`, `compileall` |
| Reproducible application and source package | PASS | Two builds produced identical SHA-256 values |
| Live Windows Codex integration, Wayland, OS suspend/reboot, user-service autostart | NOT TESTED in these scenarios | Hosted core/packaging CI does not validate live desktop integration |

The normal automated suite makes zero live model requests. The separately invoked live check made two genuine included-usage turns, in a dedicated harmless conversation, through the same production `_dispatch` method with an explicit manual-test trigger. It did not inject a fake quota or pretend that the real service had exhausted/reset. This confirms daemon-owned execution and context preservation. It did not test taking over the desktop writer, native scheduled recovery or a natural quota reset.

The final full run includes thirteen GUI tests; headless runs intentionally skip them. The 2500-case randomized quota check is counted as one test. Earlier 0.1.0 results remain in Git history and do not describe this release's execution capability.

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

Twenty-six tests cover external-scheduler exclusion, native heartbeat and thread identity, fresh allowance on repeated claims, idempotent reservation, checkpoint turnover, terminal-history reconciliation after companion restart, ordinary completion, cancellation, OFF, paid balances, weekly reserve, goal budgets, unknown external submissions, the native cap and intervening manual turns. They use controlled metadata. Separately, the [23 October live check](evidence/native-scheduled-recovery.json) observed the actual scheduled heartbeat, its successful guard command, a matching reservation and subsequent research commands in the original desktop chat. The turn was still running when recorded. A second checkpoint recovery and a natural quota reset have not yet been verified.

## Rearming regressions in 0.3.1

Eight new controller tests cover a confirmed terminal native reservation, acknowledged-but-uncertain terminal history, refusal of unresolved or unknown delivery, idempotent Arm while running, rearming a disabled but running native turn, transactional rollback when arming changes, and a later checkpoint after explicit manual rearming. Three real Tk regressions cover clicking the saved row, choosing it in the picker, and arming from a selected row with an empty entry. These make zero model requests. The separate [real UI check](evidence/rearming-0.3.1.json) also exercised both paths against the already armed research chat with server mutations forbidden, confirming the task and attempt count stayed unchanged.

The engine preserves a saved native binding and per-task settings when options are omitted. It reads bounded paginated metadata to confirm the exact acknowledged turn ended; an `interrupted` marker without `completedAt` is insufficient. Reconciliation and rearming commit atomically, and a concurrent change rolls them back.

## Required scenario coverage

PASS below means the corresponding local/mock scenario passed. It does not mean a real Codex model executed.

| Specification scenario | Result and coverage |
| --- | --- |
| 1 default OFF | PASS — registration refused while disabled |
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
| 35 multiple waiting tasks | PASS — serialization and fresh quota check; uncertainty blocks queue |
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

GUI tests require Tk and a graphical session; screenshot capture uses Pillow only during tests. Application runtime remains standard-library only. Hosted GitHub CI runs the headless core and packaging checks on Ubuntu and Windows with Python 3.10 and 3.13. These checks do not validate real Windows Codex transport or GUI integration.

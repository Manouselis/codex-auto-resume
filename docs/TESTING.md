# Testing and verification

Verified on Ubuntu 22.04.5 LTS, X11, Python 3.10.12, 17 October 2026. Test cases use invented account/thread IDs, fake clocks, mock App Server processes and simulated task state. No live model turn, quota exhaustion, reset redemption or billing operation is used.

## Results

| Check | Classification | Evidence |
| --- | --- | --- |
| Automated policy/engine/protocol/storage/packaging suite | PASS | `tests/`, [machine-readable results](evidence/test-results.json) |
| Native Tk interactions, keyboard entry, toggles, close and minimum size | PASS on Ubuntu X11 | `tests/test_ui.py` |
| Dark/light render and visual inspection | PASS after fixing clipping | [Dark](evidence/ui-dark.png), [light](evidence/ui-light.png) |
| Real bundled App Server account and quota reads | PASS | [Redacted live probe](evidence/live-probe.json) |
| Finite reset-to-completion demonstration | PASS in simulation | `python3 -m auto_resume demo`: one simulated continuation, then `COMPLETED` |
| Static import/name checks | PASS | `python3 -m pyflakes auto_resume scripts tests` |
| Python compilation | PASS | `python3 -m compileall -q auto_resume scripts tests` |
| Isolated user-prefix install, update, launch and uninstall | PASS on Ubuntu | `tests/test_packaging.py`; unrelated files preserved |
| Reproducible zipapp and source archive | PASS | Build twice and compare `dist/SHA256SUMS` |
| Runtime dependency surface | PASS | Standard library only; no third-party runtime packages |
| Real automatic continuation and financial enforcement | BLOCKED | Missing installed backend execution contract; live adapter sends zero requests |
| Actual systemd service/autostart on user's session | NOT TESTED | Template supplied; no service was installed or enabled |
| Windows / Wayland / real OS suspend and reboot | NOT TESTED on those environments | Portable branches and simulated clock/restart tests are not platform verification |
| Hosted GitHub Actions and public release | NOT TESTED | Workflow prepared; repository not published |

The final full test run contains 83 tests, with all GUI tests included. Without `--gui`, six GUI tests intentionally skip. The 2500-case randomized policy invariant check is one test, not 2500 separately counted tests.

There are no unresolved test failures in the final recorded run. Earlier failures included a simulator timestamp defect, clipped lower controls found visually, and a Tk timer/interpreter cleanup failure. Each was corrected before the final run. GUI cleanup now cancels its timer and joins work; tests collect Tk cycles on the main GUI thread.

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
| 43 unsupported protocol | PASS — no execution capabilities, no submission |
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
python3 scripts/build.py
python3 dist/codex-auto-resume-0.1.0.pyz demo
```

The GUI command needs a graphical session and Tk; screenshot capture additionally uses Pillow only in the test, not in the application. `pyflakes` is an optional development tool. Headless runs work with standard Python alone. The public CI matrix is supplied for Ubuntu and Windows and intentionally skips GUI tests until a host display is configured.

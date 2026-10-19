# Testing and real verification — 0.2.0

Verified on Ubuntu 22.04.5 LTS, X11, Python 3.10.12, 19 October 2026.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Full automated suite, including native GUI | PASS — 107 tests, zero failures/errors/skips | [Recorded results](evidence/test-results.json) |
| Genuine same-thread continuation | PASS — two real authenticated model turns; original context token recalled | [Redacted real-backend result](evidence/live-continuation.json) |
| Real daemon account/quota connection | PASS — ordinary usage authorized; both quota windows; no paid balance | [Metadata probe](evidence/live-probe.json) |
| Quota interruption → wait → fresh read → one real-protocol submission | PASS with controlled backend responses | `tests/test_live.py` |
| Weekly exhausted after 5h reset | PASS — zero continuation requests | Engine, policy and live-adapter tests |
| Real natural five-hour exhaustion/reset | NOT TESTED — no live quota was deliberately exhausted | Separate from real context/dispatch verification |
| Actual task picker / live control-panel layout | PASS — real read-only list call and GUI layout test | `live.py`, `tests/test_ui.py` |
| Dark/light and real-panel visual QA | PASS | [Real panel](evidence/ui-live.png), dark/light screenshots |
| WebSocket framing, masking, fragmentation, ping/pong, size checks | PASS | `tests/test_websocket.py`; real daemon handshake also passed |
| Crash, duplicate events, lost acknowledgements and cross-process reservation | PASS in controlled tests | Safety/protocol suites |
| Isolated installation, update and uninstall | PASS on Ubuntu; unrelated files preserved | Packaging suite |
| Static name/import checks and compilation | PASS | `pyflakes`, `compileall` |
| Reproducible application and source package | PASS | Two builds produced identical SHA-256 values |
| Windows, Wayland, OS suspend/reboot, user-service autostart | NOT TESTED on those hosts/scenarios | Portable core/fixtures are not host validation |

The normal automated suite makes zero live model requests. The separately invoked live check made two genuine included-usage turns, in a dedicated harmless conversation, through the same production `_dispatch` method with an explicit manual-test trigger. It did not inject a fake quota or pretend that the real service had exhausted/reset. This confirms actual execution and context recovery, not an unperformed natural-reset test.

The final full run includes seven GUI tests; headless runs intentionally skip them. The 2500-case randomized quota check is counted as one test. Earlier 0.1.0 results remain in Git history and do not describe this release's execution capability.

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

GUI tests require Tk and a graphical session; screenshot capture uses Pillow only during tests. Application runtime remains standard-library only. The CI workflow has not yet run on hosted GitHub or a Windows host.

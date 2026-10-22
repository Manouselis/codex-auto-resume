# Delivery summary — 0.2.1

[Documentation index](README.md) · [Release history](CHANGELOG.md)

## Implemented

The project includes a real same-thread continuation adapter, local reset scheduler, private SQLite state, native Tk control window, CLI, user-service template, installer, uninstaller and reproducible build scripts. The companion connects to the official persistent App Server over its local WebSocket socket.

Global ON and explicit per-conversation arming are required. The controller waits for a confirmed five-hour usage-limit failure and fresh included allowance before reopening the original thread and sending one contextual continuation. It checks account/model/context identity, both quota windows, ordinary permission, credits, spend controls and provider/tier configuration. Weekly exhaustion disarms the task; approvals remain manual. A durable reservation and conservative uncertain-outcome handling prevent automatic retransmission.

Version 0.2.1 fixes false cancellation when a separate reader reconstructs an unfinished external turn as interrupted. Such a turn can be armed for monitoring, while dispatch still requires a confirmed usage-limit failure. It also fixes Windows test cleanup and installation-manifest path portability.

## Verified

| Evidence | Scope |
| --- | --- |
| [Local results](evidence/test-results.json) | 120 passing Ubuntu tests, including eight native GUI tests |
| [Hosted CI](evidence/ci-0.2.1.json) | All four Ubuntu/Windows and Python 3.10/3.13 jobs passed; headless skips are recorded |
| [Real continuation](evidence/live-continuation.json) | Two authenticated model turns in the same thread preserved context |
| [Read-only arming probe](evidence/external-arm.json) | An externally running desktop turn could be armed without inference or thread mutations |

The full quota-interruption/reset flow passes with controlled backend responses. This is separate from the genuine model execution check. A natural five-hour exhaustion/reset has not yet been verified live.

## Use

Install with `python3 scripts/install.py`, then open `~/.local/bin/codex-auto-resume ui`. Enable, choose the original task and arm it. Use the [overnight background service recipe](INSTALL.md#overnight-operation-without-a-window) to wait without a control window, and keep the computer awake and online.

Source and documentation are published at [Manouselis/codex-auto-resume](https://github.com/Manouselis/codex-auto-resume). The [verification report](TESTING.md) gives exact scope and reproduction commands.

## Remaining validation

Natural quota-reset recovery, cross-client approval routing, live Windows integration, Wayland and real suspend/reboot recovery remain unverified. The public API also leaves a short cross-client dispatch race and does not reserve future quota. See [Remaining limitations](LIMITATIONS.md).

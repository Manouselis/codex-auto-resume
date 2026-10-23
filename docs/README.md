# Documentation

Codex Auto-Resume 0.3.0 is a local companion for explicitly armed, same-conversation continuation after a verified five-hour included-usage reset. It has a native control window and a CLI/background controller. Desktop writer ownership blocks external recovery; the native heartbeat guard passed its first real scheduled wake-up and research continuation on Ubuntu. Repeated checkpoint cycles and natural quota-reset recovery remain unverified. See [Recovery modes](RECOVERY.md).

## Start here

| Guide | Use it to |
| --- | --- |
| [Project README](../README.md) | Understand the feature, requirements and quick start |
| [Installation and operation](INSTALL.md) | Install, update, arm tasks, run overnight and uninstall |
| [Recovery modes](RECOVERY.md) | Distinguish context-budget stops from quota exhaustion and opt in explicitly |
| [Troubleshooting](TROUBLESHOOTING.md) | Interpret task states and resolve arming or connection problems |
| [Release history](CHANGELOG.md) | See what changed in each version |
| [Verification report](TESTING.md) | Check local, CI, real-backend and untested coverage |
| [Safety contract](SAFETY.md) | Understand included-usage, cancellation and duplicate-dispatch safeguards |
| [Remaining limitations](LIMITATIONS.md) | Assess platform support and execution boundaries |
| [Architecture](ARCHITECTURE.md) | Follow the adapter, scheduler, transport and state store |
| [Engineering decisions](DECISIONS.md) | Understand integration choices and fixes |
| [Delivery summary](DELIVERY.md) | Compare implemented behavior with remaining validation |
| [Original project brief](PROJECT_BRIEF.md) | Read the original requirements and requested scenarios |

## Verification snapshot

On 23 October 2026, the local Ubuntu GUI-inclusive suite recorded 167 passing tests, including ten GUI tests. The 0.3.0 [GitHub CI](https://github.com/Manouselis/codex-auto-resume/actions/runs/39905443617) passed all four Ubuntu/Windows and Python 3.10/3.13 jobs for code commit `701b654`. Headless CI skips GUI and platform-specific cases; it does not verify real Windows Codex integration.

The actual continuation path preserved context across two real authenticated model turns. The natural quota-exhaustion/reset sequence remains unverified live. The [verification report](TESTING.md) links the evidence and explains the distinction.

## Overnight operation

Use the [window-free background service recipe](INSTALL.md#overnight-operation-without-a-window), then confirm both `status` and `systemctl --user status codex-auto-resume.service`. A service-owned control panel can be closed while monitoring continues; global OFF still disarms tasks. Keep the computer awake and online. Approvals and exhausted weekly usage still need user action.

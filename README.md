# Codex Auto-Resume

A local companion for safe continuation after Codex usage limits.

**Version 0.1.0 is a safety-first research release. Live automatic continuation is blocked.**
The installed Codex interfaces expose authoritative usage information, but do not expose the atomic included-only billing and unchanged-thread guarantees required by this project. Enabling the control enables observation. It does **not** make real conversations resume automatically. The complete continuation flow works against an isolated simulator.

This is an independent community project, with no OpenAI endorsement or affiliation.

## Try it

Python 3.10 or newer is required. Ubuntu's graphical interface also needs `python3-tk`.

```sh
cd codex-auto-resume
python3 -m auto_resume demo
python3 -m auto_resume --simulation ui
```

The finite demo uses a fake clock. Its expected output is one simulated continuation followed by `COMPLETED`. It never connects to Codex.

In the simulation window:

1. Click **Continue automatically when the 5h limit resets** to enable it.
2. Click **Arm conversation** for the invented `demo-task`.
3. Wait for the waiting status, then click **Simulate 5h reset**.
4. Click **Complete task**, or test the weekly hard stop with a fresh simulation state.

For real, read-only usage inspection:

```sh
python3 -m auto_resume doctor --connect
python3 -m auto_resume ui
```

`doctor` prints redacted capability information. It never prints credentials, account IDs, or conversation content. A read-only child App Server uses the existing Codex login. It is **not** a connection to the desktop app's active execution session.

## What is implemented

- One-click, default-OFF control in a separate desktop window, with light/dark themes and keyboard navigation.
- Official App Server account and usage reads with a strict method allowlist.
- Quota policy using window durations and explicit model/bucket identity, fresh backend permission, no credit balance, and a weekly reserve.
- Task state machine, explicit per-conversation arming, epoch-based reset scheduling, bounded retries, SQLite persistence, and activity history.
- Cross-process controller locks and durable submission reservations. Uncertain outcomes pause automation rather than retrying a model request.
- A simulator that checks conditional included-only submission and preserves the original task identity.
- User installation/uninstallation, a reproducible zipapp and source archive, and an optional systemd user-service template.

The production adapter has **no model execution method**. No preference, environment variable, or CLI switch can unlock it. Real thread registration can also be refused when runtime, history, permissions, or model/quota binding cannot be verified.

## Install

```sh
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

Installation does not enable startup or change Codex settings. Closing the control window turns Auto-Resume OFF and disarms tasks without interrupting ordinary Codex work. Enabling it again does not rearm previously disarmed tasks.

```sh
python3 scripts/uninstall.py
```

Local task history is preserved during uninstall. See [installation and Windows notes](docs/INSTALL.md).

## Develop

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 dist/codex-auto-resume-0.1.0.pyz demo
```

There are no third-party runtime dependencies. Tk uses the operating system's Python installation. `pyflakes` is optional for development. No tests need quota exhaustion, live model calls, API keys, paid credits, or reset redemption.

Read [architecture](docs/ARCHITECTURE.md), [safety](docs/SAFETY.md), [test results](docs/TESTING.md), [limitations](docs/LIMITATIONS.md), and [engineering decisions](docs/DECISIONS.md) before changing any execution path. MIT licensed; see [CONTRIBUTING.md](CONTRIBUTING.md).

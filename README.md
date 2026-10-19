# Codex Auto-Resume

A local desktop companion that **actually continues an explicitly armed Codex conversation after its five-hour included-usage limit resets**. Version 0.2.0 replaces the read-only 0.1.0 prototype with a real App Server continuation adapter.

It uses the existing ChatGPT Plus login and original thread context. It checks fresh backend ordinary-usage permission, both quota windows, account identity, paid-credit state, provider configuration and the latest turn before sending one contextual continuation. Weekly exhaustion pauses and disarms the task until manually rearmed.

Independent community software; not an official OpenAI product.

## Ubuntu: install and use

Python 3.10+, Tk and an installed Codex CLI/desktop runtime are required. If Tk is missing, install `python3-tk` through Ubuntu's package manager.

```sh
cd codex-auto-resume
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

1. Turn ON **Continue automatically when the 5h limit resets**. This connects to or starts the official local Codex App Server daemon; it starts no model work by itself.
2. Click **Choose…**, select the original conversation, then **Arm conversation**. Arm before quota exhaustion, or while the failed task still reports an exhausted five-hour window.
3. Keep the controller running. Once a structured usage-limit failure occurs, it waits until the official reset time and verifies fresh allowance before resuming the same thread.
4. Weekly exhaustion, completion, cancellation, another turn, pending approval, changed account/model/project, paid credits or unverifiable usage stops automatic continuation.

Closing the control window disables/disarms automation, without terminating an already running daemon turn. To wait without a window, use the optional user service described in [INSTALL.md](docs/INSTALL.md). Global ON does not automatically register every conversation.

## Verified behavior

A real two-turn check ran against the authenticated Codex backend: the continuation used the same thread and correctly recalled a token from the first turn. No quota response was mocked for that check. See [redacted evidence](docs/evidence/live-continuation.json).

The full quota-exhaustion/reset event is covered by controlled tests; no live quota was deliberately exhausted. Windows and Wayland have not been tested. There is a small cross-client race between the final state read and submission; the public API has no atomic revision condition. See [LIMITATIONS.md](docs/LIMITATIONS.md).

## Commands

```sh
python3 -m auto_resume doctor --connect
python3 -m auto_resume threads
python3 -m auto_resume enable
python3 -m auto_resume arm THREAD_ID
python3 -m auto_resume run
python3 -m auto_resume disable
```

`run` is a foreground background-controller process; leave it running, or use the user-service template. The native window runs its own controller. Only one controller owns a state file at a time.

## Test, build and uninstall

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify.py --gui
python3 scripts/build.py
python3 scripts/uninstall.py
```

The application has no third-party runtime dependencies. The optional explicit live check uses two tiny genuine included-usage turns: `python3 scripts/live_check.py --run`. Routine tests use controlled fixtures instead of consuming live quota. The simulator remains available as a development tool with `python3 -m auto_resume demo`; normal operation uses the real adapter.

[Architecture](docs/ARCHITECTURE.md) · [Safety](docs/SAFETY.md) · [Test report](docs/TESTING.md) · [Delivery summary](docs/DELIVERY.md). MIT licensed. Nothing is published to GitHub automatically.

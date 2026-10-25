# Codex Auto-Resume

**Pick up where your Codex conversation stopped.**

Resume explicitly armed chats after included usage resets, with optional recovery from saved context checkpoints. Your conversation, project and model stay together.

[![Checks](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml/badge.svg)](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml) · **v0.4.0** · Python 3.10+ · MIT

| Dark mode | Light mode |
| --- | --- |
| ![Dark desktop control panel](docs/screenshots/dark.png) | ![Light desktop control panel](docs/screenshots/light.png) |

Screenshots show the live desktop panel; allowance values are snapshots.

## Get started

Requires an official Codex runtime signed in to ChatGPT Plus, Python 3.10+, and Tk (`python3-tk` on Ubuntu).

```sh
git clone https://github.com/Manouselis/codex-auto-resume.git
cd codex-auto-resume
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

1. The global checkbox starts **ON**; saved choices are remembered.
2. Choose your conversation, then click **Arm conversation**. **Disarm** is right beside it.
3. Enable **Recover context checkpoints** when unfinished work should continue after a context stop.

**Desktop chats need a [native recovery schedule](docs/RECOVERY.md#native-desktop-recovery-experimental).** A paused schedule shows **Schedule paused**. A missing or mismatched schedule stops recovery and shows **Needs attention**.

## What to expect

- Fresh included-usage checks before continuing; weekly exhaustion, paid credits and unknown billing routes block work.
- Original chat and checkpoint preserved; newer cancellations, approvals and task budgets remain stop conditions.
- Fresh arming is timestamped so the guard can distinguish it from older timer cancellations.
- Lost acknowledgements pause for inspection. Automatic submissions are never blindly retried.
- Native wake-ups use normal model turns. Keep Codex open and the computer awake.

The control panel supports dark/light modes, remaining-allowance meters, adjacent Arm/Disarm controls and an activity log. The local suite passes **189 tests**, including **15 GUI checks**. A real scheduled restart after a usage-limit interruption is [recorded](docs/evidence/limit-reset-recovery-0.4.0.json); repeated unattended reset cycles remain unverified. See [Testing](docs/TESTING.md).

[Setup](docs/INSTALL.md) · [Recovery](docs/RECOVERY.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

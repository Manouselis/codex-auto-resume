# Codex Auto-Resume

Resume an explicitly armed Codex conversation after its five-hour included-usage limit resets. The companion waits locally, checks fresh allowance, and sends a continuation in the original conversation with its saved context and configuration.

**Current version: 0.2.1.** Independent community software, licensed under MIT. The verified live setup is Ubuntu with X11 and an existing ChatGPT Plus login.

## Install and arm a conversation

Requirements: Python 3.10+, Tk (`python3-tk` on Ubuntu), and an installed official Codex CLI or desktop runtime signed in to ChatGPT Plus. Other plans and API-key authentication are not supported by this version.

```sh
git clone https://github.com/Manouselis/codex-auto-resume.git
cd codex-auto-resume
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

1. Turn on **Continue automatically when the 5h limit resets**. A fresh installation starts OFF.
2. Click **Choose…**, select the original conversation, and click **Arm conversation**. Global ON alone does not arm tasks.
3. Keep the controller running. It watches for a structured usage-limit failure, waits for the official reset time, and checks included allowance again before continuing.

You can arm a running task or one that has already stopped at its five-hour limit while usage still reports exhaustion. A task running in another Codex runtime may show **Armed — waiting for a confirmed turn result**. This is a monitoring state; it does not interrupt the task or start another turn. Version 0.2.1 fixes the earlier false cancellation error in this case.

Closing the control window turns automation OFF and disarms tasks, including when a background service owns scheduling. For overnight operation without a window, follow the [background service instructions](docs/INSTALL.md#overnight-operation-without-a-window). Keep the computer awake and online, and leave Codex open. A service does not wake a suspended computer.

## When continuation is allowed

The original turn must have a confirmed `usageLimitExceeded` failure and an observed exhausted five-hour window. Before dispatch, the companion checks the original account, model, project and turn, fresh `ordinaryUsageAllowed`, both quota windows, and the included-usage execution route.

- Weekly exhaustion disarms the task. Remaining weekly allowance must also exceed the default 5% reserve.
- Paid or unknown credits, API authentication, custom providers/endpoints, and non-default billing tiers block continuation.
- Completion, confirmed cancellation, a different turn, missing context, or a pending approval stops automation. The companion never answers approvals.
- A lost acknowledgement or uncertain submission pauses the queue without resending. The default limit is three automatic continuation attempts per arming.

These are current-state checks, not a reservation of future usage. The public API also leaves a short race between the final read and submission. See the [safety contract](docs/SAFETY.md) and [remaining limitations](docs/LIMITATIONS.md).

## What has been verified

| Check | Result |
| --- | --- |
| Local Ubuntu suite, including eight native GUI tests | 120 passed; no skips |
| GitHub CI on Ubuntu and Windows, Python 3.10 and 3.13 | All four jobs passed; GUI and platform-specific tests are skipped where appropriate |
| Real same-thread continuation | Two authenticated model turns preserved the original context |
| Arming an externally running desktop turn | Read-only reproduction passed; no thread mutations or model requests |
| Natural five-hour exhaustion followed by reset | Not yet verified live; covered with controlled backend responses |
| Windows desktop continuation, Wayland, real suspend/reboot recovery | Not verified |

The simulator is available for development, while normal operation uses the real App Server adapter. Read the [test report and evidence](docs/TESTING.md) for the scope of each check.

## Useful commands

After installation:

```sh
~/.local/bin/codex-auto-resume doctor --connect
~/.local/bin/codex-auto-resume threads
~/.local/bin/codex-auto-resume enable
~/.local/bin/codex-auto-resume arm THREAD_ID
~/.local/bin/codex-auto-resume status
~/.local/bin/codex-auto-resume disarm THREAD_ID
~/.local/bin/codex-auto-resume disable
```

Replace `THREAD_ID` with the exact ID from `threads`. `doctor --connect` checks the schema and reads account/quota metadata without starting inference. To run a foreground controller, use `~/.local/bin/codex-auto-resume run` and leave that terminal running. Only one controller owns a state file at a time.

To update an installed copy, pull the repository and rerun the installer. A controller already running must be restarted to load new application code; normal close/stop disarms tasks, so enable and rearm them afterward. See [updating safely](docs/INSTALL.md#update-an-existing-installation).

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify.py --gui
python3 scripts/build.py
```

Application runtime uses the Python standard library. GUI tests require Tk and a graphical session; screenshot capture uses Pillow. Routine tests send no live model requests. `python3 scripts/live_check.py --run` is a separate opt-in check that sends two genuine included-usage turns.

The repository is [Manouselis/codex-auto-resume](https://github.com/Manouselis/codex-auto-resume). Start with the [documentation index](docs/README.md), [release history](docs/CHANGELOG.md), or [contribution guide](CONTRIBUTING.md). To uninstall, stop the companion and follow [the uninstall instructions](docs/INSTALL.md#uninstall).

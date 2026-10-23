# Codex Auto-Resume

Resume an explicitly armed Codex conversation after its five-hour included-usage limit resets, or opt in to recovery when a run ends at a context-budget checkpoint. The local controller can continue daemon-owned conversations. Desktop-owned conversations require Codex’s native scheduler; the companion cannot take over the desktop’s exclusive writer. Both paths preserve the original conversation and check available included usage.

**Current version: 0.3.0. The first real native scheduled wake-up and research continuation passed on Ubuntu. Repeated checkpoint cycles and natural quota-reset recovery remain unverified.** Independent community software, licensed under MIT. The verified live setup is Ubuntu with X11 and an existing ChatGPT Plus login.

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

When a background service owns scheduling, closing its control panel keeps armed work active; use OFF to disarm. Closing a window that owns the only controller still disables automation. For overnight operation without a window, follow the [background service instructions](docs/INSTALL.md#overnight-operation-without-a-window). Keep the computer awake and online, and leave Codex open. A service does not wake a suspended computer.

## Desktop conversations need native recovery

A desktop chat may keep its exclusive writer while idle. Arming it for external monitoring does not grant the companion permission to restart it. The separate App Server rejects restoration; queue APIs also require successful restoration and cannot bypass that ownership. Version 0.3.0 reports this as **not sent** and pauses.

For desktop chats, the new experimental mode uses a native heartbeat in the original chat. Its prompt runs `native-claim` before substantive work and records a checkpoint or stop through `native-finish`. The external controller skips native-bound chats. This setup requires an explicit native scheduling choice; the GUI checkbox alone does not create it. See [native setup and its limits](docs/RECOVERY.md#native-desktop-recovery-experimental).

Each native wake-up is a normal model turn, even when the guard declines research. Native admission is governed by Codex’s account settings; the companion cannot check billing before that initial model turn. The guard checks fresh usage and credits before authorizing substantive work. Default limits are three external continuation attempts or ten admitted native work turns per arming.

## When continuation is allowed

Quota recovery requires a confirmed `usageLimitExceeded` failure and an observed exhausted five-hour window. Version 0.3.0 also offers explicit per-arming context-checkpoint recovery: it can continue unfinished work after a recognized context stop while included allowance is available. A context budget is separate from the five-hour allowance; see [the recovery guide](docs/RECOVERY.md). Before dispatch, the companion checks the original account, model, project and turn, fresh `ordinaryUsageAllowed`, both quota windows, and the included-usage execution route.

- Weekly exhaustion disarms the task. Remaining weekly allowance must also exceed the default 5% reserve.
- Paid or unknown credits, API authentication, custom providers/endpoints, and non-default billing tiers block continuation.
- Ordinary completion, confirmed cancellation, a different turn, missing context, or a pending approval stops automation. The companion never answers approvals.
- A lost acknowledgement or uncertain submission pauses the queue without resending. External dispatch allows three continuation attempts per arming; native mode allows ten admitted work turns.

These are current-state checks, not a reservation of future usage. The public API also leaves a short race between the final read and submission. See the [safety contract](docs/SAFETY.md) and [remaining limitations](docs/LIMITATIONS.md).

## What has been verified

| Check | Result |
| --- | --- |
| Local Ubuntu suite, including ten native GUI tests | 167 passed; no skips |
| Recorded 0.3.0 GitHub CI on Ubuntu and Windows, Python 3.10 and 3.13 | All four jobs passed at code commit `701b654`; headless platform skips apply |
| Real same-thread continuation in a daemon-owned test chat | Two authenticated model turns preserved the original context; this did not test desktop writer ownership |
| Desktop writer conflict | Reproduced live; separate-server restoration and queue start are refused |
| Native desktop recovery | First real scheduled wake-up passed: guard admitted work in the original chat, which read the saved checkpoint and resumed research |
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
# Opt in to context-budget recovery instead:
~/.local/bin/codex-auto-resume arm THREAD_ID --recover-context
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

# Installation and use

## Ubuntu 22.04

Requirements: Python 3.10+, `python3-tk`, and an installed official Codex CLI or desktop runtime signed in to ChatGPT Plus.

```sh
cd codex-auto-resume
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

1. Turn the switch ON. The companion starts/connects to the official local App Server daemon and verifies the account. It does not change login, enable remote control or start inference by itself.
2. Click **Choose…**, select the original running task, then **Arm conversation**. A task already stopped by a structured usage-limit failure can also be armed while the five-hour window remains exhausted.
   When another Codex runtime owns the running turn, the companion can show **Armed — waiting for a confirmed turn result**. It keeps monitoring; this status does not send a continuation or interrupt the original turn.
3. Leave the control window running. It waits through a five-hour interruption and sends one continuation in the same context once fresh included usage is available.
4. OFF immediately disarms scheduled work. Weekly exhaustion, completion or cancellation also stops automatic continuation. Re-enable/rearm is always explicit.

The installer creates its own application, launcher, manifest and Applications-menu entry under `~/.local`. It never modifies unrelated Codex settings. Default-OFF applies to fresh state. Existing explicit preference/task state is preserved during updates. A custom prefix is supported with `--prefix /private/path`.

Closing the control window turns Auto-Resume OFF and disarms tasks. An already acknowledged daemon turn keeps running. For long waits without an open window, use a user service.

## Optional user service

After the default installation:

```sh
mkdir -p ~/.config/systemd/user
cp packaging/codex-auto-resume.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now codex-auto-resume.service
~/.local/bin/codex-auto-resume ui
```

The service owns scheduling; the window controls the same state. Closing the window still switches OFF. To keep background operation enabled after closing the control window, explicitly run `~/.local/bin/codex-auto-resume enable` afterward. Then use `status` or reopen the window to inspect the task. Disarmed tasks must be explicitly rearmed.

Stopping the service normally disarms tasks. A process crash preserves waiting state, while uncertain submissions pause instead of retrying. Normal shutdown/SIGTERM currently disarms conservatively, so automatic rearming after a normal reboot is unsupported.

```sh
systemctl --user disable --now codex-auto-resume.service
```

No service/startup item is enabled automatically by installation. The official App Server daemon is a separate supported Codex component; the companion starts it on explicit enable, and does not stop it on disable or uninstall.

## CLI

```sh
python3 -m auto_resume enable
python3 -m auto_resume threads
python3 -m auto_resume arm THREAD_ID
python3 -m auto_resume run
```

Leave `run` running. Use another terminal for `status`, `disable`, or `disarm THREAD_ID`. `doctor --connect` reads account/quota and reports compatibility without inference. Place global flags such as `--state /private/task.sqlite3` before the subcommand.

Default state is `$XDG_STATE_HOME/codex-auto-resume/state.sqlite3`, or `~/.local/state/codex-auto-resume/state.sqlite3`. Simulation has separate state. Do not point this option at a Codex database.

## Windows

The core and `.cmd` installer remain portable, but **real continuation on Windows is not verified**. It currently needs the official local Unix-socket-compatible daemon transport; unsupported socket behavior fails closed. No Windows release is claimed. `py -m auto_resume demo` can exercise the core without a daemon. Windows transport and ACL validation remain work for an appropriate host.

## Uninstall

Stop the controller/window/service first:

```sh
python3 scripts/uninstall.py
```

Use the same `--prefix` for custom installations. Remove the optional user-service file if installed. Local task history is preserved. The official Codex daemon and settings are left untouched.

## Troubleshooting

- Missing CLI: install Codex; the Ubuntu desktop-bundled runtime is preferred when present.
- Failed daemon/socket connection: turn OFF, verify login in Codex, then enable again. `codex app-server daemon version` shows the official daemon's status. No remote control is required.
- Missing/null permission, unknown credits, unsupported quota bucket or stale history: the task pauses; inspect the reason and rearm only after resolving it.
- An approval is outstanding: automation does not answer it. Inspect the original work manually; cross-client approval routing is not verified.
- A running task incorrectly reports user cancellation when arming: update to 0.2.1 or later. Older readers confuse an unfinished external-history marker with a confirmed interruption. A genuine cancellation still requires manual inspection and does not resume automatically.
- GUI unavailable: install Tk/use a graphical session, or use the CLI/user service.
- Wayland: no keyboard automation is used, but the Tk/XWayland experience has not been tested.
- Uncertain submission: inspect the original conversation; do not clear a reservation to force a retry.

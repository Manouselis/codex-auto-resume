# Installation and operation

[Documentation index](README.md) · [Troubleshooting](TROUBLESHOOTING.md)

## Requirements

The verified live setup is Ubuntu 22.04 with X11, Python 3.10+, Tk (`python3-tk`), and an installed official Codex CLI or desktop runtime signed in to ChatGPT Plus. The companion prefers the desktop-bundled runtime when available. Application runtime uses the Python standard library and does not require an API key.

## Install on Ubuntu

```sh
git clone https://github.com/Manouselis/codex-auto-resume.git
cd codex-auto-resume
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

The installer creates the application, launcher, manifest and Applications-menu entry under `~/.local`. It does not enable a startup service. Use `--prefix /private/path` for a custom installation location; the service recipes below assume the default prefix.

A fresh installation starts OFF. Updating preserves the existing opt-in preference and local task state.

## Arm and monitor a conversation

1. Turn the switch ON. The companion starts or connects to the official local App Server daemon and verifies the account. Enabling alone starts no model work.
2. Click **Choose…**, select the original conversation, and click **Arm conversation**. You can arm a running turn, or a structured usage-limit failure while the five-hour window still reports exhaustion.
3. Leave the controller running. It watches for a confirmed five-hour interruption, waits for the official reset time, and checks fresh included allowance before sending one continuation in the original conversation.
4. Use **Disarm selected** for one task or switch OFF to disarm all tasks. Switching back ON does not rearm them.

To also recover a recognized context-budget checkpoint, select **Also recover context-budget checkpoints for this arming**, or use `arm THREAD_ID --recover-context`. This is separate from quota recovery and starts unchecked. Read [Recovery modes](RECOVERY.md) for its scope.

A task running in another Codex runtime may show **Armed — waiting for a confirmed turn result**. Its history is available, but the companion cannot yet verify a terminal result. It continues monitoring without loading or interrupting the thread. This status alone can never authorize continuation.

The table's **Next check · local time** column is the next scheduled check. For running or unresolved work it is a polling time; during a reset wait it includes the reset verification delay. It is not a guarantee that a new turn will start at that moment.

Closing a service-owned control panel leaves the background controller and armed tasks enabled. Use OFF or `disable` to stop them. Closing a window-owned controller still turns automation OFF and disarms tasks. An already acknowledged daemon turn keeps running. Use `status` from a terminal to inspect overnight operation without opening a control window.

## Overnight operation without a window

If the window is the only controller, close it before switching to a service. Enable and arm the conversation explicitly. Replace `THREAD_ID` with the exact ID printed by `threads`.

```sh
~/.local/bin/codex-auto-resume enable
~/.local/bin/codex-auto-resume threads
~/.local/bin/codex-auto-resume arm THREAD_ID
```

If `codex-auto-resume.service` is already active, keep it running and skip the start command below. Otherwise, start a session service:

```sh
systemd-run --user --unit=codex-auto-resume \
  --description="Codex Auto-Resume continuation controller" \
  --property=Restart=on-failure \
  --property=RestartSec=30 \
  --property=UMask=0077 \
  ~/.local/bin/codex-auto-resume run
```

Confirm the task is eligible and the service is running:

```sh
~/.local/bin/codex-auto-resume status
systemctl --user status codex-auto-resume.service
```

Keep the computer awake, online and logged in, and leave Codex open. The service runs independently of the launching terminal, but it does not prevent suspend or wake the computer. This transient unit does not install a startup item or provide automatic rearming after reboot.

Ordinary completion, confirmed cancellation, a superseding turn, pending approval, exhausted weekly usage, or an unverifiable safety check stops automatic continuation. A recognized context checkpoint is eligible only when that recovery mode was explicitly enabled. The default is at most three continuation attempts per arming. See [Safety](SAFETY.md) for the full conditions.

To stop monitoring:

```sh
~/.local/bin/codex-auto-resume disable
systemctl --user stop codex-auto-resume.service
```

## Optional installed user service

Choose this instead of the transient service when you want an installed service definition. If a transient unit with the same name is active, stop it first; normal stop disarms tasks.

```sh
mkdir -p ~/.config/systemd/user
cp packaging/codex-auto-resume.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now codex-auto-resume.service
~/.local/bin/codex-auto-resume enable
~/.local/bin/codex-auto-resume arm THREAD_ID
~/.local/bin/codex-auto-resume status
```

The service template uses the default installation path. Its enabled startup definition does not guarantee armed work survives a normal reboot: normal stop/SIGTERM disarms conservatively. A crash can preserve a reset wait, while an uncertain submission pauses rather than retrying. Real reboot and logout recovery have not been verified.

To remove this startup service:

```sh
systemctl --user disable --now codex-auto-resume.service
```

## Update an existing installation

Pull the repository and rerun the installer. Then restart the controller to load the new application code. A normal restart disarms tasks, so explicitly enable and rearm the desired conversation afterward.

```sh
git pull --ff-only
python3 scripts/install.py
~/.local/bin/codex-auto-resume --version
```

For a service, use `systemctl --user restart codex-auto-resume.service`, followed by `enable` and `arm THREAD_ID`. For a window-owned controller, close the old window, reopen `ui`, turn ON and rearm. These instructions concern the companion; they do not require interrupting the original Codex conversation.

## CLI and local data

The installed launcher works from any directory. From the source checkout, `python3 -m auto_resume` exposes the same commands. `run` stays in the foreground; leave the terminal running unless a service owns it. Only one controller can own a state file, while other CLI commands can inspect or control that state.

```sh
~/.local/bin/codex-auto-resume doctor --connect
~/.local/bin/codex-auto-resume status
~/.local/bin/codex-auto-resume disarm THREAD_ID
```

`doctor --connect` inspects the installed schema and reads account/quota metadata without inference. Global flags go before the subcommand, for example `--state /private/task.sqlite3 status`.

Default real state is `$XDG_STATE_HOME/codex-auto-resume/state.sqlite3`, normally `~/.local/state/codex-auto-resume/state.sqlite3`. Simulation uses a separate database. Never point `--state` at a Codex database. State contains task/account/project identifiers and safety metadata; it contains no conversation text or credentials.

## Windows

Hosted Windows CI passed the headless core, packaging, installation/update/uninstall and simulation checks on Python 3.10 and 3.13. Windows real Codex continuation, GUI integration and ACL behavior remain unverified. Live execution depends on the official local daemon transport; unsupported socket behavior stops safely.

`py -m auto_resume demo` exercises the core without a daemon. Passing that simulation is not evidence of live Windows continuation.

## Uninstall

Stop the companion window or service first, then run from the source checkout:

```sh
python3 scripts/uninstall.py
```

Use the same `--prefix` for a custom installation. Remove an optional installed user-service definition separately if you created one. The uninstaller preserves local task history. The official Codex daemon is a separate component and is not stopped or removed by companion disable/uninstall.

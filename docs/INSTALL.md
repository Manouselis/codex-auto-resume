# Installation and operation

## Ubuntu 22.04

1. Install Python 3.10+ and Tk if missing: `sudo apt install python3 python3-tk`. The project installer itself never uses sudo.
2. From the project folder, run:

   ```sh
   python3 scripts/install.py
   ~/.local/bin/codex-auto-resume ui
   ```

3. Use **Check usage** for read-only usage information. The switch defaults OFF. Turning it ON enables observation, not live continuation. Closing the window disables/disarms automation.
4. To exercise the working continuation engine without connecting to Codex:

   ```sh
   ~/.local/bin/codex-auto-resume demo
   ~/.local/bin/codex-auto-resume --simulation ui
   ```

The installer creates only its own zipapp, a launcher, a manifest, and an Applications-menu entry under `~/.local`. The menu's **Toggle Auto-Resume observation** action also changes the switch with one action. Reinstallation preserves application state and does not touch Codex configuration.

Choose a custom location with `python3 scripts/install.py --prefix /your/private/prefix`. The installed launcher uses the same Python interpreter used for installation. Keep that interpreter available. A standalone zipapp can also run directly with Python; build using `python3 scripts/build.py`.

## Optional user service

The default window owns scheduling. For observation without an open window, use the supplied systemd user-service template after a default-prefix installation:

```sh
mkdir -p ~/.config/systemd/user
cp packaging/codex-auto-resume.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now codex-auto-resume.service
```

This is opt-in and is not run by the installer. It stays OFF until explicitly enabled. Opening the control window while the service owns the controller connects to the same state instead of starting a competing scheduler. State changes cancel scheduled work immediately; a newly armed task is observed on the service's next wake, within 30 seconds.

```sh
systemctl --user disable --now codex-auto-resume.service
```

A normal service stop disables and disarms tasks. System shutdown can also send SIGTERM, so unattended rearming after a normal reboot is intentionally unsupported. A process crash preserves waiting tasks and revalidates them after restart. No user lingering, system-wide service, privileged daemon or automatic login is configured.

## Windows

The core, Tk UI, process transport, OS-lock branch and `.cmd` installer are implemented. **Windows execution and installation have not been tested on a Windows host.** A CI matrix is supplied for later verification; no successful Windows run is claimed.

With Python 3.10+ including Tk installed:

```powershell
py -m auto_resume demo
py -m auto_resume --simulation ui
py scripts/install.py
```

The default launcher is `%LOCALAPPDATA%\Programs\CodexAutoResume\bin\codex-auto-resume.cmd`. It is not added to PATH. Use `"<launcher path>" ui` in cmd, or `& '<launcher path>' ui` in PowerShell. No startup task, registry setting or tray icon is installed. Windows ACL hardening remains unverified. Live automatic continuation remains blocked.

## Local CLI

```sh
python3 -m auto_resume doctor --connect
python3 -m auto_resume status
python3 -m auto_resume enable
python3 -m auto_resume disable
python3 -m auto_resume arm THREAD_ID
python3 -m auto_resume disarm THREAD_ID
```

`arm` accepts only known running tasks or structured usage-limit failures. Live registration can be refused because a read-only process cannot prove original runtime ownership and configuration. It cannot make a live thread execute.

Default state: `$XDG_STATE_HOME/codex-auto-resume/state.sqlite3`, or `~/.local/state/codex-auto-resume/state.sqlite3`. Windows uses `%LOCALAPPDATA%\codex-auto-resume\state.sqlite3`. Simulation uses a different file. For a clean test, place `--state /private/new-file.sqlite3` **before** the subcommand. Do not point it at any Codex file.

## Uninstall

Stop the window/service first, then run `python3 scripts/uninstall.py`. For a custom prefix, pass the same `--prefix` used at installation. Remove the optional service file manually if installed. The uninstaller removes only paths in its allowlisted manifest, preserves application history, and never deletes Codex files.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Missing Codex CLI | Install Codex; run `doctor` again. The desktop's bundled runtime is preferred on this Ubuntu installation. |
| Invalid authentication | Sign in through Codex itself. This companion cannot change authentication. |
| Unable to read usage | Check network and login, then run `doctor --connect`. Null/missing fields stay unavailable. |
| App Server will not initialize | Check user-directory permissions. The runtime may need to write its own logs; do not grant broad filesystem privileges as a workaround. |
| Unsupported version/schema | Preserve state and record the redacted doctor output. Execution stays blocked. |
| UI unavailable | Install `python3-tk` and open a graphical session. Headless `status`, `disable`, and `demo` do not need Tk. |
| X11 versus Wayland | No keyboard or coordinate automation is used. X11 GUI was tested; Wayland was not. Tk's Wayland/XWayland availability depends on the OS. |
| Background failure | Use `systemctl --user status codex-auto-resume` and `journalctl --user -u codex-auto-resume`. Do not publish private runtime logs. |
| Uncertain continuation | Inspect the original conversation manually. Do not delete reservations to force a retry. This release has no live submissions to reconcile. |
| Native toggle absent | This is a separate companion window. No supported native Settings injection surface was established. |

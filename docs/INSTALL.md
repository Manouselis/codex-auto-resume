# Install Codex Auto-Resume

Download your installer from the [v0.8.3 release](https://github.com/Manouselis/codex-auto-resume/releases/tag/v0.8.3). Python and Tk are bundled. Open the official Codex desktop app and sign in to ChatGPT Plus before adding conversations.

## Ubuntu

Use the **linux-x64.deb** on Ubuntu 22.04 or later, on an x64 computer.

1. In Files, open the downloaded package with **Software Install** or your graphical package manager. If double-click opens an archive, right-click → **Open With** → **Software Install**.
2. Click **Install** and approve Ubuntu's normal installation prompt.
3. Open **Codex Auto-Resume** from Applications. Pin it to your dock if desired.

The application lives in `/opt/codex-auto-resume` and is available at `/usr/bin/codex-auto-resume`. Its installed runtime does not need system Python. A per-user systemd controller starts on demand. Closing the panel leaves recovery enabled when a background controller is active. Without a user systemd session, keep the panel open or minimized.

### Upgrade an existing Ubuntu installation

Close Software Install if it is stalled. From the folder containing the new package, install it over the old version with APT. This also works if App Center only shows **Installed**.

```sh
sudo apt install ./codex-auto-resume-0.8.3-linux-x64.deb
dpkg-query -W codex-auto-resume
```

Quit the older window and launch `/usr/bin/codex-auto-resume`. This path also avoids a shortcut left by a source install. If the new window reports **Older background controller active**, close it and stop the active Auto-Resume service before relaunching. Use `systemctl --user stop codex-auto-resume.service` for older releases or `systemctl --user stop codex-auto-resume-native.service` for a previous native controller. Stopping the controller disarms its queue, so select the chats you want to monitor again. The upgrade preserves saved recovery history.

Screen locking with Super+L is allowed. The sleep inhibitor is held only while at least one eligible chat is armed. Power off, forced suspension and lid policies can still stop execution; the status line reports when sleep prevention is unavailable. Login is required; this release does not install an always-on boot service.

## Windows 11

Open **windows-x64-setup.exe**. The wizard installs for your user, creates Start and desktop shortcuts, and offers to launch Auto-Resume. Administrator access and Python are not required. The x64 app also runs through Windows 11 ARM's x64 emulation; it is not a native ARM binary.

The community installer is not Authenticode signed. If SmartScreen appears, verify that the download is from this repository's release, then use **More info → Run anyway** if Windows offers it. Managed devices may require administrator approval.

Keep Auto-Resume open/minimized while recovery is armed. The app requests prevention of idle system sleep without preventing screen locking or display sleep. Closing it disarms recovery. The official Codex byte proxy provides access to its local daemon; unsupported runtimes stop with an actionable error rather than starting a second writer.

Uninstall using **Settings → Apps → Installed apps → Codex Auto-Resume → Uninstall**. Close the app first.

If Auto-Resume finds the Store app but asks for the standalone runtime, install the [official Codex CLI for Windows](https://developers.openai.com/codex/cli) and reopen Auto-Resume. The standalone CLI can initialize the local Codex daemon using your existing sign-in.

## macOS

Choose **macos-arm64.dmg** for Apple silicon (macOS 14+) or **macos-x64.dmg** for Intel (macOS 15+).

1. Open the disk image.
2. Drag **Codex Auto-Resume.app** to **Applications**.
3. Eject the disk image and open the app from Applications.

The app is ad-hoc signed for bundle integrity but is not Developer ID signed or notarized. macOS may initially block a downloaded copy. After attempting to open it, use **System Settings → Privacy & Security → Open Anyway**, if offered. Organizational policies may prohibit this. Do not disable Gatekeeper globally.

Keep Auto-Resume open/minimized; closing it disarms recovery. While armed, `caffeinate -i` requests prevention of idle sleep. Screen locking remains available. Quit before replacing the application during an upgrade. To uninstall, drag it from Applications to Trash.

## First use

Opening the app checks **Continue automatically when the 5h limit resets**. This alone sends no message: select a chat using **Add conversation** to arm it. Selecting an idle chat explicitly requests one `continue`. Running chats are monitored without an extra message. A disabled or normally completed chat disappears from the queue.

The app discovers standard Codex desktop/CLI install locations and the desktop's managed runtime; no API key entry is needed. If it cannot find Codex, install/open the official desktop app, sign in, and reopen Auto-Resume. The native queue requires a compatible runtime (live-tested with 0.166). The app does not download, update, stop or replace an existing Codex runtime.

## Updates and data

On Windows, install version 0.8.1 once over the existing app. From then on, Auto-Resume checks GitHub at startup and every six hours while open. You can also select **Check for updates**. When a release appears, choose **Update to** and confirm. Auto-Resume downloads and verifies the installer, briefly closes, then reopens after installation. Review the queue after reopening if a continuation was in flight.

On Ubuntu, use the [APT upgrade steps](#upgrade-an-existing-ubuntu-installation). On macOS, quit the app before replacing it in Applications.

Recovery metadata is preserved across upgrades/uninstall. It contains chat/account/project identifiers and guard state, not credentials or message text. Defaults:

- Ubuntu/macOS: `$XDG_STATE_HOME/codex-auto-resume/state.sqlite3`, normally `~/.local/state/codex-auto-resume/state.sqlite3`.
- Windows: `%LOCALAPPDATA%\codex-auto-resume\state.sqlite3`.

Uninstalling never removes Codex. Reinstalling does not silently re-arm previously disarmed chats. Disable recovery before uninstalling.

## Source/developer installation

The smaller `.pyz` is for users who already have Python 3.10+ and Tk. It is not the graphical installer. From a source checkout:

```sh
python3 scripts/install.py
~/.local/bin/codex-auto-resume ui
```

This retains the legacy per-user launcher. Close an old copy before starting a native installer version; both share the same guarded state/controller lock. See [Building](BUILDING.md) for release packaging and [Troubleshooting](TROUBLESHOOTING.md) for connection issues.

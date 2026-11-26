# Install Codex Auto-Resume

Download your installer from the [project downloads](https://manouselis.github.io/codex-auto-resume/#downloads). Python and Tk are bundled. Open the official Codex desktop app and sign in to ChatGPT Plus before adding conversations.

## Ubuntu

Use the **linux-x64.deb** on Ubuntu 22.04 or later, on an x64 computer.

1. In Files, open the downloaded package with **Software Install** or your graphical package manager. If double-click opens an archive, right-click → **Open With** → **Software Install**.
2. Click **Install** and approve Ubuntu's normal installation prompt.
3. Open **Codex Auto-Resume** from Applications. Pin it to your dock if desired.

The application lives in `/opt/codex-auto-resume` and is available at `/usr/bin/codex-auto-resume`. Its installed runtime does not need system Python. A per-user systemd controller starts on demand. Closing the panel leaves recovery enabled when a background controller is active. Without a user systemd session, keep the panel open or minimized.

### Upgrade an existing Ubuntu installation

Close Software Install if it is stalled. From the folder containing the new package, install it over the old version with APT. This also works if App Center only shows **Installed**. Replace `VERSION` with the number in your downloaded filename.

```sh
sudo apt install ./codex-auto-resume-VERSION-linux-x64.deb
dpkg-query -W codex-auto-resume
```

Quit the older window and open **Codex Auto-Resume** from Applications or your existing dock pin. Starting with 0.8.7, the DEB checks the installing account and active sessions for the standard source-generated shortcut and archives it beside the original path as a hidden `.source-backup` file. Ubuntu then uses the package launcher for the same app ID. Custom shortcuts and saved recovery data are preserved. If the new window reports **Older background controller active**, close it and stop the active Auto-Resume service before relaunching. Use `systemctl --user stop codex-auto-resume.service` for older releases or `systemctl --user stop codex-auto-resume-native.service` for a previous native controller. Stopping the controller disarms its queue, so select the chats you want to monitor again. The upgrade preserves saved recovery history.

Screen locking with Super+L is allowed. The sleep inhibitor is held only while at least one eligible chat is armed. Power off, forced suspension and lid policies can still stop execution; the status line reports when sleep prevention is unavailable. Login is required; this release does not install an always-on boot service.

## Windows 11

Open **windows-x64-setup.exe**. The wizard explains what it installs, lets you review the destination, and shows a setup log. On the finish page, leave **Open Codex Auto-Resume** checked to open the dashboard and add a conversation. Setup creates Start and desktop shortcuts for your account. Administrator access and Python are not required. The x64 app also runs through Windows 11 ARM's x64 emulation; it is not a native ARM binary.

The community installer is not Authenticode signed. If SmartScreen appears, verify that the download is from this repository's release, then use **More info → Run anyway** if Windows offers it. Managed devices may require administrator approval.

Keep Auto-Resume open/minimized while recovery is armed. The app requests prevention of idle system sleep without preventing screen locking or display sleep. Closing it disarms recovery. The official Codex byte proxy provides access to its local daemon; unsupported runtimes stop with an actionable error rather than starting a second writer.

Uninstall using **Settings → Apps → Installed apps → Codex Auto-Resume → Uninstall**. Close the app first.

If an older Auto-Resume release asks for the standalone runtime even though the Store app is installed, upgrade Auto-Resume. Starting in 0.8.4 it can use the bundled runtime to list conversations and access the desktop queue.

If the dashboard fails to open, see [startup troubleshooting](TROUBLESHOOTING.md#auto-resume-cannot-start).

## macOS

Choose **macos-arm64.dmg** for Apple silicon (macOS 14+) or **macos-x64.dmg** for Intel (macOS 15+).

1. Open the disk image.
2. Drag **Codex Auto-Resume.app** to **Applications**.
3. Eject the disk image and open the app from Applications.

The app is ad-hoc signed for bundle integrity but is not Developer ID signed or notarized. macOS may initially block a downloaded copy. After attempting to open it, use **System Settings → Privacy & Security → Open Anyway**, if offered. Organizational policies may prohibit this. Do not disable Gatekeeper globally.

Keep Auto-Resume open/minimized; closing it disarms recovery. While armed, `caffeinate -i` requests prevention of idle sleep. Screen locking remains available. Quit before replacing the application during an upgrade. To uninstall, drag it from Applications to Trash.

## First use

Opening the app checks **Continue automatically when the 5h limit resets**. Use **Add conversation** to arm an idle or running chat. It opens in Codex and appears as **Armed ahead**. Start or continue working in Codex. You can queue several chats before the limit runs out. Normal manual turns leave a chat armed. A confirmed five-hour interruption moves it to reset recovery, and normal completion after automatic recovery removes it. **Disarm** removes a chat at any time.

The app discovers standard Codex desktop and CLI install locations. Open the official desktop app and sign in before using Auto-Resume. If the discovered runtime lacks a managed daemon package, Auto-Resume uses its local stdio App Server to list conversations and access the desktop's native queue. This path requires a runtime that supports the native queue. The app does not download, update, stop or replace an existing Codex runtime.

## Updates and data

Starting with 0.8.4, the footer shows the installed version. The Windows installer, Ubuntu DEB, and installed macOS app check GitHub at startup and every six hours while open. Version 0.8.6 and later discover updates through GitHub’s public release feed and reads the installer’s published SHA-256 checksum. When an update is available, a popup asks whether to install it. If you decline, **Update to** remains available in the footer. Auto-Resume verifies the download, installs it in place, and reopens the app.

Ubuntu uses APT and prompts for administrator authorization. If its background controller was active, select the chats you want to monitor again after the upgrade. macOS updates the installed app bundle and may request administrator authorization for a protected Applications folder. Copy the app from its disk image to Applications before opening it.

If the update check in 0.8.4 or earlier fails, close the app and download the current installer from the [project website](https://manouselis.github.io/codex-auto-resume/#downloads). Run the Windows installer, use the [APT upgrade steps](#upgrade-an-existing-ubuntu-installation) on Ubuntu, or replace the macOS app in Applications.

The local state database retains recovery metadata and any custom recovery messages across upgrades and uninstall. It stores chat/account/project identifiers and guard state. Auto-Resume does not copy conversation transcripts or credentials into it. Defaults:

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

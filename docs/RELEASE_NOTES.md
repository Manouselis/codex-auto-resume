Download the installer for your computer below. Python and Tk are included. Install the official Codex desktop app and sign in to ChatGPT Plus first.

- Ubuntu x64: use Software Install for a fresh install. To upgrade from an earlier release, run `sudo apt install ./codex-auto-resume-0.8.5-linux-x64.deb` from the download folder, then reopen Auto-Resume.
- Windows 11: open `windows-x64-setup.exe` and follow the wizard (also runs on Windows 11 ARM through x64 emulation).
- macOS: choose `macos-arm64.dmg` for Apple silicon (14+) or `macos-x64.dmg` for Intel (15+); drag the app to Applications.

Use **Add conversation** to arm idle or running chats ahead of the five-hour limit. Keep working in Codex. These chats stay queued through ordinary manual turns, and Auto-Resume waits for verified included usage before recovering a confirmed interruption. **Disarm** removes a chat from the queue.

Auto-Resume checks for updates on startup through GitHub’s public release feed and verifies the installer checksum. Confirm the popup to install the update and reopen the app. If the update check fails in 0.8.4 or earlier, download the installer for 0.8.5 below and install it over your existing copy.

When the Microsoft Store runtime lacks a standalone daemon package, Auto-Resume can use the bundled App Server to list conversations and access the desktop queue.

Auto-Resume keeps explicitly armed usage-limited desktop goals in the queue. Once included allowance is available, it reactivates the goal and wakes the original Codex chat. **Running** appears after the app confirms the new turn.

This community beta is unsigned (macOS uses an ad-hoc bundle signature). SmartScreen/Gatekeeper may ask for confirmation; see the installation guide. Live Codex continuation is verified on Ubuntu with runtime 0.166. Automated installer/GUI tests on other OSes use isolated invented data; live cross-platform Codex integration, downloaded-app security prompts and repeated unattended quota-reset cycles remain unverified.

Included smoke JSON reports identify the exact tested hosts and timings. `SHA256SUMS` covers the downloadable installers, source and developer zipapp. The `.pyz` is the optional developer build, not the graphical installer.

[Installation](https://github.com/Manouselis/codex-auto-resume/blob/main/docs/INSTALL.md) · [Test scope](https://github.com/Manouselis/codex-auto-resume/blob/main/docs/TESTING.md) · [Source](https://github.com/Manouselis/codex-auto-resume)

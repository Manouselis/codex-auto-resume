# <img src="auto_resume/assets/icon.png" width="42" alt=""> Codex Auto-Resume

**Keep your Codex chats moving when included usage resets.**

A desktop companion that resumes explicitly armed Codex conversations in the same chat, with the same project and model. Add multiple conversations to the queue before your five-hour allowance runs out.

[Project website](https://manouselis.github.io/codex-auto-resume/)

[![Checks](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml/badge.svg)](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml)
[![Desktop installers](https://github.com/Manouselis/codex-auto-resume/actions/workflows/desktop.yml/badge.svg)](https://github.com/Manouselis/codex-auto-resume/actions/workflows/desktop.yml) · **v0.8.5 beta** · MIT

## Download and open

Python and Tk are bundled. Install the official Codex desktop app and sign in to ChatGPT Plus first.

| Your computer | Download | Install |
| --- | --- | --- |
| Ubuntu 22.04+ · x64 | [Ubuntu installer](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.5/codex-auto-resume-0.8.5-linux-x64.deb) | Open with Software Install for a fresh install. Use [APT for upgrades](docs/INSTALL.md#upgrade-an-existing-ubuntu-installation). |
| Windows 11 · x64 / ARM with x64 emulation | [Windows installer](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.5/codex-auto-resume-0.8.5-windows-x64-setup.exe) | Open the installer, then launch from Start. |
| macOS · Apple silicon, 14+ | [Apple silicon app](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.5/codex-auto-resume-0.8.5-macos-arm64.dmg) | Open the disk image and drag the app to Applications. |
| macOS · Intel, 15+ | [Intel app](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.5/codex-auto-resume-0.8.5-macos-x64.dmg) | Open the disk image and drag the app to Applications. |

These community beta installers are unsigned, so Windows and macOS may ask for confirmation. See [installation help](docs/INSTALL.md), [checksums and release files](https://github.com/Manouselis/codex-auto-resume/releases/tag/v0.8.5), and the [compatibility test scope](docs/TESTING.md).

Installed copies show their version in the footer and check for updates when opened. Version 0.8.5 uses GitHub’s public release feed and published checksums. If **Check for updates** fails in an older copy, close it and install 0.8.5 over it using the download above.

1. Open Auto-Resume. **Continue automatically when the 5h limit resets** starts checked.
2. Click **Add conversation**, then select an idle or running chat. The chat opens in Codex and shows **Armed ahead** in the queue. Start or keep working in Codex. Repeat to queue more chats.
3. Armed chats stay queued through ordinary manual turns. After a confirmed five-hour interruption, Auto-Resume waits for the reset and verifies fresh included usage before resuming. Click **Disarm** to remove a chat. Normal completion after automatic recovery also removes it.

Allowance refreshes every minute. Optional **Recover context checkpoints** continues unfinished work from saved checkpoints.

| Dark mode | Light mode |
| --- | --- |
| ![Dark desktop control panel](docs/screenshots/dark.png) | ![Light desktop control panel](docs/screenshots/light.png) |

## Designed for unattended recovery

- Fresh included-usage permission is checked before every continuation. Weekly exhaustion, paid usage, unknown billing routes and approvals block work.
- Lost acknowledgements pause that chat for inspection. Messages are never blindly resent.
- Cancellations, task budgets and account changes remain stop conditions. Once an interruption is pinned, a newer manual turn stops the pending recovery.
- Screen locking is allowed. Armed work requests sleep prevention. Keep Codex open; on Windows/macOS, keep Auto-Resume open or minimized too.
- Ubuntu uses a background controller when a user systemd session is available. Its status is shown in the app.

Live continuation has been verified on Ubuntu with Codex runtime **0.166**. Packaged GUI/install checks use isolated test data; they do **not** establish live Codex integration on every OS or repeated unattended quota-reset cycles. [Evidence and limitations](docs/TESTING.md).

[Installation](docs/INSTALL.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Recovery](docs/RECOVERY.md) · [Building](docs/BUILDING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

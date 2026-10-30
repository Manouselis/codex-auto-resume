# <img src="auto_resume/assets/icon.png" width="42" alt=""> Codex Auto-Resume

**Keep your Codex chats moving when included usage resets.**

A desktop companion that continues explicitly armed conversations in the same chat, with the same project and model. Multiple chats can recover independently.

[![Checks](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml/badge.svg)](https://github.com/Manouselis/codex-auto-resume/actions/workflows/ci.yml)
[![Desktop installers](https://github.com/Manouselis/codex-auto-resume/actions/workflows/desktop.yml/badge.svg)](https://github.com/Manouselis/codex-auto-resume/actions/workflows/desktop.yml) · **v0.8.0 beta** · MIT

## Download and open

**No terminal, Python installation or build tools required.** Install the official Codex desktop app and sign in to ChatGPT Plus first.

| Your computer | Download | Install |
| --- | --- | --- |
| Ubuntu 22.04+ · x64 | [Ubuntu installer](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.0/codex-auto-resume-0.8.0-linux-x64.deb) | Open with Software Install, then find **Codex Auto-Resume** in Applications. |
| Windows 11 · x64 / ARM with x64 emulation | [Windows installer](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.0/codex-auto-resume-0.8.0-windows-x64-setup.exe) | Open the installer, then launch from Start. |
| macOS · Apple silicon, 14+ | [Apple silicon app](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.0/codex-auto-resume-0.8.0-macos-arm64.dmg) | Open the disk image and drag the app to Applications. |
| macOS · Intel, 15+ | [Intel app](https://github.com/Manouselis/codex-auto-resume/releases/download/v0.8.0/codex-auto-resume-0.8.0-macos-x64.dmg) | Open the disk image and drag the app to Applications. |

These community beta installers are unsigned: Windows/macOS may ask for confirmation. See [installation help](docs/INSTALL.md), [checksums and release files](https://github.com/Manouselis/codex-auto-resume/releases/tag/v0.8.0), and the precise [compatibility test scope](docs/TESTING.md).

1. Open Auto-Resume. **Continue automatically when the 5h limit resets** starts checked.
2. Click **Add conversation**, then select a chat. Selection arms it and opens Codex. An idle chat receives one **`continue`**; a running chat keeps working.
3. Click **Disarm** to remove a chat from the queue. Normal completion also removes it.

Allowance refreshes every minute. Optional **Recover context checkpoints** continues unfinished work from saved checkpoints.

| Dark mode | Light mode |
| --- | --- |
| ![Dark desktop control panel](docs/screenshots/dark.png) | ![Light desktop control panel](docs/screenshots/light.png) |

## Designed for unattended recovery

- Fresh included-usage permission is checked before every continuation. Weekly exhaustion, paid usage, unknown billing routes and approvals block work.
- Lost acknowledgements pause that chat for inspection. Messages are never blindly resent.
- Cancellations, task budgets, newer manual work and account changes remain stop conditions.
- Screen locking is allowed. Armed work requests sleep prevention. Keep Codex open; on Windows/macOS, keep Auto-Resume open or minimized too.
- Ubuntu uses a background controller when a user systemd session is available. Its status is shown in the app.

Live continuation has been verified on Ubuntu with Codex runtime **0.166**. Packaged GUI/install checks use isolated test data; they do **not** establish live Codex integration on every OS or repeated unattended quota-reset cycles. [Evidence and limitations](docs/TESTING.md).

[Installation](docs/INSTALL.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Recovery](docs/RECOVERY.md) · [Building](docs/BUILDING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

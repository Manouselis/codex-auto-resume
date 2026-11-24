# Delivery — 0.8.5

Native download/install flows now bundle Python/Tk: Ubuntu DEB, per-user Windows NSIS wizard and separate macOS Intel/Apple silicon DMGs. Installers create an app with its icon and open the GUI without terminal arguments. [Installation](INSTALL.md) covers first use and unsigned-beta system prompts.

The release workflow builds on the target OS and checks the final installed package, its real Tk UI, icon, default-on setting, private SQLite state and isolated recovery simulation. It installs the same Ubuntu package across multiple releases and exercises the Windows x64 installer on Windows 11 ARM under emulation. Release publication is gated on every platform job. Reports identify exact hosts and timings; see [Testing](TESTING.md).

Standard desktop/runtime locations are discovered without relying on a shell PATH. Windows uses the official Codex raw byte proxy for the existing daemon; Unix platforms use the existing local WebSocket path. Frozen child-process library paths are restored before launching external programs. Linux sleep prevention uses a dedicated frozen entry command; Windows uses a scoped system-sleep request and macOS uses `caffeinate -i`.

**Add conversation** arms idle or running chats ahead of the five-hour limit. Each chat stays queued through ordinary manual turns until an eligible interruption pins the recovery turn. The scheduler preserves the same chat, model and project, verifies included usage, and uses a durable per-chat reservation. The updater checks GitHub’s release feed on startup and verifies installer checksums.

Live native-queue continuation was observed on Ubuntu/runtime 0.166 in a harmless authorized chat. Live Windows/macOS Codex integration, a full closed-desktop cold start, physical screen-lock continuation, security reputation prompts, forced suspend/reboot and repeated unattended quota-reset cycles remain unverified. These are not implied by installer/GUI tests.

Windows Authenticode and Apple Developer ID/notarization are not configured. Downloads are an explicitly unsigned community beta. Source and installers are published separately; binaries and private state are not committed into Git history.

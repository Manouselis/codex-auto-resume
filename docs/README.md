# Codex Auto-Resume documentation

Start with the [project website](https://manouselis.github.io/codex-auto-resume/) and [installation guide](INSTALL.md). Native packages include Python and Tk for Ubuntu, Windows and macOS. Open the separately installed Codex desktop app and sign in with ChatGPT Plus.

Use **Add conversation** to [arm chats ahead of the five-hour limit](RECOVERY.md#arming-ahead). Chats stay in the queue as you work in Codex. Installed copies check for updates at launch through GitHub’s public release feed and verify published checksums before installing.

| Guide | Purpose |
| --- | --- |
| [Project README](../README.md) | Downloads and first-use walkthrough |
| [Installation](INSTALL.md) | Graphical setup, updates, screen locking, uninstall |
| [Testing](TESTING.md) | Exact platform/installer checks and live-integration limits |
| [Building](BUILDING.md) | Native bundles, CI release pipeline, signing status |
| [Release checklist](RELEASING.md) | Tags, docs, website updates, and download verification |
| [Troubleshooting](TROUBLESHOOTING.md) | Connection, allowance, arming and delivery errors |
| [Recovery](RECOVERY.md) | Usage resets, context checkpoints and native schedules |
| [Safety](SAFETY.md) | Included usage, cancellation and duplicate prevention |
| [Limitations](LIMITATIONS.md) | Unverified behavior and integration boundaries |
| [Architecture](ARCHITECTURE.md) | Transport, scheduler and durable state |
| [Decisions](DECISIONS.md) | Implementation rationale and historical repairs |
| [Changelog](CHANGELOG.md) | Version history |
| [Delivery](DELIVERY.md) | Implemented behavior and remaining validation |
| [Original brief](PROJECT_BRIEF.md) | Initial requirements |

Ubuntu can run a window-free user controller; Windows/macOS currently require the app to stay open/minimized. Screen locking is permitted. An actually suspended computer cannot run recovery. Unknown acknowledgements, approvals, exhausted weekly usage and cancellations still stop automatic work.

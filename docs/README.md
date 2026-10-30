# Codex Auto-Resume documentation

Start with the [download and graphical installation guide](INSTALL.md). Version 0.8.0 bundles Python/Tk in native Ubuntu, Windows and macOS installers. The app remains a companion to the separately installed, signed-in Codex desktop app.

| Guide | Purpose |
| --- | --- |
| [Project README](../README.md) | Downloads and first-use walkthrough |
| [Installation](INSTALL.md) | Graphical setup, updates, screen locking, uninstall |
| [Testing](TESTING.md) | Exact platform/installer checks and live-integration limits |
| [Building](BUILDING.md) | Native bundles, CI release pipeline, signing status |
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

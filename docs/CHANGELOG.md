# Release history

[Documentation index](README.md) · [Verification report](TESTING.md)

## 0.8.9

- Replace the green dashboard palette with slate and blue in both themes. The website and screenshots use the same palette.
- Keep platform downloads working during release builds. The website selects the newest complete release and retains working fallback links.
- Document the required update, tag, push, and verification steps in the [release checklist](RELEASING.md).

## 0.8.8

- Reworked the dashboard with a split queue and recovery details, a more compact status and allowance area, and refreshed dark and light themes.
- Added **Open in Codex** and a conversation-specific **Timeline**. The details panel separates the reason for waiting, the next check, and the recovery message setting.
- Clarified the Windows setup screens and added a visible log of the installation stages.

## 0.8.7

- Ubuntu installs and updates archive the recognized shortcut from older source installs. The same application ID now opens the packaged launcher from Applications and the dock. Custom shortcuts, controllers, and recovery data are outside the migration.

## 0.8.6 — 25 November 2026

- Set a recovery message for each armed chat. An empty field restores the built-in prompt. Fixes [#3](https://github.com/Manouselis/codex-auto-resume/issues/3).
- Search the conversation picker by title or ID. The dashboard puts the recovery explanation and message setting next to the queue.
- Refresh the quiet dashboard once a second and update displayed rows only when they change. Allowance still refreshes once a minute.

## 0.8.5

- **Add conversation** arms idle or running chats ahead of the five-hour limit. They stay in the queue through ordinary manual turns and recover after a confirmed interruption and reset.
- Check for updates through GitHub’s public release feed and installer checksums. Startup and manual checks can discover releases when the anonymous REST API is rate-limited.

## 0.8.4 — 24 November 2026

- Display the installed version and offer verified in-app updates on Windows, Ubuntu, and macOS. Check automatically when the app opens, then install and reopen after confirmation.
- Use the bundled Codex App Server to list desktop conversations and access the native queue when the managed daemon package is missing.

## 0.8.3 — 16 November 2026

- Automatically resume explicitly armed desktop goals that hit the five-hour limit. After verifying included usage and the original goal, wake its desktop owner and confirm the continuation in the original chat.
- Add a packaged Ubuntu launcher and a separate native controller to avoid restarting a legacy source installation after an upgrade. Test in-place APT upgrades from 0.8.2 with an old controller running.

## 0.8.2 — 14 November 2026

- Keep chats with a usage-limited Codex goal armed while checking included allowance. After reset, show when to resume the goal in the original Codex chat, then monitor that goal's new turn.

## 0.8.1 — 14 November 2026

- Find the registered Microsoft Store Codex runtime and the selected standalone or daemon package from Windows Start-menu launches.
- Show when Codex is installed and the local daemon needs the official standalone CLI. Verified the live Windows connection for allowance and recent chat reads.
- Check for newer Windows releases while running. After confirmation, verify the installer against GitHub's SHA-256 digest and install in place.

## 0.8.0 — 30 October 2026

- Standalone Ubuntu DEB, Windows installer and macOS Intel/Apple silicon DMGs: bundled Python/Tk, app icon and graphical launch with no terminal setup.
- Native build/install/GUI/uninstall pipeline with Ubuntu 22.04/24.04/26.04, Windows 11 ARM (x64 emulation), Windows Server build host and macOS ARM/Intel jobs. Release assets/checksums are published only after all required checks pass.
- Discover standard desktop and managed Codex runtimes outside a shell PATH. Windows connects through Codex's official raw socket proxy; framing, guards and uncertain-send behavior are preserved.
- Fix frozen sleep-inhibitor startup; add Windows/macOS idle-sleep requests scoped to armed work. Screen locking remains enabled.
- Restore external child-process library paths; use onedir bundles for faster startup and preserve runtime symlinks. Keep build dependencies outside runtime.
- Update download-first README, graphical installation instructions, compatibility scope, build/signing guide and upstream license notices.
- Community beta: no Authenticode/Developer ID credentials; live cross-platform Codex integration remains unverified.

## 0.7.0 — 30 October 2026

- Selecting a conversation opens its original Codex desktop chat through the registered URL handler, starting the app when needed.
- Selecting an idle completed chat requests exactly one `continue`. Active chats are monitored without an extra message. Fresh included usage, approvals, identity and existing goal budgets remain guards.
- New UI selections use the native message queue, verified against runtime 0.166, without restoring or taking over the desktop writer. A client message ID must match an actual started turn before the companion reports running.
- The background controller owns idle startup. Pending sends are durably reserved and never blindly retried. Normal completion after an explicit start removes the chat from the armed queue.
- Existing native heartbeat bindings remain supported, including exact-identity admission of an explicitly selected continue.
- All 233 local tests pass, including 19 GUI checks.

## 0.6.0 — 30 October 2026

- Replaced the loop/play logo with a simpler conversation icon.
- Added an obvious **Add conversation** starting point, an explanation and an empty queue prompt. Raw conversation IDs and the separate Arm step are removed from the desktop flow.
- Selecting a conversation arms it immediately, including saved native recovery settings. An in-progress allowance check cannot discard the selection.
- Disarmed, disabled and otherwise ineligible chats disappear from the active queue. Their state, reservations and activity history are preserved.
- Allowance refreshes automatically on opening and every minute. Removed the refresh button; quiet updates preserve user action messages and stop when the panel closes.
- All 213 local tests pass, including 19 GUI checks.
## 0.5.0 — 30 October 2026

- Multiple armed chats can run independently. The durable uniqueness constraint now applies per conversation; uncertain work in one chat cannot block another.
- Reconcile acknowledged terminal reservations, including disarmed native tasks. The stale global reservation that produced an endlessly moving “Waiting for reset” row is removed only after its exact turn is confirmed ended.
- Opening the app enables the global switch. Previously disarmed chats are not silently rearmed.
- Added a logo, window icon, Ubuntu application launcher and installed user-service definition. Opening the installed app starts its background controller; closing the panel leaves it running.
- The controller holds a Linux sleep inhibitor while work is armed, without disabling screen locking. The footer reports live protection status. Acquisition and release passed on Ubuntu; a physical locked-session continuation has not yet been observed.
- Missing local Codex connections automatically start the official daemon before reconnecting. No failed model write is retried.
- Added visible per-chat reasons and connection-retry labels. All 210 local tests pass, including 16 GUI checks.
## 0.4.1 — 25 October 2026

- Recognize a checkpoint marker on the last line of a native heartbeat's XML message. The closing XML tags no longer cause the next wake-up to reject an unfinished checkpoint.
- Reject malformed, nested, ambiguous and quoted heartbeat examples; completion and blocked markers still stop recovery.
- Report the actual saved disarm reason instead of saying Auto-Resume might be OFF when its global switch is ON.
- Explicit Arm can recover a disarmed native chat after diagnostic replies by re-verifying its saved checkpoint and recording a fresh user-activity boundary. Newer messages still block admission.
- Clarified checkpoint formatting in the native prompt and added nine regressions, including three successive guarded checkpoint wake-ups. The local suite passes 198 tests.

## 0.4.0 — 25 October 2026

- Redesigned the desktop panel with dark/light themes, remaining-allowance cards, named conversations and adjacent Arm/Disarm buttons. Disarm works for the chosen chat without requiring table selection.
- Native recovery verifies its saved schedule. Missing schedules pause with an actionable reason; paused schedules use a distinct waiting state.
- The heartbeat must run its guard before acting on older cancellation history. Admission reports the current explicit arming timestamp and monitored turn; newer cancellations still block work.
- Replaced the README with a concise guide and dark/light desktop screenshots.
- Verified a real native scheduled restart after a persisted usage-limit failure and renewed included permission, preserving interrupted work. Repeated unattended reset cycles remain unverified.
- The local suite passes 189 tests, including 15 GUI checks.

## 0.3.2 — 25 October 2026

- The global five-hour continuation checkbox now defaults ON for new state files, as requested. Saved ON/OFF choices are preserved; individual chats still require explicit arming.

## 0.3.1 — 25 October 2026

- Fixed choosing-and-arming and clicking-and-arming saved conversations. Both restore the chat ID and context-recovery setting; native heartbeat bindings are preserved.
- Explicit rearming now reconciles a stale acknowledged reservation only when read-only history proves that its exact turn ended. Unknown deliveries and unfinished external markers still block retries.
- Repeated Arm on a running native turn is idempotent and preserves its attempt count. A disabled but still running native turn can be rearmed without starting another turn.
- Added eight controller and three real Tk regressions. The full local suite passed 178 tests, including thirteen GUI checks.

## 0.3.0 — 23 October 2026

- Added explicit per-arming recovery for context-budget checkpoints and structured context-window failures, with fresh included-usage checks and the existing three-attempt limit.
- Added the GUI opt-in and CLI `arm THREAD_ID --recover-context`. Ordinary completion is still a stop condition.
- Corrected the misleading **Task completed** reason: a completed turn does not prove the wider objective is finished.
- Goal state and configured token budgets are checked without modifying them. Checkpoint text is pinned across dispatch preflight.
- Closing a service-owned control panel now keeps armed background work active; OFF still disarms.
- Added an experimental admission guard and prompt for native scheduled desktop recovery. External restoration and queue start cannot bypass the desktop writer; this now reports `not_sent` and pauses. The first real native scheduled wake-up passed on Ubuntu on 23 October: fresh guards admitted work in the original chat, which resumed saved research. Repeated checkpoint cycles and natural quota-reset recovery remain unverified.
- Native mode admits at most ten work turns, checks prior checkpoints and fresh usage, and is skipped by the external scheduler. Each native wake-up is a normal model turn.
- The local suite passes 167 tests, including ten native GUI checks. See [Recovery modes](RECOVERY.md) for recognition boundaries.

## 0.2.1 — 22 October 2026

- Fixed false cancellation when arming a conversation still running in another Codex runtime. An open external-history marker is monitored as unresolved; it cannot authorize a continuation.
- Kept confirmed cancellation, completion, superseding turns, approvals and dispatch preflight safeguards in place.
- Added 12 adapter/controller regressions and one native control-panel regression. The local GUI-inclusive suite records 120 passing tests.
- Verified the arming fix against an active desktop conversation using read-only metadata and isolated state, without inference or thread mutations.
- Fixed Windows test cleanup so SQLite handles close before temporary directories are removed. Installation manifests now use portable relative paths on every platform.
- Passed all four hosted Ubuntu/Windows and Python 3.10/3.13 CI jobs. This verifies the core and packaging, not live Windows Codex integration.

## 0.2.0 — 19 October 2026

- Implemented real same-thread continuation through the official persistent App Server, replacing the observation-only execution path.
- Added local WebSocket transport, fresh account/quota/configuration checks, explicit task selection and durable submission reservations.
- Verified the continuation path with two real authenticated model turns that preserved the original context. The local suite recorded 107 passing tests at that release.

## 0.1.0 — historical prototype

The initial prototype could observe state and exercise the scheduler with fixtures, but refused real continuation. Its results do not describe the current adapter's execution capability.

## Still awaiting live validation

A natural five-hour exhaustion/reset sequence, real Windows desktop continuation, cross-client approval routing, Wayland and actual suspend/reboot recovery remain unverified. Controlled reset tests and real same-thread execution are separate pieces of evidence; see [Testing](TESTING.md).

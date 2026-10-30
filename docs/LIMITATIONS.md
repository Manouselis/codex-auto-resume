# Remaining limitations

[Documentation index](README.md) · [Verification report](TESTING.md)

Real same-thread continuation has been implemented since 0.2.0. Version 0.2.1 fixes arming work owned by another runtime. Version 0.3.0 adds opt-in context-checkpoint recovery. The daemon-owned execution path preserved context across two authenticated model turns, while the full natural quota-exhaustion/reset sequence remains unverified live.

## Execution boundaries

- Quota recovery requires an explicitly armed task, a structured `usageLimitExceeded` failure, and an observed exhausted five-hour window. An unrelated failure or unresolved history marker cannot trigger dispatch. Separately enabled context recovery requires a recognized context checkpoint; ordinary completion still stops. Arming only after the backend has already recovered may miss the evidence needed to establish a five-hour interruption.
- An unfinished external-history marker can be monitored, but the reader cannot use it to prove that a turn is running or cancelled. It waits for a confirmed result. If no such result becomes available, monitoring alone cannot recover the task.
- A desktop-owned chat retains an exclusive writer. The external controller cannot restore it. The native message-queue path was reverified on runtime 0.166 and starts selected desktop chats without restoring their writer. Native scheduled research continuation and one restart after a genuine usage-limit failure passed on Ubuntu. Repeated checkpoint cycles and uninterrupted unattended quota-reset cycles remain unverified.
- Every native wake-up is a normal model turn governed by Codex’s account settings. The local guard can authorize substantive work after fresh checks, but cannot perform a pre-inference billing check for the scheduler. OFF disarms work; pause the heartbeat too to stop wake-up model calls.
- The public API has no atomic expected-thread-revision condition. The adapter rechecks before sending, but another client can still change the thread between the final read and submission. Avoid using the same armed conversation in another client during automatic dispatch.
- Included-usage checks establish the current route; they do not reserve future quota or protect against external account, configuration or billing changes after the final read. Paid or unknown credits, API authentication, custom providers and non-default tiers are refused.
- Every reported quota bucket is checked. An exhausted or unknown bucket for another model can conservatively pause a task. This release supports ChatGPT Plus with verified 300-minute and 10080-minute windows, not every plan or quota shape that Codex may support.
- Approval/input requests are never answered automatically. Routing approval requests from a daemon-owned continuation to an independently connected desktop UI remains unverified.
- Lost acknowledgements and uncertain crash recovery pause the queue without resending. The default is at most three external continuation attempts or ten admitted native work turns per arming; this is not an unlimited overnight loop or a remote exactly-once guarantee.

Context checkpoint recognition uses explicit model-reported outcomes and a narrow compatibility rule, not a general semantic judge of whether a task is finished. Unsupported checkpoints stop for inspection. A structured context-window failure can recur if compaction cannot recover enough space; the attempt cap still applies.

## Controller lifecycle

Normal process stop and global OFF disarm tasks. Closing a window-owned controller disarms work; closing a service-owned control panel leaves monitoring enabled. On Ubuntu with a user systemd session, the installed app starts a background controller and holds a sleep inhibitor while work is armed. Screen locking remains allowed. The app cannot wake an already suspended computer or guarantee recovery after logout/reboot. Keep Codex open and remain connected and logged in. Sleep-inhibitor acquisition and release were verified on this host; a physical locked-session continuation has not been observed.

A process crash can preserve a reset wait, but an uncertain submission is paused for inspection. An enabled service definition does not override those safety decisions. See the [operation guide](INSTALL.md) for the transient and installed user-service options.

## Platform and integration scope

Standalone installers target Ubuntu 22.04+ x64, Windows 11 x64 (including emulation on ARM), macOS 14+ Apple silicon and macOS 15+ Intel. See [Testing](TESTING.md) for actual build/install/GUI results; packaging tests use invented data and are distinct from live Codex continuation.

Ubuntu X11 with runtime 0.166 is the verified live platform. Windows/macOS live Codex queue integration, Windows private-socket ACL behavior, Wayland, physical locked-session continuation, forced suspend, logout and reboot remain unverified. Windows uses Codex's official raw socket proxy; an incompatible runtime refuses execution. These community beta downloads are not Authenticode signed or Apple Developer ID signed/notarized.

Keep Auto-Resume open/minimized on Windows/macOS. On Ubuntu, a user systemd controller may continue after the panel closes, as reported by the app. The sleep requests prevent ordinary idle suspension where available; they do not wake suspended computers or override forced suspension/lid/shutdown policies.

The app opens the original chat using `codex://threads/<id>`. Opening the handler and real queued continuation were verified while Codex was already running. A complete cold start with all Codex processes closed has not been tested because other user chats were working. Unknown acknowledgements pause without resending.

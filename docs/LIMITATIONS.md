# Remaining limitations

[Documentation index](README.md) · [Verification report](TESTING.md)

Real same-thread continuation has been implemented since 0.2.0. Version 0.2.1 fixes arming work owned by another runtime. The actual execution path preserved context across two authenticated model turns, while the full natural quota-exhaustion/reset sequence remains unverified live.

## Execution boundaries

- Automatic recovery requires an explicitly armed task, a structured `usageLimitExceeded` failure, and an observed exhausted five-hour window. A completed turn, unrelated failure or unresolved history marker cannot trigger dispatch. Arming only after the backend has already recovered may miss the evidence needed to establish a five-hour interruption.
- An unfinished external-history marker can be monitored, but the reader cannot use it to prove that a turn is running or cancelled. It waits for a confirmed result. If no such result becomes available, monitoring alone cannot recover the task.
- The public API has no atomic expected-thread-revision condition. The adapter rechecks before sending, but another client can still change the thread between the final read and submission. Avoid using the same armed conversation in another client during automatic dispatch.
- Included-usage checks establish the current route; they do not reserve future quota or protect against external account, configuration or billing changes after the final read. Paid or unknown credits, API authentication, custom providers and non-default tiers are refused.
- Every reported quota bucket is checked. An exhausted or unknown bucket for another model can conservatively pause a task. This release supports ChatGPT Plus with verified 300-minute and 10080-minute windows, not every plan or quota shape that Codex may support.
- Approval/input requests are never answered automatically. Routing approval requests from a daemon-owned continuation to an independently connected desktop UI remains unverified.
- Lost acknowledgements and uncertain crash recovery pause the queue without resending. The default is at most three automatic continuation attempts per arming; this is not an unlimited overnight loop or a remote exactly-once guarantee.

## Controller lifecycle

Normal process stop, global OFF and control-window close disarm tasks. Closing the control window also disarms work when a service owns scheduling. A background service allows operation without an open control window; it does not prevent suspend, wake the computer or guarantee recovery after logout/reboot. Keep the machine awake, connected and logged in.

A process crash can preserve a reset wait, but an uncertain submission is paused for inspection. An enabled service definition does not override those safety decisions. See the [operation guide](INSTALL.md) for the transient and installed user-service options.

## Platform and integration scope

Ubuntu X11 is the verified live platform. Headless core, installer and packaging checks pass on hosted Ubuntu and Windows runners with Python 3.10 and 3.13. Live Windows Codex transport, Windows GUI/ACL behavior, Wayland and real suspend/reboot recovery remain unverified.

The control is a separate companion, not a native Codex Settings control or tray integration. It reopens the original persisted thread through the official App Server and restores saved sandbox/approval configuration. It does not attach to the desktop application's private transport. Recorded runtime/schema versions are snapshots; future protocol changes may require updates.

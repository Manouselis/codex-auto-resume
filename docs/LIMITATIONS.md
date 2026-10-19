# Remaining limitations

Real same-thread continuation is implemented in 0.2.0 and was verified against the authenticated Codex backend. The 0.1.0 blanket execution block is removed.

- A real natural five-hour quota exhaustion/reset has not been forced. The reset scheduler, structured interruption handling and weekly hard stop are tested with controlled protocol responses. The actual submission/context path uses real Codex and passed a two-turn check.
- The public API has no atomic expected-thread-revision parameter. The adapter rechecks immediately before sending, but a concurrent external client can still race that final read. Avoid using the same armed conversation in another client during automatic dispatch.
- Included-usage checks are fresh preflight checks, not a reservation of future quota or protection against external billing/account changes after the check. Paid/unknown credits, API authentication and custom/fast billing paths are refused.
- All reported quota buckets are checked. An irrelevant exhausted/unknown model bucket can conservatively pause a task.
- Approval/input requests are never answered automatically. Approval routing between a daemon-owned continuation and an independently connected desktop UI is unverified.
- Only an explicitly armed task with a structured `usageLimitExceeded` failure and observed five-hour exhaustion can resume automatically. A completed turn or unrelated failure never triggers it.
- Lost acknowledgements and uncertain crash recovery pause the queue. No automatic resend or recovery from an uncertain remote outcome is claimed.
- Normal process stop/UI close disarms; normal reboot may require manual opt-in. The controller must remain running during the wait.
- The control is a separate desktop companion, not a native Settings injection, tray icon or official OpenAI feature.
- Ubuntu X11 is the verified platform. Windows, Wayland and real suspend/reboot scenarios remain untested.
- No GitHub repository/public release is created automatically.

The daemon-based continuation reopens the original persisted thread, preserves its history and restores saved sandbox/approval configuration. It does not attach to the desktop app's private internal transport. A context token was successfully recovered by the real model after same-thread resumption.

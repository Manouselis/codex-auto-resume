# Safety contract

## Shipped release

**Zero automatic model submissions are possible through the live adapter.** This is the enforceable financial guarantee of 0.1.0. It intentionally blocks useful automation while the required backend operation is unavailable. No UI option enables a hidden unsafe mode.

The read-only transport allowlists initialization, account/usage reads, thread metadata/history reads, and model catalog reads. It cannot create or resume threads, start/steer turns, execute tools, approve permissions, change authentication, buy credits, redeem resets, upgrade a plan, or switch accounts. Credentials remain with the installed Codex runtime; this project does not open token files.

## Quota policy

All required buckets must come from an explicit, trusted model binding. No fallback to the legacy single bucket is allowed when identity is ambiguous. Each bucket must report the supported Plus plan and exactly the 300-minute and 10080-minute windows, with valid usage percentages and official Unix reset timestamps. Reversed primary/secondary positions are supported.

Before a continuation can be eligible:

- The full snapshot is at most 30 seconds old; future timestamps and clock ambiguity fail closed.
- ChatGPT authentication, original account identity and original quota identities match.
- `ordinaryUsageAllowed` is literally `true`; missing, null, numeric or textual equivalents never authorize execution.
- Both windows have available usage and current reset timestamps.
- Weekly remaining usage exceeds the configured reserve (default 5%). Exhaustion is a sticky hard stop, including when ordinary permission is false.
- Credits explicitly report `hasCredits=false`, `unlimited=false`, and a finite zero string balance. Missing or nonzero balances fail closed.
- Spend controls are explicitly available and clear. Workspace/credit-related limits are rejected.

A reset timestamp can schedule a read; it can never authorize execution. Available banked resets are ignored and never redeemed. Credit-free snapshots alone are not sufficient: the execution adapter must also enforce included-only billing atomically for the whole continuation. The live protocol does not provide that contract.

## Thread and once-only protection

Arming is explicit for each task. Completion, user cancellation, other turns, changed context, unknown history, pending approvals, missing projects, account/model/configuration changes, and unknown unfinished state pause automation. An unchanged original thread and approval/sandbox configuration must be enforced at dispatch by any future adapter.

Global disable disarms scheduled work. Re-enable does not rearm it. Weekly exhaustion requires a fresh manual arm even after the weekly reset. Disabling does not interrupt ordinary Codex work already running.

SQLite uses transactional updates and `synchronous=FULL`. One OS lock owns the scheduler. An atomic unique reservation serializes automatic tasks across controllers. The reservation is committed before dispatch. An uncertain acknowledgement is never retried; an uncertain reservation also blocks other automatic tasks. A crash before dispatch can therefore lose an automatic opportunity. This is an intentional availability tradeoff, not a claim of exactly-once remote delivery.

The simulator demonstrates one successful submission at most per interruption when its stronger backend contract holds. Real remote exactly-once delivery, billing guarantees, desktop ownership and user activity cannot be established by this simulation.

## Local security and privacy

On Ubuntu state files are mode 0600 and newly created private state directories are 0700. Existing parent permissions and Windows ACLs are not tightened. Symlink state destinations are refused. SQLite history is bounded to 1000 entries. No account IDs or original project paths are included in public evidence; fixture identities are invented.

This is a local application, not a security boundary against malicious code running as the same user. Use a private per-user state location. Uninstallation preserves history; delete it separately only after stopping controllers. Operating-system logs or the Codex child process can write their own diagnostics under their own policies.

No sensitive action approval is automated. There is no network listener or cloud backend. The live runtime may contact its normal authenticated quota service during an explicit or scheduled metadata read.

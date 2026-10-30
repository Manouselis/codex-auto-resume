# Architecture

The 0.6.0 desktop launcher starts an installed per-user service. `desktop.py` reuses an active controller or starts the service; Tk remains a control panel. `power.py` takes a `systemd-inhibit --what=sleep` lease while recovery is enabled and any chat is eligible. The lease follows controller lifetime and never inhibits idle display handling, locking or shutdown. A private heartbeat records controller liveness.

The former global `one_execution` index migrates to `one_execution_per_thread`. Submission checks use the chat ID in both external and native guards. API requests remain serialized on their RPC connection, while admitted model turns run independently. Each dispatch still reads fresh shared quota. A read-only audit releases only acknowledged running reservations whose exact turns have confirmed terminal metadata; unknown delivery stays blocked in its own chat.

Version 0.5.0, regression checks on 30 October 2026. The daemon-owned model verification is from 19 October 2026; the first native scheduled desktop continuation passed on 23 October 2026. The implementation is a standalone native Tk companion with a shared CLI/background controller. It does not inject a control into Codex Settings.

## Real integration

The recorded 19 October model check used the desktop-bundled `codex-cli 0.163.0-alpha.10.2` and an official managed daemon reporting 0.163.0. These are verification snapshots, not a promise of compatibility with every future runtime. `doctor --connect` checks the installed schema and read-only connection. Historical schema captures are kept in `docs/evidence/`.

The official daemon accepts a WebSocket HTTP upgrade on its local Unix control socket. `websocket.py` implements the small required RFC6455 client: handshake validation, client masking, fragmentation, ping/pong, bounded message sizes and serial request IDs. A socket must belong to the current user. No network listener or credentials are created. The CLI proxy is a raw transport, not a JSON-lines interface; treating it as JSON-lines was an integration bug corrected during live verification.

`live.py` uses supported methods: `account/read`, `account/rateLimits/read`, `config/read`, `thread/read`, `thread/turns/list`, `thread/list`, `thread/resume` and `turn/start`. Billing, reset redemption, account changes and approval replies remain forbidden. The production adapter cannot create a new thread. Only the separately invoked live-check script creates its harmless test conversation.

A fresh preflight checks the original account/model, every reported quota bucket, structured usage-limit failure and unchanged latest-turn fingerprint. `thread/resume` loads the original thread without model, sandbox or approval overrides. Its returned configuration is checked, and the preflight runs again. Exactly one `turn/start` carries the durable continuation ID and contextual continuation text. The original task prompt is never replayed.

Disconnecting closes the companion's socket, not the daemon or its active Codex turn. The resumed task is not a fork or a separately summarized conversation. Its same-thread context was verified using a genuine model response.

## Core modules

| Module | Responsibility |
| --- | --- |
| `policy.py` | Quota interpretation, freshness, ordinary permission and weekly reserve |
| `engine.py` | Explicit task registration, state transitions, reset scheduling and durable dispatch |
| `store.py` | Private SQLite state, history and cross-process reservations |
| `lifecycle.py` | One scheduler per state file using OS locks |
| `websocket.py` | Persistent local App Server transport |
| `live.py` | Real account/thread/goal observation and continuation |
| `native.py`, `native_prompt.py` | Admission guard and instructions for native scheduled desktop work; never starts model turns |
| `checkpoints.py` | Conservative context-checkpoint recognition and continuation outcome instructions |
| `ui.py`, `cli.py` | Native control, task chooser and local commands |
| `adapters.py`, `protocol.py` | Optional isolated simulator and read-only JSON-lines observer |

Running tasks are checked every 30 seconds; the controller loop wakes every five seconds. A `notLoaded` reader can reconstruct an open external turn as interrupted without an error or completion timestamp. That case is marked unresolved and may be explicitly armed for monitoring; only a confirmed later result changes it to completion, cancellation or usage-limit recovery. It cannot pass dispatch preflight. Reset waits use official epoch timestamps; the scheduler wakes locally without model calls. Waiting tasks get a lightweight quota audit at most every five minutes, then a fresh read at reset. Delayed backend recovery gets bounded read-only retries. Every automatic submission requires fresh checks again.

SQLite commits a unique reservation before dispatch. A lost acknowledgement or crash after reservation pauses the queue, with no automatic retransmission. `clientUserMessageId` is an attribution/deduplication marker, not a claimed server idempotency contract.

## Controller ownership and background operation

The native window and `run` command use the same engine and private state file. An OS lock permits one scheduler to own that state, while separate CLI commands and a control window can inspect or change it. A user service can own scheduling without an open window. Closing a service-owned control panel leaves the shared state active; closing a window-owned controller disables it.

The default engine limit is three continuation attempts per arming. Transient reads receive at most three bounded retries, and reset verification has a five-second buffer. The service template can restart a failed process, but that does not override conservative recovery of an uncertain submission or rearm a task after normal shutdown. See [Installation and operation](INSTALL.md) and [Safety](SAFETY.md).

## Context checkpoint recovery

The stored arming context includes an explicit `recover_context` flag. Default registrations remain quota-only. Context recovery recognizes a structured context-window error, a final checkpoint marker, or the narrow legacy stop declaration with a saved next action. Only final assistant output can report a marker; quoted examples and tool output cannot. The checkpoint text is hashed into the revision fingerprint and checked again after thread restoration.

Before context recovery, the adapter reads the persisted goal state. Paused, blocked, complete or budget-limited goals, and exhausted/unknown configured token budgets, block execution. No goal write API is permitted. Fresh included-usage checks determine whether to dispatch now or wait for reset. Prior acknowledged reservations are finished only after their turn has a confirmed terminal result, before the next durable reservation is made.

## Supported-surface evidence

- [Official App Server documentation](https://learn.chatgpt.com/docs/app-server): thread resume, turn start, history pagination and usage reads.
- [Official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference): providers and authentication restrictions.
- Installed generated schemas, recorded under `docs/evidence/`.
- [Plugin packaging](https://developers.openai.com/plugins/build/plugins) and [hooks](https://learn.chatgpt.com/docs/hooks): no native persistent Settings injection established; hooks do not replace reset scheduling.

No proprietary bundle, native Codex settings, authentication file or billing preference is patched. The initial research/83-test evidence remains in Git history; the current implementation and current verification reports take precedence.

## Desktop writer conflicts

A desktop-owned conversation can retain an exclusive writer after a turn ends. A separate App Server cannot reopen it. Queue start also requires a resumed thread on that server, so queue APIs cannot bypass desktop ownership. The adapter recognizes the exact restoration refusal, records `not_sent` and pauses. It never tries another dispatch route after that refusal.

Confirmed preflight/restoration failures before model dispatch are recorded as `not_sent`. This distinction never applies to an uncertain model start. The [redacted server-log reconciliation](evidence/desktop-writer-conflict.json) records the first real refusal. The older two-turn check used a daemon-owned chat and does not validate desktop takeover.

## Native scheduled desktop mode (experimental)

A native heartbeat runs in the original desktop writer. Its stored prompt calls `native-claim` before research, changes or experiments. The guard verifies its exact heartbeat marker, pinned arming identity, prior checkpoint or quota failure, intervening turns, goal budget, fresh quota and financial configuration. A SQLite transaction admits at most ten work turns and blocks outstanding or uncertain submissions in that same conversation. Other chats have independent reservations. Repeated claims check fresh guards but do not consume another attempt. The local scheduler skips native bindings.

`native-finish` records a checkpoint, objective completion or block. Only checkpoints remain armed; the native prompt pauses its heartbeat on completion, cancellation, OFF, approvals or other blocked work. A restarted companion leaves acknowledged native slots for a subsequent terminal-history check; it never retransmits a native turn. A manual intervening turn stops automatic research.

The guard does not start or prevent the initial native model turn. Each heartbeat wake consumes normal usage under Codex’s current account settings. Its fresh financial checks govern subsequent substantive work, not scheduler admission. A heartbeat can still wake once to notice OFF and pause itself. Disarming the companion and pausing the native heartbeat are separate operations. The first real scheduled wake-up passed on 23 October 2026: its exact heartbeat prompt ran the guard, a matching durable reservation was recorded, and the original chat resumed saved research. A [post-reset restart](evidence/limit-reset-recovery-0.4.0.json) also passed on 25 October. Repeated checkpoint cycles and uninterrupted unattended quota-reset cycles remain unverified. See the [first wake-up evidence](evidence/native-scheduled-recovery.json).

## Native schedule health

`native_schedule.py` reads only the app-generated ID, kind, target thread and status fields. It never edits native automations. Engine registration and native guards verify this metadata; the local scheduler checks it on each tick. PAUSED uses `WAITING_FOR_SCHEDULE`; missing/invalid metadata disarms. An explicit arm stores its timestamp, which admission returns with the monitored turn. Repeated Arm renews this authorization without resetting work attempts or sending another model turn.

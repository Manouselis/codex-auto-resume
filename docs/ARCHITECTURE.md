# Architecture

Version 0.2.1, regression checks on 22 October 2026. The genuine model verification below is from 19 October 2026. Option C remains a standalone native Tk companion rather than an injected Codex Settings control.

## Real integration

The desktop-bundled binary is `codex-cli 0.163.0-alpha.10.2`; the official managed daemon started locally reports 0.163.0. The earlier 0.1.0 implementation was observation-only. Its requirement for a new atomic billing-and-thread operation exceeded the requested read-time safety checks and prevented all useful execution. This version removes that blanket block and explicitly documents the remaining race instead of claiming an atomic guarantee.

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
| `live.py` | Real account/thread observation and continuation |
| `ui.py`, `cli.py` | Native control, task chooser and local commands |
| `adapters.py`, `protocol.py` | Optional isolated simulator and read-only JSON-lines observer |

Running tasks are checked every 30 seconds. A `notLoaded` reader can reconstruct an open external turn as interrupted without an error or completion timestamp. That case is marked unresolved and may be explicitly armed for monitoring; only a confirmed later result changes it to completion, cancellation or usage-limit recovery. It cannot pass dispatch preflight. Reset waits use official epoch timestamps; the scheduler wakes locally without model calls. Waiting tasks get a lightweight quota audit at most every five minutes, then a fresh read at reset. Delayed backend recovery gets bounded read-only retries. Every automatic submission requires fresh checks again.

SQLite commits a unique reservation before dispatch. A lost acknowledgement or crash after reservation pauses the queue, with no automatic retransmission. `clientUserMessageId` is an attribution/deduplication marker, not a claimed server idempotency contract.

## Supported-surface evidence

- [Official App Server documentation](https://learn.chatgpt.com/docs/app-server): thread resume, turn start, history pagination and usage reads.
- [Official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference): providers and authentication restrictions.
- Installed generated schemas, recorded under `docs/evidence/`.
- [Plugin packaging](https://developers.openai.com/plugins/build/plugins) and [hooks](https://learn.chatgpt.com/docs/hooks): no native persistent Settings injection established; hooks do not replace reset scheduling.

No proprietary bundle, native Codex settings, authentication file or billing preference is patched. The initial research/83-test evidence remains in Git history; the current implementation and current verification reports take precedence.

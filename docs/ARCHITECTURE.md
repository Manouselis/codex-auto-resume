# Architecture and integration evidence

Research performed 16–17 October 2026. These findings apply to the inspected versions; they do not establish that future versions have the same limitations.

## Installed environment

| Component | Observed value |
| --- | --- |
| OS | Ubuntu 22.04.5 LTS, GNOME, X11 |
| Desktop package | `chatgpt` 26.1007.71326, amd64 |
| Package maintainer | OpenAI, according to dpkg metadata |
| Build metadata | `codexAppBrand=chatgpt`, `codexBuildFlavor=prod` |
| Bundled App Server | `codex-cli 0.162.0-alpha.17.2` |
| PATH CLI | `codex-cli 0.156.1` |
| Python | 3.10.12; Tk 8.6 |

The package identifies itself as an OpenAI production distribution, rather than a community Linux repackaging. No independent package-signature attestation was performed. No proprietary application bundle was patched or reverse-engineered.

Generated schema field inventories and SHA-256 fingerprints are in [evidence](evidence). They were produced by each installed binary's `app-server generate-json-schema --experimental` command. The desktop binary is selected first on this machine to avoid silently testing a different runtime.

## Options evaluated

**A: Native plugin.** Documented plugin packages can contain skills, MCP servers, UI resources and lifecycle hooks. No documented persistent host Settings/task-control injection surface was established. The hook set does not document a quota-reset wake-up event. A `Stop` continuation would itself create another prompt; it cannot provide billing enforcement or survive as an independent reset scheduler. This does not meet the requirements.

**B: Plugin plus companion.** A hook could help record cancellation, but needs explicit hook trust and still cannot supply atomic execution safety. Shipping a manifest would imply capabilities it does not add. No plugin is bundled in this release.

**C: Independent companion — selected.** A small native Tk window and optional per-user service own local preferences and task metadata. The App Server is used only for supported metadata reads. This is a separate companion, not a native in-app toggle or a tray integration.

## Execution blocker

Both generated `TurnStartParams` schemas have `threadId`, `input`, configurable model/permissions and `clientUserMessageId`. Neither has a documented atomic included-only billing constraint, account/quota precondition, or expected-thread-revision precondition. `turn/start` can steer an existing active turn. A preceding metadata read cannot prevent another client from starting work between the read and submission. `clientUserMessageId` is not documented as a server-side idempotency guarantee.

The ordinary-usage permission is useful authorization at read time, not a reservation of quota for a future long-running turn. Credit absence at read time also cannot prove that a future fallback path is impossible. Consequently the live adapter's four execution capabilities are permanently false in this release. Its `submit` method raises an error, and its transport rejects model, billing, auth-change and approval methods.

## Modules

| Module | Responsibility |
| --- | --- |
| `domain.py` | Types and explicit legal state transitions |
| `policy.py` | Pure quota interpretation, freshness and weekly protection |
| `engine.py` | Task validation, scheduling decisions, reservation and once-only dispatch |
| `store.py` | Private SQLite state, transactional changes, history, crash recovery |
| `lifecycle.py` | OS controller lock, independent of desktop environment |
| `protocol.py` | Bounded JSON-lines read-only App Server transport |
| `adapters.py` | Live observer and isolated simulator |
| `ui.py` / `cli.py` | Desktop control, diagnostics and local commands |

The core has no GNOME, systemd, X11, Windows, Tk, or keyboard-automation dependency. Only the UI and lifecycle adapters interact with platform facilities. One idle scheduler thread waits on a local event; waiting tasks do not poll quota before their reported reset. Registered running tasks are inspected at most every 30 seconds. Weekly event handling accepts a complete authoritative snapshot; sparse updates never grant authorization. The live observer has no subscription to the desktop runtime, so it cannot promise immediate detection of a weekly change during a wait.

## Original context and persistence

Explicit arming pins thread, account, model, quota identities, project, permissions fingerprint and latest turn identity/revision. The core permits only a structured `usageLimitExceeded` failure with exhausted 300-minute windows to become a scheduled reset. Weekly windows are identified by 10080 minutes, regardless of primary/secondary position.

Before simulated execution the engine checks the current task, quota and feature generation, then durably records a unique continuation ID. The simulator enforces account, model, revision and included-only preconditions at submission and deduplicates that ID. It receives a contextual continuation instruction, never a replay of the original prompt.

The actual App Server can read persisted threads, but a separate process does not own the desktop's active thread runtime. `thread/resume` would load an independent execution context; this release never calls it. Thread storage paths are explicitly unstable in the generated schema. Codex's private databases and transcripts are not read or edited. Paginated history and unverified model bindings are rejected rather than reconstructed.

Only this application's SQLite file is written. It contains identifiers and safety metadata, not prompts, messages or tokens. Waiting tasks survive a process crash. Uncertain transmissions or prior active continuations require manual inspection and block further automatic execution. Explicit UI close or normal service stop disables and disarms automation.

## Sources

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins): package components, manual desktop hooks and trust requirements.
- [Hooks](https://learn.chatgpt.com/docs/hooks): lifecycle events and stop/interrupt behavior.
- [App Server protocol](https://learn.chatgpt.com/docs/app-server): read/resume/start distinctions, turn status and quota field definitions.
- [Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform): the supported harness/client architecture.
- [App Server with ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server): model catalogs are not entitlement checks.

The installed generated schemas are the primary evidence for version-specific field availability. Documentation may describe a newer release.

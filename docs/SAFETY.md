# Safety contract

The production adapter now sends real model turns. Its safety contract is explicit preflight and conservative refusal, not an impossible promise of atomic remote execution.

## Included-usage checks

Before every automatic continuation:

- Authentication must be ChatGPT Plus, not API-key or another paid provider.
- Backend `accountId` must match the armed task, and `ordinaryUsageAllowed` must be literally true.
- A complete authoritative snapshot must be fresh. Time passing alone never authorizes execution.
- Every reported quota bucket is checked. The adapter does not guess a model mapping when `normalModelSlug` is null. Unknown window shapes pause instead of silently ignoring a bucket.
- Both the 300-minute and 10080-minute windows must have usage available, regardless of primary/secondary order.
- Weekly remaining usage must exceed the default 5% reserve. Weekly exhaustion disarms the task and requires fresh user action even after reset.
- Credits must explicitly report no balance, no unlimited credits and `hasCredits=false`. Nonzero or unknown balances refuse continuation.
- Spend control must be available and clear. Custom endpoints/providers and non-default speed tiers refuse continuation.

The official default ChatGPT endpoint is accepted. The original OpenAI provider, model, sandbox and approval configuration are restored rather than changed. No API key, billing purchase, paid fallback, account switch, upgrade or reset redemption is performed by the companion. Backend service limits remain authoritative throughout execution.

These checks establish the current included-usage path. They cannot reserve future quota or protect against a concurrent external account/configuration/billing change after the final read. A user who changes those settings while a continuation is being dispatched can create a race; no stronger guarantee is claimed.

## Task and concurrency checks

Each task is explicitly armed. A new turn, completion, cancellation, changed original identity/context, missing project/history or pending approval pauses automation. Completed work is never automatically restarted. Global OFF disarms waiting work; ON does not rearm old tasks.

The controller checks state again after `thread/resume`, then sends one contextual continuation. There is a short remaining cross-client read/submission race because the API has no conditional revision argument. Do not use the same armed conversation concurrently in another client. If user activity is observed, automatic continuation stops. Different projects/conversations remain usable normally.

SQLite uses full durability, atomic transactions and a unique outstanding-submission reservation. A crash/lost acknowledgement never causes a submission retry. Uncertain outcomes block further automatic dispatch until inspected. This trades availability for avoiding duplicated operations; it is not a claim of remote exactly-once delivery.

## Approvals and local data

The companion never approves sensitive actions. A server approval or input request pauses the registered task and remains unanswered. Approval routing from an independently connected desktop client to the daemon-owned turn is not verified; manually inspect Codex before continuing.

On Ubuntu state files use mode 0600 and newly created state directories 0700. An application ID prevents overwriting unrelated databases. State contains account/thread/project identifiers and safety metadata, but no conversation text or credentials. Logs do not include raw backend error messages. Public live evidence omits the test thread ID.

The socket is restricted to the current user's official daemon. Closing the window/connection does not kill an acknowledged running daemon turn. Uninstall preserves task history and never modifies Codex's files. Windows ACLs and transport behavior remain unverified.

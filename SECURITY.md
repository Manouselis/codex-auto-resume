# Security

Version 0.2.1 sends real continuation requests only after explicit global opt-in, per-task arming and current included-usage checks. Preserve all refusal paths and the no-resend behavior for uncertain acknowledgements. Unresolved history from another runtime permits monitoring only and cannot authorize dispatch.

Never add billing purchases, API-key fallback, reset redemption, automatic approvals or implicit account changes. Changes to dispatch require tests for weekly exhaustion, missing ordinary permission, paid/unknown credits, concurrent work, cancellation and lost acknowledgements.

Report vulnerabilities privately to the project owner or, once published, through the repository's private security-reporting mechanism. Do not publish account IDs, private prompts, tokens or raw runtime logs. Public verification evidence is redacted.

The local socket and task state are per-user resources, not a boundary against malicious code already running as that user. The financial checks are preflight checks; no claim of an atomic future billing reservation is made.
